from typing import *
from vfs import VirtualFileSystem
import xml.etree.ElementTree as ElementTree
import constants

type _Value = str | int | float | bool

class ParseError(Exception):
    def __init__(self, *args: object):
        super(ParseError, self).__init__(*args)

class _Variable:
    def __init__(self, value: _Value = 0, readonly: bool=True):
        self.type_ = type(value)
        self.value = value
        self.readonly = readonly

class TerrameterLS():
    """A simulated Terrameter LS instrument"""
    def __init__(self):
        self._variables: Dict[str, _Variable] = {"measure": _Variable(value=0), "unattendedmode": _Variable(0, readonly=False)}
        self._filesystem: VirtualFileSystem = VirtualFileSystem()
        self._settings: Dict[str, str | int | float | bool] = constants.TERRAMETER_DEFAULT_SETTINGS

    def set_variable(self, variable_name: str, value: _Value) -> None:
        """raises
            TypeError if any argument is of an incorrect type.
            ValueError if the variable name or value is invalid.
            PermissionError if the variable is read-only
        """
        if type(variable_name) != str:
            raise TypeError("Variable name must be of type str.")
        if variable_name not in self._variables:
            raise ValueError(f"Variable '{variable_name}' does not exist.")
        variable = self._variables[variable_name]
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
    
    def get_variable(self, variable_name: str) -> str | int | float | bool:
        """Raises:  
            TypeError if the variable name is of an incorrect type.
            ValueError if the variable name is invalid"""
        if type(variable_name) != str:
            raise TypeError("Variable name must be of type str.")
        if variable_name not in self._variables:
            raise ValueError(f"Variable '{variable_name}' does not exist.")
        return self._variables[variable_name].value

    def read_settings(self, path: str):
        """Read data from file. 
        Raises: 
            FileNotFoundError if file doesn't exist.
            PermissionError if file can't be written to.
            ParseError if the file could not be parsed correctly."""
        # Read data and parse XML
        data_raw = self._filesystem.read(path)
        try:
            data_str = data_raw.decode()
            xml_root = ElementTree.fromstring(data_str)
        except UnicodeDecodeError as e:
            raise ParseError(f"Unicode error: {e}")
        except ElementTree.ParseError as e:
            raise ParseError(f"XML error: {e}")
        
        if xml_root.tag.lower() != "SETTINGS":
            raise ParseError("Root tag is not <Settings>")
        for child in xml_root:
            # IP_WindowSecList is a special case
            if child.tag == "IP_WindowSecList":
                try:
                    self._settings["IP_WindowSecList"] = [float(s) for s in child.text.split()]
                except Exception:
                    raise ParseError(f"Failed to parse '{text}' as list of floats")
            if child.tag in self._settings:
                text = child.text
                try:
                    type(self._settings[child.tag])(text)
                except Exception:
                    raise ParseError(f"Failed to parse '{text}' as {type(self._settings[child.tag])}")
                self._settings[child.tag] = child.text
