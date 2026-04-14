from app.analyzers.error_handling import ErrorHandlingAnalyzer
from tests.conftest import make_file


def test_bare_except_and_silent_pass_detected():
    bad = """
def risky():
    try:
        do_io()
    except:
        pass
    try:
        more()
    except Exception:
        pass
"""
    good = """
def careful():
    try:
        do_io()
    except ValueError as exc:
        logger.warning('bad input', exc)
        raise
"""
    r_bad = ErrorHandlingAnalyzer().analyze([make_file("b.py", bad)], {}).repo_score
    r_good = ErrorHandlingAnalyzer().analyze([make_file("g.py", good)], {}).repo_score
    assert r_bad > r_good
    assert r_bad >= 40


def test_js_empty_catch_detected():
    js = """
function risky() {
  try {
    doIO();
  } catch (e) {
  }
  try { more(); } catch (e) { console.log(e); }
}
"""
    r = ErrorHandlingAnalyzer().analyze([make_file("r.js", js, language="js")], {}).repo_score
    assert r > 10
