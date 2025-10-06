import pytest
from typing import *
import io
import acquisition
import acquisition.utilities
import main
from src.tests.emulator import InstrumentServerEmulator

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
    def _open(file, *args):
        if file == "!test/task/list!":
            fio = TextIO()
            fio.write(_task_list)
            fio.flush()
            fio.seek(0)
            return fio
        return io.open(file, *args)
    import builtins
    monkeypatch.setattr(acquisition.utilities, "read_monitoring_tasks", lambda _: _task_list)
    monkeypatch.setattr(main, "read_monitoring_tasks", lambda _: _task_list)
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
    return instrument

def test_empty_tasks(patch_connection_parameters, patch_task_list):
    main.run("!test/task/list!")