"""For generating configuration files from test case parameters."""
import json
import tempfile

from gemeaspy.settings import config
from gemeaspy.tests import parameter_spec
from gemeaspy.tests.test_case import AcquisitionTestCase, AcquisitionTestCaseParameters
from gemeaspy.tests.util import random_string

INVALID_FILE = ")(/&%¤~#\"!"

def _create_connection_settings(test: AcquisitionTestCase, server_port: int):
    connection_settings: dict[str, str | int | bool | None] = {
        "username": "root",
        "look_for_keys": False,
    }

    match test.parameters.connection_hostname:
        case parameter_spec.INVALID_HOSTNAME:
            connection_settings["hostname"] = f"{random_string()}.invalid"
        case None:
            pass
        case x:
            connection_settings["hostname"] = x

    match test.parameters.connection_port:
        case parameter_spec.VALID_PORT:
            connection_settings["port"] = server_port
        case None:
            pass
        case x:
            connection_settings["port"] = x

    match test.parameters.connection_password:
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

    match test.parameters.config_projects_folder:
        case parameter_spec.INVALID_FILE:
            config.TERRAMETER_PROJECTS_FOLDER = f"/media/mmcblk0p1/{random_string()}"
        case x:
            config.TERRAMETER_PROJECTS_FOLDER = x

    match test.parameters.config_local_data_path:
        case parameter_spec.VALID_LOCAL_DATA_PATH:
            f = tempfile.TemporaryDirectory(prefix="gemeaspytest_data_")
            tempfiles.append(f)
            config.LOCAL_PATH_TO_DATA = f.name
        case parameter_spec.INVALID_FILE:
            config.LOCAL_PATH_TO_DATA = INVALID_FILE
        case _:
            raise ValueError("invalid config_local_data_path")

    match test.parameters.config_connection_file:
        case parameter_spec.VALID_CONNECTION_FILE:
            f = _create_connection_settings(test, server_port)
            tempfiles.append(f)
            config.TERRAMETER_CONNECTION_FILE = f.name
        case parameter_spec.INVALID_FILE:
            config.TERRAMETER_CONNECTION_FILE = INVALID_FILE
        case _:
            raise ValueError("invalid config_connection_file")

    def _cleanup():
        for f in tempfiles:
            f.__exit__(None, None, None)

    return _cleanup


if __name__ == "__main__":
    test_case = AcquisitionTestCase(_parameters=AcquisitionTestCaseParameters(
        config_projects_folder=parameter_spec.VALID_PROJECTS_FOLDER,
        config_local_data_path=parameter_spec.VALID_LOCAL_DATA_PATH,
        config_connection_file=parameter_spec.VALID_CONNECTION_FILE,
        connection_hostname=parameter_spec.INVALID_HOSTNAME,
        connection_port=-1,
        connection_password=None,
    )
    )
    setup(test_case, 2222)
    print(config.TERRAMETER_PROJECTS_FOLDER)
    print(config.LOCAL_PATH_TO_DATA)
    print(config.TERRAMETER_CONNECTION_FILE)
