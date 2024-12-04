from abc import ABC, abstractmethod
from typing import Any

from acquisition import connections, utilities
from acquisition import monitoring_terrameter as monitoring


class Instrument(ABC):
    
    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def start_monitoring(self, task_file: str) -> None:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass


class Terrameter(Instrument):


    def __init__(self) -> None:
        self.params = utilities.read_terrameter_connection_parameters()
        self.connection = None
        self.logfile = open("logs.txt", 'a', 1)
        self._write()

    def _write(self) -> None:
        self.logfile.write("***********************************************************\n")
        self.logfile.write("New Terrameter Monitoring Session Starts\n")
        self.logfile.write("This software created by Aristeidis Nivorlis\n")

    def connect(self) -> None:
        self.logfile.write("Establishing Secure Shell Connection...\n")
        self.connection = connections.SSHConnection(self.params)
        if self.connection.connected:
            self.logfile.write("Connected!\n")
        else:
            self.logfile.write('Failed!\n')

    def start_monitoring(self, task_file: str) -> None:
        if self.connection is None:
            raise Exception("No Active Connection")
        self.logfile.write("Starting Monitoring Software\n")
        print("Starting Monitoring Software")
        monitoring.main(self.connection, self.logfile, task_file)

    def disconnect(self) -> None:
        if self.connection is None:
            raise Exception("No Active Connection")
        self.connection.disconnect()
        self.logfile.close()

    def check_input(self, tasks: list[dict[str, Any]]) -> bool:
        if self.connection is None:
            raise Exception("No Active Connection")
        print("--------------------------------")
        print('Checking protocol/spread files...')
        for task in tasks:
            command = "[ -e /home/root/protocols/{0:} ] && echo 'OK' || echo 'MISSING'".format(task['spread'])
            stdin, stdout, stderr = self.connection.send_command_shell(command, 0)
            _ = stdout.channel.recv_exit_status()  # wait for exit status
            buffer = stdout.readline().strip()
            if buffer.find("MISSING") != -1:
                print(task['name'])
                return False
            command = "[ -e /home/root/protocols/{0:} ] && echo 'OK' || echo 'MISSING'".format(task['protocol'])
            stdin, stdout, stderr = self.connection.send_command_shell(command, 0)
            _ = stdout.channel.recv_exit_status()  # wait for exit status
            buffer = stdout.readline().strip()
            if buffer.find("MISSING") != -1:
                print(task['protocol'])
                return False
            print("--------------------------------")
        else:
            print('All protocol/spread files exist!')
            return True

    def check_input_report(self, tasks) -> None:
        if self.connection is None:
            raise Exception("No Active Connection")
        for task in tasks:
            print(task['name'])
            command = "[ -e /home/root/protocols/{0:} ] && echo 'OK' || echo 'MISSING'".format(task['spread'])
            stdin, stdout, stderr = self.connection.send_command_shell(command, 0)
            _ = stdout.channel.recv_exit_status()  # wait for exit status
            buffer = stdout.readline().strip()
            if buffer.find("OK") != -1:
                print("Spread: OK!")
            elif buffer.find("MISSING") != -1:
                print("Spread: MISSING..")
            command = "[ -e /home/root/protocols/{0:} ] && echo 'OK' || echo 'MISSING'".format(task['protocol'])
            stdin, stdout, stderr = self.connection.send_command_shell(command, 0)
            _ = stdout.channel.recv_exit_status()  # wait for exit status
            buffer = stdout.readline().strip()
            if buffer.find("OK") != -1:
                print("Protocol: OK!")
            elif buffer.find("MISSING") != -1:
                print("Protocol: MISSING..")
            print("-----------------------")




