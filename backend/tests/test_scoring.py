from app.analysis.scoring import compute_debt_score, grade_for, estimate_ai_generated_pct
from app.analyzers.base import AnalyzerResult, FileResult


def test_grade_thresholds():
    assert grade_for(0) == "A"
    assert grade_for(20) == "A"
    assert grade_for(21) == "B"
    assert grade_for(41) == "C"
    assert grade_for(61) == "D"
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


def test_ai_estimate():
    results = {
        "style_homogeneity": AnalyzerResult("style_homogeneity", 0.0, file_results=[FileResult("a.py", 80), FileResult("b.py", 10)]),
        "duplication": AnalyzerResult("duplication", 0.0, file_results=[FileResult("a.py", 70), FileResult("b.py", 5)]),
        "comment_patterns": AnalyzerResult("comment_patterns", 0.0, file_results=[FileResult("a.py", 75), FileResult("b.py", 2)]),
    }
    pct = estimate_ai_generated_pct(results)
    assert pct == 50.0
