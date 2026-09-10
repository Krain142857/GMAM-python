"""Semantic evaluation and timeline translation."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional, Sequence

from .ast import (
    Composite, Conditional, Equality, Expr, Interval, MacroCall, NumberLiteral,
    MacroDefinition, Program, RawString, Value, Variable, VariableDefinition,
)
from .errors import CompileError


class Translator:
    def __init__(self):
        self.variables: Dict[str, Value] = {}
        self.macros: Dict[str, MacroDefinition] = {}
        self.timeline: Dict[float, list[str]] = {}
        self._macro_stack = []

    def translate(self, program: Program) -> Dict[int, list[str]]:
        for declaration in program.declarations:
            if isinstance(declaration, VariableDefinition):
                if declaration.name in self.variables or declaration.name in self.macros:
                    self._error("duplicate definition", declaration.location)
                self.variables[declaration.name] = self._evaluate(declaration.value) if declaration.value else Value("default", None)
            elif isinstance(declaration, MacroDefinition):
                if declaration.name in self.variables or declaration.name in self.macros:
                    self._error("duplicate definition", declaration.location)
                self._validate_parameters(declaration)
                self.macros[declaration.name] = declaration
            else:
                content = self._evaluate(declaration.content)
                if content.kind not in ("string", "number"):
                    self._error("step content must be a string", declaration.location)
                for position in declaration.positions:
                    value = self._evaluate(position)
                    for frame in self._positions(value, position.location):
                        frame = self._normalize_number(frame)
                        self.timeline.setdefault(frame, []).append(self._format_value(content))
        return self.timeline

    def _validate_parameters(self, macro):
        seen_default = False
        names = set()
        for parameter in macro.parameters:
            if parameter.name in names:
                self._error("duplicate macro parameter", parameter.location)
            names.add(parameter.name)
            if parameter.value is not None:
                seen_default = True
            elif seen_default:
                self._error("required parameter follows a default parameter", parameter.location)

    def _positions(self, value: Value, location: object) -> Sequence[float]:
        if value.kind == "number":
            return [value.value]
        if value.kind == "interval":
            begin, difference, end, include_end = value.value
            if difference == 0:
                self._error("interval difference cannot be zero", location)
            positions = []
            current = begin
            while (current <= end if difference > 0 else current >= end):
                if current == end and not include_end:
                    break
                positions.append(current)
                current += difference
            return positions
        self._error("step position must be a number or interval", location)

    def _evaluate(self, expression: Optional[Expr], local: Optional[Dict[str, Value]] = None) -> Value:
        if expression is None:
            return Value("default", None)
        local = local or {}
        if isinstance(expression, NumberLiteral):
            return Value("number", expression.value)
        if isinstance(expression, RawString):
            return Value("string", expression.value)
        if isinstance(expression, Variable):
            if expression.name in local:
                return local[expression.name]
            if expression.name in self.variables:
                return self.variables[expression.name]
            self._error(f"undefined identifier {expression.name}", expression.location)
        if isinstance(expression, Composite):
            parts = [self._evaluate(item, local) for item in expression.expressions]
            if any(item.kind not in ("string", "number") for item in parts):
                self._error("only strings and numbers can be concatenated", expression.location)
            return Value("string", "".join(self._format_value(item) for item in parts))
        if isinstance(expression, Interval):
            values = [self._evaluate(item, local) for item in (expression.begin, expression.difference, expression.end)]
            if any(item.kind != "number" for item in values):
                self._error("interval bounds must be numbers", expression.location)
            return Value("interval", (values[0].value, values[1].value, values[2].value, expression.include_end))
        if isinstance(expression, Equality):
            left, right = self._evaluate(expression.left, local), self._evaluate(expression.right, local)
            if left.kind not in ("string", "number") or right.kind not in ("string", "number"):
                self._error("equality operands must be strings or numbers", expression.location)
            if left.kind == right.kind == "number":
                equal = left.value == right.value
            else:
                equal = self._format_value(left) == self._format_value(right)
            return Value("number", int(equal))
        if isinstance(expression, Conditional):
            condition = self._evaluate(expression.condition, local)
            if condition.kind != "number":
                self._error("conditional condition must be a number", expression.condition.location)
            return self._evaluate(expression.true_branch if condition.value else expression.false_branch, local)
        if isinstance(expression, MacroCall):
            return self._call_macro(expression, local)
        self._error("unsupported expression", expression.location)

    def _call_macro(self, call: MacroCall, caller_locals: Dict[str, Value]) -> Value:
        macro = self.macros.get(call.name)
        if macro is None:
            self._error(f"undefined macro {call.name}", call.location)
        if call.name in self._macro_stack:
            self._error(f"recursive macro invocation {call.name}", call.location)
        if len(call.arguments) > len(macro.parameters):
            self._error("too many macro arguments", call.location)
        bound = {}
        next_pos = 0
        for name, expression in call.arguments:
            if name is None:
                while next_pos < len(macro.parameters) and macro.parameters[next_pos].name in bound:
                    next_pos += 1
                if next_pos >= len(macro.parameters):
                    self._error("too many positional arguments", expression.location)
                parameter = macro.parameters[next_pos]
                next_pos += 1
            else:
                parameter = next((item for item in macro.parameters if item.name == name), None)
                if parameter is None:
                    self._error(f"unknown macro argument {name}", expression.location)
                if parameter.name in bound:
                    self._error(f"duplicate macro argument {name}", expression.location)
            bound[parameter.name] = self._evaluate(expression, caller_locals)
        self._macro_stack.append(call.name)
        try:
            for parameter in macro.parameters:
                if parameter.name not in bound:
                    if parameter.value is None:
                        self._error(f"missing macro argument {parameter.name}", call.location)
                    bound[parameter.name] = self._evaluate(parameter.value, bound)
            return self._evaluate(macro.value, bound)
        finally:
            self._macro_stack.pop()

    @staticmethod
    def _error(message: str, location) -> None:
        raise CompileError(message, location.line, location.column)

    @staticmethod
    def _format_value(value: Value) -> str:
        if value.kind != "number":
            return str(value.value)
        rounded = Translator._rounded_number(value.value)
        return format(rounded, "f").rstrip("0").rstrip(".") or "0"

    @staticmethod
    def _rounded_number(value: float) -> Decimal:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _normalize_number(value: float) -> float:
        rounded = Translator._rounded_number(value)
        if rounded == rounded.to_integral():
            return int(rounded)
        return float(rounded)
