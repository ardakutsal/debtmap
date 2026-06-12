"""End-to-end API smoke test using Celery eager mode + a local git repo."""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from app.services.celery_app import celery_app


@pytest.fixture(scope="module")
def local_repo(tmp_path_factory):
    path = tmp_path_factory.mktemp("sample_repo")
    (path / "a.py").write_text(
        "def add(x, y):\n    return x + y\n\n"
        "def mul(a, b):\n    return a * b\n"
    )
    (path / "b.py").write_text(
        "def handler(data):\n"
        "    try:\n"
        "        return data * 2\n"
        "    except:\n"
        "        pass\n"
    )
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=path)
    subprocess.check_call(["git", "config", "user.email", "t@t.t"], cwd=path)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=path)
    subprocess.check_call(["git", "add", "."], cwd=path)
    subprocess.check_call(["git", "commit", "-q", "-m", "init"], cwd=path)
    return path


def test_full_analyze_flow(local_repo, tmp_path, monkeypatch):
    db_path = tmp_path / "smoke.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from app.config import get_settings
    get_settings.cache_clear()
    import app.models.db as dbmod
    dbmod._engine = None
    dbmod._SessionLocal = None

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    from fastapi.testclient import TestClient
    from app.api.main import app

    client = TestClient(app)

    health_resp = client.get("/health")
    health = health_resp.json()
    # Redis may not run on contributor machines/CI: db must be up, redis may
    # legitimately report degraded (503).
    assert health["db"] is True
    assert health_resp.status_code == (200 if health["redis"] else 503)

    resp = client.post(
        "/analyze",
        json={"repo_url": f"file://{local_repo}", "branch": "main"},
    )
    # local file:// URLs are rejected by Pydantic's HttpUrl validator (422):
    assert resp.status_code in (400, 422)

    # Direct runner test against local path (the happy path we wire into /analyze via the
    # worker). Patch the runner's own bindings — patching repo_loader is a no-op
    # once another test has already imported the runner module.
    import app.analysis.runner as runner_mod

    def fake_clone(url, branch, token, dest):
        subprocess.check_call(["git", "clone", "-q", url.replace("file://", ""), dest])
        return branch

    monkeypatch.setattr(runner_mod, "clone_repo", fake_clone)
    monkeypatch.setattr(runner_mod, "parse_repo_url", lambda url: ("local", "sample"))

    result = runner_mod.analyze_repo(f"file://{local_repo}", branch="main")
    assert result["owner"] == "local"
    assert result["repo"] == "sample"
    assert 0 <= result["debt_score"] <= 100
    assert result["grade"] in {"A", "B", "C", "D", "F"}
    assert "action_plan" in result
    assert isinstance(result["file_summary"], list)
    assert result["files_analyzed"] >= 2
