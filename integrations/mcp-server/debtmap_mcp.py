# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2", "httpx>=0.27"]
# ///
"""DebtMap MCP server — let any agent scan repos for technical debt.

A thin client over the public DebtMap API. Run locally:

    uvx --from mcp --with httpx python debtmap_mcp.py        # or:
    uv run debtmap_mcp.py

Add to Claude Code:

    claude mcp add debtmap -- uv run /path/to/debtmap_mcp.py

Point at a self-hosted instance with DEBTMAP_API_URL.
"""
from __future__ import annotations

import json
import os
import time

import httpx
from mcp.server.fastmcp import FastMCP

API = os.environ.get("DEBTMAP_API_URL", "https://api-production-99db.up.railway.app").rstrip("/")
FRONTEND = os.environ.get(
    "DEBTMAP_FRONTEND_URL", "https://frontend-production-b171.up.railway.app"
).rstrip("/")

mcp = FastMCP("debtmap")


def _summarize(result: dict) -> dict:
    """Compact, agent-friendly view of a full analysis payload."""
    provenance = result.get("provenance") or {}
    return {
        "repo": f"{result.get('owner')}/{result.get('repo')}",
        "debt_score": result.get("debt_score"),
        "grade": result.get("grade"),
        "files_analyzed": result.get("files_analyzed"),
        "ai_signed_commit_pct": result.get("ai_generated_pct"),
        "ai_agents_detected": [a["name"] for a in provenance.get("agents", [])],
        "provenance_assessment": provenance.get("assessment"),
        "analyzer_scores": {
            name: v.get("score")
            for name, v in (result.get("analyzers") or {}).items()
            if isinstance(v, dict) and not v.get("skipped")
        },
        "action_plan": [
            {"category": a.get("category"), "title": a.get("title"), "score": a.get("score")}
            for a in (result.get("action_plan") or [])
        ],
        "worst_files": [
            {"path": f.get("path"), "score": f.get("score"), "loc": f.get("loc")}
            for f in (result.get("file_summary") or [])[:10]
        ],
        "report_url": f"{FRONTEND}/results/{result.get('analysis_id')}",
    }


def _run_scan(repo: str, timeout_seconds: int = 180) -> dict:
    url = repo if repo.startswith("http") else f"https://github.com/{repo}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(f"{API}/analyze", json={"repo_url": url, "branch": "main"})
        resp.raise_for_status()
        analysis_id = resp.json()["analysis_id"]
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            r = client.get(f"{API}/results/{analysis_id}")
            data = r.json()
            if data.get("status") == "completed":
                return _summarize(data)
            if data.get("status") == "failed":
                raise RuntimeError(data.get("error") or "analysis failed")
            time.sleep(4)
    raise TimeoutError("analysis did not complete in time")


@mcp.tool()
def scan_repo(repo: str) -> str:
    """Scan a public GitHub repository for technical debt and AI provenance.

    Args:
        repo: "owner/repo" or a full GitHub URL. Recently scanned repos return
            instantly from cache; fresh scans take ~30-60s.

    Returns a JSON summary: DebtScore (0-100, lower is better), grade,
    git-evidence AI provenance, per-analyzer scores, action plan, worst files,
    and a shareable report URL.
    """
    return json.dumps(_run_scan(repo), ensure_ascii=False, indent=1)


@mcp.tool()
def get_report(repo: str) -> str:
    """Fetch the latest completed DebtMap report for a repo without triggering
    a new scan.

    Args:
        repo: "owner/repo".
    """
    owner, _, name = repo.replace("https://github.com/", "").strip("/").partition("/")
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{API}/repos/{owner}/{name}/latest")
        if r.status_code == 404:
            return json.dumps({"error": "no completed scan for this repo — use scan_repo first"})
        r.raise_for_status()
        return json.dumps(_summarize(r.json()), ensure_ascii=False, indent=1)


@mcp.tool()
def compare_repos(repo_a: str, repo_b: str) -> str:
    """Scan two repositories and compare their debt profiles side by side.

    Args:
        repo_a: "owner/repo" or GitHub URL.
        repo_b: "owner/repo" or GitHub URL.
    """
    a = _run_scan(repo_a)
    b = _run_scan(repo_b)
    return json.dumps(
        {
            "a": a,
            "b": b,
            "verdict": {
                "lower_debt": a["repo"] if (a["debt_score"] or 999) <= (b["debt_score"] or 999) else b["repo"],
                "score_gap": round(abs((a["debt_score"] or 0) - (b["debt_score"] or 0)), 1),
            },
            "compare_url": f"{FRONTEND}/compare?a={a['repo']}&b={b['repo']}",
        },
        ensure_ascii=False,
        indent=1,
    )


if __name__ == "__main__":
    mcp.run()
