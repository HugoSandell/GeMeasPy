import os
import sys
import paramiko
from paramiko import SFTPAttributes, SFTPHandle, SFTPServerInterface, ServerInterface
from paramiko.sftp import SFTP_NO_SUCH_FILE, SFTP_PERMISSION_DENIED, SFTP_FAILURE

parent_module = sys.modules['.'.join(__name__.split('.')[:-1]) or '__main__']
if __name__ == '__main__' or parent_module.__name__ == '__main__':
    import terrameter
    import host_key_store
else:
    from . import terrameter
    from . import host_key_store

class EmulatorSFTPHandle(SFTPHandle):
    def __init__(self, flags: int, path: str, instrument: terrameter.TerrameterLS):
        super(EmulatorSFTPHandle, self).__init__(flags)
        self.flags = flags
        self._instrument = instrument
        self.readfile = self._instrument.open_file(path)
        self.writefile = self.readfile
    
    def close(self):
        pass

class EmulatorSFTPServerInterface(SFTPServerInterface):
    def __init__(self, server: ServerInterface, instrument: terrameter.TerrameterLS):
        self._server = server
        self._instrument = instrument
        
    def session_started(self):
        pass
    
    def session_ended(self):
        pass
    
    def canonicalize(self, path: str) -> str:
        if path == ".": 
            return "/home/root"
        return super().canonicalize(path)
    
    def open(self, path: str, flags: int, attr: SFTPAttributes) -> int | SFTPHandle:
        try:
            if not self._instrument.path_exists(path):
                return SFTP_NO_SUCH_FILE
            return EmulatorSFTPHandle(flags, path, self._instrument)
        except NotADirectoryError:
            return SFTP_NO_SUCH_FILE
    
    def list_folder(self, path) -> int | list[str]:
        try:
            folder_name_list = self._instrument.list_folder(path)
            attribute_list = []
            for name in folder_name_list:
                attr = SFTPAttributes()
                attr.filename = name
                attribute_list.append(attr)
            return attribute_list
        except FileNotFoundError:
            return SFTP_NO_SUCH_FILE
        except NotADirectoryError:
            return SFTP_PERMISSION_DENIED
        except PermissionError:
            return SFTP_PERMISSION_DENIED
        except Exception as e:
            return SFTP_FAILURE
    
    def stat(self, file: str) -> int | SFTPAttributes:
        try:
            filename = os.path.basename(file)
            return SFTPAttributes.from_stat(self._instrument.stat(file), filename)
        except FileNotFoundError:
            return SFTP_NO_SUCH_FILE
        except NotADirectoryError:
            return SFTP_PERMISSION_DENIED
        except PermissionError:
            return SFTP_PERMISSION_DENIED
        except Exception as e:
            return SFTP_FAILURE
    
    def lstat(self, file: str) -> int | SFTPAttributes:
        return self.stat(file)

if __name__ == "__main__":
    from paramiko import SFTPServer, Transport
    import socket
    from threading import *

    class TestServerInterface(ServerInterface):
        def __init__(self):
            super(TestServerInterface, self).__init__()
        def check_auth_password(self, username, password):
            return paramiko.AUTH_SUCCESSFUL
        def get_allowed_auths(self, username):
            return "password"
        def check_channel_request(self, kind, chanid):
            if kind == "session":
                return paramiko.OPEN_SUCCEEDED
            
    instrument = terrameter.TerrameterLS()
    instrument.write_file_utf8("/home/root/test.txt", "testdata")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # SO_REUSEPORT is not available on all systems
    if hasattr(socket, 'SO_REUSEPORT'):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.settimeout(0.1) # Use timeout to prevent multithreading deadlocks
    sock.bind(("localhost", 24444))
    address = sock.getsockname()
    print(f"Running SFTP server on port {address[1]}")
    while True:
        try:
            server = TestServerInterface()
            sock.listen()
            client, addr = sock.accept()
            transport = Transport(client)
            transport.add_server_key(host_key_store.get_test_host_key())
            transport.set_subsystem_handler("sftp", SFTPServer, EmulatorSFTPServerInterface, instrument)
            server_event: Event = Event()
            transport.start_server(server_event, server) 
        except TimeoutError as e:
            continue
        except Exception as e:
            print(f"Listening error: {e}")