from app.analyzers.base import AnalyzerResult, FileInput, FileResult, Analyzer
from app.analyzers.style_homogeneity import StyleHomogeneityAnalyzer
from app.analyzers.duplication import DuplicationAnalyzer
from app.analyzers.comment_patterns import CommentPatternsAnalyzer
from app.analyzers.error_handling import ErrorHandlingAnalyzer
from app.analyzers.architectural_contracts import ArchitecturalContractsAnalyzer
from app.analyzers.dependency_graph import DependencyGraphAnalyzer
from app.analyzers.code_churn import CodeChurnAnalyzer

ANALYZERS: list[type[Analyzer]] = [
    StyleHomogeneityAnalyzer,
    DuplicationAnalyzer,
    CommentPatternsAnalyzer,
    ErrorHandlingAnalyzer,
    ArchitecturalContractsAnalyzer,
    DependencyGraphAnalyzer,
    CodeChurnAnalyzer,
]

ANALYZER_WEIGHTS: dict[str, float] = {
    "style_homogeneity": 0.15,
    "duplication": 0.25,
    "comment_patterns": 0.10,
    "error_handling": 0.20,
    "architectural_contracts": 0.15,
    "dependency_graph": 0.10,
    "code_churn": 0.05,
}

__all__ = [
    "Analyzer",
    "AnalyzerResult",
    "FileInput",
    "FileResult",
    "ANALYZERS",
    "ANALYZER_WEIGHTS",
]
