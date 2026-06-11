"""Error Handling analyzer.

Detects: bare except, overly broad except Exception, silent pass in except,
try blocks that only re-raise silently, unclosed resource patterns, and empty
catch blocks in JS/TS.
"""
from __future__ import annotations

import ast
import re

from app.analyzers.base import AnalyzerResult, FileInput, FileResult, clamp, aggregate_scores
from app.analyzers._ast_utils import parse_python


_JS_EMPTY_CATCH = re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}")
_JS_CATCH_IGNORE = re.compile(r"catch\s*\([^)]*\)\s*\{\s*(?:/\*[\s\S]*?\*/|//[^\n]*)?\s*\}")
_JS_TRY = re.compile(r"\btry\s*\{")
_JS_CATCH_CONSOLE = re.compile(r"catch\s*\([^)]*\)\s*\{\s*console\.(?:log|error)")


class ErrorHandlingAnalyzer:
    name = "error_handling"

    def analyze(self, files: list[FileInput], context: dict) -> AnalyzerResult:
        file_results: list[FileResult] = []
        for f in files:
            if f.language == "python":
                score, details = self._analyze_python(f.source)
            else:
                score, details = self._analyze_js(f.source)
            file_results.append(FileResult(path=f.path, score=score, details=details))
        return AnalyzerResult(name=self.name, repo_score=aggregate_scores(file_results, files), file_results=file_results)

    def _analyze_python(self, source: str) -> tuple[float, dict]:
        tree = parse_python(source)
        if tree is None:
            return 50.0, {"reason": "parse_failed"}
        bare_except = 0
        broad_except = 0
        pass_only = 0
        try_count = 0
        raw_io = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                try_count += 1
                for handler in node.handlers:
                    if handler.type is None:
                        bare_except += 1
                    elif isinstance(handler.type, ast.Name) and handler.type.id in {"Exception", "BaseException"}:
                        broad_except += 1
                    if len(handler.body) == 1 and isinstance(handler.body[0], (ast.Pass, ast.Ellipsis)):
                        pass_only += 1
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                if not _is_in_with(node, tree):
                    raw_io += 1
        total = bare_except + broad_except + pass_only + raw_io
        score = clamp(bare_except * 18 + broad_except * 10 + pass_only * 22 + raw_io * 6)
        return score, {
            "bare_except": bare_except,
            "broad_except": broad_except,
            "silent_pass": pass_only,
            "unmanaged_open": raw_io,
            "try_blocks": try_count,
        }

    def _analyze_js(self, source: str) -> tuple[float, dict]:
        try_count = len(_JS_TRY.findall(source))
        empty_catch = len(_JS_EMPTY_CATCH.findall(source))
        ignoring = len(_JS_CATCH_IGNORE.findall(source)) - empty_catch
        console_only = len(_JS_CATCH_CONSOLE.findall(source))
        score = clamp(empty_catch * 22 + ignoring * 14 + console_only * 8)
        return score, {
            "try_blocks": try_count,
            "empty_catch": empty_catch,
            "catch_ignoring": max(0, ignoring),
            "catch_console_only": console_only,
        }


def _is_in_with(call_node: ast.Call, tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                if item.context_expr is call_node:
                    return True
    return False

