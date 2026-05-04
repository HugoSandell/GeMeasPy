"""This module defines various behavioural patterns for testing"""

from enum import StrEnum, auto


class TerrameterMisbehavior(StrEnum):
    NONE = auto()
    #RESTART_DURING_MEASUREMENT = auto()
    #RESTART_AFTER_FIRST_TASK = auto()
    #CREATE_EMPTY_FILE = auto()
    #DELETE_PROJECT_BEFORE_TRANSFER = auto()
    #DROPPED_MESSAGES = auto() # Lose every Nth incoming message
    #TIMEOUT = auto() # Timeout before first measurement

# TODO: Implement in emulator and test setup
# TODO: Implement in oracle
class TerrameterProjectState(StrEnum):
    UNINITIALISED = auto() # No project created
    INITIALISED = auto()   # Project already created
    OLD = auto()           # Project is created, but expired/outdated
    MEASURING = auto()     # First task is measuring for a short time
    ONE_DONE = auto()      # First task of project done
    ALL_DONE = auto()      # All tasks of project done