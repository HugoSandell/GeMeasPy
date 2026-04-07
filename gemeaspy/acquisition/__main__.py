import os
import sys
import traceback

from gemeaspy.acquisition.main import logger
from gemeaspy.settings import config as _config
from . import cli_main

if __name__ == "__main__":
    cli_main()
