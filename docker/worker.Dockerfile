FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
ENV PYTHONPATH=/app

# -B embeds the beat scheduler — one container runs worker + schedules
# (purge_tokens hourly, refresh_recent_repos weekly). Keep replicas=1.
CMD ["celery", "-A", "app.services.celery_app.celery_app", "worker", "-B", "--loglevel=info", "--concurrency=2"]
