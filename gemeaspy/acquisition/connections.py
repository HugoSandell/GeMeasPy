from typing import Any

import paramiko

from gemeaspy.acquisition import utilities
from gemeaspy.acquisition.error import ConfigFileError, SSHConnectionError
from gemeaspy.settings import config


class SSHConnection():
    def __init__(self, params: dict[str, Any]) -> None:
        required_params = ("hostname", "username", "password")
        if not all(key in params.keys() for key in required_params):
            raise ConfigFileError("Missing entry in connection parameters.", file=config.TERRAMETER_CONNECTION_FILE)
        self.params = params
        self.ssh = None
        self.channel = None
        self.connected = self._setup()

    def is_ready(self) -> bool:
        """Returns true iff this connection is ready to be used"""
        if self.connected == False:
            return False
        if self.ssh == None:
            return False
        if self.channel == None:
            return False
        transport = self.ssh.get_transport()
        if transport == None:
            return False
        if transport.active == False:
            return False
        if transport.authenticated == False:
            return False
        assert self.channel != None
        return True

    def send_command_shell(self, command: str, time_to_sleep: int = 1) -> tuple[paramiko.ChannelFile, paramiko.ChannelFile, paramiko.ChannelFile]:
        """
            Raises: 
                Exception (if self.ssh is None)
                paramiko.ssh_exception.ChannelException
        """
        if not self.is_ready() or self.ssh == None:
            raise SSHConnectionError("Tried to send shell command with no active connection.", self.params)
        stdin, stdout, stderr = self.ssh.exec_command(command)
        _ = stdout.channel.recv_exit_status()  # wait for exit status
        utilities.sleep_unless_testing(time_to_sleep)
        return stdin, stdout, stderr

    def send_command_terrameter_software(self, command: str, time_to_sleep: int = 5) -> None:
        if not self.is_ready() or self.channel == None:
            raise SSHConnectionError("Tried to send Terrameter software command with no active connection.", self.params)
        self.channel.send(command.encode(encoding="UTF-8"))
        utilities.sleep_unless_testing(time_to_sleep)
            

    def read_channel_buffer(self, chars) -> str:
        if self.is_ready() and self.channel != None:
            return self.channel.recv(chars).decode(encoding="UTF-8")
        raise SSHConnectionError("Tried to read channel buffer with no active connection.", self.params)

    def _setup(self) -> bool:
        print("Establishing Secure Shell Connection...")
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self.ssh.connect(**self.params)
            if (transport:=self.ssh.get_transport()) is not None:
                self.channel = transport.open_session()
            else:
                raise SSHConnectionError("Failed to establish connection.", self.params)
            self.channel.get_pty()
            self.channel.invoke_shell()
            print("Connected!")
            return True
        except paramiko.AuthenticationException:
            print('Failed!')
        return False

    def disconnect(self) -> None:
        if not self.is_ready() or self.ssh == None:
            return
        self.ssh.close()

    def get_ip(self) -> str:
        if self.ssh != None:
            if (transport:=self.ssh.get_transport()) is not None:
                return transport.getpeername()[0]
        raise SSHConnectionError("Tried to get ip, but there is no active connection.", self.params)

