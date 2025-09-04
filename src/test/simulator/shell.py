from cmd import Cmd

class SimShell(Cmd):
    def __init__(self, stdin=None, stdout=None):
        super(SimShell, self).__init__(completekey='tab', stdin=stdin, stdout=stdout)
        self.intro = None
        self.use_rawinput=False
        self.prompt="root@LS123456789:~# "

    def do_exit(self, arg):
        """Exit the shell."""
        return True

    def default(self, line: str):
        """Handle unrecognized commands."""
        print('In: ' + line.replace('\r', r'\r').replace('\n', r'\n'))
        self.print_line_sh(line)
    
    def print_sh(self, chars: str):
        print('Out: ' + chars.replace('\r', r'\r').replace('\n', r'\n'))
        # make sure stdout is set and not closed
        if self.stdout and not self.stdout.closed:
            self.stdout.write(chars)
            self.stdout.flush()

    def print_line_sh(self, chars: str):
        self.print_sh(chars + '\r\n')

    def emptyline(self):
        self.print_sh('\r\n')
