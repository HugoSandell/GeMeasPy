import os
import subprocess
import shlex
import socket
import time

from collections import namedtuple


Config = namedtuple('config', ['address', 'port', 'com', 'mux'])

def main():
    delay = 1
    time.sleep(delay)
    sock = connect()
    time.sleep(delay)
    #sock.send(b'ResetAll(1A)')
    #time.sleep(delay)
    sock.send(b'SetAll(5A)')
    time.sleep(delay)
    #sock.send(b'ResetAll(5A)')
    time.sleep(delay)
    sock.close()
    time.sleep(delay)


def connect():  # This needs to be a contex manager
    # Read the settings.ini file
    config = read_settings()
    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Connect the socket to the port where the server is listening
    server_address = (config.address, config.port)
    sock.connect(server_address)
    return sock



def read_settings(filename="settings.ini"):
    with open(filename, 'r') as fin:
        dump = fin.readline()
        address = fin.readline().strip().split('=')[1]
        port = int(fin.readline().strip().split('=')[1])
        com = int(fin.readline().strip().split('=')[1])
        #mux = int(fin.readline().strip().split('=')[1])
        mux = 3
    config = Config(address, port, com, mux)
    return config

def start_server():
    '''
    The arduino server will listen for connection to the relay switch
    '''
    run_command(r'C:\SubvisionAB\ShiftLEYWin\svShiftLEYwin.exe')
    #os.system(r'C:\SubvisionAB\ShiftLEYWin\svShiftLEYwin.exe')

def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())
        if b'Initial address-check done' in output:
            print('Server is running.. resuming execution to main software!')
            break
    rc = process.poll()
    return rc

if __name__ == "__main__":
    #main()
    start_server()
    print('Do something for a minute')
    time.sleep(60)
    print('Do something else for another minute')
    time.sleep(60)
    print('Save something to somewhere')


