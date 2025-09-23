import time
from typing import *
from .vfs import VirtualFileSystem
import xml.etree.ElementTree as ElementTree
from . import constants
from .project import Project

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
        self._projects: Dict[str, Project] = {} # "name": object
        self._current_project: str = "" # Name of current project, if any 

    def set_variable(self, variable_name: str, value: _Value) -> None:
        """Write to a Terrameter variable.
        Raises:
            TypeError if any argument is of an incorrect type.
            ValueError if the variable name or value is invalid.
            PermissionError if the variable is read-only"""
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
        """Read a Terrameter variable.
        Raises:  
            TypeError if the variable name is of an incorrect type.
            ValueError if the variable name is invalid"""
        if type(variable_name) != str:
            raise TypeError("Variable name must be of type str.")
        if variable_name not in self._variables:
            raise ValueError(f"Variable '{variable_name}' does not exist.")
        return self._variables[variable_name].value

    def read_settings(self, path: str):
        """Read settings from file. 
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

    def create_project(self, name: str=""):
        """Create a new project. 
        Returns the final name of the new project, which may differ from the one provided.""" 
        number_separator = "_" # Character that separates the name from the number in case of conflict
        if name == "":
            # Special case if no name provided
            name = "Project"
            number_separator = ""
            
        resolved_name = name # Name to make unique if necessary
        
        if name in self._projects: 
            # Resolve name conflict by appending number
            project_number = 1
            done = False
            # Find unused number suffix
            while not done:
                resolved_name = f"{name}{number_separator}{project_number}"
                done = True # Assume done (unique name + suffix)
                for existing_project_name in self._projects:
                    # Collision test is case insensitive
                    if existing_project_name.lower() == resolved_name.lower(): 
                        project_number += 1
                        done = False # Counter-example found
        new_project = Project(resolved_name)
        self._projects[resolved_name] = new_project
        self._current_project = resolved_name
        return resolved_name

    def create_task(self, name: str, 
                    spread_file: str, protocol_file: str, 
                    spacing: Tuple[int, int ,int], unknown: Tuple[int, int, int]):
        if self._current_project not in self._projects:
            raise RuntimeError("Current project is not set or does not exist.")
        project = self._projects[self._current_project]
        project.create_task(name, spread_file, protocol_file, spacing, unknown)
        raise NotImplementedError()

    def measure(self):
        """Perform measurements"""        
        # Get the project and tasks to work on
        if self._current_project not in self._projects:
            return
        project = self._projects[self._current_project]
        unfinished_tasks = [task for task in project.tasks if not task.is_complete]
        
        while len(unfinished_tasks) > 0:
            # Get task
            current_task = unfinished_tasks[0]
            # Make sure task is still relevant
            if current_task not in project.tasks or current_task.is_complete:
                unfinished_tasks.pop(0)
                continue

            # Perform task
            time.sleep(2) # Pretend to measure
            
            # Finish task
            current_task.is_complete = True
            unfinished_tasks.pop(0)
        
        # Reset values
        self._variables["measure"].value = 0