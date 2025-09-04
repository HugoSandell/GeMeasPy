from acquisition import connections
from test.simulator import ssh_server

if __name__ == "__main__":
    params = {
        'hostname': 'localhost',
        'port': 2222,
        'username': 'root',
        'password': ''
    }

    server = ssh_server.InstrumentServerSimulator()

    conn = connections.SSHConnection(params)
    if conn.connected:
        print("Connection established successfully.")
        stdin, stdout, stderr = conn.send_command_shell('echo "Hello, World!"')
        print("STDOUT:", stdout.read().decode())
        print("STDERR:", stderr.read().decode())
        conn.disconnect()
    else:
        print("Failed to establish connection.")