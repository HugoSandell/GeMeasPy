""" Provides a virtual file system for the Terrameter emulator"""
import errno
import os
from collections import deque
from io import BytesIO
from pathlib import PurePath as _HostPlatformPath
from pathlib import PurePosixPath as Path

from gemeaspy.tests.terrameter_model._logging import logger

_INIT_PATH = os.path.join(os.path.dirname(__file__), "file_system_init")

class _Node:
    def __init__(self, name: str, parent: "_Node | None"):
        self.name: str = name
        self.is_dir: bool = False
        self.is_file: bool = False
        self.parent: _Node = self
        if parent:
            self.parent = parent
    def __str__(self) -> str:
        path = []
        i: _Node = self
        while i.parent is not i:
            path.insert(0, i.name)
            i = i.parent
        if i.name: # root has name=""
            path.insert(0, i.name)
        return Path(*path).as_posix()
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self)!r})"

class _File(_Node):
    def __init__(self, name: str, parent: _Node | None, content: bytes = b''):
        super(_File, self).__init__(name, parent)
        self.content: BytesIO = BytesIO(content)
        self.is_file = True
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self)!r})"

class _Dir(_Node):
    def __init__(self, name: str, parent: _Node | None):
        super(_Dir, self).__init__(name, parent)
        self.children: dict[str, _Node] = {}
        self.is_dir = True
    def __contains__(self, name: str):
        return name in self.children
    def __getitem__(self, key: str):
        return self.children[key]
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self)!r})"

class VirtualFileSystem(object):
    def __init__(self):
        self._root = _Dir("", None)
        self._root.children['/'] = _Dir('/', None)

    def load_initial_fs(self):
        for parent, child_dirs, child_files in os.walk(_INIT_PATH):
            relative_path = _HostPlatformPath(os.path.relpath(parent, _INIT_PATH)).as_posix()
            parent_vfs = Path("/", relative_path)

            for child in child_dirs:
                self.make_dir(parent_vfs.joinpath(child))

            for child in child_files:
                if child == ".gitkeep":
                    continue
                child_vfs = parent_vfs.joinpath(child)
                self.make_file(child_vfs)
                with open(os.path.join(parent, child), "rb") as f:
                    self.write(child_vfs, f.read())

    def canonical_path(self, path: Path) -> Path:
        """Returns the canonical form of the path with '..' and '.' parts resolved"""
        parts = deque(maxlen = len(path.parts))
        for part in path.parts:
            if part == ".":
                pass
            elif part == ".." and len(parts) != 0 and parts[-1] != "..":
                # '/..' should refer to '/'
                if not (len(parts) == 1 and parts[0] == "/"):
                    parts.pop()
            else:
                parts.append(part)
        return Path(*parts)

    def _traverse(self, path: Path) -> _Node:
        parts = list(path.parts)

        current_node = self._root
        while len(parts) > 0:
            next_name = parts.pop(0)
            if not isinstance(current_node, _Dir):
                raise NotADirectoryError(
                    errno.ENOTDIR, os.strerror(errno.ENOTDIR), path.as_posix()
                )
            if next_name in current_node:
                current_node = current_node[next_name]
            elif next_name == ".":
                continue
            elif next_name == "..":
                current_node = current_node.parent
            else:
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path.as_posix())
        return current_node

    def exists(self, path: Path):
        try:
            self._traverse(path)
        except (FileNotFoundError, NotADirectoryError):
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
        if isinstance(file, _File):
            return file.content
        else:
            raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), path.as_posix())

    def read(self, path: Path) -> bytes:
        """Read file into and return a bytes buffer.
        Raises FileNotFoundError if file does not exist.  
        Raises IsADirectoryError if path points to a directory.   
        Raises PermissionError if file cannot be read."""
        file = self._traverse(path) 
        if isinstance(file, _File):
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
        if isinstance(file, _File):
            io: BytesIO = file.content
            io.truncate(0)
            io.seek(0)
            io.write(data)
        else:
            raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), path.as_posix())
    
    def remove(self, path: Path, recursive: bool = False):
        """Removes a file.    
        If recursive is True and the target is a directory, removes directory and all subdirectories and files.  
        Raises IsADirectoryError if recursive is False and the target is a directory.   
        Raises FileNotFoundException if path doesn't point to a file or directory.
        """
        logger.debug(f"Removing {path.as_posix()} {"recursively" if recursive else "nonrecursively"}.")
        node = self._traverse(path)
        if not recursive and isinstance(node, _Dir):
            raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), path.as_posix())
        if node.parent is node:
            raise PermissionError(errno.EPERM, os.strerror(errno.EPERM), path.as_posix())
        if isinstance(node.parent, _Dir):
            removed_dir = Path("/removed")
            new_path = removed_dir.joinpath(Path(*path.parts[1:])) # Keep removed files for later inspection
            for prefix_len in range(2, len(new_path.parent.parts) + 1):
                self.make_dir(
                    Path(*new_path.parent.parts[0:prefix_len]), ignore_existing=True
                )
            self.move(path, new_path, recursive)

    def move(self, src: Path, dst: Path, recursive: bool = False):
        """Move a file from src to dst.
        If recursive is True, recursively move all subdirectories and files under the given src.
        Raises IsADirectoryError if recursive is False and the src is a directory.
        Raises FileNotFoundException if src doesn't point to an existing file or directory.
        """
        src_node = self._traverse(src)
        if not recursive and isinstance(src_node, _Dir):
            raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), src.as_posix())

        if self.exists(dst) and isinstance(self._traverse(dst), _Dir):
            dst_parent = self._traverse(dst)
            dst_name = src_node.name
        else:
            dst_parent = self._traverse(dst.parent)
            dst_name = dst.name
        if not isinstance(dst_parent, _Dir):
            raise NotADirectoryError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), dst.as_posix())

        if isinstance(src_node.parent, _Dir):
            src_node.parent.children.pop(src_node.name)
        src_node.name = dst_name
        src_node.parent = dst_parent
        dst_parent.children[dst_name] = src_node



    def _make_node(self, path: Path, node_type: type[_File | _Dir], ignore_existing: bool = False):
        if node_type not in {_File, _Dir}:
            return
        if self.exists(path):
            if ignore_existing:
                return
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), path.as_posix())
        node_name = path.name
        parent = self._traverse(path.parent)
        if not isinstance(parent, _Dir):
            raise NotADirectoryError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), path.as_posix())
        else:
            parent.children[node_name] = node_type(node_name, parent)
            logger.debug(f"Added node {node_name} with parent {parent}")
    
    def make_file(self, path: Path, ignore_existing: bool = False):
        """Create a new file at `path`  
        Raises NotADirectoryError if a part of the path is a file.  
        Raises FileExistsError if path already exists.
        Raises FileNotFoundError if directory does not exist"""
        self._make_node(path, _File, ignore_existing)
        
    def make_dir(self, path: Path, ignore_existing: bool = False):
        """Create a new directory at `path`
        Raises NotADirectoryError if a part of the path is a file
        Raises FileNotFoundError if parent directory does not exist
        Raises FileExistsError if directory already exists"""
        self._make_node(path, _Dir, ignore_existing)
        
    def stat(self, path: Path) -> os.stat_result:
        node = self._traverse(path)
        # File type masks
        S_IFREG =   0o0100000 # Regular file
        S_IFDIR =   0o0040000 # directory

        S_IRUSR =    0o00400   # owner has read permission
        S_IWUSR =   0o00200   # owner has write permission

        S_IRGRP =   0o00040   # group has read permission
        S_IWGRP =   0o00020   # group has write permission

        S_IROTH =   0o00004   # others have read permission
        S_IWOTH =   0o00002   # others have write permission
 
        mode = S_IRUSR | S_IWUSR | S_IRGRP | S_IWGRP | S_IROTH | S_IWOTH
        size = 0
        
        if isinstance(node, _Dir):
            mode |= S_IFDIR
        elif isinstance(node, _File):
            mode |= S_IFREG
            size = len(node.content.getvalue())

        stats = {"st_mode": mode, "st_ino": 0, "st_dev": 0, "st_nlink": 1, "st_uid": 0, "st_gid": 0, "st_size": size, "st_atime": 0, "st_mtime": 0, "st_ctime": 0} 
        logger.debug(f"stat for {path.as_posix()} executed with result {stats}")
        return os.stat_result(stats.values())
        