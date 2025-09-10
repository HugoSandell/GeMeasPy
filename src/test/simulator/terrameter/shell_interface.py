from typing import *
from terrameter import TerrameterLS
import argparse

class TerrameterShell():
    def __init__(self, instrument: TerrameterLS):
        self._instrument = instrument
        self.__configure_parsers()

    def __configure_parsers(self):
        self._parser = argparse.ArgumentParser('terrameter', exit_on_error=False)

        subparsers = self._parser.add_subparsers(dest='subcommand')
        s_parser = subparsers.add_parser('s', exit_on_error=False)
        s_parser.add_argument('variable')
        s_parser.add_argument('value')

        g_parser = subparsers.add_parser('g', exit_on_error=False)
        g_parser.add_argument('variable')

    def execute_command(self, command: str) -> str:
        try:
            args_ns, extra_args = self._parser.parse_known_args(command.split())
            if extra_args:
                return "terrameter: Too many arguments" # TODO: match real output
        except argparse.ArgumentError as e:
            return "terrameter: Invalid command" # TODO: match real output
        
        match args_ns.subcommand:
            case 's':
                if args_ns.variable and args_ns.value:
                    try:
                        self._instrument.set_variable(args_ns.variable, args_ns.value)
                        return ''
                    except Exception:
                        return 'terrameter: bad argument(s)' # TODO: match real output
                else:
                    return 'terrameter: missing argument(s)' #TODO: match real output
            case 'g':
                if args_ns.variable:
                    try:
                        return str(self._instrument.get_variable(args_ns.variable))
                    except Exception:
                        return 'terrameter: bad argument' #TODO: match real output
                else:
                    return 'terrameter: missing argument' #TODO: match real output
        print(f'Args: {args_ns}')
        return 'terrameter: Invalid command'
        
if __name__ == '__main__':
    # Test this file
    instrument = TerrameterLS()
    shell = TerrameterShell(instrument)
    command = 's measure 9'
    print(f"> {command}")
    print(f"< {shell.execute_command(command)}")
    command = 'g measure'
    print(f"> {command}")
    print(f"< {shell.execute_command(command)}")
    command = 's measur 9'
    print(f"> {command}")
    print(f"< {shell.execute_command(command)}")
    command = 'g measur'
    print(f"> {command}")
    print(f"< {shell.execute_command(command)}")
    command = 'f a'
    print(f"> {command}")
    print(f"< {shell.execute_command(command)}")
    command = 'g measure 77'
    print(f"> {command}")
    print(f"< {shell.execute_command(command)}")
    