from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    message: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.line}:{self.column}: {self.message}"


class CompileError(Exception):
    def __init__(self, message: str, line: int = 1, column: int = 1):
        self.diagnostic = Diagnostic(message, line, column)
        super().__init__(str(self.diagnostic))
