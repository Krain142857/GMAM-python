"""Recursive-descent parser for the GMAM language."""

from typing import List, Optional, Tuple

from .ast import (
    BinaryExpression, Composite, Conditional, Equality, Interval, MacroCall, NumberLiteral,
    MacroDefinition, Program, RawString, Step, Variable, VariableDefinition,
    UnaryExpression,
)
from .errors import CompileError
from .tokens import Lexer, Token


class Parser:
    def __init__(self, source: str):
        self.tokens = Lexer(source).tokens()
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def _error(self, message: str, token: Optional[Token] = None) -> None:
        token = token or self.current
        raise CompileError(message, token.location.line, token.location.column)

    def _accept(self, kind: str) -> Optional[Token]:
        if self.current.kind == kind:
            token = self.current
            self.index += 1
            return token
        return None

    def _expect(self, kind: str) -> Token:
        token = self._accept(kind)
        if token is None:
            self._error(f"expected {kind}, got {self.current.kind}")
        return token

    def parse(self) -> Program:
        declarations = []
        while self.current.kind != "END":
            if self.current.kind == "DEF":
                declarations.append(self._definition())
            elif self.current.kind in ("LBRACE", "LBRACK"):
                declarations.append(self._step())
            else:
                self._error("expected a definition or step")
        return Program(declarations)

    def _definition(self):
        start = self._expect("DEF")
        name = self._expect("IDENTIFIER")
        if self._accept("AT"):
            self._expect("LPAREN")
            parameters = self._parameters()
            self._expect("RPAREN")
            self._expect("ASSIGN")
            return MacroDefinition(name.value, parameters, self._expr(), start.location)
        value = self._expr() if self._accept("ASSIGN") else None
        return VariableDefinition(name.value, value, start.location)

    def _parameters(self) -> List[VariableDefinition]:
        parameters = []
        while self.current.kind != "RPAREN":
            name = self._expect("IDENTIFIER")
            value = self._expr() if self._accept("ASSIGN") else None
            parameters.append(VariableDefinition(name.value, value, name.location))
            if not self._accept("COMMA"):
                break
        return parameters

    def _step(self) -> Step:
        start = self.current
        if self._accept("LBRACE"):
            content = self._composite_after_open(start.location)
            self._expect("LBRACK")
            positions = self._expr_list("RBRACK")
        else:
            self._expect("LBRACK")
            positions = self._expr_list("RBRACK")
            self._expect("LBRACE")
            content = self._composite_after_open(start.location)
        self._expect("SEMICOLON")
        return Step(content, positions, start.location)

    def _composite_after_open(self, location):
        return Composite(self._expr_list("RBRACE"), location)

    def _expr_list(self, closing: str):
        expressions = []
        while self.current.kind != closing:
            expressions.append(self._expr())
            if not self._accept("COMMA") and self.current.kind != closing:
                if self.current.kind in ("END", "SEMICOLON"):
                    self._error(f"expected {closing}")
        self._expect(closing)
        return expressions

    def _expr(self):
        return self._expr_interval()

    def _expr_interval(self):
        expression = self._expr_condition()
        if self._accept("COLON"):
            difference = self._expr_condition()
            self._expect("COLON")
            end = self._expr_condition()
            return Interval(
                expression,
                difference,
                end,
                bool(self._accept("INCLUDEEND")),
                expression.location,
            )
        return expression

    def _expr_condition(self):
        expression = self._expr_equality()
        if self._accept("QUESTION"):
            # The first colon after the true branch belongs to this conditional.
            true_branch = self._expr_equality()
            self._expect("COLON")
            return Conditional(expression, true_branch, self._expr_condition(), expression.location)
        return expression

    def _expr_equality(self):
        expression = self._expr_additive()
        while self._accept("EQU"):
            expression = Equality(expression, self._expr_additive(), expression.location)
        return expression

    def _expr_additive(self):
        expression = self._expr_multiplicative()
        while self.current.kind in ("PLUS", "MINUS") and self._can_continue_arithmetic(expression):
            operator = self.current.value
            self.index += 1
            expression = BinaryExpression(expression, operator, self._expr_multiplicative(), expression.location)
        return expression

    @staticmethod
    def _can_continue_arithmetic(expression):
        # Raw strings and composites delimit adjacent expressions in a step.
        return not isinstance(expression, (RawString, Composite))

    def _expr_multiplicative(self):
        expression = self._expr_unary()
        operators = {"MUL", "SLASH", "DIV", "MOD"}
        while self.current.kind in operators:
            operator = self.current.value
            self.index += 1
            expression = BinaryExpression(expression, operator, self._expr_unary(), expression.location)
        return expression

    def _expr_unary(self):
        if self.current.kind in ("PLUS", "MINUS"):
            token = self.current
            self.index += 1
            return UnaryExpression(token.value, self._expr_unary(), token.location)
        return self._expr_primary()

    def _expr_primary(self):
        token = self.current
        if self._accept("RAWSTRING"):
            return RawString(token.value, token.location)
        if self._accept("NUMBER"):
            return NumberLiteral(token.value, token.location)
        if self._accept("LBRACE"):
            return self._composite_after_open(token.location)
        if self._accept("LPAREN"):
            expression = self._expr()
            self._expect("RPAREN")
            return expression
        if self._accept("IDENTIFIER"):
            if self._accept("AT"):
                self._expect("LPAREN")
                arguments = self._arguments()
                self._expect("RPAREN")
                return MacroCall(token.value, arguments, token.location)
            return Variable(token.value, token.location)
        self._error("expected an expression", token)

    def _arguments(self) -> List[Tuple[Optional[str], object]]:
        arguments = []
        while self.current.kind != "RPAREN":
            if self.current.kind == "IDENTIFIER" and self.tokens[self.index + 1].kind == "ASSIGN":
                name = self._expect("IDENTIFIER")
                self._expect("ASSIGN")
                arguments.append((name.value, self._expr()))
            else:
                arguments.append((None, self._expr()))
            if not self._accept("COMMA"):
                break
        return arguments
