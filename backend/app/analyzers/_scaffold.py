"""Framework-scaffold detection.

Next.js (and similar frameworks) require files whose near-identical shape is
the framework's contract, not copy-paste debt: per-route metadata layouts,
opengraph/twitter image pairs, loading/error boundaries. Flagging these as the
repo's top debt buries real findings under noise, so analyzers treat them as
scaffolding: duplication ignores their cross-file similarity and style skips
them entirely.
"""
from __future__ import annotations

from pathlib import PurePosixPath

_JS_SUFFIXES = {".tsx", ".ts", ".js", ".jsx"}

# Next.js special files that are duplicated-by-convention across routes.
_SCAFFOLD_STEMS = {
    "opengraph-image",
    "twitter-image",
    "icon",
    "apple-icon",
    "favicon",
    "loading",
    "error",
    "not-found",
    "global-error",
    "default",
    "template",
    "sitemap",
    "robots",
    "manifest",
}

# A layout this small is a metadata stub, not a real component.
_LAYOUT_STUB_MAX_LOC = 40


def is_scaffold(path: str, loc: int) -> bool:
    p = PurePosixPath(path.replace("\\", "/"))
    if p.suffix not in _JS_SUFFIXES:
        return False
    if p.stem in _SCAFFOLD_STEMS:
        return True
    if p.stem == "layout" and loc <= _LAYOUT_STUB_MAX_LOC:
        return True
    if p.stem.endswith(".config") or p.name.startswith("next-env"):
        return True
    return False
