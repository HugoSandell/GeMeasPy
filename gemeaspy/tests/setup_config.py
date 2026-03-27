"""For generating configuration files from test case parameters."""

import json
import os
import tempfile

from gemeaspy.settings import config
from gemeaspy.tests import parameter_spec
from gemeaspy.tests.test_case import AcquisitionTestCase, AcquisitionTestCaseParameters
from gemeaspy.tests.util import random_string


def _create_connection_settings(test: AcquisitionTestCase, server_port: int):
    connection_settings: dict[str, str | int | bool | None] = {
        "username": "root",
        "allow_agent": False,
        "look_for_keys": False,
    }

    match test.parameters.connection_hostname:
        case parameter_spec.INVALID_HOSTNAME:
            connection_settings["hostname"] = f"hostname-{random_string()}.invalid"
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
            connection_settings["password"] = f"password_{random_string()}"
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


class ConfigState:
    _tempfiles = []
    _data_invalid_path = None
    _data_invalid_content = None

    def __init__(self, test: AcquisitionTestCase, server_port: int):
        match test.parameters.config_projects_folder:
            case parameter_spec.INVALID_FILE:
                config.TERRAMETER_PROJECTS_FOLDER = (
                    f"/media/mmcblk0p1/gemeaspytest_projects_{random_string()}"
                )
            case x:
                config.TERRAMETER_PROJECTS_FOLDER = x

        match test.parameters.config_local_data_path:
            case parameter_spec.VALID_LOCAL_DATA_PATH:
                f = tempfile.TemporaryDirectory(prefix="gemeaspytest_data_")
                self._tempfiles.append(f)
                config.LOCAL_PATH_TO_DATA = f.name
            case parameter_spec.INVALID_FILE:
                f = tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix="gemeaspytest_data_invalid_",
                    delete_on_close=False,
                )
                self._data_invalid_content = random_string().encode()
                f.write(self._data_invalid_content)
                f.close()
                self._tempfiles.append(f)
                config.LOCAL_PATH_TO_DATA = self._data_invalid_path = f.name
            case _:
                raise ValueError("invalid config_local_data_path")

        match test.parameters.config_connection_file:
            case parameter_spec.VALID_CONNECTION_FILE:
                f = _create_connection_settings(test, server_port)
                self._tempfiles.append(f)
                config.TERRAMETER_CONNECTION_FILE = f.name
            case parameter_spec.INVALID_FILE:
                config.TERRAMETER_CONNECTION_FILE = (
                    f"connection_settings_{random_string()}"
                )
            case _:
                raise ValueError("invalid config_connection_file")

    def cleanup(self):
        for f in self._tempfiles:
            f.__exit__(None, None, None)

    def data_invalid_is_modified(self):
        if self._data_invalid_path is None or self._data_invalid_content is None:
            # nothing to check
            return False

        if not os.path.isfile(self._data_invalid_path):
            return True

        with open(self._data_invalid_path, "rb") as f:
            if f.read(len(self._data_invalid_content)) != self._data_invalid_content:
                return True

            # ensure no extra data has been written
            if f.read(1) != b"":
                return True

        return False


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
    state = ConfigState(test_case, 2222)
    print(config.TERRAMETER_PROJECTS_FOLDER)
    print(config.LOCAL_PATH_TO_DATA)
    print(config.TERRAMETER_CONNECTION_FILE)
    state.cleanup()
