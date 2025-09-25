from cmd import Cmd
from . import vfs
import argparse
from typing import *
from .terrameter import TerrameterLS
from . import constants

class TerrameterShell(Cmd):
    """Provides a shell to accept commands (for interacting with the terrameter software)"""
    def __init__(self, instrument: TerrameterLS, stdin: IO[str], stdout: IO[str]):
        super(TerrameterShell, self).__init__(completekey="tab", stdin=stdin, stdout=stdout)
        self.instrument = instrument
        self.cwd: vfs.Path = vfs.Path("/home/root")
        self.use_rawinput=False # Required to read from the provided stdin insted of sys.stdin 
        self.prompt="root@LS123456789:~# "
        self.terrameter_cli_active = False # Is the terrameter CLI opened
    
    def do_EOF(self, arg):
        """Called when EOF is read."""
        if self.terrameter_cli_active:
            return self.default("")
        return True # Shell should be closed (causes cmdloop to exit)
    
    ##########    TERRAMETER COMMANDS    ##########    
    def _do_terrameter_command(self, command: str, arg: str):
        arg_split = arg.split()
        match command:
            case "g":
                # Get terrameter variable
                try:
                    variable = arg_split[0]
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
            case "s":
                # Set terrameter variable
                if not self.terrameter_cli_active:
                    return self.default(f"s {arg}")
                try:
                    variable = arg_split[0]
                    value = arg_split[1]
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
            case "w":
                # Read Terrameter settings from file
                self.instrument.read_settings(arg)
                self.print_line_sh("Read settings from file: {} 0") # assume 0
            case "Q":
                # Quit terrameter
                self.print_line_sh(constants.TERRAMETER_OUTRO)
                self.terrameter_cli_active = False
                self.prompt=f"root@LS123456789:{self.cwd.as_posix()}# "
            case "P":
                # Create new Terrameter project
                try:
                    if len(arg_split) == 0:
                        # Default name: Project
                        created_project_name = self.instrument.create_project()
                    else:
                        # Uses the last argument
                        created_project_name = self.instrument.create_project(arg_split[-1])
                except: # TODO: Exception type
                    self.print_line_sh("Failed to create Project directory")
                    self.print_line_sh("Failed to create new project!")
                    return
                self.print_line_sh("Create a new Project")
                self.print_line_sh(f"Created project: {created_project_name}\n")
            case "T":
                # Create new Terrameter task
                if len(arg_split) < 9:
                    self.print_line_sh(" Too few arguments\n")
                    return
                name = arg_split[0]
                spread = arg_split[1]
                protocol = arg_split[2]
                try: 
                    spacing = tuple([float(x) for x in arg_split[3:6]])
                    unknown = tuple([float(x) for x in arg_split[6:9]]) # TODO: What is this?
                    self.instrument.create_task(name, spread, protocol, spacing, unknown)
                except ValueError:
                    self.print_line_sh()
            case "m":
                # Start/stop Terrameter measurement process
                self.instrument.measure()
                # TODO: Output
            case "S":
                # Create new Terrameter station
                raise NotImplementedError()
            case _: 
                self.print_line_sh(constants.TERRAMETER_UNKNOWN_COMMAND(command))

    ##########    BASH COMMANDS    ##########
    def do_exit(self, arg: str):
        """Called when 'exit' command is entered."""
        if self.terrameter_cli_active:
            return self._do_terrameter_command("e", f"xit {arg}")
        else:
            return True # Shell should be closed (causes cmdloop to exit)

    def do_terrameter(self, arg: str):
        if self.terrameter_cli_active:
            return self._do_terrameter_command("t", f"errameter {arg}")
        else:
            self.print_line_sh(constants.TERRAMETER_INTRO)
            self.terrameter_cli_active = True
            self.prompt = "> "
            
    def do_echo(self, arg: str):
        self.print_line_sh(arg.strip())

    def do_touch(self, arg: str):
        self.instrument.touch(arg)

    def do_help(self, arg: str):
        # Will probably never be used, so print an empty line for now.
        self.print_line_sh()
    
    def default(self, line: str):
        if self.terrameter_cli_active:
            # Forward to parser for terrameter commands
            cmd = line[0]
            arg = line[1:]
            return self._do_terrameter_command(cmd, arg)
        else:
            # Get the name of the command
            command = " "
            if line != None:
                split = line.split()
                if len(split) > 0:
                    command = split[0]
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
        """Write string to stdout with an appended line terminator (LF)"""
        self.print_sh(chars + "\n")

    def emptyline(self):
        # Do nothing when receiving an empty line
        pass

def run():
    import sys
    instrument = TerrameterLS()
    shell = TerrameterShell(instrument, sys.stdin, sys.stdout)
    shell.cmdloop()