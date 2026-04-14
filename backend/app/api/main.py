import uuid
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.schemas import AnalyzeRequest, AnalyzeResponse
from app.config import get_settings
from app.models.db import Analysis, get_engine, get_session, load_result
from app.services.badge import render_badge
from app.services.tokens import encrypt


settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="DebtMap API", version="0.1.0")
app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    get_engine()


@app.exception_handler(RateLimitExceeded)
def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})


@app.get("/health")
def health():
    redis_ok = False
    try:
        import redis as _redis

        client = _redis.Redis.from_url(settings.redis_url, socket_connect_timeout=0.5)
        redis_ok = bool(client.ping())
    except Exception:
        redis_ok = False

    db_ok = False
    try:
        session = get_session()
        try:
            session.execute(__import__("sqlalchemy").text("SELECT 1"))
            db_ok = True
        finally:
            session.close()
    except Exception:
        db_ok = False

    return {"status": "ok" if db_ok else "degraded", "version": app.version, "redis": redis_ok, "db": db_ok}


@app.post("/analyze", response_model=AnalyzeResponse, status_code=202)
@limiter.limit(f"{settings.rate_limit_per_hour}/hour")
def analyze(request: Request, body: AnalyzeRequest) -> AnalyzeResponse:
    analysis_id = uuid.uuid4().hex
    session = get_session()
    try:
        url = str(body.repo_url).rstrip("/")
        if "github.com" not in url:
            raise HTTPException(status_code=400, detail="Only github.com repositories are supported")
        from app.analysis.repo_loader import parse_repo_url

        try:
            owner, repo = parse_repo_url(url)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid GitHub URL")

        encrypted = encrypt(body.github_token) if body.github_token else None
        record = Analysis(
            id=analysis_id,
            repo_url=url,
            owner=owner,
            repo=repo,
            branch=body.branch,
            status="queued",
            progress_pct=0,
            current_step="Queued",
            encrypted_token=encrypted,
            token_expires_at=datetime.utcnow() + timedelta(hours=2) if encrypted else None,
        )
        session.add(record)
        session.commit()
    finally:
        session.close()

    try:
        from app.services.tasks import run_analysis

        run_analysis.delay(analysis_id)
    except Exception:
        import threading
        from app.services.tasks import run_analysis as task_fn

        threading.Thread(target=lambda: task_fn.apply(args=[analysis_id]), daemon=True).start()

    return AnalyzeResponse(
        analysis_id=analysis_id,
        status="queued",
        status_url=f"/results/{analysis_id}",
    )


@app.get("/results/{analysis_id}")
def get_result(analysis_id: str):
    session = get_session()
    try:
        record = session.get(Analysis, analysis_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Not found")
        if record.status != "completed":
            return {
                "analysis_id": analysis_id,
                "status": record.status,
                "progress_pct": record.progress_pct,
                "current_step": record.current_step,
                "error": record.error,
            }
        payload = load_result(record.result_json) or {}
        payload["analysis_id"] = analysis_id
        payload["status"] = "completed"
        return payload
    finally:
        session.close()


@app.get("/badge/{owner}/{repo}")
def badge(owner: str, repo: str, response: Response):
    session = get_session()
    try:
        latest = (
            session.query(Analysis)
            .filter(Analysis.owner == owner, Analysis.repo == repo, Analysis.status == "completed")
            .order_by(Analysis.updated_at.desc())
            .first()
        )
        if latest is None:
            svg = render_badge(None, None)
            response.headers["Cache-Control"] = "public, max-age=60"
        else:
            svg = render_badge(latest.debt_score, latest.grade)
            response.headers["Cache-Control"] = "public, max-age=3600"
            response.headers["ETag"] = f'W/"{latest.updated_at.isoformat()}"'
        return Response(content=svg, media_type="image/svg+xml", headers=response.headers)
    finally:
        session.close()
