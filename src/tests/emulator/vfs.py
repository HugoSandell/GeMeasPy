""" Provides a virtual file system for the Terrameter emulator"""

from typing import  *
from pathlib import PurePath as _HostPlatformPath
from pathlib import PurePosixPath as Path
import errno
import os
from io import BytesIO

_INIT_PATH = os.path.join(os.path.dirname(__file__), "file_system_init")

class _Node:
    def __init__(self, name: str):
        self.name = name
        self.is_dir = False
        self.is_file = False

class _File(_Node):
    def __init__(self, name: str, content: bytes = b''):
        super(_File, self).__init__(name)
        self.content: BytesIO = BytesIO(content)
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

class VirtualFileSystem(object):
    def __init__(self):
        self._root = _Dir("")
        self._root.children['/'] = _Dir('/')
        self._root.children['\\'] = self._root.children['/']

    def load_initial_fs(self):
        for parent, child_dirs, child_files in os.walk(_INIT_PATH):
            relative_path = _HostPlatformPath(os.path.relpath(parent, _INIT_PATH)).as_posix()
            parent_vfs = Path("/", relative_path)

            for child in child_dirs:
                self.make_dir(parent_vfs.joinpath(child))

            for child in child_files:
                child_vfs = parent_vfs.joinpath(child)
                self.make_file(child_vfs)
                with open(os.path.join(parent, child), "rb") as f:
                    self.write(child_vfs, f.read())

    def _traverse(self, path: Path) -> _Node:
        parts = list(path.parts)

        if len(parts) > 0 and parts[0] == "~": 
            #Resolve ~ for home dir
            path = Path("/home/root").joinpath(Path("/".join(path.parts[1:])))        
        
        current_node = self._root
        while len(parts) > 0:
            next_name = parts.pop(0)
            if not current_node.is_dir:
                raise NotADirectoryError(
                    errno.ENOTDIR, os.strerror(errno.ENOTDIR), path.as_posix()
                )
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
    
    def list_folder(self, path: Path) -> list[str]:
        """Get list of files in folder.
        Raises FileNotFoundException if the path does not exist.   
        Raises PermissionError if user does not have permission.   
        Raises NotADirectoryError if the target is not a directory.
        """
        dir = self._traverse(path)
        if not isinstance(dir, _Dir):
            raise NotADirectoryError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), path.as_posix())
        return list(dir.children.keys())
    
    def get_file(self, path: Path) -> BytesIO:
        """Get file as an I/O object.
        Raises FileNotFoundError if file does not exist.  
        Raises IsADirectoryError if path points to a directory.   
        Raises PermissionError if file cannot be read."""
        file = self._traverse(path) 
        if hasattr(file, 'content'):
            return file.content
        else:
            raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), path.as_posix())

    def read(self, path: Path) -> bytes:
        """Read file into and return a bytes buffer.
        Raises FileNotFoundError if file does not exist.  
        Raises IsADirectoryError if path points to a directory.   
        Raises PermissionError if file cannot be read."""
        file = self._traverse(path) 
        if hasattr(file, 'content'):
            io: BytesIO = file.content
            io.seek(0)
            return io.getvalue()
        else:
            raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), path.as_posix())

    def write(self, path: Path, data: bytes):
        """Truncate file and write data to it. 
        Raises TypeError if any argument is of the wrong type
        Raises FileNotFoundError if file does not exist.
        Raises IsADirectoryError if path points to a directory 
        Raises PermissionError if file cannot be written to."""
        if not isinstance(path, Path):
            raise TypeError(f"Expected type '{Path.__name__}', but got '{type(path).__name__}'")
        if not isinstance(data, bytes):
            raise TypeError(f"Expected type 'bytes', but got '{type(data).__name__}'")
        
        file = self._traverse(path) 
        if hasattr(file, 'content'):
            io: BytesIO = file.content
            io.truncate(0)
            io.seek(0)
            io.write(data)
        else:
            raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), path.as_posix())
    
    def _make_node(self, path: Path, node_type: type[_File | _Dir]):
        if node_type not in {_File, _Dir}:
            return
        if self.exists(path):
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), path.as_posix())
        node_name = path.name
        parent = self._traverse(path.parent)
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