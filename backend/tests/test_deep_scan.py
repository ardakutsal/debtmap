"""Deep Scan tests with a faked Anthropic client and faked clone."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ds.db'}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    import app.models.db as dbmod

    dbmod._engine = None
    dbmod._SessionLocal = None
    yield
    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._SessionLocal = None


class _Usage:
    input_tokens = 1000
    output_tokens = 200


class _FakeResp:
    def __init__(self, parsed):
        self.parsed_output = parsed
        self.usage = _Usage()


class _FakeMessages:
    def parse(self, **kwargs):
        from app.services.deep_scan import ArchitectMemo, FileReview, FileFinding, MemoRisk

        if kwargs["output_format"] is FileReview:
            return _FakeResp(
                FileReview(
                    path="app/big.py",
                    verdict="Real broad-except problem",
                    static_signal_correct=True,
                    findings=[
                        FileFinding(
                            title="Swallowed exceptions",
                            severity="high",
                            evidence="except Exception: pass",
                            fix="Catch specific errors and log",
                        )
                    ],
                )
            )
        return _FakeResp(
            ArchitectMemo(
                headline="Error handling is the load-bearing risk",
                overall_assessment="Solid shape, weak exception hygiene.",
                risks=[
                    MemoRisk(
                        title="Silent failure paths",
                        severity="high",
                        files=["app/big.py"],
                        why="Broad excepts hide incidents",
                        fix="Narrow handlers",
                    )
                ],
                quick_wins=["Replace bare except in app/big.py"],
            )
        )


class _FakeClient:
    messages = _FakeMessages()


def _seed_analysis() -> str:
    from app.models.db import Analysis, get_session

    session = get_session()
    try:
        aid = uuid.uuid4().hex
        session.add(
            Analysis(
                id=aid,
                repo_url="https://github.com/acme/widget",
                owner="acme",
                repo="widget",
                branch="main",
                status="completed",
                progress_pct=100,
                debt_score=20.0,
                grade="A",
                result_json=json.dumps(
                    {
                        "owner": "acme",
                        "repo": "widget",
                        "debt_score": 20.0,
                        "grade": "A",
                        "files_analyzed": 30,
                        "analyzers": {"error_handling": {"score": 30.0}},
                        "file_summary": [
                            {"path": "app/big.py", "loc": 400, "score": 80.0, "breakdown": {"error_handling": 82}}
                        ],
                    }
                ),
            )
        )
        session.commit()
        return aid
    finally:
        session.close()


def test_deep_scan_task_end_to_end(fresh_db, tmp_path, monkeypatch):
    import app.services.deep_scan as ds_mod
    from app.models.db import DeepScan, get_session
    from app.services.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    aid = _seed_analysis()

    monkeypatch.setattr(ds_mod, "_client", lambda: _FakeClient())

    def fake_execute_clone(url, branch, token, dest):
        from pathlib import Path

        target = Path(dest) / "app"
        target.mkdir(parents=True, exist_ok=True)
        (target / "big.py").write_text("try:\n    x()\nexcept Exception:\n    pass\n")
        return branch

    import app.analysis.repo_loader as loader_mod

    monkeypatch.setattr(ds_mod, "_clone_for_test", fake_execute_clone, raising=False)
    # _execute imports clone_repo from repo_loader at call time
    monkeypatch.setattr(loader_mod, "clone_repo", fake_execute_clone)

    session = get_session()
    try:
        ds = DeepScan(id=uuid.uuid4().hex, analysis_id=aid, ip="1.2.3.4", status="queued")
        session.add(ds)
        session.commit()
        ds_id = ds.id
    finally:
        session.close()

    ds_mod.run_deep_scan.apply(args=[ds_id])

    session = get_session()
    try:
        row = session.get(DeepScan, ds_id)
        assert row.status == "completed", row.error
        memo = json.loads(row.memo_json)
        assert memo["memo"]["headline"]
        assert memo["file_reviews"][0]["path"] == "app/big.py"
        assert row.cost_usd > 0
        assert row.input_tokens == 2000  # one file call + one synthesis call
    finally:
        session.close()


def test_deep_scan_api_quota_and_flags(fresh_db, monkeypatch):
    from fastapi.testclient import TestClient
    import app.services.tasks  # noqa: F401 — ensure task registry (and don't shadow `app` below)
    from app.api.main import app
    from app.services import deep_scan as ds_mod

    monkeypatch.setattr(ds_mod.run_deep_scan, "delay", lambda *_a, **_k: None)

    client = TestClient(app)
    aid = _seed_analysis()

    # results payload advertises availability
    r = client.get(f"/results/{aid}")
    assert r.json()["deep_scan_enabled"] is True

    first = client.post(f"/results/{aid}/deep-scan")
    assert first.status_code == 202
    # idempotent: same analysis returns the existing scan
    again = client.post(f"/results/{aid}/deep-scan")
    assert again.json()["deep_scan_id"] == first.json()["deep_scan_id"]

    status = client.get(f"/results/{aid}/deep-scan")
    assert status.status_code == 200
    assert status.json()["status"] == "queued"


def test_deep_scan_disabled_without_key(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ds2.db'}")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    import app.models.db as dbmod

    dbmod._engine = None
    dbmod._SessionLocal = None

    from fastapi.testclient import TestClient
    from app.api.main import app

    client = TestClient(app)
    aid = _seed_analysis()
    resp = client.post(f"/results/{aid}/deep-scan")
    assert resp.status_code == 503
    assert client.get(f"/results/{aid}").json()["deep_scan_enabled"] is False

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._SessionLocal = None


def test_enabled_via_openrouter_key(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ds3.db'}")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.services.deep_scan import deep_scan_enabled, llm_provider

    assert llm_provider() == "openrouter"
    assert deep_scan_enabled() is True
    get_settings.cache_clear()


def test_anthropic_preferred_over_openrouter(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.services.deep_scan import llm_provider

    assert llm_provider() == "anthropic"
    get_settings.cache_clear()


def test_openrouter_structured_parses_and_costs(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    from app.config import get_settings

    get_settings.cache_clear()
    import app.services.deep_scan as ds_mod
    from app.services.deep_scan import FileReview, _cost

    fake_payload = {
        "choices": [
            {
                "message": {
                    "content": '```json\n{"path": "a.py", "verdict": "ok", "static_signal_correct": true, "findings": []}\n```'
                }
            }
        ],
        "usage": {"prompt_tokens": 1500, "completion_tokens": 100},
    }

    class _FakeHTTPResp:
        def raise_for_status(self):
            return None

        def json(self):
            return fake_payload

    import httpx

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["model"] = json["model"]
        captured["response_format"] = json["response_format"]["type"]
        return _FakeHTTPResp()

    monkeypatch.setattr(httpx, "post", fake_post)
    parsed, inp, out = ds_mod._openrouter_structured(
        "claude-haiku-4-5", "system", "user", FileReview, 1000
    )
    assert captured["model"] == "anthropic/claude-haiku-4.5"
    assert captured["response_format"] == "json_schema"
    assert parsed is not None and parsed.path == "a.py"
    assert (inp, out) == (1500, 100)
    # openrouter cost carries the platform fee
    assert _cost("claude-haiku-4-5", 1500, 100, "openrouter") > _cost("claude-haiku-4-5", 1500, 100)
    get_settings.cache_clear()
