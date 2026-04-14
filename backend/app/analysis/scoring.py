from __future__ import annotations

import math
from dataclasses import dataclass

from app.analyzers import ANALYZER_WEIGHTS
from app.analyzers.base import AnalyzerResult


@dataclass
class Grade:
    score: float
    grade: str


def grade_for(score: float) -> str:
    if score <= 20:
        return "A"
    if score <= 40:
        return "B"
    if score <= 60:
        return "C"
    if score <= 75:
        return "D"
    return "F"


def sigmoid_smooth(score: float) -> float:
    """Gently compress extremes while preserving ordering."""
    x = (score - 50) / 18
    return 100 / (1 + math.exp(-x))


def compute_debt_score(results: dict[str, AnalyzerResult]) -> float:
    total_weight = 0.0
    weighted = 0.0
    for name, res in results.items():
        if res.skipped:
            continue
        w = ANALYZER_WEIGHTS.get(name, 0.0)
        total_weight += w
        weighted += w * res.repo_score
    if total_weight == 0:
        return 0.0
    raw = weighted / total_weight
    return round(min(100.0, max(0.0, 0.5 * raw + 0.5 * sigmoid_smooth(raw))), 2)


def estimate_ai_generated_pct(results: dict[str, AnalyzerResult]) -> float:
    style = {fr.path: fr.score for fr in results.get("style_homogeneity", _empty()).file_results}
    dup = {fr.path: fr.score for fr in results.get("duplication", _empty()).file_results}
    cmt = {fr.path: fr.score for fr in results.get("comment_patterns", _empty()).file_results}
    paths = set(style) | set(dup) | set(cmt)
    if not paths:
        return 0.0
    hits = 0
    for p in paths:
        if style.get(p, 0) > 70 and dup.get(p, 0) > 60 and cmt.get(p, 0) > 65:
            hits += 1
    return round((hits / len(paths)) * 100, 1)


def _empty() -> AnalyzerResult:
    return AnalyzerResult(name="_", repo_score=0.0)
