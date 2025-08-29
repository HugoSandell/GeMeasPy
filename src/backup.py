import os
import pickle
import time
from posixpath import join as unixjoin
from typing import Any, Callable

import paramiko

from acquisition.utilities import read_server_connection_parameters
from settings.config import (
    FILE_TRANSFER_DICTIONARY,
    LOCAL_PATH_TO_DATA,
    SERVER_BACKUP_FOLDER,
)


def timer(some_function: Callable[..., Any]) -> Callable[[], None]:
    def inner_function():
        start = time.time()
        some_function()
        end = time.time()
        time_elapsed = end - start
        print('Time elapsed {} seconds'.format(time_elapsed))
    return inner_function


@timer
def main() -> None:
    # set working directory
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    sftp, ssh = None, None
    time_started = time.time()
    settings = read_server_connection_parameters()

    root_path_local = LOCAL_PATH_TO_DATA
    root_remote_path = SERVER_BACKUP_FOLDER
    file_dictionary_name = FILE_TRANSFER_DICTIONARY


    if not os.path.isfile(file_dictionary_name):
        file_dictionary = dict()
        with open(file_dictionary_name, 'wb') as p:
            pickle.dump(file_dictionary, p)
    with open(file_dictionary_name, 'rb') as p:
        file_dictionary = pickle.load(p)
    while True:
        try:
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(**settings)
                sftp = ssh.open_sftp()
            except paramiko.SSHException:
                print("Connection Error")

            if sftp is None:
                raise Exception("No Active Connection")
            n = len(root_path_local) + 1
            print('Starting..')
            for root, dirs, files in os.walk(root_path_local, topdown=True):
                relative_path = root[n:]
                relative_path_unix = relative_path.replace('\\', '/')
                remote_path = unixjoin(root_remote_path, relative_path_unix)
                # Create folder if needed
                try:
                    sftp.chdir(remote_path)  # Test if remote_path exists
                except IOError:
                    sftp.mkdir(remote_path)  # Create remote_path
                    sftp.chdir(remote_path)
                # Move the files
                for name in files:
                    local_file = os.path.join(root, name)
                    if local_file in file_dictionary:
                        continue  # Memoization
                    remote_file = unixjoin(remote_path, name)
                    print("File: ", remote_file)
                    while True:
                        try:
                            remote_stat = sftp.stat(unixjoin(remote_path, remote_file))
                            local_stat = os.stat(local_file)
                            if local_stat.st_size == remote_stat.st_size:
                                # File exists and has equal size - mark the file as transfered!
                                print("Success!")
                                file_dictionary[local_file] = True
                                break
                            else:
                                # File exists but with different size - get the file again
                                print("File has different size, get the correct file!")
                                print(local_file)
                                sftp.put(local_file, remote_file)
                        except IOError:
                            # File does not exist - get the file
                            print("Copying... ")
                            sftp.put(local_file, remote_file, confirm=True)
            print('Backup Completed!')
            # Save file
            with open(file_dictionary_name, 'wb') as p:
                pickle.dump(file_dictionary, p)
            break
        except (paramiko.SSHException, IOError, OSError) as e:
            print(f'Connectin closed.. Trying again! Error: {e}')
            time_running = time.time() - time_started
            if time_running > 60*60*2:
                # if running for longer than 2 hours
                break
            continue
        finally:
            if sftp is not None:
                sftp.close()
            if ssh is not None:
                ssh.close()

if __name__ == "__main__":
    main()
