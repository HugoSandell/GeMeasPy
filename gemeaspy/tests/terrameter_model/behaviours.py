"""This module defines various behavioural patterns for testing"""

from enum import Enum, auto

class TerrameterBehaviour(Enum):
    IDEAL = auto()
    RESTART_DURING_MEASUREMENT = auto()
    RESTART_AFTER_FIRST_TASK = auto()
    CREATE_EMPTY_FILE = auto()
    DELETE_PROJECT_BEFORE_TRANSFER = auto()
    DROPPED_MESSAGES = auto() # Lose every Nth incoming message
    TIMEOUT = auto() # Timeout before first measurement