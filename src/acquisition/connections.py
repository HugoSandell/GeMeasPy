import time
import paramiko

from typing import Any


class SSHConnection():


    def __init__(self, params: dict[str, Any]) -> None:
        if ["hostname", "username", "password"] not in params.keys():
            raise Exception("Invalid Parameters")
        self.params = params
        self.ssh = None
        self.channel = None
        self.connected = self._setup()

    def send_command_shell(self, command: str, time_to_sleep: int = 1) -> tuple[paramiko.ChannelFile, paramiko.ChannelFile, paramiko.ChannelFile]:
        if self.ssh is None:
            raise Exception("No Active Connection")
        stdin, stdout, stderr = self.ssh.exec_command(command)
        _ = stdout.channel.recv_exit_status()  # wait for exit status
        time.sleep(time_to_sleep)
        return stdin, stdout, stderr

    def send_command_terrameter_software(self, command: str, time_to_sleep: int = 5) -> None:
        if self.channel is None:
            raise Exception("No Active Connection")
        self.channel.send(command.encode(encoding="UTF-8"))
        time.sleep(time_to_sleep)
            

    def read_channel_buffer(self, chars) -> str:
        if self.channel is not None:
            return self.channel.recv(chars).decode(encoding="UTF-8")
        raise Exception("No Active Connection")

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

