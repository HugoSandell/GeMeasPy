import time
import paramiko


class SSHConnection(object):


    def __init__(self, params):
        self.params = params
        self.ssh = None
        self.channel = None
        self.connected = self._setup()

    def send_command_shell(self, command, time_to_sleep = 1):
        #print(command)
        stdin, stdout, stderr = self.ssh.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        time.sleep(time_to_sleep)
        return stdin, stdout, stderr

    def send_command_terrameter_software(self, command, time_to_sleep = 5):
        #print(command)
        self.channel.send(command)
        time.sleep(time_to_sleep)

    def read_channel_buffer(self, chars):
        return self.channel.recv(chars).decode(encoding="UTF-8")

    def _setup(self):
        print("Establishing Secure Shell Connection...")
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self.ssh.connect(**self.params)
            self.channel = self.ssh.get_transport().open_session()
            self.channel.get_pty()
            self.channel.invoke_shell()
            print("Connected!")
            return True
        except paramiko.AuthenticationException:
            print('Failed!')
        return False

    def disconnect(self):
        self.ssh.close()

    def get_ip(self):
        return self.ssh.get_transport().getpeername()[0]

