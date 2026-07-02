"""Defines ways for a stringified int field to differ from its correct value"""

from enum import StrEnum, auto


class IntFieldError(StrEnum):
    CORRECT = auto()  # Field has correct value
    EMPTY = auto()  # Field is empty
    STRING = auto()  # Field does not parse as an integer
    MINUS_1 = auto()  # Field value is one less than correct
    PLUS_1 = auto()  # Field value is one greater than correct

    def resolve(self, value) -> str:
        match self:
            case self.CORRECT:
                return str(value)
            case self.EMPTY:
                return ""
            case self.STRING:
                return "X"
            case self.MINUS_1:
                return str(value - 1)
            case self.PLUS_1:
                return str(value + 1)
