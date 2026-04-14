from __future__ import annotations

from app.analyzers.base import FileInput
from app.analyzers._ast_utils import line_count


def make_file(path: str, source: str, language: str = "python") -> FileInput:
    return FileInput(path=path, language=language, source=source, loc=line_count(source))
