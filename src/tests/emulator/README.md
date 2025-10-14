# Terrameter LS 2 Emulator
This module loosely emulates the SSH port of a Terrameter LS 2.  
Its purpose is to allow testing of the main software without requiring physical access to a Terrameter unit and to allow faster testing by merely mimicking its behaviour.

## file_system_init
This directory contains the files to be loaded onto the emulated instrument upon initialisation.

## ssh_server.py
The main interface of this module. 
`InstrumentServerEmulator` is the main class. It implements an SSH server which handles shell sessions, command execution requests, and SFTP sessions. SFTP support is mainly handled in `sftp.py`. It creates one instance of `TerrameterLS` from `terrameter.py`, which emulates the functionality of the Terrameter software and hardware. Instances of `TerrameterShell` from `shell.py` are created to handle command execution or provide a shell (emulating bash). `TerrameterShell` also provides the interface for the Terrameter software. 

## shell.py
Reads commands sent over SSH and tries to replicate the behaviour of a bash shell or the Terrameter LS 2 CLI. Support for new commands and behaviours should be added as necessary. Shell commands are handled in methods with the signature `do_{command name}(self, args: str)`. Terrameter commands are handled in the `_do_terrameter_command` method. See the Python Standard Library `cmd` module for more information about how commands are processed.

## terrameter.py
The `TerrameterLS` class handles the internal state of the Terrameter LS 2, including a virtual file system (implemented in `vfs.py`) and execution state of the terrameter software.
  
## vfs.py
In-memory virtual file system for `TerrameterLS` to use.

## project.py
Support for the Terrameter LS2 project data.

## database.py
Support for the sqlite3 files used by Terrameter LS 2 to store project data. Uses local temporary files to bridge the `sqlite3` module's interface with the in-memory storage used by the virtual file system.