import os
import socket
import threading
import time
from typing import TypeAlias

import paramiko
import paramiko.common

from .host_key_store import get_test_host_key
from .sftp import EmulatorSFTPServerInterface
from .shell import PtyRequest, TerrameterShell
from .terrameter import TerrameterLS


ShellRequest: TypeAlias = paramiko.Channel 
"""A request for a shell session. 
Consists of a paramiko Channel to communicate through."""
ExecRequest: TypeAlias = tuple[paramiko.Channel, str]
"""A request for a command execution session. 
Consists of a paramiko Channel to communicate through and a command str to execute."""

class InstrumentServerEmulator(paramiko.ServerInterface):
    """SSH server for testing. Emulates a server connected to a Terrameter"""
    def __init__(self, host_key=get_test_host_key(), username: str = 'root', password: str = ''):
        super(InstrumentServerEmulator, self).__init__()
        self.instrument: TerrameterLS = TerrameterLS()
        self.is_running: threading.Event = threading.Event()
        self.address: tuple[str, int] = ("", 0)
        self._socket: socket.socket | None = None
        self._listen_thread: threading.Thread | None = None # Thread that listens for new connections and sets up sessions
        self._host_key: paramiko.RSAKey = host_key
        self._username: str = username
        self._password: str = password
        self._sessions: list[SSHTestServerSession] = [] # Handles state per connection
        self.has_request = threading.Event()
        self.requests: list[ShellRequest | ExecRequest] = []
        self.pty_requests: dict[int, PtyRequest] = {} # ChannelID: Request

    def start(self, host: str = 'localhost', port: int = 0):
        """Run the server"""
        # Check if already running
        if self.is_running.is_set():
            return
        self.is_running.set()
        
        os.environ['USETERRAMETEREMULATOR'] = '1' # Let the SUT know we're running the emulator
        
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # SO_REUSEPORT is not available on all systems
        try:
            self._socket.setsockopt(socket.SOL_SOCKET, getattr(socket, 'SO_REUSEPORT'), 1)
        except AttributeError:
            pass

        self._socket.settimeout(0.1) # Use timeout to prevent multithreading deadlocks
        self._socket.bind((host, 0))
        self.address = self._socket.getsockname()
        
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
            transport.set_subsystem_handler("sftp", paramiko.SFTPServer, EmulatorSFTPServerInterface, self.instrument)
            try:
                transport.start_server(server=self)
            except EOFError as e:
                return

            session = SSHTestServerSession(transport, self)
            session.open()
            self._sessions.append(session)
        except ConnectionResetError as e:
            return

    def _listen(self):
        """listen for new connections and set up sessions"""
        if not self._socket:
            return
        
        while self.is_running.is_set():
            # Clear out closed sessions. Not the best way of doing it, but it should be fine.
            self._sessions = [s for s in self._sessions if s.is_open.is_set()]
            try:
                if self.instrument.is_shut_down:
                    for session in self._sessions:
                        session.close()
                    self._sessions.clear()
                    time.sleep(0.01)
                    continue
                elif not self.instrument.allow_login:
                    time.sleep(0.01)
                    continue
                self._socket.listen() 
                client, addr = self._socket.accept()
                self._connect(client)
            except TimeoutError as e:
                continue
            
    ## Paramiko Server Interface overrides
    def check_channel_request(self, kind: str, chanid: int) -> int:
        if kind == 'session':
            return paramiko.common.OPEN_SUCCEEDED
        return paramiko.common.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_pty_request(self, channel: paramiko.Channel, term: bytes, width: int, height: int, 
                                  pixelwidth: int, pixelheight: int, modes):
        request: PtyRequest = PtyRequest(term, width, height, pixelwidth, pixelheight)
        self.pty_requests[channel.chanid] = request
        return True

    def check_auth_password(self, username: str, password: str) -> int:
        if (username == self._username) and (password == self._password):
            return paramiko.common.AUTH_SUCCESSFUL
        return paramiko.common.AUTH_FAILED

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
                 server: InstrumentServerEmulator,
                 paramiko_channel: paramiko.Channel,
                 exec_command: str | None = None,
                 pty: PtyRequest | None = None):
        """
            exec_command - The command to execute if serving an execute request. Opens a Shell if this is None.
        """
        self.is_open = threading.Event()
        self._thread = threading.Thread(target=self._serve)
        self._server: InstrumentServerEmulator = server
        self._paramiko_channel: paramiko.Channel = paramiko_channel
        self._exec_command: str | None = exec_command
        self._pty = pty

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
        if not self._paramiko_channel.closed:
            try:
                self._paramiko_channel.close()
            except EOFError:
                pass
        self.is_open.clear()

    def _serve(self):
            """Serve channel. Either handles a single command or starts a Shell."""
            self._server.has_request.clear()
            if self._exec_command:
                # Serve command execution request
                try:
                    stdin = self._paramiko_channel.makefile_stdin('rU')
                    stdout = self._paramiko_channel.makefile('wU')
                    stderr = self._paramiko_channel.makefile_stderr('wU')
                    shell = TerrameterShell(self._server.instrument, stdin, stdout, stderr=stderr)
                    shell.user = self._server._username
                    exec_command = shell.precmd(self._exec_command)
                    stop = shell.onecmd(exec_command)
                    shell.postcmd(stop, exec_command)
                    self._paramiko_channel.send_exit_status(0)
                    stdin.close()
                    stdout.close()
                except socket.error as e:
                    if "Socket is closed" not in e.args:
                        raise e
            else:
                # Serve shell request
                try:
                    stdin = self._paramiko_channel.makefile_stdin('rU')
                    stdout = self._paramiko_channel.makefile('wU')
                    stderr = self._paramiko_channel.makefile_stderr('wU')
                    shell = TerrameterShell(self._server.instrument, stdin, stdout, stderr=stderr, pty=self._pty)
                    shell.cmdloop()
                except socket.error as e:
                    if "Socket is closed" not in e.args:
                        raise e
            self.close()

class SSHTestServerSession():
    """Stores an SSH session (paramiko Transport) and manages its SSH channels"""
    def __init__(self, transport: paramiko.Transport, server: InstrumentServerEmulator):
        self.is_open = threading.Event()
        self._server = server
        self.channels: list[SSHTestServerChannel] = []
        self.pseudoterminals: list[PtyRequest] = []
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
            request_exists = self._server.has_request.wait(wait_time) 
            if request_exists:
                requests = self._server.requests.copy()
                self._server.requests.clear()
                self._server.has_request.clear()
                for request in requests:
                    match request:
                        case (paramiko_channel, command): # Execution request
                            new_channel = SSHTestServerChannel(server=self._server, paramiko_channel=paramiko_channel, exec_command=command)
                            new_channel.start()
                            self.channels.append(new_channel)
                        case paramiko_channel: # Shell request
                            pty = self._server.pty_requests.pop(paramiko_channel.chanid, None)
                            if not pty:
                                continue
                            new_channel = SSHTestServerChannel(server=self._server, paramiko_channel=paramiko_channel, pty=pty)
                            new_channel.start()
                            self.channels.append(new_channel)

# Run server. For manual testing.
def run():
    emu = InstrumentServerEmulator()
    emu.start()
    if not emu.address:
        return
    print("Running on port %s" % emu.address[1])
    input("Press Enter to stop the server...\n")
    emu.stop()