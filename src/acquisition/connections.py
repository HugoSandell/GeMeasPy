import time
import os
from typing import Any

import paramiko

from settings.config import LOG_FOLDER

class SSHConnection():
    def __init__(self, params: dict[str, Any]) -> None:
        if any(key not in params for key in ["hostname", "username", "password"]):
            raise Exception("Invalid Parameters")
        self.params = params
        self.ssh = None
        self.channel = None
        self.connected = self._setup()
        os.makedirs(os.path.realpath(LOG_FOLDER), exist_ok=True)
        if not os.path.isdir(LOG_FOLDER):
            raise Exception("Failed to create directory '" + LOG_FOLDER + "'")
        self.log = open(os.path.join(LOG_FOLDER, "ssh.log"), 'a', 1)

    def send_command_shell(self, command: str, time_to_sleep: int = 1) -> tuple[paramiko.ChannelFile, paramiko.ChannelFile, paramiko.ChannelFile]:
        if self.ssh is None:
            raise Exception("No Active Connection")
        stdin, stdout, stderr = self.ssh.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()  # wait for exit status
        self.log.write(f"SHELL:{time.time().hex()}>{command}<{exit_status}\n")
        time.sleep(time_to_sleep)
        return stdin, stdout, stderr

    def send_command_terrameter_software(self, command: str, time_to_sleep: int = 5) -> None:
        if self.channel is None:
            raise Exception("No Active Connection")
        encoded_command = command.encode(encoding="UTF-8")
        self.log.write(f"TERRA:{time.time().hex()}>{encoded_command.hex()}\n")
        self.channel.send(encoded_command)
        time.sleep(time_to_sleep)
            
    def read_channel_buffer(self, chars) -> str:
        if self.channel is None:
            raise Exception("No Active Connection")
        # Receive, decode, log, and return data
        rx_raw = self.channel.recv(chars)
        rx_decoded = rx_raw.decode(encoding="UTF-8", errors='replace')
        self.log.write(f"TERRA:{time.time().hex()}<{rx_raw.hex()}\n")
        return rx_decoded

    def _setup(self) -> bool:
        print("Establishing Secure Shell Connection...")
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self.ssh.connect(**self.params)
            if (transport:=self.ssh.get_transport()) is not None:
                self.channel = transport.open_session()
            else:
                raise Exception("Transport is None")
            self.channel.get_pty()
            self.channel.invoke_shell()
            print("Connected!")
            return True
        except paramiko.AuthenticationException:
            print('Failed!')
        return False

    def disconnect(self) -> None:
        if self.ssh is None:
            raise Exception("No Active Connection")
        self.ssh.close()
             

    def get_ip(self) -> str:
        if self.ssh is not None:
            if (transport:=self.ssh.get_transport()) is not None:
                return transport.getpeername()[0]
        raise Exception("No Active Connection")
    

