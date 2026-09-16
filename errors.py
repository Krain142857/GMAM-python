from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    message: str
    line: int
    column: int
    element: object = None

    def __str__(self) -> str:
        suffix = "" if self.element is None else f" (element: {self.element!r})"
        return f"{self.line}:{self.column}: {self.message}{suffix}"


class CompileError(Exception):
    def __init__(self, message: str, line: int = 1, column: int = 1, element=None):
        self.diagnostic = Diagnostic(message, line, column, element)
        super().__init__(str(self.diagnostic))
