class GeMeasPyError(Exception):
    def __init__(self, msg: str):
        Exception.__init__(self, msg)
        self.msg = msg

class ConfigFileError(GeMeasPyError):
    def __init__(self, msg: str, file: str | None=None):
        GeMeasPyError.__init__(self, msg)
        self.file = file

class TransferError(GeMeasPyError):
    def __init__(self, msg: str, file: str | None=None):
        GeMeasPyError.__init__(self, msg)
        self.file = file

class SSHConnectionError(GeMeasPyError):
    def __init__(self, msg: str, params: dict):
        GeMeasPyError.__init__(self, msg)
        self.params = params

class TaskFileIOError(GeMeasPyError):
    def __init__(self, file: str):
        GeMeasPyError.__init__(self, "File could not be read")
        self.file = file

class TaskFileParseError(GeMeasPyError):
    def __init__(self, msg: str, file: str | None = None):
        GeMeasPyError.__init__(self, msg)
        self.file = file

class MissingFileError(GeMeasPyError):
    def __init__(self, msg: str, file: str):
        GeMeasPyError.__init__(self, msg)
        self.file = file
        
class InvalidLocalDirectoryError(GeMeasPyError):
    def __init__(self, msg: str, dir: str):
        GeMeasPyError.__init__(self, msg)
        self.dir = dir
        
class ProjectTransferError(GeMeasPyError):
    def __init__(self, msg: str, local_dir: str, remote_dir: str):
        GeMeasPyError.__init__(self, msg)
        self.remote_dir = remote_dir
        self.local_dir = local_dir