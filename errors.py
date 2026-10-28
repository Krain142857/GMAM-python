from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Diagnostic:
    message: str
    line: int
    column: int
    element: object = None
    filename: Optional[str] = None

    def __str__(self) -> str:
        prefix = "" if self.filename is None else f"{self.filename}:"
        suffix = "" if self.element is None else f" (element: {self.element!r})"
        return f"{prefix}{self.line}:{self.column}: {self.message}{suffix}"


class CompileError(Exception):
    def __init__(
        self,
        message: str,
        line: int = 1,
        column: int = 1,
        element=None,
        filename: Optional[str] = None,
    ):
        self.diagnostic = Diagnostic(message, line, column, element, filename)
        super().__init__(str(self.diagnostic))
