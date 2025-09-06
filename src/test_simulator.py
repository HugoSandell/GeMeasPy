from acquisition import connections
from test.simulator import ssh_server
from acquisition import utilities
import threading
import logging
import paramiko
import time
from settings.config import LOG_FOLDER

conn: connections.SSHConnection = None

def test_simulator():
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
            print("Connection established successfully.")
            stdin, stdout, stderr = conn.send_command_shell('echo "Hello, World!"')
            print("Command sent.")
            print("STDOUT:", stdout.read().decode())
            print("STDERR:", stderr.read().decode())
            conn.disconnect()
        else:
            print("Failed to establish connection.")

if __name__ == "__main__":
    paramiko.util.log_to_file(f'{LOG_FOLDER}/paramiko.log')
    server = ssh_server.InstrumentServerSimulator()
    print("Starting server.")
    server.start()
    utilities.progress_bar(1, 50)

    test_thread = threading.Thread(target=test_simulator, daemon=True)
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