# Temporary file for testing Terrameter emulator
import os
from acquisition import connections
from tests.emulator import ssh_server
from acquisition import utilities
import threading
import logging
import paramiko
import time
from settings.config import LOG_FOLDER

conn: connections.SSHConnection = None

def print_output():
    global conn
    recv: str = ""
    while not conn.channel.closed:
        recv = recv + conn.read_channel_buffer(256)
        if len(recv) > 0:
            lines = recv.splitlines(True)
            # Ignore unfinished line
            recv = ""
            if not lines[-1].endswith("\n"):
                recv = lines[-1]
            for line in lines:
                print("\n<", line, end="", flush=True)
        time.sleep(0.0001)
    print("Closed", flush=True)


def send_to_sh(command: str):
    print("\n>", command, flush=True)
    conn.send_command_terrameter_software(f"{command}\n", time_to_sleep=0.1)

def send_single_command(command: str):
    print("\n>", command, flush=True)
    stdin, stdout, stderr = conn.send_command_shell(f"{command}", time_to_sleep=0.1)

def test_emulator():
    global conn
    params = {
        'hostname': 'localhost',
        'port': 2222,
        'username': 'root',
        'password': ''
    }

    conn = connections.SSHConnection(params)
    if conn:
        if conn.connected:
            print("Connection established successfully.", flush=True)
            print_thread: threading.Thread = threading.Thread(target=print_output)
            print_thread.start()

            project_name = "abc"

            try:
                send_to_sh("terrameter")
                time.sleep(0.1)
                send_single_command("touch /monitoring/new_day")
                time.sleep(0.1)
                send_single_command(f"echo {project_name} > /monitoring/new_day")
                time.sleep(0.1)
                send_to_sh("P test")
                time.sleep(0.1)
                send_to_sh("T Task1 /home/root/protocols/2X21.xml /home/root/protocols/Gradient_2x21.xml 1 1 1 0 0 0")
                time.sleep(0.1)
                send_to_sh("w /home/root/settings/testing1s.settings")
                time.sleep(0.1)
                send_to_sh("S 1")
                time.sleep(2)
            except Exception as e:
                print(f"{type(e).__name__}: {e}")
                print(f"Context: {e.__context__}")
            
            conn.disconnect()
            print_thread.join()
        else:
            print("Failed to establish connection.")

if __name__ == "__main__":
    os.makedirs(LOG_FOLDER, exist_ok=True)
    paramiko.util.log_to_file(f'{LOG_FOLDER}/paramiko.log')
    server = ssh_server.InstrumentServerEmulator()
    print("Starting server.")
    server.start()
    while not server.is_listening():
        time.sleep(0.0001)
    test_thread = threading.Thread(target=test_emulator)
    test_thread.start()
    try:
        while test_thread.is_alive():
            test_thread.join(0.1)
    except KeyboardInterrupt:
        print("Test interrupted.")
        conn.disconnect()
        print("Watiting for test thread to join.")
        test_thread.join(5)
    server.stop()