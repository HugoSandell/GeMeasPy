import json
import os
import random
import string
import sys
import tempfile

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from settings import config
from tests.test_case import TestCase


def _random_string():
    return "".join(random.choices(string.ascii_letters + string.digits, k=22))


def _create_connection_settings(test: TestCase):
    # TODO: ensure values are correct
    connection_settings = {
        "username": "root",
    }

    match test["hostname"]:
        case True:
            connection_settings["hostname"] = "127.0.0.1"
        case False:
            connection_settings["hostname"] = f"{_random_string()}.invalid"
        case None:
            pass

    match test["port"]:
        case True:
            connection_settings["port"] = 2222
        case None:
            pass
        case x:
            connection_settings["port"] = x

    match test["password"]:
        case True:
            connection_settings["password"] = ""
        case None:
            pass

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
    config.TERRAMETER_PROJECTS_FOLDER = (
        "/media/mmcblk0p1/projects"
        if test["TERRAMETER_PROJECTS_FOLDER"]
        else f"/media/mmcblk0p1/{_random_string()}"
    )
    config.LOCAL_PATH_TO_DATA = (
        tempfile.mkdtemp(prefix="gemeaspytest_data_")  # TODO cleanup
        if test["LOCAL_PATH_TO_DATA"]
        else f"{_random_string()}/{_random_string()}"
    )
    config.TERRAMETER_CONNECTION_FILE = (
        _create_connection_settings(test)
        if test["TERRAMETER_CONNECTION_FILE"]
        else _random_string()
    )


if __name__ == "__main__":
    setup(
        {
            "TERRAMETER_PROJECTS_FOLDER": True,
            "LOCAL_PATH_TO_DATA": True,
            "TERRAMETER_CONNECTION_FILE": True,
            "hostname": False,
            "port": -1,
            "password": None,
            "look_for_keys": None,
        }
    )
    print(config.TERRAMETER_PROJECTS_FOLDER)
    print(config.LOCAL_PATH_TO_DATA)
    print(config.TERRAMETER_CONNECTION_FILE)
