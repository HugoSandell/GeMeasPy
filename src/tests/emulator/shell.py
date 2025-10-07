import shlex
from cmd import Cmd
from typing import *

from . import constants, vfs
from .terrameter import TerrameterLS

class PtyRequest:
    """A request for a pseudo terminal.
    Terminal, width, height, pixel_width, pixel_height"""
    def __init__(self, terminal: str = "vt100", 
                 width: int = 80, height: int = 24, 
                 width_pixels: int = 0, height_pixels: int = 0):
        self.terminal: str = terminal
        self.width: int = width
        self.height: int = height
        self.width_pixels: int = width_pixels
        self.height_pixels: int = height_pixels

def _split_args(args: str) -> list[str]:
    # Only supports single level of quotation
    arg_list = [] # Store result here
    part_start = -1 # Where the current argument starts in the string. Negative for no part.
    excluded_characters = [] # Indices of which characters to exclude from the part, relative to part_start
    quote_start = -1 # Where a quote (single or double) was opened. Negative for no open quote.
    
    # End the current part at the given index (exclusive) and add it to the argument list
    def end_part(end: int):
        nonlocal part_start, excluded_characters, arg_list
        part = args[part_start:end]
        excluded_characters.sort(reverse=True) # Just to be sure
        for ec in excluded_characters:
            part = part[:ec] + part[ec+1:]
        excluded_characters.clear()
        part_start = -1
        arg_list.append(part)
    
    for i, c in enumerate(args + " "):
        match c:
            case '"' | "'":
                if quote_start >= 0:
                    # Close quote if char matches opening quote
                    if args[quote_start] == c: 
                        quote_start = -1
                        excluded_characters.append(i - part_start)
                else:
                    # Open quote
                    quote_start = i
                    if part_start < 0:
                        part_start = i+1
                    else:
                        excluded_characters.append(i - part_start)
            case " " | "\t" | "\n":
                is_last_char = i == len(args) - 1
                if (quote_start < 0 or is_last_char) and part_start >= 0:
                    end_part(i)
            case "<" | ">":
                if quote_start < 0:
                    end_part(i)
                    arg_list.append(c)
            case _:
                if part_start < 0:
                    part_start = i
    # Add last part, even if quote isn't closed
    if part_start >= 0 and len(arg_list) - part_start > 1:
        arg_list.append(args[part_start:])
    return arg_list

class TerrameterShell(Cmd):
    """Provides a shell to accept commands (for interacting with the terrameter software)"""
    def __init__(self, instrument: TerrameterLS, stdin: IO[str], stdout: IO[str], pty: PtyRequest = None):
        super(TerrameterShell, self).__init__(completekey="tab", stdin=stdin, stdout=stdout)
        self.instrument = instrument
        self.cwd: vfs.Path = vfs.Path("/home/root")
        self.use_rawinput=False # Required to read from the provided stdin insted of sys.stdin 
        self.prompt="root@LS123456789:~# "
        self.terrameter_cli_active = False # Is the terrameter CLI opened
        self.pty = pty is not None
        if self.pty:
            self.width = pty.width
            self.height = pty.height
            self.line_terminator = "\r\n"
        else:
            self.line_terminator = "\n"

    def print_os_error(self, program: str, error: OSError):
        if error.filename != "":
            self.print_line_sh(f"{program}: {error.filename}: {error.strerror}")
        else:
            self.print_line_sh(f"{program}: {error.strerror}")
        
    
    def precmd(self, line: str) -> str:
        self.print_line_sh(line)
        line = line.strip()
        # Override
        if len(line) > 1 and line.split(maxsplit=1)[0] == "[":
            return line.replace("[", "left_square_bracket", 1)
        return line
    
    def do_EOF(self, arg):
        """Called when EOF is read."""
        if self.terrameter_cli_active:
            return self.default("")
        return True # Shell should be closed (causes cmdloop to exit)
    
    ##########    TERRAMETER COMMANDS    ##########    
    def _do_terrameter_command(self, command: str, args: str):
        arg_split = args.split()
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
                        self.print_line_sh(f"{variable}\t{self.instrument.get_variable(variable)}\n")
                    except Exception:
                        self.print_line_sh()
                        return
                else:
                    self.print_line_sh()
                    return
            case "s":
                # Set terrameter variable
                if not self.terrameter_cli_active:
                    return self.default(f"s {args}")
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
                try:
                    self.instrument.read_settings(_split_args(args)[-1])
                except OSError as e:
                    self.print_os_error("terrameter", e)
                    return
                self.print_line_sh(f"Read settings from file: {args} 0") # assume 0
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
    def do_exit(self, args: str):
        """Called when 'exit' command is entered."""
        if self.terrameter_cli_active:
            return self._do_terrameter_command("e", f"xit {args}")
        else:
            return True # Shell should be closed (causes cmdloop to exit)

    def do_terrameter(self, args: str):
        if self.terrameter_cli_active:
            return self._do_terrameter_command("t", f"errameter {args}")
        else:
            self.print_line_sh(constants.TERRAMETER_INTRO)
            self.terrameter_cli_active = True
            self.prompt = "> "
            
    def do_echo(self, args: str):
        arg_list = _split_args(args)
        outfile = "&1" # &1 for stdout
        
        num_text_segments = len(arg_list) # How many text segments to echo
        for i, arg in enumerate(arg_list):
            if arg == ">":
                if num_text_segments == len(arg_list):
                    num_text_segments = i
                if i+1 < len(arg_list):
                    outfile=arg_list[i+1]
                else:
                    self.print_line_sh("-bash: syntax error near unexpected token `newline'")
        if outfile == "&1":
            self.print_line_sh(" ".join(arg_list[:num_text_segments]))
        else:
            try:
                self.instrument.write_file_utf8(outfile, " ".join(arg_list[:num_text_segments]))
            except OSError as e:
                self.print_os_error("-bash", e)
                return

    def do_touch(self, args: str):
        path = _split_args(args)[0]
        try:
            self.instrument.touch(path)
        except OSError as e:
            self.print_os_error("-bash", e)
            return

    # Also known as `[`
    # Currently only supports testing for existence of paths.
    def do_test(self, args: str):
        arg_list = _split_args(args)

        # Logic operators are not implemented at the shell level, so handle them
        # specially here. Does not work correctly if the same operator occurs twice.
        try:
            true_i = arg_list.index("&&")
        except ValueError:
            true_i = len(arg_list)
        try:
            false_i = arg_list.index("||")
        except ValueError:
            false_i = len(arg_list)

        # split out commands to execute based on result
        true_cmd = arg_list[true_i + 1 : false_i if false_i > true_i else None]
        false_cmd = arg_list[false_i + 1 : true_i if true_i > false_i else None]
        arg_list = arg_list[: min(true_i, false_i)]
        
        # Ignore closing ]
        if "]" in arg_list:
            arg_list.remove("]") 

        # implementation of test
        result = False
        match arg_list:
            case []:
                pass
            case [arg]:
                if arg:
                    result = True
            case ["-e", path]:
                result = self.instrument.path_exists(path)
            case _:
                raise NotImplementedError()

        # execute another command based on result
        self.onecmd(shlex.join(true_cmd if result else false_cmd))

    def do_left_square_bracket(self, args: str):
        split_args = _split_args(args)
        if "]" not in split_args:
            self.print_line_sh("-bash: [: missing `]'")
        self.do_test(args)

    def do_help(self, args: str):
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
        if not self.stdout or self.stdout.closed:
            return    
        self.stdout.write(chars)
        self.stdout.flush()
        
    def print_line_sh(self, chars: str = ""):
        """Write string to stdout with an appended line terminator (CRLF)"""
        self.print_sh(chars + self.line_terminator)

    def emptyline(self):
        # Do nothing when receiving an empty line
        pass

def run():
    import sys
    instrument = TerrameterLS()
    shell = TerrameterShell(instrument, sys.stdin, sys.stdout, pty={"terminal": "vt100", "width": 80, "height": 24, "width_pixels": 0, "height_pixels": 0})
    shell.cmdloop()