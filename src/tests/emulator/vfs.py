""" Provides a virtual file system for the Terrameter emulator"""

from typing import  *
import os.path
from pathlib import PurePosixPath as Path

class _Node:
    def __init__(self, name: str):
        self.name = name
        self.is_dir = False
        self.is_file = False

class _File(_Node):
    def __init__(self, name: str, content: bytes = b''):
        super(_File, self).__init__(name)
        self.content: bytes = content
        self.is_file = True

class _Dir(_Node):
    def __init__(self, name: str):
        super(_Dir, self).__init__(name)
        self.children: Dict[str, _Node] = {}
        self.is_dir = True
    def __contains__(self, name: str):
        return name in self.children
    def __getitem__(self, key: str):
        return self.children[key]

class VirtualFileSystem:
    def __init__(self):
        self._root = _Dir("")
        self._root.children['/'] = _Dir('/')
        self._root.children['\\'] = self._root.children['/']
    
    def _traverse(self, path: Path) -> _Node:
        if path.parts[0] == "~": 
            #Resolve ~ for home dir
            path = Path("/home/root").joinpath(Path("/".join(path.parts[1:])))
        
        parts = list(path.parts)

        current_node = self._root
        while len(parts) > 0:
            next_name = parts.pop(0)
            if next_name in current_node:
                current_node = current_node[next_name]
                if len(parts) == 0:
                    return current_node
            else:
                raise FileNotFoundError(f"[Errno 2] No such file or directory: '{path}'")

    def exists(self, path: Path):
        try:
            self._traverse(path)
        except FileNotFoundError:
            return False
        finally:
            return True
    
    def read(self, path: Path) -> bytes:
        """Read file. Raises FileNotFoundError if file doesn't exist, or PermissionError if file can't be read."""
        file = self._traverse(path) 
        if hasattr(file, 'content'):
            return file.content
        else:
            raise PermissionError("[Errno 13] Permission denied: '{}'")
        
    def write(self, path: Path, data: bytes):
        """Write data to file. 
        Raises FileNotFoundError if file doesn't exist. 
        Raises PermissionError if file can't be written to."""
        file = self._traverse(path) 
        if hasattr(file, 'content'):
            file.content = data
        else:
            raise PermissionError("[Errno 13] Permission denied: '{}'")
    
    def _make_node(self, path: Path, node_type: type[_File | _Dir]):
        if node_type is not type[_File | _Dir]:
            return
        if self.exists(path):
            return
        node_name = path.name
        parent = self._traverse(path.parent.as_posix())
        if type(parent) != _Dir:
            raise PermissionError("[Errno 13] Permission denied: '{}'")
        else:
            parent.children[node_name] = node_type(node_name)
    
    def make_file(self, path: Path):
        """Create a new file at `path`
        Raises PermissionError
        Raises FileNotFoundError"""
        print("Making file: " + path.as_posix())
        self._make_node(path, _File)
        if self.exists(path):
            print("File exists now!")
        else:
            print("Warning: file still doesn't exist!")
        
        
    def make_dir(self, path: Path):
        """Create a new file at `path`
        Raises PermissionError
        Raises FileNotFoundError"""
        self._make_node(path, _Dir)