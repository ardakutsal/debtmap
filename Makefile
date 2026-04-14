.PHONY: install test dev worker api frontend fmt

install:
	cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

test:
	cd backend && .venv/bin/python -m pytest -q

api:
	cd backend && .venv/bin/uvicorn app.api.main:app --reload

worker:
	cd backend && .venv/bin/celery -A app.services.celery_app.celery_app worker --loglevel=info

frontend:
	cd frontend && npm run dev

up:
	docker compose up --build

down:
	docker compose down -v
