import json
import os
import sys
import tempfile

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from settings import config
from tests import parameter_spec
from tests.test_case import AcquisitionTestCase
from tests.util import random_string


def _create_connection_settings(test: AcquisitionTestCase, server_port: int):
    connection_settings: dict[str, str | int | bool | None] = {
        "username": "root",
        "look_for_keys": False,
    }

    match test.connection_hostname:
        case parameter_spec.INVALID_HOSTNAME:
            connection_settings["hostname"] = f"{random_string()}.invalid"
        case None:
            pass
        case x:
            connection_settings["hostname"] = x

    match test.connection_port:
        case parameter_spec.VALID_PORT:
            connection_settings["port"] = server_port
        case None:
            pass
        case x:
            connection_settings["port"] = x

    match test.connection_password:
        case parameter_spec.INVALID_PASSWORD:
            connection_settings["password"] = random_string()
        case None:
            pass
        case x:
            connection_settings["password"] = x

    f = tempfile.NamedTemporaryFile(
        mode="w",
        prefix="gemeaspytest_connection_settings_",
        suffix=".json",
        delete_on_close=False,
    )
    json.dump(connection_settings, f)
    f.close()
    return f


def setup(test: AcquisitionTestCase, server_port: int):
    tempfiles = []

    match test.config_projects_folder:
        case parameter_spec.INVALID_FILE:
            config.TERRAMETER_PROJECTS_FOLDER = f"/media/mmcblk0p1/{random_string()}"
        case x:
            config.TERRAMETER_PROJECTS_FOLDER = x

    match test.config_local_data_path:
        case parameter_spec.VALID_LOCAL_DATA_PATH:
            f = tempfile.TemporaryDirectory(prefix="gemeaspytest_data_")
            tempfiles.append(f)
            config.LOCAL_PATH_TO_DATA = f.name
        case parameter_spec.INVALID_FILE:
            config.LOCAL_PATH_TO_DATA = f"{random_string()}/{random_string()}"
        case _:
            raise ValueError("invalid config_local_data_path")

    match test.config_connection_file:
        case parameter_spec.VALID_CONNECTION_FILE:
            f = _create_connection_settings(test, server_port)
            tempfiles.append(f)
            config.TERRAMETER_CONNECTION_FILE = f.name
        case parameter_spec.INVALID_FILE:
            config.TERRAMETER_CONNECTION_FILE = random_string()
        case _:
            raise ValueError("invalid config_connection_file")

    def _cleanup():
        for f in tempfiles:
            f.__exit__(None, None, None)

    return _cleanup


if __name__ == "__main__":
    test_case = AcquisitionTestCase(
        config_projects_folder=parameter_spec.VALID_PROJECTS_FOLDER,
        config_local_data_path=parameter_spec.VALID_LOCAL_DATA_PATH,
        config_connection_file=parameter_spec.VALID_CONNECTION_FILE,
        connection_hostname=parameter_spec.INVALID_HOSTNAME,
        connection_port=-1,
        connection_password=None,
    )
    setup(test_case, 2222)
    print(config.TERRAMETER_PROJECTS_FOLDER)
    print(config.LOCAL_PATH_TO_DATA)
    print(config.TERRAMETER_CONNECTION_FILE)
