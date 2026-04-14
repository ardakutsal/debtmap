from __future__ import annotations

import ast
import re
from dataclasses import dataclass


@dataclass
class FunctionInfo:
    name: str
    lineno: int
    end_lineno: int
    length: int
    num_args: int
    has_docstring: bool
    has_annotations: bool
    body_tokens: list[str]


def parse_python(source: str) -> ast.Module | None:
    try:
        return ast.parse(source)
    except (SyntaxError, ValueError):
        return None


def python_functions(tree: ast.AST) -> list[FunctionInfo]:
    out: list[FunctionInfo] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno) or node.lineno
            body_tokens: list[str] = []
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    body_tokens.append(sub.id)
                elif isinstance(sub, ast.Attribute):
                    body_tokens.append(sub.attr)
            ann = any(a.annotation is not None for a in node.args.args) or node.returns is not None
            out.append(
                FunctionInfo(
                    name=node.name,
                    lineno=node.lineno,
                    end_lineno=end,
                    length=end - node.lineno + 1,
                    num_args=len(node.args.args),
                    has_docstring=ast.get_docstring(node) is not None,
                    has_annotations=ann,
                    body_tokens=body_tokens,
                )
            )
    return out


_JS_FN_RE = re.compile(
    r"(?:function\s+(\w+)\s*\(([^)]*)\)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>|\b(\w+)\s*\(([^)]*)\)\s*\{)",
    re.MULTILINE,
)

_JS_COMMENT_RE = re.compile(r"//[^\n]*|/\*[\s\S]*?\*/")
_JS_STRING_RE = re.compile(r"(['\"`])(?:\\.|(?!\1).)*\1")


def js_functions_simple(source: str) -> list[FunctionInfo]:
    stripped = _JS_STRING_RE.sub('""', source)
    out: list[FunctionInfo] = []
    for m in _JS_FN_RE.finditer(stripped):
        name = m.group(1) or m.group(3) or m.group(5) or "<anon>"
        args_str = m.group(2) or m.group(4) or m.group(6) or ""
        start = stripped[: m.start()].count("\n") + 1
        end = _find_block_end(stripped, m.end())
        end_line = stripped[:end].count("\n") + 1 if end else start
        args = [a.strip() for a in args_str.split(",") if a.strip()]
        out.append(
            FunctionInfo(
                name=name,
                lineno=start,
                end_lineno=end_line,
                length=max(1, end_line - start + 1),
                num_args=len(args),
                has_docstring=False,
                has_annotations=":" in args_str or "=>" in args_str,
                body_tokens=[],
            )
        )
    return out


def _find_block_end(text: str, start: int) -> int:
    depth = 0
    started = False
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
            started = True
        elif c == "}":
            depth -= 1
            if started and depth <= 0:
                return i
    return len(text)


def strip_comments_and_strings(source: str, language: str) -> str:
    if language == "python":
        lines = []
        for raw in source.splitlines():
            code = raw.split("#", 1)[0]
            lines.append(code)
        text = "\n".join(lines)
    else:
        text = _JS_COMMENT_RE.sub("", source)
    return _JS_STRING_RE.sub('""', text)


def line_count(source: str) -> int:
    return sum(1 for line in source.splitlines() if line.strip())


def comment_lines(source: str, language: str) -> int:
    count = 0
    in_block = False
    for raw in source.splitlines():
        line = raw.strip()
        if language == "python":
            if line.startswith("#"):
                count += 1
        else:
            if in_block:
                count += 1
                if "*/" in line:
                    in_block = False
                continue
            if line.startswith("//"):
                count += 1
            elif line.startswith("/*"):
                count += 1
                if "*/" not in line:
                    in_block = True
    return count
