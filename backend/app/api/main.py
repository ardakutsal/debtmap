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

    payload = {"status": "ok" if (db_ok and redis_ok) else "degraded", "version": app.version, "redis": redis_ok, "db": db_ok}
    if payload["status"] != "ok":
        # 503 so platform health checks actually alarm instead of silently passing.
        return JSONResponse(status_code=503, content=payload)
    return payload


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

        # Reuse a fresh completed scan of the same repo+branch instead of
        # re-running — keeps viral traffic from melting the worker.
        if not body.force:
            reuse_cutoff = datetime.utcnow() - timedelta(hours=settings.reuse_window_hours)
            recent = (
                session.query(Analysis)
                .filter(
                    Analysis.owner == owner,
                    Analysis.repo == repo,
                    Analysis.branch == body.branch,
                    Analysis.status == "completed",
                    Analysis.updated_at >= reuse_cutoff,
                )
                .order_by(Analysis.updated_at.desc())
                .first()
            )
            if recent is not None:
                return AnalyzeResponse(
                    analysis_id=recent.id, status="completed", status_url=f"/results/{recent.id}"
                )
            inflight_cutoff = datetime.utcnow() - timedelta(minutes=settings.inflight_window_minutes)
            inflight = (
                session.query(Analysis)
                .filter(
                    Analysis.owner == owner,
                    Analysis.repo == repo,
                    Analysis.branch == body.branch,
                    Analysis.status.in_(["queued", "running"]),
                    Analysis.created_at >= inflight_cutoff,
                )
                .order_by(Analysis.created_at.desc())
                .first()
            )
            if inflight is not None:
                return AnalyzeResponse(
                    analysis_id=inflight.id, status=inflight.status, status_url=f"/results/{inflight.id}"
                )

        queue_depth = (
            session.query(Analysis).filter(Analysis.status.in_(["queued", "running"])).count()
        )
        if queue_depth >= settings.max_queue_depth:
            raise HTTPException(status_code=503, detail="Scanner is busy — try again in a few minutes.")

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
        from app.services.deep_scan import deep_scan_enabled

        payload["deep_scan_enabled"] = deep_scan_enabled()
        return payload
    finally:
        session.close()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.post("/results/{analysis_id}/deep-scan", status_code=202)
def start_deep_scan(analysis_id: str, request: Request):
    from datetime import timedelta as _td

    from app.models.db import DeepScan
    from app.services.deep_scan import deep_scan_enabled, monthly_spend_usd

    if not deep_scan_enabled():
        raise HTTPException(status_code=503, detail="Deep Scan is not enabled on this instance.")

    session = get_session()
    try:
        record = session.get(Analysis, analysis_id)
        if record is None or record.status != "completed":
            raise HTTPException(status_code=404, detail="Completed analysis not found")

        existing = (
            session.query(DeepScan)
            .filter(DeepScan.analysis_id == analysis_id, DeepScan.status.in_(["queued", "running", "completed"]))
            .order_by(DeepScan.created_at.desc())
            .first()
        )
        if existing is not None:
            return {"deep_scan_id": existing.id, "status": existing.status}

        ip = _client_ip(request)
        day_ago = datetime.utcnow() - _td(hours=24)
        used_today = (
            session.query(DeepScan).filter(DeepScan.ip == ip, DeepScan.created_at >= day_ago).count()
        )
        if used_today >= settings.deep_scan_daily_per_ip:
            raise HTTPException(status_code=429, detail="Daily Deep Scan quota reached — try again tomorrow.")
        if monthly_spend_usd(session) >= settings.deep_scan_monthly_cap_usd:
            raise HTTPException(
                status_code=503, detail="Deep Scan monthly budget exhausted on this instance."
            )

        ds = DeepScan(id=uuid.uuid4().hex, analysis_id=analysis_id, ip=ip, status="queued")
        session.add(ds)
        session.commit()
        ds_id = ds.id
    finally:
        session.close()

    from app.services.deep_scan import run_deep_scan

    run_deep_scan.delay(ds_id)
    return {"deep_scan_id": ds_id, "status": "queued"}


@app.get("/results/{analysis_id}/deep-scan")
def get_deep_scan(analysis_id: str):
    from app.models.db import DeepScan

    session = get_session()
    try:
        ds = (
            session.query(DeepScan)
            .filter(DeepScan.analysis_id == analysis_id)
            .order_by(DeepScan.created_at.desc())
            .first()
        )
        if ds is None:
            raise HTTPException(status_code=404, detail="No deep scan for this analysis")
        payload = {
            "deep_scan_id": ds.id,
            "status": ds.status,
            "error": ds.error,
            "cost_usd": ds.cost_usd,
        }
        if ds.status == "completed" and ds.memo_json:
            payload.update(load_result(ds.memo_json) or {})
        return payload
    finally:
        session.close()


@app.get("/repos/{owner}/{repo}/latest")
def latest_for_repo(owner: str, repo: str):
    session = get_session()
    try:
        latest = (
            session.query(Analysis)
            .filter(Analysis.owner == owner, Analysis.repo == repo, Analysis.status == "completed")
            .order_by(Analysis.updated_at.desc())
            .first()
        )
        if latest is None:
            raise HTTPException(status_code=404, detail="No completed analysis for this repository")
        payload = load_result(latest.result_json) or {}
        payload["analysis_id"] = latest.id
        payload["status"] = "completed"
        payload["updated_at"] = latest.updated_at.isoformat()
        return payload
    finally:
        session.close()


@app.get("/leaderboard")
def leaderboard(limit: int = 50):
    """Latest completed analysis per distinct repo, best DebtScore first."""
    limit = max(1, min(int(limit), 100))
    session = get_session()
    try:
        from sqlalchemy import func

        sub = (
            session.query(
                Analysis.owner,
                Analysis.repo,
                func.max(Analysis.updated_at).label("latest"),
            )
            .filter(Analysis.status == "completed", Analysis.debt_score.isnot(None))
            .group_by(Analysis.owner, Analysis.repo)
            .subquery()
        )
        rows = (
            session.query(Analysis)
            .join(
                sub,
                (Analysis.owner == sub.c.owner)
                & (Analysis.repo == sub.c.repo)
                & (Analysis.updated_at == sub.c.latest),
            )
            .filter(Analysis.status == "completed")
            .order_by(Analysis.debt_score.asc())
            .limit(limit * 2)
            .all()
        )
        out = []
        seen: set[tuple[str, str]] = set()
        for r in rows:
            key = (r.owner, r.repo)
            if key in seen:
                continue
            seen.add(key)
            result = load_result(r.result_json) or {}
            files = result.get("files_analyzed", 0)
            if files < 10:  # skip junk/tiny scans
                continue
            out.append(
                {
                    "owner": r.owner,
                    "repo": r.repo,
                    "debt_score": r.debt_score,
                    "grade": r.grade,
                    "ai_generated_pct": r.ai_generated_pct,
                    "files_analyzed": files,
                    "analysis_id": r.id,
                    "updated_at": r.updated_at.isoformat(),
                }
            )
            if len(out) >= limit:
                break
        return {"entries": out}
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
