import pytest
from typing import *
import io
import acquisition
import acquisition.utilities
import main
from src.tests.emulator import InstrumentServerEmulator
from io import StringIO

_port = 0
_task_list = ""
_connection_parameters = {"hostname": "localhost", "port": 0, "username": "root", "password": "", "look_for_keys": False}

@pytest.fixture(autouse=True)
def init_config():
    global _task_list, _connection_parameters
    _task_list = []
    _connection_parameters = {"hostname": "localhost",
        "port": _port,
        "username": "root",
        "password": "",
        "look_for_keys": False}

@pytest.fixture
def patch_task_list(monkeypatch):
    class FileWrapper:
        def __init__(self, file):
            self.file = file
        def __enter__(self):
            return self.file
        def __exit__(self, exc_type, exc_value, traceback):
            return

    def _open(file, *args):
        if file == "!test/task/list!":
            fio = StringIO()
            fio.write(_task_list)
            fio.flush()
            fio.seek(0)
            return FileWrapper(fio)
        return io.open(file, *args)
    import builtins
    monkeypatch.setattr(builtins, "open", _open)
    
@pytest.fixture
def patch_connection_parameters(monkeypatch):
    monkeypatch.setattr(acquisition.utilities, "read_terrameter_connection_parameters", lambda: _connection_parameters)

@pytest.fixture(autouse=True)
def test_server():
    global _connection_parameters
    instrument = InstrumentServerEmulator()
    instrument.start()
    _connection_parameters["port"] = instrument.address[1]
    yield instrument
    instrument.stop()

def test_empty_tasks(patch_connection_parameters, patch_task_list):
    main.run("!test/task/list!")

def test_one(patch_connection_parameters, patch_task_list):
    global _task_list
    _task_list = "2 0\nTask1\n2X21.xml\nGradient_2x21.xml\nCABIN.settings\n1 1 1"
    main.run("!test/task/list!")