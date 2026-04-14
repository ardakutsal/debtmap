from __future__ import annotations

import traceback
from datetime import datetime, timedelta

from app.analysis.runner import analyze_repo
from app.models.db import Analysis, dump_result, get_session
from app.services.celery_app import celery_app
from app.services.tokens import decrypt


def _short_txn(analysis_id: str, mutator):
    """Run a tiny write transaction. Short-lived sessions keep SQLite's single
    writer lock free during long-running work (clone, GitHub API calls)."""
    session = get_session()
    try:
        record = session.get(Analysis, analysis_id)
        if record is None:
            return
        mutator(record)
        session.commit()
    finally:
        session.close()


def _load_fields(analysis_id: str) -> tuple[str, str, str | None]:
    session = get_session()
    try:
        record = session.get(Analysis, analysis_id)
        if record is None:
            raise RuntimeError(f"analysis {analysis_id} not found")
        return record.repo_url, record.branch, record.encrypted_token
    finally:
        session.close()


@celery_app.task(name="debtmap.run_analysis", bind=True)
def run_analysis(self, analysis_id: str) -> None:
    def _mark_running(r: Analysis) -> None:
        r.status = "running"
        r.progress_pct = 1
        r.current_step = "Starting"

    _short_txn(analysis_id, _mark_running)

    repo_url, branch, encrypted_token = _load_fields(analysis_id)
    token = decrypt(encrypted_token)

    def progress(pct: int, step: str):
        def _update(r: Analysis) -> None:
            r.progress_pct = pct
            r.current_step = step
        _short_txn(analysis_id, _update)

    try:
        result = analyze_repo(repo_url, branch=branch, github_token=token, progress=progress)

        def _mark_completed(r: Analysis) -> None:
            r.debt_score = result.get("debt_score")
            r.grade = result.get("grade")
            r.ai_generated_pct = result.get("ai_generated_pct")
            r.result_json = dump_result(result)
            r.status = "completed"
            r.progress_pct = 100
            r.current_step = "Done"
            r.token_expires_at = datetime.utcnow() + timedelta(hours=1)
        _short_txn(analysis_id, _mark_completed)
    except Exception as exc:
        tb = traceback.format_exc()

        def _mark_failed(r: Analysis) -> None:
            r.status = "failed"
            r.error = f"{exc}\n{tb}"
        _short_txn(analysis_id, _mark_failed)
        raise


@celery_app.task(name="debtmap.purge_tokens")
def purge_expired_tokens() -> int:
    session = get_session()
    try:
        now = datetime.utcnow()
        q = session.query(Analysis).filter(Analysis.token_expires_at < now, Analysis.encrypted_token.isnot(None))
        count = 0
        for record in q.all():
            record.encrypted_token = None
            count += 1
        session.commit()
        return count
    finally:
        session.close()
