from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Callable

from app.analysis.action_plan import build_action_plan
from app.analysis.repo_loader import (
    LoadedRepo,
    clone_repo,
    cleanup,
    load_files_from_dir,
    parse_repo_url,
    temp_clone_dir,
)
from app.analysis.scoring import compute_debt_score, estimate_ai_generated_pct, grade_for
from app.analyzers import ANALYZERS, ANALYZER_WEIGHTS
from app.analyzers.base import AnalyzerResult, FileInput


ProgressCb = Callable[[int, str], None]


def analyze_files(
    files: list[FileInput],
    context: dict,
    progress: ProgressCb | None = None,
) -> dict:
    results: dict[str, AnalyzerResult] = {}
    total = len(ANALYZERS)
    for idx, Cls in enumerate(ANALYZERS):
        analyzer = Cls()
        if progress:
            progress(
                int(20 + (idx / total) * 70),
                f"Running {analyzer.name}",
            )
        results[analyzer.name] = analyzer.analyze(files, context)

    debt_score = compute_debt_score(results)
    return {
        "debt_score": debt_score,
        "grade": grade_for(debt_score),
        "ai_generated_pct": estimate_ai_generated_pct(results),
        "analyzers": {
            name: {
                "score": round(r.repo_score, 2),
                "weight": ANALYZER_WEIGHTS.get(name, 0.0),
                "skipped": r.skipped,
                "notes": r.notes,
                "file_results": [
                    {"path": fr.path, "score": round(fr.score, 2), "details": fr.details}
                    for fr in r.file_results
                ],
            }
            for name, r in results.items()
        },
        "file_summary": _file_summary(results, files),
        "action_plan": build_action_plan(results),
    }


def _file_summary(results: dict[str, AnalyzerResult], files: list[FileInput]) -> list[dict]:
    per_file: dict[str, dict[str, float]] = {}
    for name, r in results.items():
        if r.skipped:
            continue
        for fr in r.file_results:
            per_file.setdefault(fr.path, {})[name] = fr.score
    file_loc = {f.path: f.loc for f in files}
    summary = []
    for path, scores in per_file.items():
        total_w = 0.0
        weighted = 0.0
        for name, score in scores.items():
            w = ANALYZER_WEIGHTS.get(name, 0.0)
            total_w += w
            weighted += w * score
        file_score = round(weighted / total_w, 2) if total_w else 0.0
        summary.append(
            {
                "path": path,
                "loc": file_loc.get(path, 0),
                "score": file_score,
                "breakdown": {k: round(v, 2) for k, v in scores.items()},
            }
        )
    summary.sort(key=lambda s: s["score"], reverse=True)
    return summary


def analyze_repo(url: str, branch: str = "main", github_token: str | None = None, progress: ProgressCb | None = None) -> dict:
    owner, repo = parse_repo_url(url)
    work = temp_clone_dir()
    try:
        if progress:
            progress(5, "Cloning repository")
        actual_branch = clone_repo(url, branch, github_token, work)
        branch = actual_branch
        if progress:
            progress(15, "Scanning files")
        loaded = load_files_from_dir(work)
        loaded.owner = owner
        loaded.repo = repo
        context = {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "github_token": github_token,
        }
        start = time.time()
        result = analyze_files(loaded.files, context, progress=progress)
        elapsed = time.time() - start
        if progress:
            progress(95, "Finalizing")
        return {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "files_analyzed": len(loaded.files),
            "files_skipped_too_large": loaded.skipped_too_large,
            "elapsed_seconds": round(elapsed, 2),
            **result,
        }
    finally:
        cleanup(work)


def _cli():
    parser = argparse.ArgumentParser(description="DebtMap analysis runner")
    parser.add_argument("url", help="GitHub repository URL")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    def printer(pct: int, step: str):
        print(f"[{pct:3d}%] {step}", file=sys.stderr)

    result = analyze_repo(args.url, args.branch, args.token, progress=printer)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    _cli()
