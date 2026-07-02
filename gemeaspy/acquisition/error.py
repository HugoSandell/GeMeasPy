import sys
import os
import traceback
from paramiko import ChannelException
from gemeaspy.acquisition.logger import logger

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
        
class TerrameterResponseError(GeMeasPyError):
    def __init__(self, msg: str):
        GeMeasPyError.__init__(self, msg)
        

def handle_exception(e: Exception) -> int:
    """Print error message, log exception, and return an exit code"""
    
    verbose = "DEBUG" in os.environ
    if isinstance(e, ChannelException):
        print("Error: Failed to create SSH channel connection to Terrameter!")
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        logger.error(f"ChannelException - [{e.code}] {e.text}", exc_info=True)
        return 3
    elif isinstance(e, ConfigFileError):
        print(f"Error: {e.msg} ({e.file})")
        logger.error(f"ConfigFileError - [{e.file}] {e.msg}", exc_info=True)
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        return 4
    elif isinstance(e, TransferError):
        print(f"Error: Project transfer failed - {e.msg} ({e.file})")
        logger.error(f"TransferError - [{e.file}] {e.msg}", exc_info=True)
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        return 5
    elif isinstance(e, SSHConnectionError):
        print(f"Error: A connection error occured - {e.msg}")
        logger.error(f"SSHConnectionError - [{e.params}] {e.msg}", exc_info=True)
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        return 6
    elif isinstance(e, TaskFileIOError):
        print(f"Error: Failed to read task file {e.file!r}!")
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        logger.error(f"TaskFileIOError - Failed to read {e.file!r}", exc_info=True)
        return 7
    elif isinstance(e, TaskFileParseError):
        if e.file is None:
            print(f"Error: Failed to parse task file: {e.msg}")
        else:
            print(f"Error: Failed to parse task file {e.file!r}: {e.msg}")
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        logger.error(f"TaskFileParseError - {e.msg}", exc_info=True)
        return 8
    elif isinstance(e, MissingFileError):
        print(f"Error: Task file references a non-existent file - {e.msg} {e.file!r}")
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        logger.error(f"MissingFileError - {e.msg} {e.file!r}", exc_info=True)
        return 9
    elif isinstance(e, InvalidLocalDirectoryError):
        print(f"Error: Local data directory {e.dir!r} could not be used - {e.msg}")
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        logger.error(f"InvalidLocalDirectory - {e.msg} {e.dir!r}", exc_info=True)
        return 10
    elif isinstance(e, ProjectTransferError):
        print(f"Error: Project transfer from remote directory {e.remote_dir} to local directory {e.local_dir} failed - {e.msg}")
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        logger.error(f"ProjectTransferError - {e.msg} {e.remote_dir!r} -> {e.local_dir!r}", exc_info=True)
        return 11
    elif isinstance(e, TerrameterResponseError):
        print(f"Error: Failure caused by response from Terrameter - {e.msg}")
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        logger.error(f"TerrameterResponseError - {e.msg}", exc_info=True)
        return 12
    return -1