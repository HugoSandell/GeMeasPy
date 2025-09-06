from cmd import Cmd
from typing import *

class SimShell(Cmd):
    def __init__(self, stdin: IO[str]=None, stdout: IO[str]=None):
        super(SimShell, self).__init__(completekey='tab', stdin=stdin, stdout=stdout)
        self.intro = 'Test Shell.\n'
        self.use_rawinput=False
        self.prompt="root@LS123456789:~# "

    def do_exit(self, arg):
        """Exit the shell."""
        return True
    
    def do_EOF(self, arg):
        print('shell.py | EOF received', flush=True)
    
    def do_help(self, arg):
        return super().do_help(arg)
    
    def default(self, line: str):
        """Handle unrecognized commands."""
        print('In: ' + line.replace('\r', r'\r').replace('\n', r'\n'), flush=True)
        self.print_line_sh(line)

    def print_sh(self, chars: str):
        print('Out: ' + chars.replace('\r', r'\r').replace('\n', r'\n'), flush=True)
        # make sure stdout is set and not closed
        if self.stdout and not self.stdout.closed:
            self.stdout.write(chars)
            self.stdout.flush()

    def print_line_sh(self, chars: str):
        self.print_sh(chars + '\r\n')

    def emptyline(self):
        self.print_sh('\r\n')
