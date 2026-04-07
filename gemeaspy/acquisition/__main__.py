import os
import sys
import traceback

from gemeaspy.acquisition.main import logger
from gemeaspy.settings import config as _config
from . import run_acquisition

if __name__ == "__main__":
    # Read environment variables
    for _var in _config.__dict__:
        if not hasattr(_config, _var) or _var not in os.environ:
            continue
        try:
            setattr(_config, _var, type(_var)(os.environ[_var]))
        except Exception:
            print(f"Ignoring invalid environment variable {_var}='{os.environ[_var]}'")
    try:
        exit_code = run_acquisition(sys.argv)
        sys.exit(exit_code)
    except Exception as e:
        print(f"Error: An unexpected error occured. Check logs for more information.")
        logger.error(f"Unhandled exception.", exc_info=True)
        if "DEBUG" in os.environ:
            traceback.print_exception(e, file=sys.stderr)
        sys.exit(1)
