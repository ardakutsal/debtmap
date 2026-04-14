"""Dependency Graph analyzer.

Builds an import graph across project files. Flags:
- cycles (each participating file gets a hit)
- high fan-out (>15 imports)
- direct os.environ / process.env access outside a config module
- heavy use of globals
"""
from __future__ import annotations

import ast
import re
from collections import defaultdict

import networkx as nx

from app.analyzers.base import AnalyzerResult, FileInput, FileResult, clamp
from app.analyzers._ast_utils import parse_python


_JS_IMPORT_RE = re.compile(r"""import\s+(?:[^'"]+?\s+from\s+)?['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\)""")
_JS_PROCESS_ENV = re.compile(r"\bprocess\.env\.\w+")
_PY_ENV = re.compile(r"\bos\.environ\b|\bos\.getenv\b")


class DependencyGraphAnalyzer:
    name = "dependency_graph"

    def analyze(self, files: list[FileInput], context: dict) -> AnalyzerResult:
        graph: nx.DiGraph = nx.DiGraph()
        imports_per_file: dict[str, set[str]] = defaultdict(set)
        env_hits: dict[str, int] = defaultdict(int)
        globals_hits: dict[str, int] = defaultdict(int)

        path_set = {f.path for f in files}
        for f in files:
            graph.add_node(f.path)
            imports = self._imports(f)
            imports_per_file[f.path] = imports
            for imp in imports:
                target = _resolve(imp, f.path, path_set)
                if target:
                    graph.add_edge(f.path, target)
            if f.language == "python":
                env_hits[f.path] = len(_PY_ENV.findall(f.source))
                tree = parse_python(f.source)
                if tree is not None:
                    globals_hits[f.path] = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Global))
            else:
                env_hits[f.path] = len(_JS_PROCESS_ENV.findall(f.source))

        cycle_members: set[str] = set()
        try:
            for cycle in nx.simple_cycles(graph):
                cycle_members.update(cycle)
        except Exception:
            pass

        file_results: list[FileResult] = []
        for f in files:
            fan_out = len([e for e in graph.out_edges(f.path)])
            fan_in = len([e for e in graph.in_edges(f.path)])
            is_config = "config" in f.path.lower() or "settings" in f.path.lower()
            env_penalty = env_hits[f.path] * (0 if is_config else 5)
            cycle_penalty = 35 if f.path in cycle_members else 0
            fanout_penalty = max(0, fan_out - 15) * 3
            fanin_penalty = max(0, fan_in - 20) * 2
            globals_penalty = globals_hits[f.path] * 8

            score = clamp(cycle_penalty + fanout_penalty + fanin_penalty + env_penalty + globals_penalty)
            file_results.append(
                FileResult(
                    path=f.path,
                    score=score,
                    details={
                        "fan_out": fan_out,
                        "fan_in": fan_in,
                        "in_cycle": f.path in cycle_members,
                        "env_direct_access": env_hits[f.path],
                        "global_declarations": globals_hits[f.path],
                    },
                )
            )
        notes = [f"Detected {len(cycle_members)} files in import cycles"] if cycle_members else []
        return AnalyzerResult(name=self.name, repo_score=_loc_weighted(file_results, files), file_results=file_results, notes=notes)

    def _imports(self, f: FileInput) -> set[str]:
        out: set[str] = set()
        if f.language == "python":
            tree = parse_python(f.source)
            if tree is None:
                return out
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        out.add(a.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        out.add(node.module)
                        for a in node.names:
                            out.add(f"{node.module}.{a.name}")
        else:
            for m in _JS_IMPORT_RE.finditer(f.source):
                out.add(m.group(1) or m.group(2) or "")
        return {i for i in out if i}


def _resolve(imp: str, from_path: str, paths: set[str]) -> str | None:
    if not imp:
        return None
    if imp.startswith("."):
        base = from_path.rsplit("/", 1)[0]
        parts = imp.lstrip(".")
        parent_levels = len(imp) - len(parts)
        for _ in range(max(0, parent_levels - 1)):
            base = base.rsplit("/", 1)[0]
        candidate_base = f"{base}/{parts}" if parts else base
        for ext in (".py", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js", "/__init__.py"):
            c = candidate_base + ext
            if c in paths:
                return c
        return None
    dotted = imp.replace(".", "/")
    for ext in (".py", ".ts", ".tsx", ".js", ".jsx"):
        for candidate in (dotted + ext, dotted + "/__init__.py", dotted + "/index.ts", dotted + "/index.js"):
            for p in paths:
                if p.endswith(candidate):
                    return p
    return None


def _loc_weighted(results, files):
    if not results:
        return 0.0
    loc = {f.path: max(1, f.loc) for f in files}
    total = sum(loc.get(r.path, 1) for r in results)
    if total == 0:
        return 0.0
    return sum(r.score * loc.get(r.path, 1) for r in results) / total
