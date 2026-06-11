"""Calibration harness: run the analyzer over a known corpus and print a table.

Usage:
    cd backend && .venv/bin/python -m scripts.calibrate [--json out.json]

The corpus mixes mature human-written repos with known vibe-coded ones. The
score must order them defensibly: a 15-year curated library should never grade
worse than a 2-day AI-generated repo. Tune weights/thresholds against this
table, not against intuition.
"""
from __future__ import annotations

import argparse
import json
import sys

from app.analysis.runner import analyze_repo

CORPUS: list[tuple[str, str]] = [
    # (label, url) — label: human-mature | ai-built | mixed
    ("human-mature", "https://github.com/psf/requests"),
    ("human-mature", "https://github.com/pallets/click"),
    ("human-mature", "https://github.com/pallets/flask"),
    ("human-mature", "https://github.com/encode/httpx"),
    ("ai-built", "https://github.com/Garl-Protocol/garl"),
]

COLUMNS = [
    "style_homogeneity",
    "duplication",
    "comment_patterns",
    "error_handling",
    "architectural_contracts",
    "dependency_graph",
    "code_churn",
    "test_coverage",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=None, help="dump full results to this path")
    parser.add_argument("--repo", action="append", default=None, help="extra repo URL (repeatable)")
    args = parser.parse_args()

    corpus = list(CORPUS)
    for extra in args.repo or []:
        corpus.append(("extra", extra))

    rows = []
    full = {}
    for label, url in corpus:
        name = url.rstrip("/").split("github.com/")[-1]
        print(f"→ analyzing {name} …", file=sys.stderr)
        try:
            result = analyze_repo(url)
        except Exception as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            continue
        full[name] = result
        analyzer_scores = {
            k: (None if v.get("skipped") else v.get("score"))
            for k, v in result["analyzers"].items()
        }
        rows.append(
            {
                "label": label,
                "repo": name,
                "files": result["files_analyzed"],
                "score": result["debt_score"],
                "grade": result["grade"],
                "ai_pct": result.get("ai_generated_pct"),
                **{c: analyzer_scores.get(c) for c in COLUMNS},
            }
        )

    rows.sort(key=lambda r: r["score"])
    header = f"{'repo':32} {'label':13} {'files':>5} {'score':>6} {'grade':>5} {'ai%':>6}  " + "  ".join(
        c[:7] for c in COLUMNS
    )
    print("\n" + header)
    print("-" * len(header))
    for r in rows:
        cols = "  ".join(
            f"{(r[c] if r[c] is not None else '—'):>7}" if not isinstance(r[c], float) else f"{r[c]:7.1f}"
            for c in COLUMNS
        )
        print(
            f"{r['repo']:32} {r['label']:13} {r['files']:>5} {r['score']:>6.1f} {r['grade']:>5} {r['ai_pct']:>6}  {cols}"
        )

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(full, fh, indent=1)
        print(f"\nfull results → {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
