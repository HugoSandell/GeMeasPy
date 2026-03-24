import sys
from . import run_acquisition

if __name__ == "__main__":
    exit_code = run_acquisition(sys.argv)
    sys.exit(exit_code)
