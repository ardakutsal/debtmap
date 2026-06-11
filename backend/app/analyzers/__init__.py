from app.analyzers.base import AnalyzerResult, FileInput, FileResult, Analyzer
from app.analyzers.style_homogeneity import StyleHomogeneityAnalyzer
from app.analyzers.duplication import DuplicationAnalyzer
from app.analyzers.comment_patterns import CommentPatternsAnalyzer
from app.analyzers.error_handling import ErrorHandlingAnalyzer
from app.analyzers.architectural_contracts import ArchitecturalContractsAnalyzer
from app.analyzers.dependency_graph import DependencyGraphAnalyzer
from app.analyzers.code_churn import CodeChurnAnalyzer
from app.analyzers.test_coverage import TestCoverageAnalyzer

ANALYZERS: list[type[Analyzer]] = [
    StyleHomogeneityAnalyzer,
    DuplicationAnalyzer,
    CommentPatternsAnalyzer,
    ErrorHandlingAnalyzer,
    ArchitecturalContractsAnalyzer,
    DependencyGraphAnalyzer,
    CodeChurnAnalyzer,
    TestCoverageAnalyzer,
]

# Calibrated 2026-06-11 against a known corpus (mature human libs vs
# vibe-coded repos) via scripts/calibrate.py. Error handling, structure, and
# test presence are the strongest real-debt signals. Style homogeneity is
# weight 0 — informational only: curated human code measures MORE uniform than
# AI output, so "uniformity = debt" failed calibration.
ANALYZER_WEIGHTS: dict[str, float] = {
    "style_homogeneity": 0.0,
    "duplication": 0.20,
    "comment_patterns": 0.10,
    "error_handling": 0.25,
    "architectural_contracts": 0.20,
    "dependency_graph": 0.10,
    "code_churn": 0.05,
    "test_coverage": 0.10,
}

__all__ = [
    "Analyzer",
    "AnalyzerResult",
    "FileInput",
    "FileResult",
    "ANALYZERS",
    "ANALYZER_WEIGHTS",
]
