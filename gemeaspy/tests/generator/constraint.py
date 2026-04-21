"""Implements constraints according to the ACTS constraint spec"""

import json
import random
import re
from dataclasses import dataclass
from enum import Enum
from collections.abc import Mapping, MutableMapping

from gemeaspy.tests.generator.parameters import ParameterValue
from gemeaspy.tests.generator.util import acts_enum_to_string, string_to_acts_enum


class _BooleanOp(Enum):
    AND = "&&"
    OR = "||"
    CONDITION = "=>"

class _ArithmeticOp(Enum):
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    MOD = "%"

class _RelationalOp(Enum):
    EQ = "="
    NEQ = "!="
    LT = "<"
    LTE = "<="
    GT = ">"
    GTE = ">="

class _TokenKind(Enum):
    STRING            = "STRING"
    BOOLEAN_OP        = "BOOLEAN_OP"
    RELATION_OP       = "RELATION_OP"
    ARITHMETIC_OP     = "ARITHMETIC_OP"
    PARENTHESIS_LEFT  = "PARENTHESIS_LEFT"
    PARENTHESIS_RIGHT = "PARENTHESIS_RIGHT"
    INT               = "INT"
    BOOL              = "BOOL"
    IDENTIFIER        = "IDENTIFIER"

type _Value = ParameterValue
type _Term = _ArithmeticTerm | _Parameter | _Value
type _Constraint = _SimpleConstraint | _BooleanTerm

@dataclass
class _Parameter[T: _Value]:
    p_name: str

@dataclass
class _ArithmeticTerm:
    left: _Parameter
    op: _ArithmeticOp
    right: _Parameter | _Value
    def __str__(self) -> str:
        return f"{self.left} {self.op} {self.right}"

@dataclass
class _BooleanTerm:
    left: _Constraint
    op: _BooleanOp
    right: _Constraint
    def __str__(self) -> str:
        return f"{self.left} {self.op} {self.right}"

@dataclass
class _SimpleConstraint:
    left: _Term
    op: _RelationalOp
    right: _Term
    def __str__(self) -> str:
        return f"{self.left} {self.op} {self.right}"


# Match valid tokens. Substrings must go after superstrings
_TOKEN_REGEX = re.compile(
    r'"[^"]*"'
    r'|&&'
    r'|\|\|'
    r'|=>'
    r'|=='
    r'|!='
    r'|<='
    r'|>='
    r'|[<>=]'
    r'|[+\-*/%]'
    r'|[()]'  
    r'|\d+'             
    r'|true|false'      
    r'|[a-zA-Z_]\w*' # Identifiers
    r'|\S' # unexpected character (will raise in parser)
)

_BOOLEAN_OPS  = {"&&", "||", "=>"}
_RELATION_OPS = {"=", "==", "!=", "<", "<=", ">", ">="}
_ARITHMETIC_OPS = {"+", "-", "*", "/", "%"}

def _tokenize(s: str) -> list[tuple[_TokenKind, str]]:
    """Return list of (kind, value) tokens, skipping whitespace."""
    tokens = []
    for m in _TOKEN_REGEX.finditer(s):
        v = m.group()
        if v[0] == '"':
            tokens.append((_TokenKind.STRING, v[1:-1]))
        elif v in _BOOLEAN_OPS:
            tokens.append((_TokenKind.BOOLEAN_OP, v))
        elif v in _RELATION_OPS:
            tokens.append((_TokenKind.RELATION_OP, v if v != "==" else "="))
        elif v in _ARITHMETIC_OPS:
            tokens.append((_TokenKind.ARITHMETIC_OP, v))
        elif v == "(":
            tokens.append((_TokenKind.PARENTHESIS_LEFT, v))
        elif v == ")":
            tokens.append((_TokenKind.PARENTHESIS_RIGHT, v))
        elif v.lstrip("-").isdigit():
            tokens.append((_TokenKind.INT, v))
        elif v in ("true", "false"):
            tokens.append((_TokenKind.BOOL, v))
        elif v[0].isalpha() or v[0] == "_":
            tokens.append((_TokenKind.IDENTIFIER, v))
        else:
            raise ValueError(f"Unexpected character in constraint: {repr(v)}")
    return tokens


# Recursive parameter name extraction from tree
def _extract_parameters(node: _Constraint) -> list[str]:
    """Walk a parsed constraint tree and return unique parameter names in order."""
    seen: set[str] = set()
    result: list[str] = []

    def walk_term(t: _Term) -> None:
        if isinstance(t, _Parameter):
            if t.p_name not in seen:
                seen.add(t.p_name)
                result.append(t.p_name)
        elif isinstance(t, _ArithmeticTerm):
            walk_term(t.left)
            if isinstance(t.right, _Parameter):
                walk_term(t.right)
                
    def walk(n: _Constraint) -> None:
        if isinstance(n, _BooleanTerm):
            walk(n.left)
            walk(n.right)
        elif isinstance(n, _SimpleConstraint):
            walk_term(n.left)
            walk_term(n.right)

    walk(node)
    return result


# Constraint evaluation
def _eval_term(term: _Term, params: Mapping[str, _Value]) -> _Value:
    """Resolve a term to a concrete value using the supplied parameter bindings."""
    if isinstance(term, _Parameter):
        if term.p_name not in params:
            raise KeyError(f"Parameter '{term.p_name}' is missing from the input")
        return params[term.p_name]
    if isinstance(term, _ArithmeticTerm):
        left_val  = _eval_term(term.left,  params)
        right_val = _eval_term(term.right, params)
        if not isinstance(left_val, int) or not isinstance(right_val, int):
            raise TypeError(
                f"Arithmetic operator '{term.op.value}' requires integer operands, "
                f"got {type(left_val).__name__} and {type(right_val).__name__}"
            )
        match term.op:
            case _ArithmeticOp.ADD: return left_val + right_val
            case _ArithmeticOp.SUB: return left_val - right_val
            case _ArithmeticOp.MUL: return left_val * right_val
            case _ArithmeticOp.DIV: return int(left_val / right_val)
            case _ArithmeticOp.MOD: return left_val % right_val
    return term


def _eval_constraint(node: _Constraint, params: Mapping[str, _Value]) -> bool:
    """Recursively evaluate a parsed constraint tree against parameter bindings."""
    if isinstance(node, _BooleanTerm):
        match node.op:
            case _BooleanOp.AND:
                return _eval_constraint(node.left, params) and _eval_constraint(node.right, params)
            case _BooleanOp.OR:
                return _eval_constraint(node.left, params) or _eval_constraint(node.right, params)
            case _BooleanOp.CONDITION:
                # p => q  is equivalent to  (not p) or q
                return not _eval_constraint(node.left, params) or _eval_constraint(node.right, params)
    if isinstance(node, _SimpleConstraint):
        left_val  = _eval_term(node.left,  params)
        right_val = _eval_term(node.right, params)
        if node.op in (_RelationalOp.LT, _RelationalOp.LTE, _RelationalOp.GT, _RelationalOp.GTE):
            if not isinstance(left_val, int) or not isinstance(right_val, int):
                raise TypeError(
                    f"Relational operator '{node.op.value}' requires integer operands, "
                    f"got {type(left_val).__name__} {node.left} and {type(right_val).__name__} {node.right}"
                )
        match node.op:
            case _RelationalOp.EQ:  return left_val == right_val
            case _RelationalOp.NEQ: return left_val != right_val
        if type(left_val) == int and type(right_val) == int:
            match node.op:
                case _RelationalOp.LT:  return left_val < right_val
                case _RelationalOp.LTE: return left_val <= right_val
                case _RelationalOp.GT:  return left_val > right_val
                case _RelationalOp.GTE: return left_val >= right_val
        elif node.op in _RelationalOp:
            raise TypeError(f"Operator {node.op.name} is not valid for operands of type {type(left_val)} and {type(right_val)}.")
    raise TypeError(f"Unknown constraint node type: {type(node)}")


class _ConstraintParser:
    """Parse an ACTS constraint string into a _Constraint tree"""
    
    @classmethod
    def parse_tokens(cls: type, tokens: list[tuple[_TokenKind, str]]) -> _Constraint:
        """Perform parsing and return result"""
        return _ConstraintParser(tokens).parse()
    
    def __init__(self, tokens: list[tuple[_TokenKind, str]]) -> None:
        self.tokens = tokens
        self.pos = 0

    def parse(self) -> _Constraint:
        """Perform parsing and return result"""
        left = self._parse_or()
        tok = self._peek()
        if tok and tok == (_TokenKind.BOOLEAN_OP, "=>"):
            self._consume()
            right = self.parse()  # right-associative
            return _BooleanTerm(left, _BooleanOp.CONDITION, right)
        return left

    def _peek(self) -> tuple[_TokenKind, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _consume(self, kind: _TokenKind | None = None) -> tuple[_TokenKind, str]:
        tok = self._peek()
        if tok is None:
            raise ValueError("Unexpected end of constraint expression")
        if kind is not None and tok[0] != kind:
            raise ValueError(f"Expected {kind!r}, got {tok[0]!r} ({tok[1]!r})")
        self.pos += 1
        return tok

    def _parse_or(self) -> _Constraint:
        left = self._parse_and()
        while self._peek() == (_TokenKind.BOOLEAN_OP, "||"):
            self._consume()
            right = self._parse_and()
            left = _BooleanTerm(left, _BooleanOp.OR, right)
        return left

    def _parse_and(self) -> _Constraint:
        left = self._parse_primary()
        while self._peek() == (_TokenKind.BOOLEAN_OP, "&&"):
            self._consume()
            right = self._parse_primary()
            left = _BooleanTerm(left, _BooleanOp.AND, right)
        return left

    def _parse_primary(self) -> _Constraint:
        """Parse a Simple_Constraint or a parenthesised constraint."""
        tok = self._peek()
        if tok and tok[0] == _TokenKind.PARENTHESIS_LEFT:
            self._consume(_TokenKind.PARENTHESIS_LEFT)
            node = self.parse()
            self._consume(_TokenKind.PARENTHESIS_RIGHT)
            return node
        # Must be a Simple_Constraint: Term RelOp Term
        left = self._parse_term()
        rel_tok = self._consume(_TokenKind.RELATION_OP)
        op = _RelationalOp(rel_tok[1])
        right = self._parse_term()
        return _SimpleConstraint(left, op, right)

    def _parse_term(self) -> _Term:
        """Parse Parameter [ArithOp (Parameter|Value)]."""
        atom = self._parse_atom()
        tok = self._peek()
        if tok and tok[0] == _TokenKind.ARITHMETIC_OP:
            if not isinstance(atom, _Parameter):
                raise ValueError("Left side of arithmetic term must be a parameter")
            self._consume(_TokenKind.ARITHMETIC_OP)
            arithmetic_op = _ArithmeticOp(tok[1])
            right_atom = self._parse_atom()
            return _ArithmeticTerm(atom, arithmetic_op, right_atom)
        return atom

    def _parse_atom(self) -> _Parameter | _Value:
        """Parse a parameter name, int literal, bool literal, or string literal."""
        tok = self._peek()
        if tok is None:
            raise ValueError("Expected a term (parameter, int, bool, or string), but reached end of constraint.")
        kind, val = tok
        if kind == _TokenKind.IDENTIFIER:
            self._consume()
            return _Parameter(p_name=val)
        if kind == _TokenKind.INT:
            self._consume()
            return int(val)
        if kind == _TokenKind.BOOL:
            self._consume()
            return val == "true"
        if kind == _TokenKind.STRING:
            self._consume()
            return json.loads(acts_enum_to_string(val))
        raise ValueError(f"Expected a term (parameter, int, bool, or string), got {kind!r} ({val!r}).")


# Public class
class Constraint:
    """An ACTS-style constraint"""

    def __init__(self, constraint: str) -> None:
        self.text: str = constraint
        self.value: _Constraint = _ConstraintParser.parse_tokens(_tokenize(constraint))
        self.parameters: list[str] = (
            _extract_parameters(self.value)
        )

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"Constraint('{str(self)}')"

    def test(self, params: MutableMapping[str, _Value]) -> bool:
        """Return True if the constraint holds for the given parameter bindings.
        Raises:
            KeyError:   A parameter referenced by the constraint is absent from params.
            TypeError:  An operator is applied to operands of incompatible types.
            ZeroDivisionError: A division or modulo by zero occurs during evaluation.
        """
        missing = [p for p in self.parameters if p not in params]
        if missing:
            raise KeyError(f"Missing parameters: {missing}")
        # Safety check
        for param in params:
            val = params[param]
            if isinstance(val, str):
                params[param] = string_to_acts_enum(val)
        return _eval_constraint(self.value, params)

# For manual testing
if __name__ == "__main__":
    constraint_str = 'param_a > param_b + param_c => param_b % 3 == 0 || param_b == 1 && param_d == "A" || param_d == "B"'
    print("Creating constraint from: " + constraint_str)
    constraint = Constraint(constraint_str)
    print("Created constraint:       " + str(constraint))
    print("Parameters:               " + str(constraint.parameters))
    print("Testing all cominations in domain: ")

    domains: dict[str, range | list] = {
        'a': range(-8, 8),
        'b': range(0, 8),
        'c': range(-2, 2),
        'd': ["A", "B", "C", "D"]
    }

    n_combinations = 1
    
    for parameter, domain in domains.items():
        print(f"domain_{parameter}: {domain}")
        n_combinations *= len(domain)

    mismatch_found = False
    for i in range(n_combinations):
        k: dict[str, _Value] = {
            "param_a": random.randint(-8,8),
            "param_b": random.randint(0,8),
            "param_c": random.randint(-2,2),
            "param_d": random.choice(["A", "B", "C", "D"])
        }
        left = eval(f'{k["param_a"]} > {k["param_b"]} + {k["param_c"]}')
        right = eval(f'{k["param_b"]} % 3 == 0 or {k["param_b"]} == 1 and "{k["param_d"]}" == "A" or "{k["param_d"]}" == "B"')
        test_python_eval = not left or left and right
        if test_python_eval == constraint.test(k):
            continue
        print(f"-- Test Case {i+1} --")
        print(f"param_a: {k['param_a']}\tparam_b: {k['param_b']}")
        print(f"param_c: {k['param_c']}\tparam_d: {k['param_d']}")
        print(f'{k["param_a"]} > {k["param_b"]} + {k["param_c"]} => {k["param_b"]} % 3 == 0 || {k["param_b"]} == 1 && {k["param_d"]} == "A" || {k["param_d"]} == "B"')
        print("✖ Mismatch between python eval and constrain.test")
        mismatch_found = True

    if not mismatch_found:
        print("✔ No issues found")

    div_zero_test_str = 'param_a / param_b > 2 => param_c == "A"'
    print(f"Testing division by zero: {div_zero_test_str} where param_b = 0")
    try:
        Constraint(div_zero_test_str).test({"param_a": 2, "param_b": 0, "param_c": "A"})
        print("✖ Expected exception not caught! Something is wrong.")
    except ZeroDivisionError:
        print("✔ Expected exception raised correctly.")

    incompatible_types_test_str = 'param_a + param_b > 2 => param_c == "A"'
    print(f'Testing invalid operation between types: {incompatible_types_test_str} where param_a = 5 and param_b = "S"')
    try:
        Constraint(incompatible_types_test_str).test({"param_a": 5, "param_b": "S", "param_c": "A"})
        print("✖ Expected exception not caught! Something is wrong.")
    except TypeError:
        print("✔ Expected exception raised correctly.")
    except Exception:
        print("✖ Unexpected exception caught!")
        raise
    
