"""Test Coverage Proxy analyzer.

The strongest cheap signal separating maintained code from vibe-coded sprawl:
mature repos ship substantial test suites; throwaway AI output usually ships
none. We don't run anything — we compare test LOC to production LOC among the
files already loaded.

A repo keeping its tests in a separate repository will be over-penalized; the
note in the result says exactly what was measured so the score is arguable
rather than mysterious.
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath

from app.analyzers.base import AnalyzerResult, FileInput, clamp

# Ratio at (or above) which we consider the repo healthily tested.
HEALTHY_RATIO = 0.35
MAX_SCORE = 60.0

_TEST_DIR_RE = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)")
_TEST_FILE_RE = re.compile(
    r"(^test_.*\.py$)|(_test\.py$)|(\.(test|spec)\.(ts|tsx|js|jsx)$)|(^conftest\.py$)"
)


def is_test_file(path: str) -> bool:
    p = path.replace("\\", "/")
    if _TEST_DIR_RE.search(p.rsplit("/", 1)[0] + "/" if "/" in p else ""):
        return True
    return bool(_TEST_FILE_RE.search(PurePosixPath(p).name))


class TestCoverageAnalyzer:
    name = "test_coverage"

    def analyze(self, files: list[FileInput], context: dict) -> AnalyzerResult:
        test_loc = sum(f.loc for f in files if is_test_file(f.path))
        prod_loc = sum(f.loc for f in files if not is_test_file(f.path))
        if prod_loc == 0:
            return AnalyzerResult(name=self.name, repo_score=0.0, skipped=True)

        ratio = test_loc / prod_loc
        score = clamp(MAX_SCORE * (1 - min(ratio, HEALTHY_RATIO) / HEALTHY_RATIO))
        notes = [
            f"test LOC / production LOC = {ratio:.2f} "
            f"({test_loc} / {prod_loc}; healthy ≥ {HEALTHY_RATIO})"
        ]
        if test_loc == 0:
            notes.append("No test files found among analyzed files")
        return AnalyzerResult(name=self.name, repo_score=round(score, 2), notes=notes)
