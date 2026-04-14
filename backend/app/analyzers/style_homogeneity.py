"""Style Homogeneity analyzer.

AI-generated code is unusually uniform. Real teams drift. We measure:
- variance of function lengths
- variance of indent width
- Shannon entropy of identifier length distribution
- uniformity of import styles

Low variance/entropy → higher score (more AI-like / more debt).
"""
from __future__ import annotations

import math
import re
from collections import Counter

from app.analyzers.base import AnalyzerResult, FileInput, FileResult, clamp
from app.analyzers._ast_utils import parse_python, python_functions, js_functions_simple


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class StyleHomogeneityAnalyzer:
    name = "style_homogeneity"

    def analyze(self, files: list[FileInput], context: dict) -> AnalyzerResult:
        file_results: list[FileResult] = []
        all_func_lengths: list[int] = []

        for f in files:
            fn_lengths = self._fn_lengths(f)
            identifiers = _IDENT_RE.findall(f.source)
            ident_lengths = [len(i) for i in identifiers] or [1]
            indent_widths = _indent_widths(f.source)

            fn_variance = _normalized_stdev(fn_lengths) if len(fn_lengths) >= 2 else 0.0
            ident_entropy = _shannon_entropy(ident_lengths)
            indent_uniformity = _uniformity(indent_widths)

            # Low variance → high uniformity → high score
            variance_score = 100 - _scale(fn_variance, 0, 1.0)
            entropy_score = 100 - _scale(ident_entropy, 0, 3.5)
            indent_score = _scale(indent_uniformity, 0, 1.0)

            score = clamp(0.45 * variance_score + 0.35 * entropy_score + 0.20 * indent_score)
            file_results.append(
                FileResult(
                    path=f.path,
                    score=score,
                    details={
                        "fn_length_stdev_normalized": round(fn_variance, 3),
                        "identifier_entropy": round(ident_entropy, 3),
                        "indent_uniformity": round(indent_uniformity, 3),
                        "num_functions": len(fn_lengths),
                    },
                )
            )
            all_func_lengths.extend(fn_lengths)

        repo_score = _weighted_average(file_results, files)
        notes: list[str] = []
        if len(all_func_lengths) >= 5:
            repo_variance = _normalized_stdev(all_func_lengths)
            if repo_variance < 0.25:
                notes.append("Repo-wide function length variance is very low")
        return AnalyzerResult(name=self.name, repo_score=repo_score, file_results=file_results, notes=notes)

    def _fn_lengths(self, f: FileInput) -> list[int]:
        if f.language == "python":
            tree = parse_python(f.source)
            if tree is None:
                return []
            return [fn.length for fn in python_functions(tree)]
        return [fn.length for fn in js_functions_simple(f.source)]


def _normalized_stdev(values: list[int]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(var) / mean


def _shannon_entropy(values: list[int]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    total = sum(counts.values())
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def _indent_widths(source: str) -> list[int]:
    widths: list[int] = []
    for line in source.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue
        widths.append(len(line) - len(stripped))
    return widths


def _uniformity(values: list[int]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    top = counts.most_common(1)[0][1]
    return top / len(values)


def _scale(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return clamp(((value - lo) / (hi - lo)) * 100)


def _weighted_average(results: list[FileResult], files: list[FileInput]) -> float:
    if not results:
        return 0.0
    loc_by_path = {f.path: max(1, f.loc) for f in files}
    total_loc = sum(loc_by_path.get(r.path, 1) for r in results)
    if total_loc == 0:
        return 0.0
    return sum(r.score * loc_by_path.get(r.path, 1) for r in results) / total_loc
