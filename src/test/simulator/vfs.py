""" Provides a virtual file system for the Terrameter emulator"""

from typing import  *
import os.path
import pathlib

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
    
    def _traverse(self, path: str) -> _Node:
        parts = list(pathlib.PurePosixPath(path).parts)
        current_node = self._root
        while len(parts) > 0:
            next_name = parts.pop(0)
            if next_name in current_node:
                current_node = current_node[next_name]
                if len(parts) == 0:
                    return current_node
            else:
                raise FileNotFoundError(f"[Errno 2] No such file or directory: '{path}'")

    def exists(self, path: str):
        try:
            self._traverse(path)
        except FileNotFoundError:
            return False
        finally:
            return True
    
    def read(self, path: str) -> bytes:
        """Read file. Raises FileNotFoundError if file doesn't exist, or PermissionError if file can't be read."""
        file = self._traverse(path) 
        if hasattr(file, 'content'):
            return file.content
        else:
            raise PermissionError("[Errno 13] Permission denied: '{}'")
        
    def write(self, path: str, data: bytes):
        """Write data to file. Raises FileNotFoundError if file doesn't exist, or PermissionError if file can't be written to."""
        file = self._traverse(path) 
        if hasattr(file, 'content'):
            file.content = data
        else:
            raise PermissionError("[Errno 13] Permission denied: '{}'")