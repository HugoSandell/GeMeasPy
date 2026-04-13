import errno
import os
import threading
import time
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable
from io import BytesIO

from . import constants
from .project import Project
from .task import Protocol, Spread, Task
from .vfs import Path, VirtualFileSystem

type Value = str | int | float | bool

class _Variable:
    def __init__(self, value: Value = 0, readonly: bool=True):
        self.type_ = type(value)
        self.value = value
        self.readonly = readonly

class ParseError(Exception):
    def __init__(self, *args: object):
        super(ParseError, self).__init__(*args)

class TerrameterLS():
    """An emulated Terrameter LS instrument"""
    def __init__(self):
        self.allow_login: bool = True
        self.is_shut_down: bool = False
        self.on_kill_program_instance: Callable | None = None
        """Called when terrameter software should be shut down""" 
        self._variables: dict[str, _Variable] = {"measure": _Variable(value=0), "unattendedmode": _Variable(0, readonly=False)}
        self._filesystem: VirtualFileSystem = VirtualFileSystem()
        self._filesystem.load_initial_fs()
        self._settings: dict[str, int | float | bool | list[float]] = constants.TERRAMETER_DEFAULT_SETTINGS
        self._projects: dict[str, Project] = {} # "name": object
        self._current_project_name: str = "" # Name of current project, if any

    def _shutdown(self):
        # "Reboot"
        self.allow_login = False
        self.is_shut_down = True
        time.sleep(0.1) # Reboot time
        self.is_shut_down = False
        self.allow_login = True
        pass

    def initialise_shutdown(self, timer_seconds: float):
        if not self.allow_login:
            return
        def disable_login(self):
            self.allow_login=False
        # Disable logins 5 minutes beforehand
        threading.Timer(interval=max(0, timer_seconds/60 - (5 * 60)), function=disable_login, args=(self,)).start()
        # Perform shutdown
        threading.Timer(interval=timer_seconds/60, function=self._shutdown).start()

    def quit_cli(self):
        if self.on_kill_program_instance and callable(self.on_kill_program_instance):
            self.on_kill_program_instance()
            self.on_kill_program_instance = None

    def set_variable(self, variable_name: str, value: Value, permission_override: bool = False) -> None:
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
        if variable.readonly and not permission_override:
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
        parsed_path = Path(path)
        data_raw = self._filesystem.read(parsed_path)
        try:
            data_str = data_raw.decode()
            xml_root = ElementTree.fromstring(data_str)
        except UnicodeDecodeError as e:
            raise ParseError(f"Unicode error: {e}")
        except ElementTree.ParseError as e:
            raise ParseError(f"XML error: {e}")

        if xml_root.tag.lower() != "settings":
            raise ParseError("Root tag is not <Settings>")
        for child in xml_root:
            text = child.text
            if not text:
                text = ""
            # IP_WindowSecList is a special case
            if child.tag == "IP_WindowSecList":
                try:
                    self._settings["IP_WindowSecList"] = [
                        float(s) for s in text.split()
                    ]
                except Exception:
                    raise ParseError(
                        f"Failed to parse {child.tag} '{text}' as list of floats"
                    )
            if child.tag in self._settings:
                try:
                    tag_type = type(self._settings[child.tag])
                    if issubclass(tag_type, list): # Assume only floats
                        values = [float(x) for x in text.split()]
                        self._settings[child.tag] = values
                    else:
                        self._settings[child.tag] = tag_type(text)
                except Exception:
                    raise ParseError(
                        f"Failed to parse {child.tag} '{text}' as {type(self._settings[child.tag])}"
                    )

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
        self._current_project_name = resolved_name

        project_path = Path(f"/media/mmcblk0p1/projects/{resolved_name}")
        project_name_path = project_path.joinpath("project_name.txt")
        self._filesystem.make_dir(project_path)
        self._filesystem.make_file(project_name_path)
        self._filesystem.write(project_name_path, resolved_name.encode())

        return resolved_name

    def create_task(
        self,
        name: str,
        spread_file: str,
        protocol_file: str,
        spacing: tuple[float, float, float],
        base_reference: tuple[float, float, float],
    ) -> tuple[Task, str]:
        """Add a task to the current project. Returns the task and non-fatal errors."""
        if self._current_project_name not in self._projects:
            raise RuntimeError("Current project is not set or does not exist.")
        project = self._projects[self._current_project_name]
        errors = ""

        def failed_to_open_file(path: str) -> str:
            return f"""{path} Couldn't load {path} <ticpp.cpp@645>
Description: Failed to open file
File: {path}
Line: 0
Column: 0"""

        spread = None
        try:
            spread = Spread.parse(self._filesystem.read(Path(spread_file)).decode())
        except OSError:
            errors += f"Load spread exception {failed_to_open_file(spread_file)}"

        protocol = None
        try:
            protocol = Protocol.parse(
                self._filesystem.read(Path(protocol_file)).decode()
            )
        except OSError:
            # newline for protocol but not spread is intentional
            errors += (
                f"XML Protocol file exception: {failed_to_open_file(protocol_file)}\n"
            )

        return (
            project.create_task(
                name,
                spread_file,
                protocol_file,
                spread,
                protocol,
                spacing,
                base_reference,
            ),
            errors,
        )

    def create_station(self, index_selection: str) -> Task.CreateStationResult:
        if self._current_project_name not in self._projects:
            raise RuntimeError("Current project is not set or does not exist.")
        project: Project = self._projects[self._current_project_name]
        return project.create_station(index_selection)

    def measure(self):
        """Perform measurements"""        
        # Get the project and tasks to work on
        if self._current_project_name not in self._projects:
            return
        project = self._projects[self._current_project_name]
        unfinished_tasks = [task for task in project.tasks if not task.is_complete]
        
        self.set_variable("measure", value=1, permission_override=True)
            
        while len(unfinished_tasks) > 0:
            # Get task
            current_task = unfinished_tasks[0]
            # Make sure task is still relevant
            if current_task not in project.tasks or current_task.is_complete:
                unfinished_tasks.pop(0)
                continue

            # Perform task
            time.sleep(0.1) # Pretend to measure
            
            # Finish task
            current_task.is_complete = True
            unfinished_tasks.pop(0)

        self.set_variable("measure", 0, permission_override=True)
    
    ### Interface to the file system ###
    def canonical_absolute_path(self, path: str, relative_to: str | None = None) -> Path:
        """Raises ValueError if path is relative and relative_to is relative or None"""
        parsed_path = Path(path)
        if not parsed_path.is_absolute():
            if not relative_to:
                raise ValueError("No absolute path provided as reference")
            parsed_path = Path(relative_to).joinpath(parsed_path)
            if not parsed_path.is_absolute():
                raise ValueError(f"'{relative_to}' is not an absolute path.")
        return self._filesystem.canonical_path(parsed_path)
    
    def touch(self, file_path: str, relative_to: str | None = None):
        """Approximates the Unix `touch` command. Creates a file at path if it does not exist.  
        Raises FileNotFoundException if the directory containing the file doesn't exist.   
        Raises NotADirectoryError if part of path is not a directory."""
        try:
            parsed_path = self.canonical_absolute_path(file_path, relative_to)
            self._filesystem.make_file(parsed_path)
        except IsADirectoryError:
            pass
        except FileExistsError:
            pass
        except ValueError:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), file_path)

    def list_folder(self, folder_path: str, relative_to: str | None = None) -> list[str]:
        """Get list of files in folder.
        Raises TypeError if the path is of the wrong type  
        Raises FileNotFoundException if the path does not exist.   
        Raises PermissionError if user does not have permission.   
        Raises NotADirectoryError if the target is not a directory.
        """
        if not isinstance(folder_path, str):
            raise TypeError(f"Expected 'str', but got '{type(folder_path).__name__}'")
        try:
            parsed_path = self.canonical_absolute_path(folder_path, relative_to)
        except ValueError:
            raise FileNotFoundError()
        return self._filesystem.list_folder(parsed_path)

    def open_file(self, file_path: str, relative_to: str | None = None) -> BytesIO:
        """Get BytesIO object for file at path.  
        Raises TypeError if the path is of the wrong type  
        Raises FileNotFoundException if the file does not exist.   
        Raises PermissionError if file can not be opened.   
        Raises IsADirectoryError if path points to a directory."""
        if not isinstance(file_path, str):
            raise TypeError(f"Expected 'str', but got '{type(file_path).__name__}'")
        try:
            parsed_path = self.canonical_absolute_path(file_path, relative_to)
        except ValueError:
            raise FileNotFoundError()
        return self._filesystem.get_file(parsed_path)
    
    def write_file(self, file_path: str, data: bytes = b'', relative_to: str | None = None, append: bool = False):
        """Writes data to file at path.  
        Raises TypeError if any argument is of the wrong type
        Raises FileNotFoundException if the directory containing the file does not exist.   
        Raises IsADirectoryError if path points to a directory.  
        Raises NotADirectoryError if part of path is not a directory."""
        try:
            parsed_path = self.canonical_absolute_path(file_path, relative_to)
        except ValueError:
            raise FileNotFoundError()
        if not self._filesystem.exists(parsed_path):
            self._filesystem.make_file(parsed_path)
        if append:
            file = self._filesystem.get_file(parsed_path)
            file.seek(0, 2)
            file.write(data)
        else:
            self._filesystem.write(parsed_path, data)
        
    def write_file_utf8(self, file_path: str, data: str = '', relative_to: str | None = None, append: bool = False):
        """Writes string to file at path.  
        Raises TypeError if any argument is of the wrong type
        Raises FileNotFoundException if the directory containing the file does not exist.   
        Raises IsADirectoryError if path points to a directory.  
        Raises NotADirectoryError if part of path is not a directory."""
        self.write_file(file_path, data=data.encode("utf-8"), relative_to=relative_to, append=append)

    def read_file(self, file_path: str, relative_to: str | None = None) -> bytes:
        """Read data from file at path.  
        Raises TypeError if any argument is of the wrong type
        Raises FileNotFoundException if the directory containing the file does not exist.   
        Raises IsADirectoryError if path points to a directory.  
        Raises NotADirectoryError if part of path is not a directory."""
        parsed_path = self.canonical_absolute_path(file_path, relative_to)
        return self._filesystem.read(parsed_path)

    def make_directory(self, path: str, relative_to: str | None = None):
        parsed_path = self.canonical_absolute_path(path, relative_to)
        self._filesystem.make_dir(parsed_path)

    def remove(self, path: str, relative_to: str | None = None, recursive: bool = False):
        """Removes a file.    
        If recursive is True and the target is a directory, removes directory and all subdirectories and files.  
        Raises IsADirectoryError if recursive is False and the target is a directory.   
        Raises FileNotFoundException if path doesn't point to a file or directory.
        """
        parsed_path = self.canonical_absolute_path(path, relative_to)
        self._filesystem.remove(parsed_path, recursive)

    def path_exists(self, path: str, relative_to: str | None = None) -> bool:
        """Checks if a file or directory exists at a path.
        Returns True if it exists and False if it does not.
        Raises NotADirectoryError if part of path is not a directory."""
        parsed_path = self.canonical_absolute_path(path, relative_to)
        return self._filesystem.exists(parsed_path)

    def stat(self, path, relative_to: str | None = None) -> os.stat_result:
        parsed_path = self.canonical_absolute_path(path, relative_to)
        return self._filesystem.stat(parsed_path)