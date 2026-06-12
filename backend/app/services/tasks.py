from __future__ import annotations

import traceback
from datetime import datetime, timedelta

from app.analysis.runner import analyze_repo
from app.models.db import Analysis, dump_result, get_session
from app.services.celery_app import celery_app
from app.services.tokens import decrypt


def _short_txn(analysis_id: str, mutator):
    """Run a tiny write transaction. Short-lived sessions keep SQLite's single
    writer lock free during long-running work (clone, GitHub API calls)."""
    session = get_session()
    try:
        record = session.get(Analysis, analysis_id)
        if record is None:
            return
        mutator(record)
        session.commit()
    finally:
        session.close()


class RepoTooLargeError(Exception):
    """Raised before cloning when GitHub reports the repo above our size cap."""


def _precheck_repo_size(repo_url: str, token: str | None) -> None:
    """Ask GitHub for repo size before cloning. Fail friendly when oversized;
    on any check failure (rate limit, network) proceed — the clone timeout is
    the backstop."""
    import httpx

    from app.analysis.repo_loader import parse_repo_url
    from app.config import get_settings

    try:
        owner, repo = parse_repo_url(repo_url)
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = httpx.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=headers,
            timeout=10.0,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return
        size_kb = int(resp.json().get("size") or 0)
    except Exception:
        return
    max_kb = get_settings().max_repo_size_kb
    if size_kb > max_kb:
        raise RepoTooLargeError(
            f"Repository is ~{size_kb // 1024} MB — above the hosted limit of {max_kb // 1024} MB. "
            "Run DebtMap locally (docker compose up) for very large repositories."
        )


def _load_fields(analysis_id: str) -> tuple[str, str, str | None]:
    session = get_session()
    try:
        record = session.get(Analysis, analysis_id)
        if record is None:
            raise RuntimeError(f"analysis {analysis_id} not found")
        return record.repo_url, record.branch, record.encrypted_token
    finally:
        session.close()


@celery_app.task(name="debtmap.run_analysis", bind=True)
def run_analysis(self, analysis_id: str) -> None:
    def _mark_running(r: Analysis) -> None:
        r.status = "running"
        r.progress_pct = 1
        r.current_step = "Starting"

    _short_txn(analysis_id, _mark_running)

    repo_url, branch, encrypted_token = _load_fields(analysis_id)
    token = decrypt(encrypted_token)

    def progress(pct: int, step: str):
        def _update(r: Analysis) -> None:
            r.progress_pct = pct
            r.current_step = step
        _short_txn(analysis_id, _update)

    try:
        _precheck_repo_size(repo_url, token)
        result = analyze_repo(repo_url, branch=branch, github_token=token, progress=progress)

        def _mark_completed(r: Analysis) -> None:
            r.debt_score = result.get("debt_score")
            r.grade = result.get("grade")
            r.ai_generated_pct = result.get("ai_generated_pct")
            r.result_json = dump_result(result)
            r.status = "completed"
            r.progress_pct = 100
            r.current_step = "Done"
            r.token_expires_at = datetime.utcnow() + timedelta(hours=1)
        _short_txn(analysis_id, _mark_completed)
    except Exception as exc:
        from app.analysis.repo_loader import RepoCloneError

        tb = traceback.format_exc()
        is_user_facing = isinstance(exc, (RepoCloneError, RepoTooLargeError))
        clean_msg = str(exc) if is_user_facing else f"{exc}\n{tb}"

        def _mark_failed(r: Analysis) -> None:
            r.status = "failed"
            r.error = clean_msg
        _short_txn(analysis_id, _mark_failed)
        if is_user_facing:
            # Don't raise — user-facing errors are not retryable and shouldn't
            # pollute worker logs with stack traces.
            return
        raise


@celery_app.task(name="debtmap.refresh_recent_repos")
def refresh_recent_repos(limit: int = 20) -> int:
    """Weekly: re-scan repos analyzed in the last 90 days so leaderboard and
    badges stay current. Newest-activity repos first, capped to keep the
    worker calm."""
    import uuid as _uuid
    from datetime import datetime as _dt, timedelta as _td

    session = get_session()
    try:
        from sqlalchemy import func

        cutoff = _dt.utcnow() - _td(days=90)
        rows = (
            session.query(Analysis.owner, Analysis.repo, Analysis.repo_url, func.max(Analysis.updated_at))
            .filter(Analysis.status == "completed", Analysis.updated_at >= cutoff)
            .group_by(Analysis.owner, Analysis.repo, Analysis.repo_url)
            .order_by(func.max(Analysis.updated_at).desc())
            .limit(limit)
            .all()
        )
        created = 0
        for owner, repo, repo_url, _latest in rows:
            # Guard against double-enqueue (e.g. two beat processes during a
            # deploy overlap): skip repos already queued/running.
            inflight = (
                session.query(Analysis)
                .filter(
                    Analysis.owner == owner,
                    Analysis.repo == repo,
                    Analysis.status.in_(["queued", "running"]),
                )
                .count()
            )
            if inflight:
                continue
            new_id = _uuid.uuid4().hex
            session.add(
                Analysis(
                    id=new_id,
                    repo_url=repo_url,
                    owner=owner,
                    repo=repo,
                    branch="main",
                    status="queued",
                    progress_pct=0,
                    current_step="Queued (weekly refresh)",
                )
            )
            session.commit()
            run_analysis.delay(new_id)
            created += 1
        return created
    finally:
        session.close()


@celery_app.task(name="debtmap.purge_tokens")
def purge_expired_tokens() -> int:
    session = get_session()
    try:
        now = datetime.utcnow()
        q = session.query(Analysis).filter(Analysis.token_expires_at < now, Analysis.encrypted_token.isnot(None))
        count = 0
        for record in q.all():
            record.encrypted_token = None
            count += 1
        session.commit()
        return count
    finally:
        session.close()
