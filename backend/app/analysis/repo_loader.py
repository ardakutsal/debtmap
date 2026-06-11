from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.analyzers.base import FileInput
from app.analyzers._ast_utils import line_count
from app.config import get_settings


@dataclass
class LoadedRepo:
    owner: str
    repo: str
    files: list[FileInput]
    total_files_considered: int
    skipped_too_large: int


def parse_repo_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) < 2:
        raise ValueError(f"Not a valid GitHub repo URL: {url}")
    return parts[0], parts[1]


class RepoCloneError(Exception):
    """Clone failed for a reason worth showing to the user."""


def clone_repo(url: str, branch: str, token: str | None, dest: str) -> str:
    """Clone the repo at the given branch. If that branch does not exist,
    fall back to the remote's default branch. Returns the branch actually used."""
    from git import Repo
    from git.exc import GitCommandError

    clone_url = url
    if token:
        parsed = urlparse(url)
        netloc = f"{token}@{parsed.netloc}"
        clone_url = parsed._replace(netloc=netloc).geturl()

    # Depth must cover enough history for provenance sampling, not just HEAD.
    depth = get_settings().clone_depth
    try:
        Repo.clone_from(clone_url, dest, depth=depth, branch=branch, multi_options=["--no-tags"])
        return branch
    except GitCommandError as exc:
        msg = str(exc).lower()
        if "remote branch" in msg and "not found" in msg:
            import shutil as _shutil
            _shutil.rmtree(dest, ignore_errors=True)
            try:
                repo = Repo.clone_from(clone_url, dest, depth=depth, multi_options=["--no-tags"])
                return repo.active_branch.name
            except GitCommandError as exc2:
                raise _friendly_clone_error(exc2) from exc2
        raise _friendly_clone_error(exc) from exc


def _friendly_clone_error(exc) -> RepoCloneError:
    msg = str(exc).lower()
    if "could not read username" in msg or "authentication failed" in msg or "authorization" in msg:
        return RepoCloneError(
            "Repository not found or not publicly accessible. "
            "If this is a private repo, provide a GitHub token when submitting."
        )
    if "not found" in msg or "does not exist" in msg or "repository not found" in msg:
        return RepoCloneError("Repository not found.")
    if "timed out" in msg or "timeout" in msg:
        return RepoCloneError("Clone timed out — repository may be too large or network unavailable.")
    return RepoCloneError(f"Clone failed: {str(exc).splitlines()[0][:200]}")


def load_files_from_dir(root: str) -> LoadedRepo:
    settings = get_settings()
    root_path = Path(root)
    files: list[FileInput] = []
    total = 0
    skipped_large = 0
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "node_modules", "dist", "build", ".next", "__pycache__", "venv", ".venv"} for part in path.parts):
            continue
        if path.suffix not in settings.supported_extensions:
            continue
        if path.name.endswith(".d.ts"):
            continue
        total += 1
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > settings.max_file_bytes:
            skipped_large += 1
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = str(path.relative_to(root_path))
        language = _language_for(path.suffix)
        files.append(
            FileInput(
                path=rel,
                language=language,
                source=source,
                loc=line_count(source),
            )
        )
        if len(files) >= settings.max_files_per_repo:
            break
    return LoadedRepo(owner="", repo="", files=files, total_files_considered=total, skipped_too_large=skipped_large)


def _language_for(suffix: str) -> str:
    if suffix == ".py":
        return "python"
    if suffix in (".ts", ".tsx"):
        return "tsx" if suffix == ".tsx" else "ts"
    if suffix in (".js", ".jsx"):
        return "jsx" if suffix == ".jsx" else "js"
    return "text"


def cleanup(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def temp_clone_dir() -> str:
    return tempfile.mkdtemp(prefix="debtmap_")
