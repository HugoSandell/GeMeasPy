""" Provides a virtual file system for the Terrameter emulator"""

from typing import  *
from pathlib import PurePosixPath as Path
import errno
import os

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
            if not current_node.is_dir:
                raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), path.as_posix())
            if next_name in current_node:
                current_node = current_node[next_name]
                if len(parts) == 0:
                    return current_node
            else:
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path.as_posix())

    def exists(self, path: Path):
        try:
            self._traverse(path)
        except FileNotFoundError:
            return False
        return True

    def read(self, path: Path) -> bytes:
        """Read file.         
        Raises FileNotFoundError if file does not exist.  
        Raises IsADirectoryError if path points to a directory.   
        Raises PermissionError if file cannot be read."""
        file = self._traverse(path) 
        if hasattr(file, 'content'):
            return file.content
        else:
            raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), path.as_posix())
        
    def write(self, path: Path, data: bytes):
        """Write data to file. 
        Raises FileNotFoundError if file does not exist.
        Raises IsADirectoryError if path points to a directory 
        Raises PermissionError if file cannot be written to."""
        file = self._traverse(path) 
        if hasattr(file, 'content'):
            file.content = data
        else:
            raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), path.as_posix())
    
    def _make_node(self, path: Path, node_type: type[_File | _Dir]):
        if node_type is not type[_File | _Dir]:
            return
        if self.exists(path):
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), path.as_posix())
        node_name = path.name
        parent = self._traverse(path.parent.as_posix())
        if type(parent) != _Dir:
            raise NotADirectoryError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), path.as_posix())
        else:
            parent.children[node_name] = node_type(node_name)
    
    def make_file(self, path: Path):
        """Create a new file at `path`  
        Raises NotADirectoryError if a part of the path is a file.  
        Raises FileExistsError if path already exists.
        Raises FileNotFoundError if directory does not exist"""
        self._make_node(path, _File)
        
    def make_dir(self, path: Path):
        """Create a new file at `path`
        Raises NotADirectoryError if a part of the path is a file    
        Raises FileNotFoundError if parent directory does not exist  
        Raises FileExistsError if directory already exists"""
        self._make_node(path, _Dir)