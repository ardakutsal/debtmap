"""Architectural Contracts analyzer.

Detects: low type annotation coverage, rampant `any`, god classes/functions,
functions with too many parameters, missing return types.
"""
from __future__ import annotations

import ast
import re

from app.analyzers.base import AnalyzerResult, FileInput, FileResult, clamp
from app.analyzers._ast_utils import parse_python, python_functions, js_functions_simple


_ANY_TYPE = re.compile(r"\bany\b|\bAny\b", re.MULTILINE)
_TS_FN_WITH_TYPES = re.compile(r":\s*\w+(?:<[^>]+>)?\s*(?:=|,|\)|\{|=>)")


class ArchitecturalContractsAnalyzer:
    name = "architectural_contracts"

    def analyze(self, files: list[FileInput], context: dict) -> AnalyzerResult:
        file_results: list[FileResult] = []
        for f in files:
            if f.language == "python":
                score, details = self._python(f.source)
            else:
                score, details = self._ts(f.source, f.language)
            file_results.append(FileResult(path=f.path, score=score, details=details))
        return AnalyzerResult(name=self.name, repo_score=_loc_weighted(file_results, files), file_results=file_results)

    def _python(self, source: str) -> tuple[float, dict]:
        tree = parse_python(source)
        if tree is None:
            return 50.0, {"reason": "parse_failed"}
        fns = python_functions(tree)
        total = len(fns)
        annotated = sum(1 for fn in fns if fn.has_annotations)
        god_fn = sum(1 for fn in fns if fn.length > 200)
        huge_fn = sum(1 for fn in fns if fn.length > 500)
        many_args = sum(1 for fn in fns if fn.num_args > 6)
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        god_cls = sum(
            1 for c in classes
            if (getattr(c, "end_lineno", c.lineno) or c.lineno) - c.lineno > 500
        )
        no_ann_ratio = 0.0 if total == 0 else 1.0 - annotated / total
        score = clamp(
            no_ann_ratio * 55
            + huge_fn * 15
            + god_fn * 6
            + god_cls * 12
            + many_args * 3
        )
        return score, {
            "num_functions": total,
            "annotation_coverage": round(1 - no_ann_ratio, 3),
            "god_functions": god_fn,
            "huge_functions": huge_fn,
            "god_classes": god_cls,
            "functions_with_many_args": many_args,
        }

    def _ts(self, source: str, language: str) -> tuple[float, dict]:
        fns = js_functions_simple(source)
        total = len(fns)
        huge = sum(1 for fn in fns if fn.length > 300)
        god = sum(1 for fn in fns if fn.length > 500)
        many_args = sum(1 for fn in fns if fn.num_args > 6)
        any_count = len(_ANY_TYPE.findall(source)) if language in ("ts", "tsx") else 0
        typed_sites = len(_TS_FN_WITH_TYPES.findall(source))
        any_density = any_count / max(1, typed_sites + any_count) if language in ("ts", "tsx") else 0
        score = clamp(any_density * 55 + huge * 12 + god * 6 + many_args * 3 + (10 if typed_sites == 0 and language in ("ts", "tsx") else 0))
        return score, {
            "num_functions": total,
            "huge_functions": huge,
            "god_functions": god,
            "functions_with_many_args": many_args,
            "any_usages": any_count,
            "any_density": round(any_density, 3),
        }


def _loc_weighted(results, files):
    if not results:
        return 0.0
    loc = {f.path: max(1, f.loc) for f in files}
    total = sum(loc.get(r.path, 1) for r in results)
    if total == 0:
        return 0.0
    return sum(r.score * loc.get(r.path, 1) for r in results) / total
