from __future__ import annotations

from app.analyzers import ANALYZER_WEIGHTS
from app.analyzers.base import AnalyzerResult

CATEGORY_COPY = {
    "style_homogeneity": {
        "title": "Audit template-stamped files",
        "why": "Many near-identical structures usually mean one template was stamped out N times — centralize the template instead of maintaining every copy.",
        "effort": "S",
    },
    "duplication": {
        "title": "Extract shared logic from copy-pasted blocks",
        "why": "Repeated blocks across files drift apart over time: a bug fixed in one copy stays alive in the others.",
        "effort": "M",
    },
    "comment_patterns": {
        "title": "Rewrite low-information comments",
        "why": "Comments that restate the code hide the ones that explain why — keep intent, delete narration.",
        "effort": "S",
    },
    "error_handling": {
        "title": "Tighten error handling",
        "why": "Bare and broad excepts swallow production failures and make incidents hard to debug.",
        "effort": "M",
    },
    "architectural_contracts": {
        "title": "Split oversized units and add type contracts",
        "why": "500+ line functions and missing types block safe refactors and slow onboarding.",
        "effort": "L",
    },
    "dependency_graph": {
        "title": "Resolve import cycles and scattered env access",
        "why": "Circular imports cause fragile module loading; direct env reads make config untestable.",
        "effort": "M",
    },
    "code_churn": {
        "title": "Stabilize fix-loop hotspots",
        "why": "Files re-edited heavily right after creation suggest patch-over-patch loops — pin behavior with tests before the next edit.",
        "effort": "M",
    },
    "test_coverage": {
        "title": "Add tests where there are none",
        "why": "Code without tests cannot be refactored safely — every other debt item compounds until behavior is pinned.",
        "effort": "L",
    },
}


def build_action_plan(results: dict[str, AnalyzerResult], limit: int = 6) -> list[dict]:
    ordered = sorted(
        (
            (name, r)
            for name, r in results.items()
            # Zero-weight analyzers are informational — they don't drive the
            # score, so they don't get to demand action either.
            if not r.skipped and ANALYZER_WEIGHTS.get(name, 0.0) > 0
        ),
        key=lambda item: item[1].repo_score,
        reverse=True,
    )
    plan: list[dict] = []
    for priority, (name, res) in enumerate(ordered, start=1):
        if res.repo_score < 25:
            continue
        top_files = sorted(res.file_results, key=lambda fr: fr.score, reverse=True)[:5]
        copy = CATEGORY_COPY.get(name, {"title": name, "why": "", "effort": "M"})
        plan.append(
            {
                "priority": priority,
                "category": name,
                "title": copy["title"],
                "why": copy["why"],
                "effort": copy["effort"],
                "score": round(res.repo_score, 1),
                "files": [{"path": fr.path, "score": round(fr.score, 1)} for fr in top_files],
            }
        )
        if len(plan) >= limit:
            break
    return plan
