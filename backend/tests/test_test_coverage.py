from app.analyzers.test_coverage import TestCoverageAnalyzer, is_test_file
from tests.conftest import make_file


def test_untested_repo_scores_high():
    files = [make_file(f"app/module_{i}.py", "x = 1\n" * 50) for i in range(5)]
    result = TestCoverageAnalyzer().analyze(files, {})
    assert result.repo_score == 60.0
    assert any("No test files" in n for n in result.notes)


def test_well_tested_repo_scores_zero():
    files = [
        make_file("app/module.py", "x = 1\n" * 100),
        make_file("tests/test_module.py", "assert True\n" * 60),
    ]
    result = TestCoverageAnalyzer().analyze(files, {})
    assert result.repo_score == 0.0


def test_partial_coverage_scales():
    files = [
        make_file("app/module.py", "x = 1\n" * 100),
        make_file("tests/test_module.py", "assert True\n" * 10),
    ]
    result = TestCoverageAnalyzer().analyze(files, {})
    assert 0 < result.repo_score < 60


def test_test_file_detection():
    assert is_test_file("tests/test_api.py")
    assert is_test_file("src/__tests__/Button.test.tsx")
    assert is_test_file("src/components/Button.spec.ts")
    assert is_test_file("backend/tests/conftest.py")
    assert not is_test_file("app/contest.py")
    assert not is_test_file("src/latest_news.py")
    assert not is_test_file("app/protester.tsx")
