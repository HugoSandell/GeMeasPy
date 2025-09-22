from typing import *
import socket
import threading
if __name__ != "__main__": # Is there a better way to do this?
    from .shell import SimShell
    from .host_key_store import get_test_host_key
    from .terrameter import TerrameterLS
else:
    from shell import SimShell
    from host_key_store import get_test_host_key
    from terrameter import TerrameterLS
import paramiko

type ShellRequest = paramiko.Channel 
"""A request for a shell session. 
Consists of a paramiko Channel to communicate through."""
type ExecRequest = Tuple[paramiko.Channel, str]
"""A request for a command execution session. 
Consists of a paramiko Channel to communicate through and a command str to execute."""

class InstrumentServerSimulator():
    """SSH server for testing. Emulates a server connected to a Terrameter"""
    def __init__(self, host_key=get_test_host_key(), username: str = 'root', password: str = ''):
        self.instrument = TerrameterLS()
        self.is_running = threading.Event()
        self._socket = None
        self._listen_thread = None # Thread that listens for new connections and sets up sessions
        self._host_key = host_key
        self._username = username
        self._password = password
        self._sessions: List[SSHTestServerSession] = [] # Handles state per connection

    def start(self, host: str = 'localhost', port: int = 2222):
        """Run the server"""
        # Check if already running
        if self.is_running.is_set():
            return
        self.is_running.set()
        
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # SO_REUSEPORT is not available on all systems
        if hasattr(socket, 'SO_REUSEPORT'):
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        self._socket.settimeout(0.1) # Use timeout to prevent multithreading deadlocks
        self._socket.bind((host, port))
        
        self._listen_thread = threading.Thread(target=self._listen)
        self._listen_thread.start()
    
    def stop(self):
        # Shut down connections and stop listening
        for session in self._sessions:
            session.close()
        self._sessions.clear()

        self.is_running.clear()
        if self._listen_thread:
            self._listen_thread.join()
            self._listen_thread = None
        
        if self._socket:
            self._socket.close()
            self._socket = None
    
    def is_listening(self):
        if self._listen_thread:
            return self._listen_thread.is_alive() and self.is_running.is_set()
    
    def _connect(self, client: socket.socket):
        """Establish a new session with the client on the given socket"""
        try:
            transport = paramiko.Transport(client)
            transport.add_server_key(self._host_key)

            paramiko_interface = SSHTestServerInterface(username=self._username, password=self._password)
            try:
                transport.start_server(server=paramiko_interface)
            except paramiko.SSHException as e:
                print(f"ssh_server.py | Failed to start SSH server: {str(e)}", flush=True)
                return

            session = SSHTestServerSession(transport, self, paramiko_interface)
            session.open()
            self._sessions.append(session)
        except Exception as e:
            print(f"ssh_server.py | Failed to connect to {client.getpeername()}: {e}", flush=True)

    def _listen(self):
        """Listen for new connections and """
        while self.is_running.is_set():
            # Clear out closed sessions. Not the best way of doing it, but it should be fine.
            self._sessions = [s for s in self._sessions if s.is_open.is_set()]
            try:
                self._socket.listen() 
                client, addr = self._socket.accept()
                self._connect(client)
            except TimeoutError as e:
                continue
            except Exception as e:
                print(f"ssh_server.py | Listening error: {e}")
                
class SSHTestServerInterface(paramiko.server.ServerInterface):
    """Paramiko server overrides. Stores requests for new channels."""
    def __init__(self, username: str, password: str):
        self.has_request = threading.Event()
        self.requests: List[ShellRequest | ExecRequest] = []

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
        # Store the request
        self.requests.append(channel)
        self.has_request.set()
        return True

    def check_channel_exec_request(self, channel: paramiko.Channel, command: bytes) -> bool:
        # Store the request
        self.requests.append((channel, command.decode()))
        self.has_request.set()
        return True

class SSHTestServerChannel():
    """Serves a paramiko SSH channel."""
    def __init__(self, 
                 server: InstrumentServerSimulator,
                 server_interface: SSHTestServerInterface, 
                 paramiko_channel: paramiko.Channel, 
                 exec_command: str | None = None):
        """
            exec_command - The command to execute if serving an execute request. Opens a Shell if this is None.
        """
        self.is_open = threading.Event()
        self._thread = threading.Thread(target=self._serve)
        self._server: InstrumentServerSimulator = server
        self._server_interface: SSHTestServerInterface = server_interface
        self._paramiko_channel: paramiko.Channel = paramiko_channel
        self._exec_command: str = exec_command

    def start(self):
        """Start thread to serve channel"""
        if self._thread.is_alive():
            return
        self.is_open.set()
        self._thread.start()

    def close(self):
        """Stop serving and close channel"""
        if not self.is_open.is_set():
            return
        if self._paramiko_channel.active:
            try:
                self._paramiko_channel.close()
            except EOFError:
                pass
        self.is_open.clear()

    def _serve(self):
            """Serve channel. Either handles a single command or starts a Shell."""
            self._server_interface.has_request.clear()
            if self._exec_command:
                # Serve command execution request
                self._paramiko_channel.send(self._exec_command)
                self._paramiko_channel.send_exit_status(0)
            else:
                # Serve shell request
                try:
                    stdin = self._paramiko_channel.makefile('rU')
                    stdout = self._paramiko_channel.makefile('wU')
                    shell = SimShell(self._server.instrument , stdin, stdout)
                    shell.cmdloop()
                except socket.error as e:
                    print(f"ssh_server.py | Socket error: {e}")
                except Exception as e:
                    print(f"ssh_server.py | Session error: {e}")
            self.close()

class SSHTestServerSession():
    """Stores an SSH session (paramiko Transport) and manages its SSH channels"""
    def __init__(self, transport: paramiko.Transport, server: InstrumentServerSimulator, server_interface: SSHTestServerInterface):
        self.is_open = threading.Event()
        self._server = server
        self.server_interface = server_interface
        self.channels: List[SSHTestServerChannel] = []
        self._transport = transport
        self._thread = threading.Thread(target = self._serve)
        self.__close_event = threading.Event() # Signifies that the session is closing

    def open(self):
        self.is_open.set()
        self._thread.start()

    def close(self):
        self.__close_event.set()
        for channel in self.channels:
            channel.close()
        if self._thread.is_alive():
            self._thread.join(0.1)
        self.channels.clear()
        self._transport.close()
        self.is_open.clear()

    def _serve(self):
        while not self.__close_event.is_set() and self._transport.is_alive():
            # Clear out closed channels. Not the best way of doing it, but it should be fine.
            self.channels = [c for c in self.channels if c.is_open.is_set()]
            wait_time = 0.1 # Timeout in seconds to avoid multithreading deadlocks
            request_exists = self.server_interface.has_request.wait(wait_time) 
            if request_exists:
                for request in self.server_interface.requests:
                    match request:
                        case (paramiko_channel, command): # Execution request
                            new_channel = SSHTestServerChannel(self._server, self.server_interface, paramiko_channel, command)
                            new_channel.start()
                            self.channels.append(new_channel)
                        case paramiko_channel: # Shell request
                            new_channel = SSHTestServerChannel(self._server, self.server_interface, paramiko_channel)
                            new_channel.start()
                            self.channels.append(new_channel)
                # Clear handled requests
                self.server_interface.requests.clear()
                self.server_interface.has_request.clear()


# Run server. For manual testing.
def run():
    sim = InstrumentServerSimulator()
    sim.start()
    input("Press Enter to stop the server...\n")
    sim.stop()