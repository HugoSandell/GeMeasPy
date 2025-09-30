import argparse
import os
import sys
import time

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests import ssh_log_format

FG_BLUE = "\x1b[34m"
FG_CYAN = "\x1b[36m"
FG_GRAY = "\x1b[90m"
FG_DEFAULT = "\x1b[39m"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plays back an SSH log file. Shell commands are displayed in cyan, "
        "sent data in blue and received data in the default color."
    )
    parser.add_argument("log_file")
    parser.add_argument("--speed", default=1, type=float)
    args = parser.parse_args()

    entries = ssh_log_format.parse_ssh_log_file(args.log_file)
    start_log_time = entries[0]["timestamp"]
    start_time = time.monotonic()

    for entry in entries:
        sleep_duration = (
            start_time
            + (entry["timestamp"] - start_log_time) / 1000 / args.speed
            - time.monotonic()
        )
        if sleep_duration > 0:
            time.sleep(sleep_duration)

        decoded_data = entry["data"].decode(errors="replace")
        prefix = ""
        suffix = FG_DEFAULT

        match entry["type"], entry["direction"]:
            case "SH", ">":
                prefix = FG_CYAN
                suffix = (
                    f"{FG_GRAY} exited with status {entry['exit_status']}{suffix}\n"
                )
            case "TM", ">":
                prefix = FG_BLUE
            case "TM", "<":
                suffix = ""

        print(prefix + decoded_data + suffix, end="")
