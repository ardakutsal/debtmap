import datetime

import pytest
from git import Actor, Repo

from app.analysis.provenance import analyze_provenance


HUMAN = Actor("Jane Dev", "jane@example.com")
CLAUDE_BOT = Actor("claude[bot]", "claude[bot]@users.noreply.github.com")
DEPENDABOT = Actor("dependabot[bot]", "support@dependabot.com")


def _make_repo(tmp_path, commits):
    """commits: list of (message, author, commit_dt)."""
    repo = Repo.init(tmp_path)
    marker = tmp_path / "file.txt"
    for i, (message, author, dt) in enumerate(commits):
        marker.write_text(f"rev {i}\n")
        repo.index.add(["file.txt"])
        stamp = dt.strftime("%Y-%m-%dT%H:%M:%S")
        repo.index.commit(
            message,
            author=author,
            committer=author,
            author_date=stamp,
            commit_date=stamp,
        )
    return repo


def _dt(day: int, hour: int = 12, minute: int = 0):
    return datetime.datetime(2026, 1, day, hour, minute, tzinfo=datetime.timezone.utc)


def test_trailer_and_identity_detection(tmp_path):
    _make_repo(
        tmp_path,
        [
            ("plain human commit", HUMAN, _dt(1)),
            ("fix: thing\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>", HUMAN, _dt(2)),
            ("feat: other\n\nCo-authored-by: Cursor Agent <agent@cursor.com>", HUMAN, _dt(3)),
            ("chore: bump deps", DEPENDABOT, _dt(4)),
            ("bot-authored change", CLAUDE_BOT, _dt(5)),
        ],
    )
    prov = analyze_provenance(str(tmp_path))
    assert prov is not None
    assert prov["commits_sampled"] == 5
    assert prov["ai_commits"] == 3  # two trailers + one bot identity
    assert prov["ai_commit_pct"] == 60.0
    assert prov["automation_commits"] == 1
    agent_names = {a["name"] for a in prov["agents"]}
    assert "Claude Code" in agent_names
    assert "Cursor" in agent_names
    assert prov["human_authors"] == 1
    assert prov["confidence"] == "high"
    assert prov["likely_ai_assisted"] is True


def test_generated_with_body_line(tmp_path):
    _make_repo(
        tmp_path,
        [("add feature\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)", HUMAN, _dt(1))],
    )
    prov = analyze_provenance(str(tmp_path))
    assert prov["ai_commit_pct"] == 100.0
    assert prov["agents"][0]["name"] == "Claude Code"


def test_human_name_does_not_false_positive(tmp_path):
    # "Augusto" must not match the Augment trailer keyword via identity rules.
    augusto = Actor("Augusto Silva", "augusto@example.com")
    _make_repo(tmp_path, [("normal work", augusto, _dt(1)), ("more work", augusto, _dt(2))])
    prov = analyze_provenance(str(tmp_path))
    assert prov["ai_commits"] == 0
    assert prov["likely_ai_assisted"] is False
    assert prov["confidence"] == "medium"


def test_velocity_flag_without_signatures(tmp_path):
    commits = [
        (f"commit {i}", HUMAN, _dt(1, hour=8, minute=i * 2))
        for i in range(25)
    ]
    _make_repo(tmp_path, commits)
    prov = analyze_provenance(str(tmp_path))
    assert prov["ai_commit_pct"] == 0.0
    assert prov["velocity"]["flag"] == "very_high"
    assert prov["velocity"]["peak_commits_24h"] == 25
    assert prov["likely_ai_assisted"] is True
    assert prov["confidence"] == "low"


def test_non_git_dir_returns_none(tmp_path):
    assert analyze_provenance(str(tmp_path)) is None
