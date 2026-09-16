"""Semantic evaluation and timeline translation."""

from decimal import Decimal, ROUND_HALF_UP
from math import lcm
from typing import Dict, Optional

from .ast import (
    Assignment, BinaryExpression, Composite, Conditional, Equality, Expr, ForExpression, ForStep, Interval,
    ExpressionStatement, MacroCall, NumberLiteral, MacroDefinition, Program, RawString, Step, Value, Variable,
    VariableDefinition,
    UnaryExpression,
)
from .errors import CompileError


class Translator:
    def __init__(self):
        self.variables: Dict[str, Value] = {
            "TIME": Value("number", 0),
            "BPM": Value("number", 120),
            "NOTE_PER_BEAT": Value("number", 4),
            "TLSTEP_PER_BEAT": Value("number", 8),
        }
        self.macros: Dict[str, MacroDefinition] = {}
        self.timeline: Dict[float, list[str]] = {}
        self._macro_stack = []
        self._timing_notes = []
        self._non_integer_timing = False
        self._timing_location = None
        self.scaled_source = None
        self.output_source = None
        self._step_mode = False

    def translate(self, program: Program, time_scale="ask", confirm=None, step_mode=False) -> Dict[int, list[str]]:
        self._step_mode = step_mode
        for declaration in program.declarations:
            if isinstance(declaration, VariableDefinition):
                if declaration.name in self.variables or declaration.name in self.macros:
                    self._error(f"duplicate definition {declaration.name!r}", declaration.location, declaration.name)
                self.variables[declaration.name] = self._evaluate(declaration.value) if declaration.value else Value("default", None)
            elif isinstance(declaration, MacroDefinition):
                if declaration.name in self.variables or declaration.name in self.macros:
                    self._error(f"duplicate definition {declaration.name!r}", declaration.location, declaration.name)
                self._validate_parameters(declaration)
                self.macros[declaration.name] = declaration
            elif isinstance(declaration, ExpressionStatement):
                self._evaluate(declaration.expression)
            elif isinstance(declaration, ForStep):
                self._translate_for_step(declaration)
            else:
                self._translate_step(declaration)
        return self._resolve_moments(time_scale, confirm)

    def _translate_for_step(self, declaration: ForStep) -> None:
        sources = []
        names = set()
        for binding in declaration.bindings:
            if binding.name in names:
                self._error("forstep binding identifier is duplicated", binding.location)
            names.add(binding.name)
            source = self._evaluate(binding.source)
            if source.kind != "list":
                self._error("forstep source must evaluate to a list", binding.location, source)
            sources.append(self._flatten(source.value))
        lengths = {len(source) for source in sources}
        if len(lengths) > 1:
            self._error(
                f"forstep source lists must have equal length: {[len(source) for source in sources]}",
                declaration.location,
            )
        for index in range(len(sources[0])):
            local = {}
            for binding, source in zip(declaration.bindings, sources):
                local[binding.name] = source[index]
            for step in declaration.steps:
                if isinstance(step, ExpressionStatement):
                    self._evaluate(step.expression, local)
                else:
                    self._translate_step(step, local)

    def _translate_step(self, declaration: Step, local=None) -> None:
        content = self._evaluate(declaration.content, local)
        if content.kind != "list":
            self._error("step content must be a composite list", declaration.location, content)
        positions = self._evaluate(declaration.positions, local)
        if positions.kind != "list":
            self._error("step positions must be a composite list", declaration.location, positions)
        content_text = "".join(
            self._format_value(value) for value in self._flatten(content.value)
        )
        self._timing_location = declaration.positions.location
        for value in self._flatten(positions.value):
            frame = self._moment(value, declaration.positions.location)
            self.timeline.setdefault(frame, []).append(content_text)

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
        if local is None:
            local = {}
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
        if isinstance(expression, Assignment):
            value = self._evaluate(expression.value, local)
            if expression.name in local:
                local[expression.name] = value
            elif expression.name in self.variables:
                self.variables[expression.name] = value
            else:
                self._error(f"undefined identifier {expression.name}", expression.location)
            return Value("null", None)
        if isinstance(expression, Composite):
            values = [self._evaluate(item, local) for item in expression.expressions]
            return Value("list", [value for value in values if value.kind != "null"])
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
                self._error("interval bounds must be numbers", expression.location, values)
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
            if expression.operator == "==":
                if (left.kind == "list") != (right.kind == "list"):
                    result = False
                elif left.kind not in ("string", "number") or right.kind not in ("string", "number"):
                    self._error(
                        "equality operands must be strings or numbers",
                        expression.location,
                        (left, right),
                    )
                result = (
                    left.value == right.value
                    if left.kind == right.kind == "number"
                    else self._format_value(left) == self._format_value(right)
                )
            else:
                if left.kind != "number" or right.kind != "number":
                    self._error(
                        f"{expression.operator} operands must be numbers",
                        expression.location,
                        (left, right),
                    )
                result = {
                    "<": left.value < right.value,
                    ">": left.value > right.value,
                    "<=": left.value <= right.value,
                    ">=": left.value >= right.value,
                }[expression.operator]
            return Value("number", int(result))
        if isinstance(expression, Conditional):
            condition = self._evaluate(expression.condition, local)
            if condition.kind != "number":
                self._error("conditional condition must be a number", expression.condition.location, condition)
            return self._evaluate(expression.true_branch if condition.value else expression.false_branch, local)
        if isinstance(expression, MacroCall):
            if expression.name in ("go", "look"):
                return self._call_timing_builtin(expression, local)
            return self._call_macro(expression, local)
        self._error("unsupported expression", expression.location)

    def _call_timing_builtin(self, call: MacroCall, local: Dict[str, Value]) -> Value:
        if len(call.arguments) != 2 or any(name is not None for name, _ in call.arguments):
            self._error(f"{call.name} requires listValue and note", call.location)
        list_value = self._evaluate(call.arguments[0][1], local)
        note = self._evaluate(call.arguments[1][1], local)
        if list_value.kind not in ("list", "number"):
            self._error(
                f"{call.name} listValue must be a number or list",
                call.arguments[0][1].location,
                list_value,
            )
        if note.kind != "number" or note.value <= 0:
            self._error(f"{call.name} note must be a positive number", call.arguments[1][1].location, note)
        self._timing_notes.append(note.value)
        self._timing_location = call.location
        time = self.variables["TIME"]
        if time.kind != "number":
            self._error("TIME must be a number", call.location, time)
        note_per_beat = self.variables["NOTE_PER_BEAT"]
        step_per_beat = self.variables["TLSTEP_PER_BEAT"]
        if note_per_beat.kind != "number" or step_per_beat.kind != "number":
            self._error(
                "NOTE_PER_BEAT and TLSTEP_PER_BEAT must be numbers",
                call.location,
                (note_per_beat, step_per_beat),
            )
        if self._step_mode:
            bpm = self.variables["BPM"]
            if bpm.kind != "number" or bpm.value <= 0:
                self._error("BPM must be a positive number", call.location, bpm)
            step_per_note = 50 * 60 / bpm.value * note_per_beat.value / note.value
        else:
            step_per_note = step_per_beat.value * note_per_beat.value / note.value
        if list_value.kind == "number":
            result = Value("number", time.value + list_value.value * step_per_note)
            self._non_integer_timing |= not self._is_integer(result.value)
            if call.name == "go":
                self.variables["TIME"] = result
            return result
        values = []
        for value in self._flatten(list_value.value):
            if value.kind != "number":
                self._error(
                    f"{call.name} listValue must contain numbers",
                    call.arguments[0][1].location,
                    value,
                )
            values.append(Value("number", time.value + value.value * step_per_note))
        self._non_integer_timing |= any(not self._is_integer(value.value) for value in values)
        if call.name == "go":
            if not values:
                self._error("go listValue cannot be empty", call.arguments[0][1].location, list_value)
            self.variables["TIME"] = max(values, key=lambda value: value.value)
        return Value("list", values)

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
    def _error(message: str, location, element=None) -> None:
        if isinstance(element, Value):
            element = f"{element.kind}={element.value!r}"
        elif isinstance(element, (list, tuple)):
            element = tuple(
                f"{item.kind}={item.value!r}" if isinstance(item, Value) else item
                for item in element
            )
        raise CompileError(message, location.line, location.column, element)

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
                self._error("flat requires a list", location, value)
            return Value("list", self._flatten(value.value))
        if value.kind == "list":
            return Value("list", [
                self._apply_unary_value(item, operator, location)
                for item in value.value
            ])
        if value.kind != "number":
            self._error("unary operators require numbers or lists of numbers", location, value)
        if operator == "+":
            return value
        if operator == "-":
            return Value("number", -value.value)
        self._error(f"unsupported unary operator {operator}", location)

    def _apply_binary_values(self, left: Value, right: Value, operator: str, location, right_location) -> Value:
        if operator == "rep":
            if left.kind != "list" or right.kind != "number":
                self._error("rep requires a list and a natural number", location, (left, right))
            if not self._is_integer(right.value) or right.value < 0:
                self._error("rep count must be a natural number", right_location, right)
            return Value("list", left.value * int(right.value))
        if left.kind == "list" and right.kind == "list":
            if len(left.value) != len(right.value):
                self._error(
                    "arithmetic list operands must have equal length",
                    location,
                    (len(left.value), len(right.value)),
                )
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
            self._error(
                "arithmetic operators require numbers or lists of numbers",
                location,
                (left, right),
            )
        if operator in ("/", "div", "mod") and right.value == 0:
            self._error("division by zero", right_location, right)
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
                self._error(f"{operator} requires integer operands", location, (left, right))
            quotient = int(left.value / right.value)
            result = quotient if operator == "div" else left.value - quotient * right.value
        else:
            self._error(f"unsupported arithmetic operator {operator}", location)
        return Value("number", result)

    def _expand_interval(self, begin, difference, end, include_end, location) -> list[Value]:
        if difference == 0:
            self._error("interval difference cannot be zero", location, difference)
        values = []
        current = begin
        while (current <= end if difference > 0 else current >= end):
            if current == end and not include_end:
                break
            values.append(Value("number", current))
            current += difference
        return values

    def _moment(self, value: Value, location) -> float:
        if value.kind != "number" or value.value < 0:
            self._error("step position must evaluate to a non-negative number", location, value)
        return value.value

    def _resolve_moments(self, time_scale, confirm) -> Dict[int, list[str]]:
        if self._step_mode:
            timeline = self._rounded_timeline(self.timeline)
            self.output_source = self._format_step_source(timeline)
            return timeline
        if time_scale not in ("ask", "adjust", "round"):
            raise ValueError("unsupported time scale strategy")
        if not self._non_integer_timing:
            if any(not self._is_integer(moment) for moment in self.timeline):
                self._error(
                    "step position must evaluate to an integer",
                    self._timing_location,
                    tuple(self.timeline),
                )
            timeline = {int(moment): values for moment, values in self.timeline.items()}
            self.output_source = self._format_step_source(timeline)
            return timeline
        if any(not self._is_integer(note) for note in self._timing_notes):
            self._error("note must be an integer for adaptive timing", self._timing_location)
        note_values = [int(note) for note in self._timing_notes]
        common_note = lcm(*note_values)
        note_per_beat = self.variables["NOTE_PER_BEAT"].value
        if not self._is_integer(note_per_beat) or note_per_beat <= 0:
            self._error("NOTE_PER_BEAT must be a positive integer", self._timing_location)
        suggested_step = common_note / note_per_beat
        current_step = self.variables["TLSTEP_PER_BEAT"].value
        alternate_step = suggested_step * current_step
        suggested_text = self._format_number(suggested_step)
        alternate_text = self._format_number(alternate_step)
        if time_scale == "ask":
            if confirm is None:
                confirm = input
            answer = confirm(
                f"检测到非整数 TIME。推荐 TLSTEP_PER_BEAT：\n"
                f"1. {suggested_text}（按音符计算）\n"
                f"2. {alternate_text}（若手动输入过具体时间，可以考虑使用此值）\n"
                f"是否调整？[y/N] "
            ).strip().lower()
            if answer in ("y", "yes", "是"):
                selected = confirm(
                    f"请输入 TLSTEP_PER_BEAT（直接回车使用推荐值 {suggested_text}）："
                ).strip()
                try:
                    suggested_step = float(selected) if selected else suggested_step
                except ValueError:
                    self._error("TLSTEP_PER_BEAT must be a number", self._timing_location)
                time_scale = "adjust"
            else:
                time_scale = "round"
        if time_scale == "adjust":
            if suggested_step <= 0:
                self._error("TLSTEP_PER_BEAT must be positive", self._timing_location)
            factor = suggested_step / current_step
            timeline = self._rounded_timeline(
                {moment * factor: values for moment, values in self.timeline.items()}
            )
            self.scaled_source = self._format_scaled_source(timeline, suggested_step)
            self.output_source = self._format_step_source(timeline)
            return timeline
        timeline = self._rounded_timeline(self.timeline)
        self.output_source = self._format_step_source(timeline)
        return timeline

    @staticmethod
    def _format_scaled_source(timeline, step_per_beat) -> str:
        lines = [f"TLSTEP_PER_BEAT = {Translator._format_number(step_per_beat)};"]
        lines.extend(Translator._format_step_lines(timeline))
        return "\n".join(lines) + "\n"

    @staticmethod
    def _format_step_source(timeline) -> str:
        return "\n".join(Translator._format_step_lines(timeline)) + "\n"

    @staticmethod
    def _format_step_lines(timeline) -> list[str]:
        grouped = {}
        for moment in sorted(timeline):
            moments = str(moment)
            for content in timeline[moment]:
                grouped.setdefault(content, []).append(moments)
        lines = []
        for content, moments in grouped.items():
            escaped = content.replace("\\", "\\\\").replace("`", "\\`")
            lines.append(f"[{', '.join(moments)}] {{`{escaped}`}};")
        return lines

    @staticmethod
    def _rounded_timeline(timeline) -> Dict[int, list[str]]:
        rounded = {}
        for moment, values in timeline.items():
            target = int(Decimal(str(moment)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            rounded.setdefault(target, []).extend(values)
        return rounded

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
    def _format_number(value: object) -> str:
        return str(int(value)) if Translator._is_integer(value) else str(value)

    @staticmethod
    def _format_value(value: Value) -> str:
        if value.kind != "number":
            return str(value.value)
        rounded = Translator._rounded_number(value.value)
        return format(rounded, "f").rstrip("0").rstrip(".") or "0"

    @staticmethod
    def _rounded_number(value: float) -> Decimal:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
