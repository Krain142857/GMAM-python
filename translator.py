"""Semantic evaluation and timeline translation."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional

from .ast import (
    BinaryExpression, Composite, Conditional, Equality, Expr, ForExpression, Interval,
    MacroCall, NumberLiteral, MacroDefinition, Program, RawString, Value, Variable,
    VariableDefinition,
    UnaryExpression,
)
from .errors import CompileError


class Translator:
    def __init__(self):
        self.variables: Dict[str, Value] = {}
        self.macros: Dict[str, MacroDefinition] = {}
        self.timeline: Dict[int, list[str]] = {}
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
                if content.kind != "list":
                    self._error("step content must be a composite list", declaration.location)
                positions = self._evaluate(declaration.positions)
                if positions.kind != "list":
                    self._error("step positions must be a composite list", declaration.location)
                content_text = "".join(
                    self._format_value(value) for value in self._flatten(content.value)
                )
                for value in self._flatten(positions.value):
                    frame = self._moment(value, declaration.positions.location)
                    self.timeline.setdefault(frame, []).append(content_text)
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

    def _evaluate(self, expression: Optional[Expr], local: Optional[Dict[str, Value]] = None) -> Value:
        if expression is None:
            return Value("default", None)
        local = local or {}
        if isinstance(expression, NumberLiteral):
            return Value("number", expression.value)
        if isinstance(expression, UnaryExpression):
            operand = self._evaluate(expression.operand, local)
            return self._apply_unary_value(operand, expression.operator, expression.location)
        if isinstance(expression, RawString):
            return Value("string", expression.value)
        if isinstance(expression, Variable):
            if expression.name in local:
                return local[expression.name]
            if expression.name in self.variables:
                return self.variables[expression.name]
            self._error(f"undefined identifier {expression.name}", expression.location)
        if isinstance(expression, Composite):
            return Value("list", [self._evaluate(item, local) for item in expression.expressions])
        if isinstance(expression, ForExpression):
            sources = []
            names = set()
            for binding in expression.bindings:
                if binding.name in names:
                    self._error("for binding identifier is duplicated", binding.location)
                names.add(binding.name)
                source = self._evaluate(binding.source, local)
                if source.kind != "list":
                    self._error("for source must evaluate to a list", binding.location)
                sources.append(self._flatten(source.value))
            lengths = {len(source) for source in sources}
            if len(lengths) > 1:
                self._error("for source lists must have equal length", expression.location)
            results = []
            for index in range(len(sources[0])):
                bindings = dict(local)
                for binding, source in zip(expression.bindings, sources):
                    bindings[binding.name] = source[index]
                body = self._evaluate(expression.body, bindings)
                if body.kind != "list":
                    self._error("for body must evaluate to a list", expression.body.location)
                results.extend(body.value)
            return Value("list", results)
        if isinstance(expression, Interval):
            values = [self._evaluate(item, local) for item in (expression.begin, expression.difference, expression.end)]
            if any(item.kind != "number" for item in values):
                self._error("interval bounds must be numbers", expression.location)
            return Value("list", self._expand_interval(
                values[0].value,
                values[1].value,
                values[2].value,
                expression.include_end,
                expression.location,
            ))
        if isinstance(expression, BinaryExpression):
            return self._evaluate_binary(expression, local)
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

    def _evaluate_binary(self, expression: BinaryExpression, local: Dict[str, Value]) -> Value:
        left = self._evaluate(expression.left, local)
        right = self._evaluate(expression.right, local)
        return self._apply_binary_values(
            left,
            right,
            expression.operator,
            expression.location,
            expression.right.location,
        )

    def _apply_unary_value(self, value: Value, operator: str, location) -> Value:
        if operator == "flat":
            if value.kind != "list":
                self._error("flat requires a list", location)
            return Value("list", self._flatten(value.value))
        if value.kind == "list":
            return Value("list", [
                self._apply_unary_value(item, operator, location)
                for item in value.value
            ])
        if value.kind != "number":
            self._error("unary operators require numbers or lists of numbers", location)
        if operator == "+":
            return value
        if operator == "-":
            return Value("number", -value.value)
        self._error(f"unsupported unary operator {operator}", location)

    def _apply_binary_values(self, left: Value, right: Value, operator: str, location, right_location) -> Value:
        if operator == "rep":
            if left.kind != "list" or right.kind != "number":
                self._error("rep requires a list and a natural number", location)
            if not self._is_integer(right.value) or right.value < 0:
                self._error("rep count must be a natural number", right_location)
            return Value("list", left.value * int(right.value))
        if left.kind == "list" and right.kind == "list":
            if len(left.value) != len(right.value):
                self._error("arithmetic list operands must have equal length", location)
            return Value("list", [
                self._apply_binary_values(item_left, item_right, operator, location, right_location)
                for item_left, item_right in zip(left.value, right.value)
            ])
        if left.kind == "list":
            return Value("list", [
                self._apply_binary_values(item, right, operator, location, right_location)
                for item in left.value
            ])
        if right.kind == "list":
            return Value("list", [
                self._apply_binary_values(left, item, operator, location, right_location)
                for item in right.value
            ])
        if left.kind != "number" or right.kind != "number":
            self._error("arithmetic operators require numbers or lists of numbers", location)
        if operator in ("/", "div", "mod") and right.value == 0:
            self._error("division by zero", right_location)
        if operator == "+":
            result = left.value + right.value
        elif operator == "-":
            result = left.value - right.value
        elif operator == "*":
            result = left.value * right.value
        elif operator == "/":
            result = left.value / right.value
        elif operator in ("div", "mod"):
            if not self._is_integer(left.value) or not self._is_integer(right.value):
                self._error(f"{operator} requires integer operands", location)
            quotient = int(left.value / right.value)
            result = quotient if operator == "div" else left.value - quotient * right.value
        else:
            self._error(f"unsupported arithmetic operator {operator}", location)
        return Value("number", result)

    def _expand_interval(self, begin, difference, end, include_end, location) -> list[Value]:
        if difference == 0:
            self._error("interval difference cannot be zero", location)
        values = []
        current = begin
        while (current <= end if difference > 0 else current >= end):
            if current == end and not include_end:
                break
            values.append(Value("number", current))
            current += difference
        return values

    def _moment(self, value: Value, location) -> int:
        if value.kind != "number" or not self._is_integer(value.value) or value.value < 0:
            self._error("step position must evaluate to a natural number", location)
        return int(value.value)

    @staticmethod
    def _flatten(values) -> list[Value]:
        flattened = []
        for value in values:
            if value.kind == "list":
                flattened.extend(Translator._flatten(value.value))
            else:
                flattened.append(value)
        return flattened

    @staticmethod
    def _is_integer(value: object) -> bool:
        return isinstance(value, (int, float)) and float(value).is_integer()

    @staticmethod
    def _format_value(value: Value) -> str:
        if value.kind != "number":
            return str(value.value)
        rounded = Translator._rounded_number(value.value)
        return format(rounded, "f").rstrip("0").rstrip(".") or "0"

    @staticmethod
    def _rounded_number(value: float) -> Decimal:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
