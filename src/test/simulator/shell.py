from cmd import Cmd
import pathlib
import argparse
from typing import *
from terrameter import TerrameterLS
import constants

class SimShell(Cmd):
    """Provides a shell to accept commands (for interacting with the terrameter software)"""
    def __init__(self, instrument: TerrameterLS, stdin: IO[str]=None, stdout: IO[str]=None):
        super(SimShell, self).__init__(completekey="tab", stdin=stdin, stdout=stdout)
        self.instrument = instrument
        self.cwd: pathlib.PurePosixPath = pathlib.PurePosixPath("/home/root")
        self.use_rawinput=False # Required to read from the provided stdin insted of sys.stdin 
        self.prompt="root@LS123456789:~# "
        self.terrameter_cli_active = False # Is the terrameter CLI opened
    
    def do_EOF(self, arg):
        """Called when EOF is read."""
        if self.terrameter_cli_active:
            return self.default("")
        return True # Shell should be closed (causes cmdloop to exit)
    
    ##########    TERRAMETER COMMANDS    ##########
    def do_s(self, arg: str):
        """Set terrameter variable"""
        if not self.terrameter_cli_active:
            return self.default(f"s {arg}")
        try:
            variable = arg.split()[0]
            value = arg.split()[1]
        except Exception:
            self.print_line_sh()
            return
        if variable and value:
            try:
                self.instrument.set_variable(variable, value)
                self.print_line_sh()
                return
            except Exception:
                self.print_line_sh()
                return
        else:
            self.print_line_sh()
            return
        
    def do_g(self, arg: str):
        """Get terrameter variable"""
        if not self.terrameter_cli_active:
            return self.default(f"g {arg}")
        try:
            variable = arg.split()[0]
        except Exception:
            self.print_line_sh()
            return
        if variable:
            try:
                self.print_line_sh(f"{variable} {self.instrument.get_variable(variable)}\n")
            except Exception:
                self.print_line_sh()
                return
        else:
            self.print_line_sh()
            return

    def do_Q(self, arg: str):
        """Quit terrameter"""
        if self.terrameter_cli_active:
            self.print_line_sh(constants.TERRAMETER_OUTRO)
            self.terrameter_cli_active = False
            self.prompt=f"root@LS123456789:{self.cwd.as_posix()}# "
        else:
            return self.default(f"Q {arg}")
    
    def do_w(self, arg: str):
        """Read terrameter settings from file"""
        if self.terrameter_cli_active:
            self.instrument.read_settings(arg)
        else:
            return self.default(f"w {arg}")
        
    ##########    BASH COMMANDS    ##########
    def do_exit(self, arg: str):
        """Called when 'exit' command is entered."""
        if self.terrameter_cli_active:
            return self.default(f"exit {arg}")
        else:
            return True # Shell should be closed (causes cmdloop to exit)

    
    def do_terrameter(self, arg: str):
        if self.terrameter_cli_active:
            self.default(f"terrameter {arg}")
        else:
            self.print_line_sh(constants.TERRAMETER_INTRO)
            self.terrameter_cli_active = True
            self.prompt = "> "

    def do_help(self, arg: str):
        # Will probably never be used, so print an empty line for now.
        self.print_line_sh()
    
    def default(self, line: str):
        # Get the name of the command
        command = " "
        if line != None:
            split = line.split()
            if len(split) > 0:
                command = split[0]
        # Print error message
        if self.terrameter_cli_active:
            self.print_line_sh(constants.TERRAMETER_UNKNOWN_COMMAND(command))
        else:
            # Emulate bash
            self.print_line_sh(f"-bash: {command}: command not found")
            # zsh version
            #self.print_line_sh(f"zsh: {command}: command not found")

    def print_sh(self, chars: str):
        """Write string to stdout"""
        if self.stdout and not self.stdout.closed:
            self.stdout.write(chars)
            self.stdout.flush()

    def print_line_sh(self, chars: str = ""):
        """Write string to stdout with an appended Windows-style line terminator (CRLF)"""
        self.print_sh(chars + "\r\n")

    def emptyline(self):
        # Do nothing when receiving an empty line
        pass

if __name__ == "__main__":
    import sys
    instrument = TerrameterLS()
    shell = SimShell(instrument, sys.stdin, sys.stdout)
    shell.cmdloop()