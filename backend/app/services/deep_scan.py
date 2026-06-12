"""Deep Scan — the LLM architect-review layer on top of the static analysis.

Flow: re-clone the repo, hand the worst static-analysis files to Claude Haiku
for structured per-file findings (static counters say *what*, the model judges
*whether it matters*), then have Claude Sonnet synthesize one architect memo.

Cost control is layered: feature is off without ANTHROPIC_API_KEY, per-IP
daily quota and a monthly USD cap are enforced at the API, and every scan
records its measured token spend.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.config import get_settings
from app.models.db import DeepScan, get_session
from app.services.celery_app import celery_app

# USD per 1M tokens (input, output) — keep in sync with platform pricing.
MODEL_PRICES = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
}

MAX_FILE_CHARS = 28_000


class FileFinding(BaseModel):
    title: str
    severity: Literal["high", "medium", "low"]
    evidence: str = Field(description="The specific code pattern or line that proves the issue")
    fix: str


class FileReview(BaseModel):
    path: str
    verdict: str = Field(description="One-sentence judgement of this file's real debt")
    static_signal_correct: bool = Field(
        description="Whether the static analyzer's flag on this file reflects real debt (false for idiomatic/boilerplate noise)"
    )
    findings: list[FileFinding]


class MemoRisk(BaseModel):
    title: str
    severity: Literal["high", "medium", "low"]
    files: list[str]
    why: str
    fix: str


class ArchitectMemo(BaseModel):
    headline: str = Field(description="One sentence a CTO would quote")
    overall_assessment: str
    risks: list[MemoRisk]
    quick_wins: list[str]


def deep_scan_enabled() -> bool:
    return bool(get_settings().anthropic_api_key)


def monthly_spend_usd(session) -> float:
    from sqlalchemy import func

    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = (
        session.query(func.coalesce(func.sum(DeepScan.cost_usd), 0.0))
        .filter(DeepScan.created_at >= month_start)
        .scalar()
    )
    return float(total or 0.0)


def _client():
    import anthropic

    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


def _cost(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, out = MODEL_PRICES.get(model, (5.0, 25.0))
    return input_tokens / 1e6 * inp + output_tokens / 1e6 * out


_FILE_SYSTEM_PROMPT = """You are a principal engineer reviewing one file from a repository flagged by a static technical-debt scanner.
Judge whether the static signals reflect REAL maintenance risk. Framework boilerplate, idiomatic repetition, and deliberate patterns are NOT debt — say so via static_signal_correct=false.
Report only findings a senior reviewer would defend in review: swallowed exceptions, divergent copy-paste, unbounded growth, missing tests for risky logic, dangerous defaults.
Be specific: every finding cites concrete evidence from the file. No style nits."""

_MEMO_SYSTEM_PROMPT = """You are a principal engineer writing a short architect memo about a repository, based on per-file reviews and scanner metadata.
Synthesize SYSTEMIC risks (patterns across files), not a list of file nits. 3-5 risks maximum, each with concrete files and a pragmatic fix. Quick wins are changes doable in under an hour.
Write plainly and credibly — the reader is the repo owner, and overstatement destroys trust."""


def _mark(deep_scan_id: str, mutator) -> None:
    session = get_session()
    try:
        record = session.get(DeepScan, deep_scan_id)
        if record is None:
            return
        mutator(record)
        session.commit()
    finally:
        session.close()


@celery_app.task(name="debtmap.run_deep_scan", bind=True, time_limit=60 * 8)
def run_deep_scan(self, deep_scan_id: str) -> None:
    settings = get_settings()

    def _running(r: DeepScan) -> None:
        r.status = "running"

    _mark(deep_scan_id, _running)

    session = get_session()
    try:
        record = session.get(DeepScan, deep_scan_id)
        if record is None:
            return
        from app.models.db import Analysis, load_result

        analysis = session.get(Analysis, record.analysis_id)
        if analysis is None or analysis.status != "completed":
            raise RuntimeError("parent analysis missing or incomplete")
        result = load_result(analysis.result_json) or {}
        repo_url = analysis.repo_url
        branch = analysis.branch
    finally:
        session.close()

    try:
        reviews, memo, usage = _execute(repo_url, branch, result, settings)
        total_cost = usage.pop("cost_usd")

        def _done(r: DeepScan) -> None:
            r.status = "completed"
            r.memo_json = json.dumps(
                {
                    "memo": memo.model_dump(),
                    "file_reviews": [fr.model_dump() for fr in reviews],
                    "models": {
                        "per_file": settings.deep_scan_file_model,
                        "synthesis": settings.deep_scan_synthesis_model,
                    },
                }
            )
            r.input_tokens = usage["input_tokens"]
            r.output_tokens = usage["output_tokens"]
            r.cost_usd = round(total_cost, 4)

        _mark(deep_scan_id, _done)
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"

        def _failed(r: DeepScan) -> None:
            r.status = "failed"
            r.error = msg[:2000]

        _mark(deep_scan_id, _failed)
        raise


def _execute(repo_url: str, branch: str, result: dict, settings) -> tuple[list[FileReview], ArchitectMemo, dict]:
    from app.analysis.repo_loader import clone_repo, cleanup, temp_clone_dir

    client = _client()
    usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    file_summary = result.get("file_summary") or []
    top = [f for f in file_summary if f.get("loc", 0) >= 10][: settings.deep_scan_top_files]

    work = temp_clone_dir()
    sources: dict[str, str] = {}
    try:
        clone_repo(repo_url, branch, None, work)
        from pathlib import Path

        for entry in top:
            p = Path(work) / entry["path"]
            try:
                sources[entry["path"]] = p.read_text(encoding="utf-8")[:MAX_FILE_CHARS]
            except OSError:
                continue
    finally:
        cleanup(work)

    reviews: list[FileReview] = []
    for entry in top:
        source = sources.get(entry["path"])
        if not source:
            continue
        prompt = (
            f"File: {entry['path']}\n"
            f"Static analyzer per-category scores (0-100, higher = more debt): {json.dumps(entry.get('breakdown', {}))}\n\n"
            f"```\n{source}\n```"
        )
        resp = client.messages.parse(
            model=settings.deep_scan_file_model,
            max_tokens=2000,
            system=[{"type": "text", "text": _FILE_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_format=FileReview,
        )
        _track(usage, resp, settings.deep_scan_file_model)
        if resp.parsed_output is not None:
            reviews.append(resp.parsed_output)

    memo_input = {
        "repo": f"{result.get('owner')}/{result.get('repo')}",
        "debt_score": result.get("debt_score"),
        "grade": result.get("grade"),
        "provenance": result.get("provenance"),
        "analyzer_scores": {
            name: v.get("score") for name, v in (result.get("analyzers") or {}).items() if isinstance(v, dict)
        },
        "file_reviews": [fr.model_dump() for fr in reviews],
    }
    memo_resp = client.messages.parse(
        model=settings.deep_scan_synthesis_model,
        max_tokens=3000,
        system=_MEMO_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(memo_input, ensure_ascii=False)}],
        output_format=ArchitectMemo,
    )
    _track(usage, memo_resp, settings.deep_scan_synthesis_model)
    memo = memo_resp.parsed_output
    if memo is None:
        raise RuntimeError("synthesis returned no parsable memo")
    return reviews, memo, usage


def _track(usage: dict, resp, model: str) -> None:
    u = getattr(resp, "usage", None)
    if u is None:
        return
    inp = int(getattr(u, "input_tokens", 0) or 0)
    out = int(getattr(u, "output_tokens", 0) or 0)
    usage["input_tokens"] += inp
    usage["output_tokens"] += out
    usage["cost_usd"] += _cost(model, inp, out)
