from app.analyzers.code_churn import CodeChurnAnalyzer
from tests.conftest import make_file


def test_skipped_without_context():
    result = CodeChurnAnalyzer().analyze([make_file("a.py", "x=1")], {})
    assert result.skipped is True
    assert result.repo_score == 50.0
