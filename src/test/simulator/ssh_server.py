import paramiko
import socket
import threading
from cmd import Cmd
from host_key_store import get_test_host_key

class Shell(Cmd):
    def __init__(self, stdin=None, stdout=None):
        super(Shell, self).__init__(completekey='tab', stdin=stdin, stdout=stdout)
        self.intro = None
        self.use_rawinput=False
        self.prompt="root@LS123456789:~# "

    def do_exit(self, arg):
        """Exit the shell."""
        return True

    def default(self, line: str):
        """Handle unrecognized commands."""
        print('In: ' + line.replace('\r', r'\r').replace('\n', r'\n'))
        self.print_line_sh(line)
    
    def print_sh(self, chars: str):
        print('Out: ' + chars.replace('\r', r'\r').replace('\n', r'\n'))
        # make sure stdout is set and not closed
        if self.stdout and not self.stdout.closed:
            self.stdout.write(chars)
            self.stdout.flush()

    def print_line_sh(self, chars: str):
        self.print_sh(chars + '\r\n')

    def emptyline(self):
        self.print_sh('\r\n')

class InstrumentServerSimulator():
    """SSH server for testing. Will be used to emulate Terrameter server"""
    def __init__(self, host_key=get_test_host_key(), username: str = 'root', password: str = ''):
        self._is_running = threading.Event()
        self._socket = None
        self._client_shell = None
        self._listen_thread = None
        self._host_key = host_key
        
        self._username = username
        self._password = password

    def start(self, host: str = 'localhost', port: int = 2222):
        if not self._is_running.is_set():
            self._is_running.set()
            
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # SO_REUSEPORT is not available on all systems
            if hasattr(socket, 'SO_REUSEPORT'):
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

            self._socket.settimeout(1.0)
            self._socket.bind((host, port))

            self._listen_thread = threading.Thread(target=self._listen)
            self._listen_thread.start()
    
    def stop(self):
        if self._is_running.is_set():
            self._is_running.clear()
            if self._listen_thread:
                self._listen_thread.join()
                self._listen_thread = None
            if self._socket:
                self._socket.close()
                self._socket = None
    
    def _connect(self, client):
        try:
            session = paramiko.Transport(client)
            session.add_server_key(self._host_key)

            server = SSHTestServerInterface(username=self._username, password=self._password)
            try:
                session.start_server(server=server)
            except paramiko.SSHException:
                return

            channel = session.accept()
            stdio = channel.makefile('rwU')

            self.client_shell = Shell(stdio, stdio)
            self.client_shell.cmdloop()

            session.close()
        except:
            pass

    def _listen(self):
        while self._is_running.is_set():
            try:
                self._socket.listen(1)
                client, addr = self._socket.accept()
                self._connect(client)
            except TimeoutError as e:
                continue
            except Exception as e:
                print(f"Server error: {e}")

class SSHTestServerInterface(paramiko.server.ServerInterface):
    """For paramiko"""
    def __init__(self, username: str = 'root', password: str = ''):
        self.event = threading.Event()

    def check_channel_request(self, kind: str, chanid: int) -> int:
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username: str, password: str) -> int:
        if (username == 'root') and (password == ''):
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:
        return 'password'

    def check_channel_shell_request(self, channel: paramiko.Channel) -> bool:
        self.event.set()
        return True

    def check_channel_exec_request(self, channel: paramiko.Channel, command: bytes) -> bool:
        self.event.set()
        return True
