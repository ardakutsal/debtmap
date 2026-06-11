"""Duplication analyzer.

Finds repeated token sequences within and across files using shingled
MinHash LSH. More cheaply than full AST matching, and robust to variable renames
because we normalize identifiers to the token class.
"""
from __future__ import annotations

import re
from collections import defaultdict

from datasketch import MinHash, MinHashLSH

from app.analyzers.base import AnalyzerResult, FileInput, FileResult, clamp, aggregate_scores
from app.analyzers._ast_utils import strip_comments_and_strings
from app.analyzers._scaffold import is_scaffold


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[^\s\w]")
_KEYWORDS = {
    "if", "else", "elif", "for", "while", "return", "def", "class", "import",
    "from", "try", "except", "finally", "raise", "with", "as", "in", "and",
    "or", "not", "is", "None", "True", "False", "function", "const", "let",
    "var", "new", "this", "export", "default", "interface", "type", "extends",
    "implements", "async", "await",
}
SHINGLE_K = 7
MIN_TOKENS = 25


class DuplicationAnalyzer:
    name = "duplication"

    def analyze(self, files: list[FileInput], context: dict) -> AnalyzerResult:
        file_shingles: dict[str, set[str]] = {}
        minhashes: dict[str, MinHash] = {}

        for f in files:
            stripped = strip_comments_and_strings(f.source, f.language)
            tokens = _normalize_tokens(_TOKEN_RE.findall(stripped))
            if len(tokens) < MIN_TOKENS:
                file_shingles[f.path] = set()
                continue
            shingles = {" ".join(tokens[i : i + SHINGLE_K]) for i in range(len(tokens) - SHINGLE_K + 1)}
            file_shingles[f.path] = shingles
            mh = MinHash(num_perm=128)
            for s in shingles:
                mh.update(s.encode("utf-8"))
            minhashes[f.path] = mh

        lsh = MinHashLSH(threshold=0.55, num_perm=128)
        for path, mh in minhashes.items():
            lsh.insert(path, mh)

        file_results: list[FileResult] = []
        for f in files:
            shingles = file_shingles[f.path]
            if not shingles:
                file_results.append(FileResult(path=f.path, score=0.0, details={"reason": "too small"}))
                continue

            internal_dup = 1.0 - (len(shingles) / max(1, len(shingles)))
            tokens = _normalize_tokens(_TOKEN_RE.findall(strip_comments_and_strings(f.source, f.language)))
            total_ngrams = max(1, len(tokens) - SHINGLE_K + 1)
            dup_internal_ratio = 1.0 - (len(shingles) / total_ngrams)

            cross = 0.0
            neighbors = [n for n in lsh.query(minhashes[f.path]) if n != f.path]
            if neighbors:
                best = 0.0
                for n in neighbors:
                    other = file_shingles.get(n, set())
                    if not other:
                        continue
                    jaccard = len(shingles & other) / max(1, len(shingles | other))
                    best = max(best, jaccard)
                cross = best

            # Framework scaffolding (Next.js layouts, og/twitter image pairs)
            # is similar by convention — its cross-file similarity is not debt.
            scaffold = is_scaffold(f.path, f.loc)
            effective_cross = 0.0 if scaffold else cross

            # Internal n-gram overlap is a weak signal (idiomatic repetition
            # inflates it in every codebase); cross-file similarity is the
            # strong one.
            score = clamp(45 * dup_internal_ratio + 80 * effective_cross)
            details = {
                "internal_dup_ratio": round(dup_internal_ratio, 3),
                "max_cross_jaccard": round(cross, 3),
                "num_duplicate_peers": len(neighbors),
            }
            if scaffold:
                details["scaffold"] = True
            file_results.append(FileResult(path=f.path, score=score, details=details))

        repo_score = aggregate_scores(file_results, files)
        return AnalyzerResult(name=self.name, repo_score=repo_score, file_results=file_results)


def _normalize_tokens(tokens: list[str]) -> list[str]:
    out = []
    for t in tokens:
        if not t:
            continue
        if t.isidentifier() and t not in _KEYWORDS:
            out.append("ID")
        elif t.isdigit():
            out.append("N")
        else:
            out.append(t)
    return out

