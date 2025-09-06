# TODO: Support multiple clients
import time
from typing import *
import socket
import threading
from .shell import SimShell
from .host_key_store import get_test_host_key
import paramiko

type ShellRequest = paramiko.Channel
type ExecRequest = Tuple[paramiko.Channel, str]

class InstrumentServerSimulator():
    """SSH server for testing. Will be used to emulate Terrameter server"""
    def __init__(self, host_key=get_test_host_key(), username: str = 'root', password: str = ''):
        self._is_running = threading.Event()
        self._socket = None
        self._listen_thread = None
        self._host_key = host_key
        self._username = username
        self._password = password
        self._sessions: List[SSHTestServerSession] = []

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
            for session in self._sessions:
                session.close()
            self._sessions.clear()
            if self._listen_thread:
                self._listen_thread.join()
                self._listen_thread = None
            if self._socket:
                self._socket.close()
                self._socket = None
    
    def _connect(self, client: socket.socket):
        try:
            transport = paramiko.Transport(client)
            transport.add_server_key(self._host_key)

            server = SSHTestServerInterface(username=self._username, password=self._password)
            try:
                transport.start_server(server=server)
            except paramiko.SSHException as e:
                print(f"ssh_server.py | Failed to start SSH server: {str(e)}", flush=True)
                return

            session = SSHTestServerSession(transport, server)
            session.open()
            self._sessions.append(session)
            print(f'ssh_server.py | Number of sessions: {str(len(self._sessions))}', flush=True)
        except Exception as e:
            print(f"ssh_server.py | Failed to connect to {client.getpeername()}: {e}", flush=True)

    def _listen(self):
        while self._is_running.is_set():
            self._sessions = [s for s in self._sessions if s.is_open.is_set()]
            try:
                self._socket.listen(1)
                client, addr = self._socket.accept()
                self._connect(client)
            except TimeoutError as e:
                continue
            except Exception as e:
                print(f"ssh_server.py | Server error: {e}")
                
class SSHTestServerInterface(paramiko.server.ServerInterface):
    """For paramiko"""
    def __init__(self, username: str, password: str):
        self.event = threading.Event()
        self.requests = [ShellRequest | ExecRequest]

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
        self.requests.append(channel)
        self.event.set()
        return True

    def check_channel_exec_request(self, channel: paramiko.Channel, command: bytes) -> bool:
        self.requests.append((channel, command.decode()))
        self.event.set()
        return True

class SSHTestServerChannel():
    def __init__(self, 
                 server_interface: SSHTestServerInterface, 
                 paramiko_channel: paramiko.Channel, 
                 exec_command: str | None = None):
        
        self.is_open = threading.Event()
        self._thread = threading.Thread(target=self._serve)
        self._server_interface = server_interface
        self._paramiko_channel = paramiko_channel
        self._exec_command = exec_command

    def start(self):
        if not self._thread.is_alive():
            self.is_open.set()
            self._thread.start()
            print(f'ssh_server.py | channel {self._paramiko_channel.chanid} opened')

    def close(self):
        if not self.is_open.is_set():
            return
        if self._paramiko_channel.active:
            try:
                self._paramiko_channel.close()
            except EOFError as e:
                pass
                
        self.is_open.clear()
        print(f'ssh_server.py | channel {self._paramiko_channel.chanid} closed')
        
    def _serve(self):
            self._server_interface.event.clear()
            if self._exec_command:
                print(f'ssh_server.py | channel {self._paramiko_channel.chanid} > Executing command: {self._exec_command}')
                self._paramiko_channel.send(self._exec_command)
                self._paramiko_channel.send_exit_status(0)
                print(f'ssh_server.py | channel {self._paramiko_channel.chanid} > Command executed')
            else:
                try:
                    stdin = self._paramiko_channel.makefile('rU')
                    stdout = self._paramiko_channel.makefile('wU')
                    shell = SimShell(stdin, stdout)
                    print(f'ssh_server.py | channel {self._paramiko_channel.chanid} > CMDLoop')
                    shell.cmdloop()
                    print(f'ssh_server.py | channel {self._paramiko_channel.chanid} > CMDLoop done')
                except socket.error as e:
                    print(f"ssh_server.py | Socket error: {e}")
                except Exception as e:
                    print(f"ssh_server.py | Session error: {e}")
            self.close()


class SSHTestServerSession():
    def __init__(self, transport: paramiko.Transport, server_interface: SSHTestServerInterface):
        self.is_open = threading.Event()
        self.server_interface = server_interface
        self.channels: List[SSHTestServerChannel] = []
        self._transport = transport
        self._thread = threading.Thread(target = self._serve)
        self.__close_event = threading.Event()

    def open(self):
        self.is_open.set()
        self._thread.start()

    def close(self):
        self.__close_event.set()
        for channel in self.channels:
            channel.close()
        if self._thread.is_alive():
            self._thread.join(1)
        self.channels.clear()
        self._transport.close()
        self.is_open.clear()

    def _serve(self):
        while not self.__close_event.is_set() and self._transport.is_alive():
            self.channels = [c for c in self.channels if c.is_open.is_set()]
            event_set = self.server_interface.event.wait(1)
            if event_set:
                request = self.server_interface.requests.pop()
                match request:
                    case (paramiko_channel, command):
                        print('ssh_server.py | opening exec channel')
                        new_channel = SSHTestServerChannel(self.server_interface, paramiko_channel, command)
                        new_channel.start()
                        self.channels.append(new_channel)
                    case (paramiko_channel):
                        print('ssh_server.py | opening shell channel')
                        new_channel = SSHTestServerChannel(self.server_interface, paramiko_channel)
                        new_channel.start()
                        self.channels.append(new_channel)
                self.server_interface.event.clear()
