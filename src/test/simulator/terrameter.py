from typing import *

class _Variable:
    def __init__(self, value: str | int | float = 0, type_: Type =int, readonly: bool=True):
        self.type_ = type_
        self.value = type_(value) # May raise exception
        self.readonly = readonly

class TerrameterLS():
    """A simulated Terrameter LS instrument"""


    def __init__(self):
        self.__variables: Dict[str, _Variable] = {'measure': _Variable(value=0), 'unattendedmode': _Variable(0, readonly=False)}

    def set_variable(self, variable_name: str, value: str | int | float) -> None:
        """raises
            TypeError if any argument is of an incorrect type.
            ValueError if the variable name or value is invalid.
            PermissionError if the variable is read-only
        """
        if type(variable_name) != str:
            raise TypeError("Variable name must be of type str.")
        if variable_name not in self.__variables:
            raise ValueError(f"Variable '{variable_name}' does not exist.")
        variable = self.__variables[variable_name]
        if variable.readonly:
            raise PermissionError(f"Variable '{variable_name}' is read-only.")
        expected_type = variable.type_
        if type(value) != expected_type:
            # Try to convert value. 
            if type(value) == str:
                try:
                    value = expected_type(value)
                except Exception:
                    raise ValueError(f"'{value}' could not be parsed as type {expected_type}.")
            else:
                raise ValueError(f"Value is of invalid type {type(value)}; expected {expected_type}.")
        variable.value = value
    
    def get_variable(self, variable_name: str) -> str | int | float:
        """raises 
            TypeError if the variable name is of an incorrect type.
            ValueError if the variable name is invalid"""
        if type(variable_name) != str:
            raise TypeError("Variable name must be of type str.")
        if variable_name not in self.__variables:
            raise ValueError(f"Variable '{variable_name}' does not exist.")
        return self.__variables[variable_name].value