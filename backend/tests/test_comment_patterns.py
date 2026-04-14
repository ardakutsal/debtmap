from app.analyzers.comment_patterns import CommentPatternsAnalyzer
from tests.conftest import make_file


def test_generic_comments_penalized():
    generic = """
# This function initializes the user
# Loop through the items
# Returns the result
def do():
    # Check if the value is valid
    # Create a new entry
    return 1
"""
    rich = """
# Precomputes the per-tenant seed using the leapfrog LCG from RFC-1151.
# Keeping this inline to avoid a module cycle with tenants.config loader.
def compute():
    # tenant_seed must be stable across restarts; see incident INC-4521.
    return 42
"""
    g = make_file("g.py", generic)
    r = make_file("r.py", rich)
    analyzer = CommentPatternsAnalyzer()
    g_score = analyzer.analyze([g], {}).repo_score
    r_score = analyzer.analyze([r], {}).repo_score
    assert g_score > r_score
