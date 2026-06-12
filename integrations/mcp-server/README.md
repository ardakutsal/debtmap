# DebtMap MCP Server

Give your coding agent (Claude Code, Cursor, anything MCP-capable) the ability
to scan repositories for technical debt and AI provenance — including the code
it just wrote.

## Tools

| Tool | What it does |
|---|---|
| `scan_repo(repo)` | Scan a public GitHub repo (~30-60s, cached for recent scans) |
| `get_report(repo)` | Fetch the latest report without re-scanning |
| `compare_repos(a, b)` | Side-by-side debt comparison with a verdict |

## Install (Claude Code)

```bash
claude mcp add debtmap -- uv run /path/to/debtmap/integrations/mcp-server/debtmap_mcp.py
```

Requires [uv](https://docs.astral.sh/uv/) — dependencies (`mcp`, `httpx`) are
declared inline and resolved automatically.

## Self-hosted instance

```bash
export DEBTMAP_API_URL=http://localhost:8000
export DEBTMAP_FRONTEND_URL=http://localhost:3000
```

## Example agent prompts

- "Scan github.com/owner/repo with debtmap and summarize the action plan."
- "Compare my repo against upstream with debtmap — who carries more debt?"
- "Before committing, scan this repo and tell me if error handling got worse."
