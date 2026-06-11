"""AI provenance from git metadata.

Code style cannot reliably identify modern AI-written code (typed, linted,
idiomatic output defeats every stylistic tell). Commit metadata can: AI coding
agents leave explicit fingerprints — Co-Authored-By trailers, "Generated with"
body lines, and bot author/committer identities. We scan the cloned history
(bounded by clone depth) and report evidence, never a style guess.

Detection scope is split in three, because they mean different things:
- AI agents      → counted toward ai_commit_pct
- automation bots (dependabot, renovate, CI) → counted separately
- velocity        → reported as a signal, never as a percentage
"""
from __future__ import annotations

import re
from pathlib import Path

MAX_COMMITS = 1000

# Inside an explicit Co-Authored-By trailer or a "Generated with/by" line,
# loose keywords are safe — the line itself declares non-human authorship.
_TRAILER_AGENTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"claude", re.I), "Claude Code"),
    (re.compile(r"copilot", re.I), "GitHub Copilot"),
    (re.compile(r"cursor", re.I), "Cursor"),
    (re.compile(r"devin", re.I), "Devin"),
    (re.compile(r"aider", re.I), "Aider"),
    (re.compile(r"\bcline\b", re.I), "Cline"),
    (re.compile(r"roo[ -]?code", re.I), "Roo Code"),
    (re.compile(r"windsurf|codeium", re.I), "Windsurf"),
    (re.compile(r"chatgpt|openai|\bcodex\b", re.I), "OpenAI Codex"),
    (re.compile(r"openhands", re.I), "OpenHands"),
    (re.compile(r"gemini|\bjules\b", re.I), "Gemini"),
    (re.compile(r"amazon ?q|codewhisperer", re.I), "Amazon Q"),
    (re.compile(r"augment", re.I), "Augment"),
    (re.compile(r"\bsweep\b", re.I), "Sweep"),
    (re.compile(r"qodo", re.I), "Qodo"),
    (re.compile(r"continue\.dev", re.I), "Continue"),
    (re.compile(r"zencoder", re.I), "Zencoder"),
]

# Author/committer identity must match a *specific* marker — a human named
# "Augusto" must never match "augment", so no loose keywords here.
_IDENTITY_AGENTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"noreply@anthropic\.com|claude\[bot\]|claude-code", re.I), "Claude Code"),
    (re.compile(r"copilot-swe-agent|copilot\[bot\]|copilot@github", re.I), "GitHub Copilot"),
    (re.compile(r"cursoragent|cursor agent|cursor\[bot\]|@cursor\.(sh|com)", re.I), "Cursor"),
    (re.compile(r"devin-ai|devin\[bot\]|@devin\.ai", re.I), "Devin"),
    (re.compile(r"aider \(|aider\[bot\]|@aider\.chat", re.I), "Aider"),
    (re.compile(r"openhands", re.I), "OpenHands"),
    (re.compile(r"sweep-ai|sweep\[bot\]", re.I), "Sweep"),
    (re.compile(r"google-labs-jules|jules\[bot\]", re.I), "Gemini"),
    (re.compile(r"codegen(-sh)?\[bot\]", re.I), "Codegen"),
    (re.compile(r"factory-droid|droid\[bot\]", re.I), "Factory Droid"),
]

_AUTOMATION_RE = re.compile(
    r"dependabot|renovate|github-actions|pre-commit-ci|semantic-release|"
    r"release-please|mergify|snyk|imgbot|allcontributors|greenkeeper|"
    r"whitesource|step-security|crowdin",
    re.I,
)

_TRAILER_RE = re.compile(r"^\s*co-authored-by:\s*(.+)$", re.I | re.M)
_GENERATED_RE = re.compile(r"generated (?:with|by)[: ]+\[?([^\]\n(]+)", re.I)

VELOCITY_VERY_HIGH = 20  # commits in any sliding 24h window
VELOCITY_HIGH = 10


def analyze_provenance(repo_dir: str) -> dict | None:
    """Scan the cloned repo's commit history for AI-agent evidence.

    Returns None when the directory is not a usable git repo (e.g. tests that
    analyze a bare file list) — callers treat that as "no provenance data".
    """
    try:
        from git import Repo

        repo = Repo(repo_dir)
        commits = list(repo.iter_commits(max_count=MAX_COMMITS))
    except Exception:
        return None
    if not commits:
        return None

    agent_counts: dict[str, int] = {}
    ai_commits = 0
    automation_commits = 0
    human_authors: set[str] = set()
    timestamps: list[int] = []

    for c in commits:
        timestamps.append(int(c.committed_date))
        message = c.message if isinstance(c.message, str) else c.message.decode("utf-8", "replace")
        author_id = f"{c.author.name or ''} <{c.author.email or ''}>"
        committer_id = f"{c.committer.name or ''} <{c.committer.email or ''}>"

        agents = _agents_in_commit(message, author_id, committer_id)
        is_automation = bool(_AUTOMATION_RE.search(author_id) or _AUTOMATION_RE.search(committer_id))

        if agents:
            ai_commits += 1
            for a in agents:
                agent_counts[a] = agent_counts.get(a, 0) + 1
        elif is_automation:
            automation_commits += 1
        else:
            human_authors.add(author_id)

    n = len(commits)
    ai_pct = round(ai_commits / n * 100, 1)
    window_days = round((max(timestamps) - min(timestamps)) / 86400, 1) if n > 1 else 0.0
    peak_24h = _peak_in_window(sorted(timestamps), 86400)
    active_days = len({ts // 86400 for ts in timestamps})
    velocity_flag = (
        "very_high" if peak_24h >= VELOCITY_VERY_HIGH
        else "high" if peak_24h >= VELOCITY_HIGH
        else "normal"
    )

    agents_sorted = sorted(agent_counts.items(), key=lambda kv: -kv[1])
    likely_ai = False
    if ai_pct > 0:
        confidence = "high"
        top = ", ".join(name for name, _ in agents_sorted[:3])
        assessment = f"{ai_pct}% of sampled commits carry AI-agent signatures ({top})."
    elif velocity_flag == "very_high" and window_days <= 14 and n >= 20:
        confidence = "low"
        likely_ai = True
        assessment = (
            f"No explicit AI signatures, but {peak_24h} commits landed within a single day "
            f"on a {window_days}-day history — a velocity consistent with heavy AI assistance."
        )
    else:
        confidence = "medium"
        assessment = "No AI-agent signatures found in sampled commits."

    return {
        "commits_sampled": n,
        "history_truncated": Path(repo_dir, ".git", "shallow").exists(),
        "window_days": window_days,
        "ai_commits": ai_commits,
        "ai_commit_pct": ai_pct,
        "automation_commits": automation_commits,
        "agents": [{"name": name, "commits": count} for name, count in agents_sorted],
        "human_authors": len(human_authors),
        "velocity": {
            "peak_commits_24h": peak_24h,
            "active_days": active_days,
            "commits_per_active_day": round(n / max(1, active_days), 1),
            "flag": velocity_flag,
        },
        "likely_ai_assisted": likely_ai or ai_pct > 0,
        "confidence": confidence,
        "assessment": assessment,
    }


def _agents_in_commit(message: str, author_id: str, committer_id: str) -> set[str]:
    agents: set[str] = set()
    for m in _TRAILER_RE.finditer(message):
        agents |= _match_agents(m.group(1), _TRAILER_AGENTS)
    for m in _GENERATED_RE.finditer(message):
        agents |= _match_agents(m.group(1), _TRAILER_AGENTS)
    for identity in (author_id, committer_id):
        agents |= _match_agents(identity, _IDENTITY_AGENTS)
    return agents


def _match_agents(text: str, rules: list[tuple[re.Pattern, str]]) -> set[str]:
    return {name for pattern, name in rules if pattern.search(text)}


def _peak_in_window(sorted_ts: list[int], window_seconds: int) -> int:
    best = 0
    left = 0
    for right in range(len(sorted_ts)):
        while sorted_ts[right] - sorted_ts[left] > window_seconds:
            left += 1
        best = max(best, right - left + 1)
    return best
