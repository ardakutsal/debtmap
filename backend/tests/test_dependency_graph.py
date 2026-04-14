from app.analyzers.dependency_graph import DependencyGraphAnalyzer
from tests.conftest import make_file


def test_cycle_flagged():
    a = make_file("pkg/a.py", "from pkg import b\nx = 1\n")
    b = make_file("pkg/b.py", "from pkg import a\ny = 2\n")
    result = DependencyGraphAnalyzer().analyze([a, b], {})
    scores = {r.path: r.score for r in result.file_results}
    assert scores["pkg/a.py"] > 0
    assert scores["pkg/b.py"] > 0


def test_env_direct_access_penalized_outside_config():
    ugly = make_file("service.py", "import os\nkey = os.environ['KEY']\n")
    ok = make_file("config.py", "import os\nkey = os.environ['KEY']\n")
    result = DependencyGraphAnalyzer().analyze([ugly, ok], {})
    scores = {r.path: r.score for r in result.file_results}
    assert scores["service.py"] > scores["config.py"]
