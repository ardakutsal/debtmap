from app.analysis.scoring import compute_debt_score, grade_for
from app.analyzers.base import AnalyzerResult


def test_grade_thresholds():
    assert grade_for(0) == "A"
    assert grade_for(22) == "A"
    assert grade_for(23) == "B"
    assert grade_for(43) == "C"
    assert grade_for(63) == "D"
    assert grade_for(90) == "F"


def test_weighted_score_skips_skipped():
    results = {
        "style_homogeneity": AnalyzerResult("style_homogeneity", 40.0),
        "duplication": AnalyzerResult("duplication", 80.0),
        "comment_patterns": AnalyzerResult("comment_patterns", 0.0),
        "error_handling": AnalyzerResult("error_handling", 20.0),
        "architectural_contracts": AnalyzerResult("architectural_contracts", 50.0),
        "dependency_graph": AnalyzerResult("dependency_graph", 10.0),
        "code_churn": AnalyzerResult("code_churn", 0.0, skipped=True),
    }
    score = compute_debt_score(results)
    assert 20 < score < 80


# AI-share estimation now lives in app.analysis.provenance (git metadata);
# see tests/test_provenance.py.
