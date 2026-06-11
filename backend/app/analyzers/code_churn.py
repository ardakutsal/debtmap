"""Code Churn analyzer.

Uses GitHub Commits API. For each file we check commits touching it in the first
14 days after its first appearance. Files with 5+ commits in that window indicate
"vibe-fixed" hotspots.

Rate limit strategy:
- Always watch `X-RateLimit-Remaining` and bail out (skipped=True) once it drops
  below a safety margin, so an in-progress scan never exhausts the quota.
- Respect 403 + "rate limit" text and 429 explicitly.
- Hard cap on per-commit detail fetches so a tiny token budget still returns a
  useful signal rather than erroring out.
- When skipped we set score=50 (neutral) and the aggregator drops our weight,
  so the repo-level DebtScore stays well-calibrated.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

import httpx

from app.analyzers.base import AnalyzerResult, FileInput, FileResult, clamp, aggregate_scores


MIN_REMAINING = 5          # stop calling once quota is nearly gone
MAX_COMMIT_DETAILS = 80    # hard cap: per-commit file fetches
LIST_PAGES = 5             # up to 500 recent commits


class CodeChurnAnalyzer:
    name = "code_churn"

    def analyze(self, files: list[FileInput], context: dict) -> AnalyzerResult:
        owner = context.get("owner")
        repo = context.get("repo")
        token = context.get("github_token")
        branch = context.get("branch", "main")
        if not owner or not repo:
            return _skipped("no repo metadata")

        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"https://api.github.com/repos/{owner}/{repo}/commits"

        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            commits, status = _list_commits(client, url, branch, headers)
            if status != "ok":
                return _skipped(status)
            if not commits:
                return _skipped("no commits returned")

            touches: dict[str, list[datetime]] = defaultdict(list)
            detail_budget = min(MAX_COMMIT_DETAILS, len(commits))
            remaining_after = None
            for c in commits[:detail_budget]:
                sha = c.get("sha")
                if not sha:
                    continue
                try:
                    resp = client.get(f"{url}/{sha}", headers=headers)
                except httpx.HTTPError:
                    continue
                rl = _remaining(resp)
                if rl is not None:
                    remaining_after = rl
                    if rl < MIN_REMAINING:
                        break
                if resp.status_code == 403 and "rate limit" in resp.text.lower():
                    break
                if resp.status_code == 429 or resp.status_code >= 500:
                    break
                if resp.status_code >= 400:
                    continue
                payload = resp.json()
                try:
                    when = datetime.fromisoformat(
                        payload["commit"]["author"]["date"].replace("Z", "+00:00")
                    )
                except (KeyError, ValueError):
                    continue
                for f in payload.get("files", []):
                    touches[f.get("filename", "")].append(when)

        if not touches:
            return _skipped("no commit details retrieved")

        file_results: list[FileResult] = []
        for f in files:
            dates = sorted(touches.get(f.path, []))
            if len(dates) < 2:
                file_results.append(FileResult(path=f.path, score=10.0, details={"commits_seen": len(dates)}))
                continue
            first = dates[0]
            window_end = first + timedelta(days=14)
            in_window = sum(1 for d in dates if d <= window_end)
            score = clamp((in_window - 4) * 18) if in_window >= 5 else clamp(in_window * 5)
            file_results.append(
                FileResult(
                    path=f.path,
                    score=score,
                    details={
                        "commits_in_14d_window": in_window,
                        "total_commits_seen": len(dates),
                    },
                )
            )
        notes = []
        if remaining_after is not None:
            notes.append(f"github rate-limit remaining: {remaining_after}")
        return AnalyzerResult(
            name=self.name,
            repo_score=aggregate_scores(file_results, files),
            file_results=file_results,
            notes=notes,
        )


def _list_commits(client: httpx.Client, url: str, branch: str, headers: dict) -> tuple[list, str]:
    commits: list = []
    for page in range(1, LIST_PAGES + 1):
        try:
            resp = client.get(url, headers=headers, params={"sha": branch, "per_page": 100, "page": page})
        except httpx.HTTPError as exc:
            return commits, f"github error: {exc}"
        rl = _remaining(resp)
        if resp.status_code == 403 and ("rate limit" in resp.text.lower() or (rl is not None and rl == 0)):
            return commits, "github rate limit"
        if resp.status_code == 429:
            return commits, "github rate limit (429)"
        if resp.status_code == 404:
            return commits, "repo not found"
        if resp.status_code >= 400:
            return commits, f"github status {resp.status_code}"
        data = resp.json()
        if not data:
            break
        # Guard: if GitHub returned an unexpected shape (e.g. a dict error body
        # slipped past the status check), skip rather than crash downstream.
        if not isinstance(data, list):
            return commits, f"github unexpected response shape"
        commits.extend(data)
        if len(data) < 100:
            break
        if rl is not None and rl < MIN_REMAINING:
            break
    return commits, "ok"


def _remaining(resp: httpx.Response) -> int | None:
    raw = resp.headers.get("X-RateLimit-Remaining")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _skipped(reason: str) -> AnalyzerResult:
    return AnalyzerResult(name="code_churn", repo_score=50.0, skipped=True, notes=[reason])

