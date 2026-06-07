# Terrameter LS 2 emulator
<sup><span style="opacity:0.6">Last updated on June 7 2026</span></sup><br>
This module simulates the SSH interface of a Terrameter LS 2 so the GeMeasPy software can be tested without physical hardware. It does not simulate physics or signal processing. What it emulates is the SSH shell, the SFTP server, an in-memory file system, the project and task data model, and the Terrameter command-line interface.

## How a test client talks to it

A test creates an `InstrumentServerEmulator` and starts it on a TCP port. Paramiko handles the SSH handshake on each incoming connection. A session may host shell, exec, and SFTP channels. Shell and exec channels run a `TerrameterShell`; SFTP channels run an `EmulatorSFTPServerInterface`. Both operate on the same `TerrameterLS` instance, which holds the state of the simulated instrument: file system, projects, variables, settings, and shutdown flags. There is one `TerrameterLS` per server because there is one physical instrument in real life.

```python
from gemeaspy.tests.terrameter_model import InstrumentServerEmulator

emu = InstrumentServerEmulator()
emu.start(host="localhost", port=0)  # port=0 picks a free port
host, port = emu.address
# ...point the software under test at (host, port)...
emu.stop()
```

The `run_server.py` script does the same thing for manual testing.

## Files

| File or folder         | Role                                                                |
| ---------------------- | ------------------------------------------------------------------- |
| `__init__.py`          | Re-exports `InstrumentServerEmulator`.                              |
| `run_server.py`        | Starts the server manually; not used by automated tests.            |
| `ssh_server.py`        | Accepts TCP connections and dispatches SSH channels.                |
| `shell.py`             | Implements the bash-like and Terrameter command interfaces.         |
| `terrameter.py`        | `TerrameterLS`, the central state object.                           |
| `vfs.py`               | In-memory file system used by `TerrameterLS`.                       |
| `project.py`           | A single project: tasks, stations, and database.                    |
| `task.py`              | A task and the XML parsers for spread and protocol files.           |
| `database.py`          | Reads and writes the SQLite `project.db` file.                      |
| `project_types.py`     | One class per database table row.                                   |
| `project_schema.sql`   | SQL schema used to initialise a new `project.db`.                   |
| `sftp.py`              | SFTP server interface that delegates to `TerrameterLS`.             |
| `host_key_store.py`    | Hard-coded RSA host key. Test use only.                             |
| `parameters.py`        | Enums for fault injection and pre-configured project states.        |
| `constants.py`         | Banner strings, default settings, and other canned text.            |
| `_logging.py`          | Configures the `gemeaspy_tests_emulator` logger.                    |
| `file_system_init/`    | Files copied into the VFS at startup.                               |

## Notes on the implementation

### Shell

`TerrameterShell` is built on Python's standard [`cmd.Cmd`](https://docs.python.org/3/library/cmd.html#cmd.Cmd). A method named `do_<name>(self, args)` implements the command `<name>`. The shell has two modes, tracked by `terrameter_cli_active`. In bash mode, lines go through the usual `cmd.Cmd` dispatcher. In Terrameter CLI mode, entered via the `terrameter` command, each line is a single letter routed by `_do_terrameter_command`, which contains one branch per Terrameter command. The intro and outro banners in `constants.py` are printed on mode change.

The `[` test command cannot be implemented as `do_[` because that is not a valid Python identifier. `precmd` rewrites it to `left_square_bracket`. If the emulator is shut down mid-command, `precmd` discards further input by swapping in empty [`StringIO`](https://docs.python.org/3/library/io.html#io.StringIO) objects.

### TerrameterLS state

`TerrameterLS` holds:

- `_filesystem`, a `VirtualFileSystem`
- `_projects`, a dict from project name to `Project`
- `_current_project_name`, the open project
- `_variables`, named values for the Terrameter CLI `g` and `s` commands
- `_settings`, acquisition settings seeded from `TERRAMETER_DEFAULT_SETTINGS`
- `allow_login` and `is_shut_down`, flags consulted by the listener thread
- `_misbehavior`, a `TerrameterMisbehavior` value used for fault injection

It also exposes a file-system API (`list_folder`, `open_file`, `read_file`, `write_file`, `make_directory`, `remove`, `stat`, and others) that both the shell and the SFTP interface call. New file operations should be added here so both interfaces benefit.

### Virtual file system

`vfs.py` implements a tree of `_File` and `_Dir` nodes in memory. Paths are [`pathlib.PurePosixPath`](https://docs.python.org/3/library/pathlib.html#pathlib.PurePosixPath) instances, kept POSIX style on every host operating system. Initial contents come from `file_system_init/` at startup. Files removed by `remove()` are moved to `/removed/...` inside the VFS rather than discarded, so tests can inspect what the software under test deleted. The VFS raises standard exceptions (`FileNotFoundError`, `IsADirectoryError`, and so on). The shell and SFTP layers translate them into the formats the real instrument would produce.

### Projects and the SQLite database

A real Terrameter stores each project under `/media/mmcblk0p1/projects/<name>/` with a `project_name.txt` and a `project.db` SQLite file. The emulator does the same. `TerrameterLS.create_project()` creates the folder, copies the default schema from `project_schema.sql` into the database blob, and wraps the result in a `Project` object.

Python's [`sqlite3`](https://docs.python.org/3/library/sqlite3.html) cannot operate on a [`BytesIO`](https://docs.python.org/3/library/io.html#io.BytesIO) directly, so `ProjectDatabase._connect_copy()` writes the in-VFS bytes to a [`NamedTemporaryFile`](https://docs.python.org/3/library/tempfile.html#tempfile.NamedTemporaryFile), opens an `sqlite3` connection against it, reads or writes the required rows, and copies the bytes back into the VFS. Each table has a matching `...Row` class in `project_types.py`. The tables `write()` persists are listed in `TERRAMETER_DATABASE_TABLE_NAMES` at the bottom of that file.

### Threading

One thread runs the TCP listener, one runs per session, and one runs per channel. Every blocking call uses a 0.1 second timeout so that `stop()` can shut things down without waiting forever. Hangs during teardown usually point here.

## Initial file system

Every file under `file_system_init/` is copied into the VFS at the same relative path at startup. Empty directories are kept with a `.gitkeep` file, which the loader skips. The current contents are:

- `home/root/protocols/`, example XML protocol files.
- `home/root/settings/`, an example settings file.
- `media/mmcblk0p1/projects/`, where projects will be created. Empty.
- `monitoring/`, used by the real Terrameter for task-control flag files
  (`task_NN_started`, `task_NN_completed`, `new_day`, `datetime.NN`). Empty.

To make a file always exist on the emulated instrument from boot, place it in the matching subdirectory. To vary a file between tests, write it into the VFS after the emulator is created.

## Fault injection and project state

Two enums in `parameters.py` cover scenarios beyond the normal path.

`TerrameterMisbehavior` is intended for fault injection (restart during measurement, dropped messages, and so on). Only `NONE` is active; the remaining cases are listed but commented out. The value can be passed to the `InstrumentServerEmulator` constructor or set through the environment variable `TERRAMETER_EMULATOR_MISBEHAVIOR`. New cases should be checked wherever the relevant behaviour is simulated, mostly in `terrameter.py`.

`TerrameterProjectState` is used by `TerrameterLS.setup_project_state()` to fast-forward the emulator to a state such as "first task currently measuring" or "all tasks completed". The mechanism uses the `/monitoring/new_day`, `/monitoring/task_NN_started`, and `/monitoring/task_NN_completed` flag files that the real acquisition program writes. The `MEASURING` state additionally toggles the `measure` variable on a [`threading.Timer`](https://docs.python.org/3/library/threading.html#threading.Timer), which can make timing-sensitive tests flaky on a busy machine (see the `TODO` in that method).

## Where to look to fix or extend things

| To...                                                  | Edit                                                       |
| ------------------------------------------------------ | ---------------------------------------------------------- |
| Add a bash command                                     | new `do_<name>` method in `TerrameterShell` (`shell.py`).  |
| Add a Terrameter CLI command                           | new branch in `_do_terrameter_command` (`shell.py`).       |
| Add a boot-time file                                   | place it under `file_system_init/`.                        |
| Change default acquisition settings                    | `TERRAMETER_DEFAULT_SETTINGS` in `constants.py`.           |
| Change boot banner or canned strings                   | `constants.py`.                                            |
| Add an instrument variable for `g` and `s`             | `TerrameterLS._variables` in `terrameter.py`.              |
| Add a project database table                           | add to `project_schema.sql`, add a `...Row` class in `project_types.py`, add a `_<TableName>` attribute on `ProjectDatabase`, and add the name to `TERRAMETER_DATABASE_TABLE_NAMES`. |
| Implement a fault-injection case                       | uncomment the case in `TerrameterMisbehavior` and add the check in `terrameter.py`. |
| Add a starting project state                           | extend `TerrameterProjectState` and the matching branch in `setup_project_state()`. |
| Add an SFTP feature                                    | extend `EmulatorSFTPServerInterface` in `sftp.py`, with a matching method on `TerrameterLS` if needed. |
| Change file system semantics                           | `vfs.py`, mainly `_traverse`, `stat`, and `remove`.        |

## Logging and standalone runs

The module logger is `gemeaspy_tests_emulator`. On import it writes to `<gemeaspy>/../log/emulator/emulator<YYYYMMDDhhmmss>.log` at DEBUG level or higher. The active log path is in `_logging.file_path` after the logger has initialised. The `/removed` branch of the VFS preserves deleted files, which is sometimes more informative than the log.

Three standalone entry points help when working outside pytest:

- `python -m gemeaspy.tests.terrameter_model.run_server` starts an SSH server on a free port. Connect with any SSH client (user `root`, empty password) to walk through commands by hand.
- The `__main__` block of `sftp.py` starts an SFTP-only server on port 24444 with a single test file at `/home/root/test.txt`.
- The `__main__` block of `database.py` runs a self-test against a reference project database. Useful when changing `project_types.py` or `project_schema.sql`.

When the emulator starts, it sets the environment variable `USETERRAMETEREMULATOR=1`. The software under test can read this to adjust any behaviour that should differ between hardware and emulator.
