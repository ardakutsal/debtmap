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
