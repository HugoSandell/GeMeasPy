from cmd import Cmd
from typing import *

class SimShell(Cmd):
    """Provides a shell to accept commands (for interacting with the terrameter software)"""
    def __init__(self, stdin: IO[str]=None, stdout: IO[str]=None):
        super(SimShell, self).__init__(completekey='tab', stdin=stdin, stdout=stdout)
        self.use_rawinput=False # Required to read from the provided stdin insted of sys.stdin 
        self.prompt="root@LS123456789:~# "

    def do_exit(self, arg):
        """Called when 'exit' command is entered."""
        return True # Shell should be closed (causes cmdloop to exit)
    
    def do_EOF(self, arg):
        """Called when EOF is read."""
        return True # Shell should be closed (causes cmdloop to exit)
    
    def do_help(self, arg):
        # Will probably never be used, so print an empty line for now.
        self.print_line_sh()
    
    def default(self, line: str):
        # Emulate bash
        self.print_line_sh(f'-bash: {line.split()[0]}: command not found')
        # zsh version
        #self.print_line_sh(f'zsh: {line.split()[0]}: command not found')

    def print_sh(self, chars: str):
        """Write string to stdout"""
        if self.stdout and not self.stdout.closed:
            self.stdout.write(chars)
            self.stdout.flush()

    def print_line_sh(self, chars: str = ''):
        """Write string to stdout with an appended Windows-style line terminator (CRLF)"""
        self.print_sh(chars + '\r\n')

    def emptyline(self):
        # Do nothing when receiving an empty line
        pass