class GeMeasPyError(Exception):
    def __init__(self, msg: str):
        Exception.__init__(self, msg)
        self.msg = msg

class ConfigFileError(GeMeasPyError):
    def __init__(self, msg: str, file: str | None=None):
        GeMeasPyError.__init__(self, msg)
        self.file = file