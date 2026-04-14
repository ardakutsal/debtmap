from app.analyzers.architectural_contracts import ArchitecturalContractsAnalyzer
from tests.conftest import make_file


def test_missing_annotations_raises_score():
    untyped = """
def a(x, y, z):
    return x + y + z

def b(p, q):
    return p * q

def c(one, two, three, four, five, six, seven):
    return one
"""
    typed = """
def a(x: int, y: int, z: int) -> int:
    return x + y + z

def b(p: float, q: float) -> float:
    return p * q
"""
    u = ArchitecturalContractsAnalyzer().analyze([make_file("u.py", untyped)], {}).repo_score
    t = ArchitecturalContractsAnalyzer().analyze([make_file("t.py", typed)], {}).repo_score
    assert u > t
