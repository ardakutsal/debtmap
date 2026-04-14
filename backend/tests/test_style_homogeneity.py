from app.analyzers.style_homogeneity import StyleHomogeneityAnalyzer
from tests.conftest import make_file


def test_homogeneous_code_scores_higher_than_varied():
    uniform_src = "\n\n".join(
        f"def handler_{i}(data):\n    result = process(data)\n    validate(result)\n    return result"
        for i in range(20)
    )
    varied_src = """
def tiny(x): return x
def medium(a, b, c):
    total = 0
    for item in (a, b, c):
        total += item * 2
    return total
def sprawling_processor(payload, ctx, logger, retries=3, timeout=10):
    buf = []
    for i, entry in enumerate(payload):
        if not entry:
            continue
        try:
            logger.debug('entry', i)
            buf.append(entry * i)
        except Exception as exc:
            logger.error(exc)
            if retries > 0:
                retries -= 1
                continue
            raise
    return sum(buf) / max(1, len(buf))
"""
    uniform = make_file("u.py", uniform_src)
    varied = make_file("v.py", varied_src)
    analyzer = StyleHomogeneityAnalyzer()
    u_score = analyzer.analyze([uniform], {}).repo_score
    v_score = analyzer.analyze([varied], {}).repo_score
    assert u_score > v_score
