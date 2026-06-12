# DebtMap

[![CI](https://github.com/ardakutsal/debtmap/actions/workflows/ci.yml/badge.svg)](https://github.com/ardakutsal/debtmap/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

> Technical-debt scanner for AI-generated and "vibe-coded" repositories.

**Try it live: [frontend-production-b171.up.railway.app](https://frontend-production-b171.up.railway.app)** — paste a GitHub URL, get a report in ~30s. [Leaderboard](https://frontend-production-b171.up.railway.app/leaderboard) · [Compare two repos](https://frontend-production-b171.up.railway.app/compare) · [Example report](https://frontend-production-b171.up.railway.app/results/b986c4f382e044c38853aacb61bee754)

DebtMap takes a GitHub URL, runs eight analyzers against the code, and returns:

- **DebtScore (0–100)** and **A–F grade** — one number, LOC-weighted across all analyzers
- **AI provenance report** — % of sampled commits carrying AI-agent signatures (`Co-Authored-By` trailers, bot author identities, "Generated with" lines), plus a commit-velocity signal. Evidence from git metadata — never a code-style guess.
- **File treemap** — box size = LOC, color = debt score
- **Prioritized action plan** — category, effort estimate, affected files
- **Embeddable SVG badge** — shields.io style, cached 1 hour

## Quick start (Docker)

```bash
git clone https://github.com/your-org/debtmap.git
cd debtmap
cp .env.example .env
docker compose up --build
```

Open `http://localhost:3000`. Paste a GitHub URL. Wait ~30-60s.

From a cold `docker compose up` on a clean machine the stack is ready in under three minutes.

## Quick start (local dev)

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.api.main:app --reload        # in one terminal
celery -A app.services.celery_app.celery_app worker --loglevel=info   # in another
redis-server                              # or via Docker
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

CLI one-shot (no API / worker required — useful for CI):
```bash
cd backend
python -m app.analysis.runner https://github.com/facebook/react --branch main
```

## Architecture

```
┌──────────────┐    POST /analyze     ┌──────────┐    enqueue     ┌─────────┐
│  Next.js UI  │ ───────────────────► │ FastAPI  │ ─────────────► │ Celery  │
│  (landing +  │ ◄─────── GET /results│ (SQLite) │                │ worker  │
│  dashboard)  │                      └──────────┘ ◄── progress   └─────────┘
└──────────────┘                                                       │
                                                                       ▼
                                                             ┌────────────────┐
                                                             │ 8 AST-only     │
                                                             │ analyzers +    │
                                                             │ GitHub Commits │
                                                             └────────────────┘
```

| Service  | Role                                   |
| -------- | -------------------------------------- |
| api      | FastAPI, rate-limited, token-encrypted |
| worker   | Celery worker, clones + analyzes repo  |
| redis    | broker + results backend               |
| frontend | Next.js 14, App Router, dark theme     |

## The eight analyzers

| # | Analyzer                 | Weight | What it catches                                                               |
| - | ------------------------ | ------ | ----------------------------------------------------------------------------- |
| 1 | Error Handling           | 25%    | `except:`, broad Exception, silent pass, empty JS catch, unmanaged resources  |
| 2 | Duplication              | 20%    | MinHash-LSH across shingled, identifier-normalized ASTs                       |
| 3 | Architectural Contracts  | 20%    | God functions/classes, multi-thousand-line modules, `any` density, weak typing |
| 4 | Test Coverage Proxy      | 10%    | Test LOC vs. production LOC — untested code can't be refactored safely        |
| 5 | Comment Patterns         | 10%    | Generic boilerplate comments, comment/code ratio, low-entropy wording         |
| 6 | Dependency Graph         | 10%    | Import cycles, fan-out > 20, direct env access, global declarations           |
| 7 | Code Churn               | 5%     | 5+ commits in the first 14 days of a file's life (requires GitHub API)        |
| 8 | Style Homogeneity        | 0% (informational) | Uniform fn lengths, identifier-length entropy — reported, not scored |

Weights and grade bands are calibrated against a corpus of known repos (mature
human-written libraries vs. known vibe-coded projects) via `scripts/calibrate.py`.
Style homogeneity is informational because calibration showed curated human code
measures *more* uniform than AI output — "uniformity = debt" failed the data.
Per-analyzer repo scores blend the LOC-weighted mean with the worst decile, so
five dangerous files can't hide behind a hundred clean ones.

Each analyzer returns per-file scores `[0, 100]`. The repo score is
`0.5 * weighted_avg + 0.5 * sigmoid(weighted_avg)` — a gentle compression
that prevents tail clumping while preserving ordering.

Framework scaffolding (Next.js metadata layouts, `opengraph-image`/`twitter-image`
pairs, loading/error boundaries) is detected and excluded from cross-file
duplication and style scoring — similar-by-convention files are not debt.

### AI provenance

`ai_generated_pct` and the `provenance` block come from commit history, not code
style: `Co-Authored-By` trailers and bot identities for Claude Code, Copilot,
Cursor, Devin, Aider, Cline, Windsurf and others; automation bots (dependabot,
renovate, CI) are counted separately; commit velocity is reported as a signal
with explicit confidence, never silently folded into a percentage.

## API

### `POST /analyze`
```json
{ "repo_url": "https://github.com/owner/repo", "branch": "main", "github_token": "optional" }
```
→ `202 { "analysis_id": "...", "status": "queued", "status_url": "/results/..." }`

### `GET /results/{id}`
While running:
```json
{ "status": "running", "progress_pct": 45, "current_step": "Running duplication" }
```
When complete: full payload with `debt_score`, `grade`, `ai_generated_pct`,
`analyzers` (per-category breakdown + per-file scores), `file_summary`, `action_plan`.

### `GET /badge/{owner}/{repo}`
Returns an SVG badge, cached 1 hour, ETag-enabled.

### `GET /repos/{owner}/{repo}/latest` · `GET /leaderboard`
Latest completed report for a repo; latest scan per distinct repo, best score first.

### `POST /results/{id}/deep-scan` · `GET /results/{id}/deep-scan`
LLM architect review (Claude Haiku per-file + Sonnet synthesis). Only active when
the instance sets `ANTHROPIC_API_KEY`; per-IP daily quota and a monthly USD cap
are enforced (`DEEP_SCAN_*` settings).

## Integrations

- **MCP server** — let your coding agent scan repos (including its own output):
  [`integrations/mcp-server`](./integrations/mcp-server). Tools: `scan_repo`,
  `get_report`, `compare_repos`.
- **Compare** — `/compare?a=owner/repo&b=owner/repo` on the web UI.
- **Weekly refresh** — repos scanned in the last 90 days are re-scanned weekly
  so badges and the leaderboard stay current.

## Safety & limits

- Analyzed code is **never executed** — only AST-parsed.
- **Max 500 files / repo, max 500 KB / file.** Supported: `.py`, `.ts`, `.tsx`, `.js`, `.jsx`.
- **Rate limit:** 10 analyses / IP / hour via slowapi.
- **Tokens:** Fernet-encrypted at rest; the encrypted payload is purged 1 hour after completion by the `debtmap.purge_tokens` task.
- **GitHub rate limits:** Without a token, `code_churn` gracefully skips on 403 and the analyzer is simply dropped from the weighted score.

## Database migrations

MVP uses SQLAlchemy `Base.metadata.create_all()` at startup — the schema is a
single table (`analyses`) and is idempotent to create. If you add a column,
either drop the SQLite file or introduce Alembic (`pip install alembic && alembic init migrations`)
at that point; adding it up-front is unnecessary complexity for a one-table MVP.

## Contributing

1. `make test` (or `cd backend && pytest -q`) must pass.
2. Add an analyzer: implement `app.analyzers.base.Analyzer`, export from `app/analyzers/__init__.py`, add a weight in `ANALYZER_WEIGHTS`.
3. Each new analyzer ships with a unit test.

## License

MIT — see [LICENSE](./LICENSE).
