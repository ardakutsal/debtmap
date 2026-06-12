# Contributing to DebtMap

Thanks for considering a contribution!

## Dev setup

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q                      # must pass before any PR

# frontend
cd frontend
npm install
npm run dev
```

Full stack with one command: `docker compose up --build` (see README).

## Ground rules

1. `pytest -q` (backend) and `npx tsc --noEmit` + `npm run build` (frontend) must pass — CI enforces both.
2. **Every analyzer change goes through calibration.** Run
   `python -m scripts.calibrate` and include the before/after table in your PR.
   The invariant: mature human-written libraries (requests, flask, click, httpx)
   must not grade worse than known vibe-coded repos.
3. New analyzers implement `app.analyzers.base.Analyzer`, are exported from
   `app/analyzers/__init__.py` with a weight, and ship with unit tests.
4. Analyzed code is never executed — AST/regex only. Keep it that way.
5. Provenance detection rules (`app/analysis/provenance.py`) welcome additions:
   new agent trailers/identities need a test case in `tests/test_provenance.py`.

## Reporting issues

Use the issue templates. For security problems see [SECURITY.md](SECURITY.md).
