"""API behavior tests: reuse cache, leaderboard, latest-by-repo."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from app.config import get_settings

    get_settings.cache_clear()
    import app.models.db as dbmod

    dbmod._engine = None
    dbmod._SessionLocal = None

    from fastapi.testclient import TestClient
    from app.api.main import app

    yield TestClient(app)
    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._SessionLocal = None


def _insert_completed(owner: str, repo: str, score: float, files: int = 50, age_minutes: int = 5):
    from app.models.db import Analysis, get_session

    session = get_session()
    try:
        ts = datetime.utcnow() - timedelta(minutes=age_minutes)
        record = Analysis(
            id=uuid.uuid4().hex,
            repo_url=f"https://github.com/{owner}/{repo}",
            owner=owner,
            repo=repo,
            branch="main",
            status="completed",
            progress_pct=100,
            debt_score=score,
            grade="A" if score <= 22 else "B",
            ai_generated_pct=0.0,
            result_json=json.dumps({"files_analyzed": files, "debt_score": score}),
            created_at=ts,
            updated_at=ts,
        )
        session.add(record)
        session.commit()
        return record.id
    finally:
        session.close()


def test_analyze_reuses_recent_completed(client):
    rid = _insert_completed("acme", "widget", 18.0)
    resp = client.post("/analyze", json={"repo_url": "https://github.com/acme/widget"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["analysis_id"] == rid
    assert body["status"] == "completed"


def test_analyze_force_bypasses_reuse(client, monkeypatch):
    rid = _insert_completed("acme", "widget", 18.0)
    # Don't actually enqueue celery work in tests.
    import app.services.tasks as tasks_mod

    monkeypatch.setattr(tasks_mod.run_analysis, "delay", lambda *_a, **_k: None)
    resp = client.post("/analyze", json={"repo_url": "https://github.com/acme/widget", "force": True})
    assert resp.status_code == 202
    assert resp.json()["analysis_id"] != rid
    assert resp.json()["status"] == "queued"


def test_leaderboard_orders_and_filters(client):
    _insert_completed("good", "repo", 12.0, files=100)
    _insert_completed("worse", "repo", 30.0, files=100)
    _insert_completed("tiny", "repo", 1.0, files=3)  # filtered: <10 files
    resp = client.get("/leaderboard")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    names = [(e["owner"], e["repo"]) for e in entries]
    assert ("tiny", "repo") not in names
    assert names.index(("good", "repo")) < names.index(("worse", "repo"))


def test_latest_for_repo(client):
    _insert_completed("acme", "widget", 25.0, age_minutes=60)
    newest = _insert_completed("acme", "widget", 18.0, age_minutes=1)
    resp = client.get("/repos/acme/widget/latest")
    assert resp.status_code == 200
    assert resp.json()["analysis_id"] == newest
    missing = client.get("/repos/nope/nope/latest")
    assert missing.status_code == 404
