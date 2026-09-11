"""Abstract syntax tree and evaluated values for the GMAM language."""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

from .tokens import Location


class Expr:
    location: Location


@dataclass
class RawString(Expr):
    value: str
    location: Location


@dataclass
class NumberLiteral(Expr):
    value: Union[int, float]
    location: Location


@dataclass
class UnaryExpression(Expr):
    operator: str
    operand: Expr
    location: Location


@dataclass
class BinaryExpression(Expr):
    left: Expr
    operator: str
    right: Expr
    location: Location


@dataclass
class Assignment(Expr):
    name: str
    value: Expr
    location: Location


@dataclass
class Variable(Expr):
    name: str
    location: Location


@dataclass
class Composite(Expr):
    expressions: List[Expr]
    location: Location


@dataclass
class Interval(Expr):
    begin: Expr
    difference: Expr
    end: Expr
    include_end: bool
    location: Location


@dataclass
class MacroCall(Expr):
    name: str
    arguments: List[Tuple[Optional[str], Expr]]
    location: Location


@dataclass
class Conditional(Expr):
    condition: Expr
    true_branch: Expr
    false_branch: Expr
    location: Location


@dataclass
class Equality(Expr):
    left: Expr
    right: Expr
    location: Location


@dataclass
class ForBinding:
    name: str
    source: Expr
    location: Location


@dataclass
class ForExpression(Expr):
    bindings: List[ForBinding]
    body: Composite
    location: Location


@dataclass
class VariableDefinition:
    name: str
    value: Optional[Expr]
    location: Location


@dataclass
class MacroDefinition:
    name: str
    parameters: List[VariableDefinition]
    value: Expr
    location: Location


@dataclass
class Step:
    content: Composite
    positions: Composite
    location: Location


@dataclass
class ExpressionStatement:
    expression: Expr
    location: Location


@dataclass
class Program:
    declarations: list


@dataclass(frozen=True)
class Value:
    kind: str
    value: object
