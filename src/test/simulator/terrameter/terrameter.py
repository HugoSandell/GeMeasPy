from typing import *

class TerrameterLS():
    """A simulated Terrameter LS instrument"""
    def __init__(self):
        self.__variables: Dict[str, str | int | float] = {'measure': 0}
    
    def set_variable(self, variable_name: str, value: str | int | float) -> None:
        """Raises TypeError if any argument is of an incorrect type.
        Raises ValueError if the variable name or value is invalid."""
        if type(variable_name) != str:
            raise TypeError("Variable name must be of type str.")
        if variable_name not in self.__variables:
            raise ValueError(f"Variable '{variable_name}' does not exist.")
        expected_type = type(self.__variables[variable_name])
        if type(value) != expected_type:
            # Try to convert value. 
            if type(value) == str:
                try:
                    value = expected_type(value)
                except Exception:
                    raise ValueError(f"'{value}' could not be parsed as type {expected_type}.")
            else:
                raise ValueError(f"Value is of invalid type {type(value)}; expected {expected_type}.")
        self.__variables[variable_name] = value
    
    def get_variable(self, variable_name: str) -> str | int | float:
        """Raises TypeError if the variable name is of an incorrect type.
        Raises ValueError if the variable name is invalid"""
        if type(variable_name) != str:
            raise TypeError("Variable name must be of type str.")
        if variable_name not in self.__variables:
            raise ValueError(f"Variable '{variable_name}' does not exist.")
        return self.__variables[variable_name]