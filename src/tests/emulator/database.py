"""Terrameter LS2 project database file utilities."""
import sqlite3
from datetime import datetime, timezone
from typing import *
import os 
import tempfile
from .project_types import *

Path: TypeAlias = str | bytes | os.PathLike 
FileDescriptorOrPath: TypeAlias = int | Path

class ProjectDatabase:
    """Terrameter LS2 project database."""
    def __init__(self, db_file: Optional[FileDescriptorOrPath] = None):
        self._AcqSettings: list[AcqSettingsRow] = []
        self._CommonSchemaVersion: CommonSchemaVersionRow = CommonSchemaVersionRow()
        self._DP_ABMN: list[DP_ABMNRow] = []
        self._DatasetItems: list[DatasetItemsRow] = []
        self._Datasets: list[DatasetsRow] = []
        self._Electrodes: list[ElectrodesRow] = []
        self._Measures: list[MeasuresRow] = []
        self._Tasks: list[TasksRow] = []
        self._Sessions: list[SessionsRow] = []
        self._Stations: list[StationsRow] = []
        self._file: Optional[Path] = None
        self._tmpfile: Optional[tuple[int, str]] = None # (file descriptor, path)
        if db_file is not None:
            self.open(db_file)

    def is_open(self):
        return self._file != None and self._tmpfile != None

    def open(self, db_file: FileDescriptorOrPath):
        """Open the provided stream as the active database.  
        Closes previously opened database if any.  
        Raises TypeError if db_file is not a file descriptor or path.
        Raises OSError or RuntimeError if file or SQLite operations fail."""
        if not isinstance(db_file, (int, str, bytes, os.PathLike)):
            raise TypeError(f"db_file should be string, bytes or os.PathLike, not {type(db_file)}")
        self._file = db_file

        # Create a temporary file as a middle ground between the file and sqlite3.
        # sqlite3 cannot work with file descriptors        
        with open(db_file, "rb", closefd=isinstance(db_file, Path)) as dbf:
            raw_data = dbf.read()
        self._tmpfile = tempfile.mkstemp(prefix="gemeaspy")    
        tmp_file_stream = open(file=self._tmpfile[0], mode="r+b")
        tmp_file_stream.write(raw_data)
        tmp_file_stream.close()
        try:
            connection = sqlite3.connect(self._tmpfile[1])
        except sqlite3.OperationalError as e:
            raise RuntimeError("Something went wrong when opening temporary database file.") from e

        # Get tables
        cursor = connection.execute(r"SELECT `name` FROM `sqlite_master` WHERE type='table';")
        tables: list[str] = [table_name for (table_name,) in cursor]
        
        for table in tables:
            # See if table has a matching defined row type and attribute in ProjectDatabase
            row_class = globals().get(table + "Row")
            if not row_class or not hasattr(self, "_" + table):
                continue
            
            attribute = getattr(self, "_" + table)
            
            # Get column names
            column_names = ()
            cursor = connection.execute(f"PRAGMA table_info(`{table}`)")
            for (_, column_name, _, _, _, _) in cursor:
                column_names += (column_name,)
            
            # Get all rows from table and add to this object
            query = f"SELECT {", ".join(column_names)} FROM {table}"
            cursor = connection.execute(query)
            for row in cursor:
                new_row = row_class()
                for i in range(len(column_names)):
                    setattr(new_row, column_names[i], row[i])                      
                if isinstance(attribute, list):
                    attribute.append(new_row)
                else: # Support for single row attributes
                    attribute = new_row
                    break
        cursor.close()
        connection.close()

    def close(self):
        self._file = None
        if self._tmpfile:
            try:
                os.remove(self._tmpfile[1])
            except (OSError, FileNotFoundError):
                pass
        self._tmpfile = None
    
    def get_AcqSetting(self, key1: int, key2: int, name: str) -> Optional[int | float | list[float]]:
        """Get a value from the AcqSettings table.
        May return None if no match was found"""
        for row in self._AcqSettings:
            if row.key1 == key1 and row.key2 == key2 and row.Setting == name:
                value = None
                try:
                    value = int(row.Value)
                except:
                    try:
                        value = float(row.Value)
                    except:
                        try:
                            value = [float(v) for v in row.Value.split()]
                        except:
                            return None # Bad value
                return value
    
    def set_AcqSetting(self, key1: int, key2: int, name: str, value: int | float | list[float], auto: int = 0):
        """Update the content of the AcqSettings table."""
        for row in self._AcqSettings:
            if row.key1 == key1 and row.key2 == key2 and row.Setting == name:
                if isinstance(value, list):
                    row.Value = " ".join(value)
                else:
                    row.Value = str(value)
                return
        # Setting not found; add it
        new_row = AcqSettingsRow()
        new_row.key1 = key1
        new_row.key2 = key2
        new_row.Auto = auto
        self._AcqSettings.append(new_row)

if __name__ == "__main__":
    # Testing script
    import pathlib

    # Find path to reference database file
    relative_path = "reference/reference_measurement_data/project.db"
    path = pathlib.Path(__file__).parents[1].resolve().joinpath(relative_path).as_posix()

    def check_output():
        # Loose output validation
        # AcqSettings
        settings = [{'Setting': row.Setting, 'Value': row.Value, 'key1': row.key1, 'key2': row.key2, 'Auto': row.Auto} for row in db._AcqSettings]
        assert {'Setting': 'IP_OffTimeSec', 'Value': '1.000000', 'key1': 1, 'key2': -1, 'Auto': 0} in settings
        assert {'Setting': 'Measure_SNR', 'Value': '0', 'key1': 1, 'key2': -1, 'Auto': 0} in settings
        assert {'Setting': 'BoreholeStepDown', 'Value': '1', 'key1': 1, 'key2': -1, 'Auto': 0} in settings
        assert {'Setting': 'IP_MinOffTimeSec', 'Value': '1.000000', 'key1': 2, 'key2': -1, 'Auto': 0} in settings
        assert {'Setting': 'Fullwaveform', 'Value': '0', 'key1': 2, 'key2': -1, 'Auto': 0} in settings
        # Tasks
        tasks = [{'Setting': row.Setting, 'Value': row.Value, 'key1': row.key1, 'key2': row.key2, 'Auto': row.Auto} for row in db._AcqSettings]
        # DP_ABMN
        dp_abmn = [{'ID': row.ID, 'TaskID': row.TaskID, 'DPKEY': row.DPKEY} for row in db._DP_ABMN]
        assert {'ID': 194, 'TaskID': 1, 'DPKEY': [19,0,0,37,0,0,29,0,0,31,0,0,-2]} in dp_abmn
    
    
    print("Running with file descriptor")
    f = open(path, "r+b")
    db = ProjectDatabase(f.fileno())
    db.close()
    assert not f.closed
    f.close()
    check_output()
    
    print("Running with file path")
    db = ProjectDatabase(path)
    db.close()
    check_output()
        
    print("Running with file opened with `with` keyword")
    with open(path, "r+b") as f:
        db = ProjectDatabase(f.fileno())
        db.close()
    check_output()
    
    print("Running with bad argument type")
    raised_correct_exception = False
    try:
        db = ProjectDatabase([1,2,3])
        db.close()
    except Exception as e:
        if isinstance(e, TypeError):
            raised_correct_exception = True
    assert raised_correct_exception
    
    print("Running with nonexistent file")
    raised_correct_exception = False
    try:
        db = ProjectDatabase("file/that/does/not/exists.txt")
    except FileNotFoundError:
        raised_correct_exception = True
    assert raised_correct_exception
    
    print("Tests done!")