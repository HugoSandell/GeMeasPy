import argparse
import time

from gemeaspy.tests import ssh_log_format
from gemeaspy.tests._sgr import CLR_BLUE_FG, CLR_CYAN_FG, CLR_GRAY_FG, with_sgr

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
    if not isinstance(start_log_time, int):
        exit(1)
    start_time = time.monotonic()

    for entry in entries:
        if not isinstance(entry["timestamp"], int):
            continue
        if not isinstance(entry["data"], bytes):
            continue
        sleep_duration = (
            start_time
            + (entry["timestamp"] - start_log_time) / 1000 / args.speed
            - time.monotonic()
        )
        if sleep_duration > 0:
            time.sleep(sleep_duration)

        decoded_data = entry["data"].decode(errors="replace")
        style = None
        suffix = ""

        match entry["type"], entry["direction"]:
            case "SH", ">":
                style = CLR_CYAN_FG
                suffix = (
                    with_sgr(f" exited with status {entry['exit_status']}", CLR_GRAY_FG)
                    + "\n"
                )
            case "TM", ">":
                style = CLR_BLUE_FG
            case "TM", "<":
                pass

        print(with_sgr(decoded_data, style) + suffix, end="")
