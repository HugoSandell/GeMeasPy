# Utility for reading ssh log files
# Log format (v1):
# Each line is formatted as:
# TYPE:TIMESTAMP?DATA(<EXIT_STATUS)
# TYPE is either SH (for shell data) or TM (for terrameter data)
# TIMESTAMP is the Unix/POSIX time in milliseconds when the data was sent (16 character hex representation of integer)
# ? is either > (for sent datas) or < (for received data)
# DATA is the data sent (in hex representation of bytes)
# EXIT_STATUS is the exit status of the data (only for shell datas)
# Examples:
# SH:000001991008d8bf>70696e6720686f7374<0
# TM:000001991008d8bf>5020323032333032
# TM:000001991008d8bf<4f4b0a

# Possible future work: Create new format that's more compact and easier to parse?
# E.g. use binary format, tag fields with length prefixes instead of searching for separators, etc.

import os

TIMESTAMP_LENGTH = 16 # in characters

def parse_ssh_log_file(filepath: str) -> list[dict[str, str|bytes|int]]:
    """Parse an ssh log file.
    returns
        A list of dictionaries with keys 'type', 'timestamp', 'direction', 'data', and 'exit_status'.
        <type> is 'SH' or 'TM'
        <timestamp> is an integer timestamp in milliseconds
        <direction> is '>' for sent data and '<' for received data
        <data> is the data as a bytes object
        <exit_status> is an integer exit status (only applicable for shell commands)
    raises
        ValueError if any line is not in the correct format
        FileNotFoundError if the file does not exist
        OSError for other file read errors
    """
    log_entries = []
    
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File '{filepath}' does not exist")

    try:
        with open(filepath, 'r') as file:
            for line in file:
                line = line.strip()
                if line == '':
                    continue
                try:
                    log_entry = parse_ssh_log_line(line)
                except ValueError as e:
                    raise ValueError(f"Error parsing line '{line}': {e}")
                log_entries.append(log_entry)
    except OSError as e:
        raise e
    return log_entries

def parse_ssh_log_line(line: str) -> dict[str, str|bytes|int]:
    """Parse a single line from the ssh log file.
    returns
        A dictionary with keys 'type', 'timestamp', 'direction', 'data', and 'exit_status'.
    raises
        ValueError if the line is not in the correct format
    """
    log_entry = {
        'type': '', 
        'timestamp': 0, 
        'direction': '', 
        'data': b'', 
        'exit_status': 0
    }

    # Check type separator
    type_separator_index = line.find(':')
    if type_separator_index == -1:
        raise ValueError("Invalid log line format - missing ':'")
    elif line.find(':', type_separator_index + 1) != -1:
        raise ValueError("Invalid log line format - too many ':'")
        
    # Get type
    log_entry['type'] = line[:type_separator_index].upper()
    if log_entry['type'] not in ['SH', 'TM']:
        raise ValueError("Invalid log type - must be 'SH' or 'TM'")

    # Calculate some indices for parsing
    timestamp_index = type_separator_index + 1
    direction_index = timestamp_index + TIMESTAMP_LENGTH
    data_index = direction_index + 1
    data_end_index = len(line) # assume data goes to end of line unless exit status is found

    # Check minimum length - type + ':' + timestamp + direction + at least 1 char of data
    if len(line) < type_separator_index + 1 + TIMESTAMP_LENGTH + 1 + 1:
        raise ValueError("Invalid log line format - too short")
    
    # Get timestamp
    timestamp_hex = line[timestamp_index : direction_index]
    try:
        log_entry['timestamp'] = int(timestamp_hex, 16)
    except ValueError:
        raise ValueError("Invalid timestamp - must be hex integer")

    # Get direction
    log_entry['direction'] = line[direction_index] 
    if log_entry['direction'] not in ['>', '<']:
        raise ValueError("Invalid log line format - missing '>' or '<'")
    if log_entry['type'] == 'SH':
        if log_entry['direction'] != '>':
            raise ValueError("Invalid log line format - shell log must have '>' direction")
        exit_status_index = line.find('<', data_index) + 1
        if exit_status_index not in range(len(line)):
            raise ValueError("Invalid log line format - missing exit status for shell log")
        try:
            log_entry['exit_status'] = int(line[exit_status_index:])
        except ValueError:
            raise ValueError("Invalid exit status - must be integer")
        data_end_index = exit_status_index - 1
    
    # Get data
    data_hex = line[data_index : data_end_index]
    try:
        data_bytes = bytes.fromhex(data_hex)
    except ValueError:
        raise ValueError("Invalid data - must be hex bytes")
    log_entry['data'] = data_bytes

    return log_entry