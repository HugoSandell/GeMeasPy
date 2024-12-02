import sys

from acquisition.utilities import read_terrameter_connection_parameters
from acquisition.instruments import Terrameter
from acquisition.terrameter_commands import check_transfer, transfer_project, delete_project


def main():
    # read connection and measurement settings
    connection_parameters = read_terrameter_connection_parameters()
    ls = Terrameter()
    ls.connect()

    # Check if there are files to be transfered
    stdin, stdout, stderr = ls.connection.send_command_shell("more /monitoring/new_day")
    project_name = stdout.readline().strip()
    if project_name is not '':
        while not check_transfer(ls.connection):
            transfer_project(ls.connection)
        print("Files ahve succesfully transferred to the pc!")
        delete_project(ls.connection, project_name)
    else:
        print("No files were to transfer")

    ls.connection.send_command_shell("rm /monitoring/*")
    ls.connection.send_command_shell("shutdown -r 1")
    ls.disconnect()

if __name__ == "__main__":
    main()
                