import json
import os
import sys
import tempfile

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from settings import config
from tests import parameter_spec
from tests.test_case import TestCase
from tests.util import random_string


def _create_connection_settings(test: TestCase):
    # TODO: ensure values are correct
    connection_settings = {
        "username": "root",
    }

    match test["connection_hostname"]:
        case parameter_spec.INVALID_HOSTNAME:
            connection_settings["hostname"] = f"{random_string()}.invalid"
        case None:
            pass
        case x:
            connection_settings["hostname"] = x

    match test["connection_port"]:
        case "":
            connection_settings["port"] = 2222
        case None:
            pass
        case x:
            connection_settings["port"] = x

    match test["connection_password"]:
        case "X":
            connection_settings["password"] = random_string()
        case None:
            pass
        case x:
            connection_settings["password"] = x

    # TODO remove?
    match test["look_for_keys"]:
        case None:
            pass
        case x:
            connection_settings["look_for_keys"] = x

    # TODO cleanup
    fd, path = tempfile.mkstemp(
        prefix="gemeaspytest_connection_settings_", suffix=".json"
    )

    with open(fd, "w") as f:
        json.dump(connection_settings, f)

    return path


def setup(test: TestCase):
    match test["config_projects_folder"]:
        case parameter_spec.VALID_PROJECTS_FOLDER:
            config.TERRAMETER_PROJECTS_FOLDER = "/media/mmcblk0p1/projects"
        case parameter_spec.INVALID_FILE:
            config.TERRAMETER_PROJECTS_FOLDER = f"/media/mmcblk0p1/{random_string()}"
        case _:
            raise ValueError("invalid config_projects_folder")

    match test["config_local_data_path"]:
        case parameter_spec.VALID_LOCAL_DATA_PATH:
            # TODO cleanup
            config.LOCAL_PATH_TO_DATA = tempfile.mkdtemp(prefix="gemeaspytest_data_")
        case parameter_spec.INVALID_FILE:
            config.LOCAL_PATH_TO_DATA = f"{random_string()}/{random_string()}"
        case _:
            raise ValueError("invalid config_local_data_path")

    match test["config_connection_file"]:
        case parameter_spec.VALID_CONNECTION_FILE:
            config.TERRAMETER_CONNECTION_FILE = _create_connection_settings(test)
        case parameter_spec.INVALID_FILE:
            config.TERRAMETER_CONNECTION_FILE = random_string()
        case _:
            raise ValueError("invalid config_connection_file")


if __name__ == "__main__":
    setup(
        {
            "config_projects_folder": parameter_spec.VALID_PROJECTS_FOLDER,
            "config_local_data_path": parameter_spec.VALID_LOCAL_DATA_PATH,
            "config_connection_file": parameter_spec.VALID_CONNECTION_FILE,
            "connection_hostname": parameter_spec.INVALID_HOSTNAME,
            "connection_port": -1,
            "connection_password": None,
            "look_for_keys": None,
        }
    )
    print(config.TERRAMETER_PROJECTS_FOLDER)
    print(config.LOCAL_PATH_TO_DATA)
    print(config.TERRAMETER_CONNECTION_FILE)
