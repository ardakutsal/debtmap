from app.analyzers.duplication import DuplicationAnalyzer
from tests.conftest import make_file


def test_cross_file_duplication_detected():
    dup = """
def process(items):
    result = []
    for i, item in enumerate(items):
        if item > 0:
            result.append(item * 2)
        else:
            result.append(item * 3)
    return sum(result) / len(result)
"""
    unique = """
def transform(payload):
    bucket = {}
    for key in payload:
        bucket[key] = payload[key] ** 2
    return bucket
"""
    a = make_file("a.py", dup)
    b = make_file("b.py", dup)
    c = make_file("c.py", unique)
    result = DuplicationAnalyzer().analyze([a, b, c], {})
    scores = {r.path: r.score for r in result.file_results}
    assert scores["a.py"] > scores["c.py"]
    assert scores["b.py"] > scores["c.py"]
