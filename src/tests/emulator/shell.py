import shlex
from cmd import Cmd
from typing import *
import sys
import argparse
import re
import io  

parent_module = sys.modules['.'.join(__name__.split('.')[:-1]) or '__main__']
if __name__ == '__main__' or parent_module.__name__ == '__main__':
    import constants, vfs
    from terrameter import TerrameterLS
else:
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
    
    # Resolve the special character ~ for home dir. 
    # Could be precompiled for performance, but not likely needed
    args = re.sub(r"(^|[\s])~([/\s]|$)", r"\1/home/root\2", args)

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
                    if arg_list[-1] == c:
                        arg_list[-1] += c # Not accurate if bad sequence of > < is provided 
                    else:
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
        self.use_rawinput=False 
        """Required to read from the provided stdin insted of sys.stdin""" 
        self.prompt="root@LS123456789:~# "
        self.terrameter_cli_active = False 
        """Is the terrameter CLI opened"""
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
        if self.instrument.is_shut_down:
            self.terrameter_cli_active = False
            self.stdin = io.StringIO()
            self.stdout = io.StringIO()
            return ""
        if self.pty:
            self.print_line_sh(line)
        line = line.strip()
        # Override
        if len(line) > 1 and line.split(maxsplit=1)[0] == "[":
            return line.replace("[", "left_square_bracket", 1)
        return line
    
    def postcmd(self, stop: bool, line: str) -> bool:
        if self.instrument.is_shut_down:
            return True
        else:
            return stop
    
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
        
        # Should we interpret e.g. \n as a newline?
        backslash_escapes = arg_list[0] == "-e"
        if backslash_escapes:
            arg_list = arg_list[1:]
        should_print_final_newline = True # Should this command exit with a newline to console? Used for character '\c'
        
        outfile = "&1" # &1 for stdout
        append = ">>" in arg_list # Append to outfile? (for >>)
        
        num_text_segments = len(arg_list) # How many text segments to echo
        for i, arg in enumerate(arg_list):
            if arg in (">", ">>"):
                if num_text_segments == len(arg_list):
                    num_text_segments = i
                if i+1 < len(arg_list):
                    outfile=arg_list[i+1]
                else:
                    self.print_line_sh("-bash: syntax error near unexpected token `newline'")
            if backslash_escapes:
                arg = arg.replace(r"\\", "\\")
                arg = arg.replace(r"\a", "\a")
                arg = arg.replace(r"\b", "\b")
                arg = arg.replace(r"\f", "\f")
                arg = arg.replace(r"\n", "\n")
                arg = arg.replace(r"\r", "\r")
                arg = arg.replace(r"\t", "\t")
                arg = arg.replace(r"\v", "\v")
                e_index = arg.find(r"\e") # Escape (this argument)
                if e_index >= 0:
                    arg = arg[:e_index]
                c_index = arg.find(r"\c") # Produce no further output (this command)
                if c_index >= 0:
                    should_print_final_newline = False
                    arg_list[i] = arg[:c_index]
                    arg_list = arg_list[:(i+1)]
                    break
                arg_list[i] = arg
        
        if outfile == "&1":
            self.print_line_sh(" ".join(arg_list[:num_text_segments]))
        else:
            try:
                self.instrument.write_file_utf8(file_path=outfile, data=" ".join(arg_list[:num_text_segments]), relative_to=self.cwd, append=append)
            except OSError as e:
                self.print_os_error("-bash", e)
        if should_print_final_newline:
            self.print_line_sh()
    
    def do_cd(self, args: str):
        split_args = _split_args(args)
        if len(split_args) > 1:
            self.print_line_sh("-bash: cd: too many arguments")
            return
        elif len(split_args) == 0:
            self.cwd = vfs.Path("/home/root")
            return
        try:
            self.instrument.list_folder(split_args[0], self.cwd)
        except OSError as e:
            self.print_os_error("-bash: cd", e)
            return
        self.cwd = self.instrument.canonical_absolute_path(self.cwd.joinpath(split_args[0]), self.cwd)

    def do_ls(self, args: str):
        # Not very accurate to the real thing
        split_args = _split_args(args)
        if len(split_args) == 0:
            split_args.append(self.cwd.as_posix())
        folders = {}
        
        for path in split_args:
            try:
                folders[path] = self.instrument.list_folder(path, self.cwd)
            except OSError as e:
                self.print_os_error("-bash: ls", e)
                return
                
        for folder_path in folders:
            files = folders[folder_path]
            if len(split_args) > 1:
                self.print_line_sh(f"{folder_path}:")
                self.print_sh(" ")
            for name in files:
                self.print_line_sh(name)
            self.print_line_sh()
    
    def do_more(self, args: str):
        # Doesn't actually allow scrolling for large files
        paths = _split_args(args)
        buffer: list[tuple[str, str]] = [] # [(path, text), ...]
        for path in paths:
            try:
                path_data = self.instrument.read_file(path, self.cwd)
                buffer.append((path, path_data.decode()))
            except IsADirectoryError as e:
                self.print_line_sh(f"\n*** {path}: directory ***\n")
            except FileNotFoundError as e:
                self.print_line_sh(f"more: cannot open {path}: No such file or directory")
            except OSError as e:
                self.print_os_error("more", e)
            except UnicodeDecodeError as e:
                self.print_line_sh(f"\n******** {path}: Not a text file ********\n")
        if len(buffer) == 1:
            self.print_line_sh(buffer[0][1])
        elif len(buffer) > 1:
            for path, text in buffer:
                self.print_line_sh("::::::::::::::")
                self.print_line_sh(path)
                self.print_line_sh("::::::::::::::")
                self.print_line_sh(text)
        self.print_line_sh()

    def do_rm(self, args: str):
        class MissingArgumentError(Exception):
            pass
        
        def argparse_error(message):
            raise MissingArgumentError("Argument parser exception")
        
        args_list = _split_args(args)

        parser = argparse.ArgumentParser("rm", exit_on_error=False)
        parser.error = argparse_error
        
        parser.add_argument("-r", "-R", "--recursive", action="store_true")
        parser.add_argument("files", action="extend", nargs="+", type=str)
        try:
            args_namespace, _ = parser.parse_known_args(args_list)
        except MissingArgumentError:
            self.print_line_sh("rm: missing operand")
            self.print_line_sh("Try 'rm --help' for more information.\n")
            return
        
        for path in args_namespace.files:
            try:
                self.instrument.remove(path, self.cwd, args_namespace.recursive)
            except OSError as e:
                self.print_line_sh(f"rm: cannot remove '{path}': {e.strerror}")
        self.print_line_sh()
        
    def do_mkdir(self, args: str):
        args_list = _split_args(args)
        for path in args_list:
            try:
                self.instrument.make_directory(path, self.cwd)
            except OSError as e:
                self.print_line_sh(f"rm: cannot create directory '{path}': {e.strerror}")
        self.print_line_sh()

    def do_touch(self, args: str):
        path = _split_args(args)[0]
        try:
            self.instrument.touch(path, self.cwd)
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

        # implementation of test
        result = False
        match arg_list:
            case []:
                pass
            case [arg]:
                if arg:
                    result = True
            case ["-e", path]:
                result = self.instrument.path_exists(path, self.cwd)
            case _:
                raise NotImplementedError()

        # execute another command based on result
        self.onecmd(shlex.join(true_cmd if result else false_cmd))

    def do_left_square_bracket(self, args: str):
        split_args = _split_args(args)
        try:
            right_bracket_index = split_args.index("]")
        except ValueError:
            self.print_line_sh("-bash: [: missing `]'")
            return
        separator_index = len(args) # >= len(args) implies none found
        try:
            separator_index = split_args.index("&&")
        except:
            pass
        try:
            separator_index = min(separator_index, split_args.index("||"))
        except:
            pass
        if separator_index < len(args):
            # one of || or && must immediately follow ] if they're present
            if separator_index != right_bracket_index + 1:
                self.print_line_sh("-bash: [: missing `]'")
                return
        
        adapted_args = split_args[:right_bracket_index] + split_args[right_bracket_index+1:]
        return self.do_test(" ".join([f'"{a}"' for a in adapted_args]))

    def do_help(self, args: str):
        # Will probably never be used, so print an empty line for now.
        self.print_line_sh()
        
    def do_shutdown(self, args: str):
        class MissingArgumentError(Exception):
            pass
        
        def argparse_error(message):
            raise MissingArgumentError("Argument parser exception")
        
        args_list = _split_args(args)

        parser = argparse.ArgumentParser("shutdown", exit_on_error=False)
        parser.error = argparse_error
        
        parser.add_argument("-r", action="store_true", dest="reboot")
        parser.add_argument("time", nargs="?", type=str, default="+1")
        parser.add_argument("wall", nargs="?", type=str, default=None)
        
        parser.parse_known_args(_split_args(args))
        try:
            args_namespace, _ = parser.parse_known_args(args_list)
        except MissingArgumentError:
            return
        
        time_str: str = args_namespace.time
        if re.fullmatch(r"now", time_str, flags=re.IGNORECASE):
            seconds = 0
        if re.fullmatch(r"^\+?[0-9]+$", time_str):
            seconds = int(time_str.removeprefix("+")) * 60
        elif re.fullmatch(r"^[0-9]{1,2}:[0-9]{1,2}$", time_str):
            hours_str, minutes_str = time_str.split(":")
            hours = int(hours_str)
            minutes = int(minutes_str)
            if hours > 59 or minutes > 59:
                self.print_line_sh(f"Failed to parse time specification: {time_str}")
            seconds = (minutes + hours * 60) * 60
        else:
            self.print_line_sh(f"Failed to parse time specification: {time_str}")
        self.instrument.initialise_shutdown(timer_seconds=seconds)
        self.print_line_sh(f"Shutdown scheduled for {"%a %Y-%m-%d %H:%M:%S %Z"}, use 'shutdown -c' to cancel.\n") #TODO: Get timestamp 
    
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
    pty = PtyRequest(width = 100, height = 60)
    shell = TerrameterShell(instrument, sys.stdin, sys.stdout, pty)
    shell.cmdloop()

if __name__ == "__main__":
    run()