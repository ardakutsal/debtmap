from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class FileInput:
    path: str
    language: str
    source: str
    loc: int


@dataclass
class FileResult:
    path: str
    score: float
    details: dict = field(default_factory=dict)


@dataclass
class AnalyzerResult:
    name: str
    repo_score: float
    file_results: list[FileResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    skipped: bool = False


class Analyzer(Protocol):
    name: str

    def analyze(self, files: list[FileInput], context: dict) -> AnalyzerResult: ...


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))


def aggregate_scores(results: list[FileResult], files: list[FileInput]) -> float:
    """LOC-weighted mean blended with the worst decile.

    Debt concentrates in hotspots: a plain mean lets a hundred clean files hide
    the five files where incidents actually start. Blending in the worst 10%
    keeps repo scores honest about concentrated risk without letting a single
    outlier dominate.
    """
    if not results:
        return 0.0
    loc = {f.path: max(1, f.loc) for f in files}

    def wmean(rs: list[FileResult]) -> float:
        total = sum(loc.get(r.path, 1) for r in rs)
        if total == 0:
            return 0.0
        return sum(r.score * loc.get(r.path, 1) for r in rs) / total

    overall = wmean(results)
    k = max(1, len(results) // 10)
    worst = sorted(results, key=lambda r: r.score, reverse=True)[:k]
    return 0.75 * overall + 0.25 * wmean(worst)
