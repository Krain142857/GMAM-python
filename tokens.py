"""Location-aware lexer for the GMAM language."""

from dataclasses import dataclass
from typing import List

from .errors import CompileError


@dataclass(frozen=True)
class Location:
    line: int
    column: int


@dataclass(frozen=True)
class Token:
    kind: str
    value: object
    location: Location


class Lexer:
    _keywords = {
        "def": "DEF",
        "div": "DIV",
        "mod": "MOD",
        "for": "FOR",
        "in": "IN",
        "do": "DO",
    }

    def __init__(self, source: str):
        self.source = source
        self.index = 0
        self.line = 1
        self.column = 1

    def _error(self, message: str) -> None:
        raise CompileError(message, self.line, self.column)

    def _advance(self, text: str) -> None:
        lines = text.splitlines(True)
        if len(lines) == 1:
            self.column += len(text)
        else:
            self.line += len(lines) - 1
            self.column = len(lines[-1].rstrip("\r\n")) + 1
        self.index += len(text)

    def tokens(self) -> List[Token]:
        result: List[Token] = []
        if self.source.startswith("\ufeff"):
            self._advance("\ufeff")
        while self.index < len(self.source):
            start = Location(self.line, self.column)
            rest = self.source[self.index:]
            if rest[0] in " \t":
                self._advance(rest[0])
                continue
            if rest.startswith("//"):
                end = rest.find("\n")
                self._advance(rest if end < 0 else rest[:end])
                continue
            if rest.startswith("/*"):
                end = rest.find("*/", 2)
                if end < 0:
                    self._error("unterminated block comment")
                self._advance(rest[:end + 2])
                continue
            if rest[0] in "\r\n":
                self._advance("\r\n" if rest.startswith("\r\n") else rest[0])
                continue
            if rest[0] == "`":
                self._advance("`")
                value = []
                while self.index < len(self.source) and self.source[self.index] != "`":
                    if self.source[self.index] == "\\":
                        if self.index + 1 >= len(self.source):
                            self._error("unterminated raw string")
                        escaped = self.source[self.index:self.index + 2]
                        value.append({"\\\\": "\\", "\\`": "`", "\\n": "\n"}.get(escaped, escaped[1]))
                        self._advance(escaped)
                    else:
                        value.append(self.source[self.index])
                        self._advance(self.source[self.index])
                if self.index >= len(self.source):
                    self._error("unterminated raw string")
                self._advance("`")
                result.append(Token("RAWSTRING", "".join(value), start))
                continue
            if rest[0].isdigit():
                end = 1
                while end < len(rest) and rest[end].isdigit():
                    end += 1
                if end < len(rest) and rest[end] == ".":
                    fraction_end = end + 1
                    while fraction_end < len(rest) and rest[fraction_end].isdigit():
                        fraction_end += 1
                    if fraction_end == end + 1:
                        self._error("expected digits after decimal point")
                    end = fraction_end
                text = rest[:end]
                self._advance(text)
                result.append(Token("NUMBER", float(text) if "." in text else int(text), start))
                continue
            if rest[0].isalpha():
                end = 1
                while end < len(rest) and (rest[end].isalnum() or rest[end] == "_"):
                    end += 1
                text = rest[:end]
                self._advance(text)
                result.append(Token(self._keywords.get(text, "IDENTIFIER"), text, start))
                continue
            kind = {"++": "INCLUDEEND", "==": "EQU"}.get(rest[:2])
            if kind:
                self._advance(rest[:2])
                result.append(Token(kind, rest[:2], start))
                continue
            kind = {
                "{": "LBRACE", "}": "RBRACE", "[": "LBRACK", "]": "RBRACK",
                ";": "SEMICOLON", ",": "COMMA", ":": "COLON", "=": "ASSIGN",
                "?": "QUESTION", "(": "LPAREN", ")": "RPAREN", "@": "AT",
                "+": "PLUS", "-": "MINUS", "*": "MUL", "/": "SLASH",
            }.get(rest[0])
            if kind:
                self._advance(rest[0])
                result.append(Token(kind, rest[0], start))
                continue
            self._error(f"unexpected character {rest[0]!r}")
        result.append(Token("END", None, Location(self.line, self.column)))
        return result
