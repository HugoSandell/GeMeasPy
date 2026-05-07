import os
import socket
from datetime import datetime
from typing import Any

import paramiko

import gemeaspy
from gemeaspy.acquisition import utilities
from gemeaspy.acquisition.error import ConfigFileError, SSHConnectionError
from gemeaspy.acquisition.logger import logger
from gemeaspy.settings import config

class SSHConnection():
    def __init__(self, params: dict[str, str | int | bool | float | None]) -> None:
        required_params = ("hostname", "username", "password")
        if not all(key in params.keys() for key in required_params):
            raise ConfigFileError("Missing entry in connection parameters.", file=config.TERRAMETER_CONNECTION_FILE)
        if "port" not in params:
            params["port"] = 22 # standard port for SSH
        elif not isinstance(params["port"], int):
            raise ConfigFileError(f"Port number should be an integer, got {type(params["port"])}", file=config.TERRAMETER_CONNECTION_FILE)
        elif not (1 <= params["port"] <= 65535):
            raise ConfigFileError(f"Port number {(params["port"])} not in valid range.", file=config.TERRAMETER_CONNECTION_FILE)
        if "timeout" not in params:
            params["timeout"] = 1.0 if "USETERRAMETEREMULATOR" in os.environ else 10.0
        
        self.params: dict[str, Any] = params
        self.ssh = None
        self.channel = None
        self.debug_log = _DebugLogger()
        self.connected = self._setup()
        self._read_buf = bytes()

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
        exit_status = stdout.channel.recv_exit_status()  # wait for exit status
        self.debug_log.shell(command, exit_status)
        utilities.sleep_unless_testing(time_to_sleep)
        return stdin, stdout, stderr

    def send_command_terrameter_software(self, command: str, time_to_sleep: int = 5) -> None:
        if not self.is_ready() or self.channel == None:
            raise SSHConnectionError("Tried to send Terrameter software command with no active connection.", self.params)
        self.channel.send(self.debug_log.send(command.encode(encoding="UTF-8")))
        utilities.sleep_unless_testing(time_to_sleep)

    def read_channel_buffer(self, chars: int) -> str:
        if self.is_ready() and self.channel != None:
            if len(self._read_buf) > 0:
                size = min(chars, len(self._read_buf))
                data = self._read_buf[:size]
                self._read_buf = self._read_buf[size:]
            else:
                data = self.channel.recv(chars)
            return data.decode(encoding="UTF-8")
        raise SSHConnectionError("Tried to read channel buffer with no active connection.", self.params)

    def read_channel_line(self) -> str:
        if self.is_ready() and self.channel is not None:
            line = self._read_buf

            while b"\n" not in line:
                data = self.channel.recv(1024)
                if len(data) == 0:
                    break
                line += data

            size = line.find(b"\n") + 1
            if size == 0:
                # EOF reached before newline, return everything
                size = len(line)
            self._read_buf = line[size:]
            line = line[:size]
            return line.decode(encoding="UTF-8")

        raise SSHConnectionError(
            "Tried to read channel line with no active connection.", self.params
        )

    def _setup(self) -> bool:
        print("Establishing Secure Shell Connection...")
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        from paramiko import ssh_exception
        try:
            self.ssh.connect(**self.params)
            if (transport:=self.ssh.get_transport()) is not None and transport.is_authenticated():
                if isinstance(transport.sock, socket.socket):
                    transport.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.channel = transport.open_session()
            else:
                raise SSHConnectionError("Failed to establish connection.", self.params)

            orig_recv = self.channel.recv

            def logging_recv(nbytes: int) -> bytes:
                return self.debug_log.recv(orig_recv(nbytes))

            self.channel.recv = logging_recv

            self.channel.get_pty()
            self.channel.invoke_shell()
            print("Connected!")
            return True
        except ssh_exception.NoValidConnectionsError:
            raise SSHConnectionError("Could not reach the server - connection refused or host unreachable. Check the hostname and port.", self.params)
        except paramiko.BadHostKeyException:
            raise SSHConnectionError("The server's host key did not match what was expected - the server may have changed or be untrusted.", self.params)
        except paramiko.AuthenticationException:
            raise SSHConnectionError("Authentication failed - check the username and password in the connection settings file.", self.params)
        except paramiko.SSHException:
            raise SSHConnectionError("Could not establish an SSH session - the server may not be running SSH on this port.", self.params)
        except socket.gaierror:
            raise SSHConnectionError("Could not resolve hostname - check its value in the connection settings file.", self.params)
        except socket.timeout:
            raise SSHConnectionError("Connection timed out - check that the hostname and port are reachable.", self.params)
        except Exception as e:
            logger.fatal(f"Unhandled exception:\n{e}")
            raise
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


class _DebugLogger:
    def __init__(self):
        if "DEBUG" in os.environ:
            log_dir = os.path.normpath(f"{os.path.dirname(gemeaspy.__file__)}/../log/ssh")
            os.makedirs(log_dir, exist_ok=True)
            self.logfile = open(
                os.path.join(
                    log_dir, f"ssh.{datetime.now().strftime('%Y-%m-%dT%H%M%S.%f')}.log"
                ),
                "a",
                1,
            )
        else:
            self.logfile = None

    def shell(self, command: str, exit_status: int):
        if self.logfile:
            self.logfile.write(
                f"SH:{utilities.timestamp_hex()}>{command.encode().hex()}<{exit_status}\n"
            )

    def send(self, data: bytes) -> bytes:
        if self.logfile:
            self.logfile.write(f"TM:{utilities.timestamp_hex()}>{data.hex()}\n")
        return data

    def recv(self, data: bytes) -> bytes:
        if self.logfile:
            self.logfile.write(f"TM:{utilities.timestamp_hex()}<{data.hex()}\n")
        return data
