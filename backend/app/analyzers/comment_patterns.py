"""Comment Patterns analyzer.

AI frequently produces generic, low-entropy comments ("This function handles X",
"Initialize the variable", etc.). We measure:
- comment/code ratio (penalize > 40%)
- Shannon entropy of word distribution across comments
- fraction of comments matching generic AI templates
"""
from __future__ import annotations

import math
import re
from collections import Counter

from app.analyzers.base import AnalyzerResult, FileInput, FileResult, clamp, aggregate_scores
from app.analyzers._ast_utils import comment_lines, line_count


_GENERIC_PATTERNS = [
    re.compile(r"^\s*#?\s*this\s+(function|method|class|variable|constant)\b", re.I),
    re.compile(r"^\s*(//|#)?\s*initialize\s+the\s+\w+", re.I),
    re.compile(r"^\s*(//|#)?\s*returns?\s+the\s+\w+$", re.I),
    re.compile(r"^\s*(//|#)?\s*set\s+up\s+\w+", re.I),
    re.compile(r"^\s*(//|#)?\s*handles?\s+the\s+\w+", re.I),
    re.compile(r"^\s*(//|#)?\s*main\s+entry\s+point", re.I),
    re.compile(r"^\s*(//|#)?\s*loop\s+through", re.I),
    re.compile(r"^\s*(//|#)?\s*create\s+(a|an|the)\s+\w+", re.I),
    re.compile(r"^\s*(//|#)?\s*check\s+if", re.I),
]

_COMMENT_LINE_RE = re.compile(r"^\s*(#|//|/\*|\*|\*/)")
_WORD_RE = re.compile(r"[A-Za-z]{3,}")


class CommentPatternsAnalyzer:
    name = "comment_patterns"

    def analyze(self, files: list[FileInput], context: dict) -> AnalyzerResult:
        file_results: list[FileResult] = []
        for f in files:
            total_lines = max(1, line_count(f.source))
            c_lines = comment_lines(f.source, f.language)
            ratio = c_lines / total_lines

            comment_texts = self._extract_comments(f.source, f.language)
            generic_hits = sum(1 for c in comment_texts if _is_generic(c))
            generic_rate = generic_hits / max(1, len(comment_texts))
            entropy = _word_entropy(comment_texts)

            ratio_score = _penalize_ratio(ratio)
            generic_score = generic_rate * 100
            entropy_score = clamp(100 - (entropy / 4.5) * 100)

            score = clamp(0.4 * ratio_score + 0.35 * generic_score + 0.25 * entropy_score)
            file_results.append(
                FileResult(
                    path=f.path,
                    score=score,
                    details={
                        "comment_ratio": round(ratio, 3),
                        "generic_comment_rate": round(generic_rate, 3),
                        "word_entropy": round(entropy, 3),
                        "num_comments": len(comment_texts),
                    },
                )
            )
        repo_score = aggregate_scores(file_results, files)
        return AnalyzerResult(name=self.name, repo_score=repo_score, file_results=file_results)

    def _extract_comments(self, source: str, language: str) -> list[str]:
        out: list[str] = []
        in_block = False
        for raw in source.splitlines():
            line = raw.strip()
            if language == "python":
                if line.startswith("#"):
                    out.append(line.lstrip("#").strip())
            else:
                if in_block:
                    out.append(line.strip("*/ "))
                    if "*/" in line:
                        in_block = False
                    continue
                if line.startswith("//"):
                    out.append(line[2:].strip())
                elif line.startswith("/*"):
                    txt = line[2:]
                    if "*/" in txt:
                        out.append(txt.replace("*/", "").strip())
                    else:
                        out.append(txt.strip())
                        in_block = True
        return [c for c in out if c]


def _is_generic(text: str) -> bool:
    return any(p.search(text) for p in _GENERIC_PATTERNS)


def _word_entropy(comments: list[str]) -> float:
    words: list[str] = []
    for c in comments:
        words.extend(w.lower() for w in _WORD_RE.findall(c))
    if len(words) < 5:
        return 4.5  # neutral — not enough signal
    counts = Counter(words)
    total = sum(counts.values())
    return -sum((v / total) * math.log2(v / total) for v in counts.values())


def _penalize_ratio(ratio: float) -> float:
    if ratio <= 0.10:
        return 0.0
    if ratio >= 0.40:
        return clamp(60 + (ratio - 0.40) * 400)
    return clamp((ratio - 0.10) / 0.30 * 60)

