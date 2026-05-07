"""Terrameter LS2 project database file utilities."""

import io
import os
import sqlite3
from functools import cache
from sqlite3 import Connection
from tempfile import NamedTemporaryFile, _TemporaryFileWrapper
from typing import Any, TypeAlias

from .project_types import *

Path: TypeAlias = str | bytes | os.PathLike
File: TypeAlias = Path | io.BufferedIOBase

class ProjectDatabase:
    """Terrameter LS2 project database."""
    def __init__(self, db_file: File | None = None):
        self._AcqSettings: list[AcqSettingsRow] = []
        self._CommonSchemaVersion: CommonSchemaVersionRow = CommonSchemaVersionRow()
        self._ProjectSchemaVersion: ProjectSchemaVersionRow = ProjectSchemaVersionRow()
        self._DPV: list[DPVRow]= []
        self._DP_ABMN: list[DP_ABMNRow] = []
        self._DP_MEASURE: list[DP_MEASURERow] = []
        self._DatasetItems: list[DatasetItemsRow] = []
        self._Datasets: list[DatasetsRow] = []
        self._Electrodes: list[ElectrodesRow] = []
        self._Measures: list[MeasuresRow] = []
        self._Sessions: list[SessionsRow] = []
        self._Stations: list[StationsRow] = []
        self._TaskSettings: list[TaskSettingsRow] = []
        self._Tasks: list[TasksRow] = []
        self._sqlite_sequence: list[sqlite_sequenceRow] = []
        self._Log: list[LogRow] = []
        self._Positions: list[PositionsRow] = []
        self._GPSPositions: list[GPSPositionsRow] = []
        self._EventSources: list[EventSourcesRow] = []
        self._ExternalData: list[ExternalDataRow] = []
        self._Datatype: list[DatatypeRow] = []
        self._file: File | None = None
        if db_file is not None:
            self.open(db_file)
    
    def __del__(self):
        self.close()
            
    def is_open(self):
        return self._file != None

    @staticmethod
    def _connect_copy(file: File) -> tuple[_TemporaryFileWrapper, Connection]:
        """Copy the SQLite database `file` to a temporary file and open a connection to it"""

        # Create a temporary file as a middle ground between the file and sqlite3.
        # sqlite3 doesn't accept `io.BufferedIOBase` objects.
        if isinstance(file, Path):
            with open(file, "rb") as dbf:
                raw_data = dbf.read()
        else:
            if file.seekable():
                file.seek(0)
            raw_data = file.read()

        tmp_f = NamedTemporaryFile(
            mode="wb", prefix="gemeaspytest_", suffix=".db", delete_on_close=False
        )
        tmp_f.write(raw_data)
        tmp_f.close()

        # Create SQLite connection to temporary database file
        try:
            def date_adapter(object_date: datetime) -> str:
                """sqlite3 gives warnings if default adapter is used"""
                print('Adapter called')
                adapter_format_str = object_date.isoformat()
                return adapter_format_str
            sqlite3.register_adapter(datetime, date_adapter)
            connection = sqlite3.connect(tmp_f.name)
        except sqlite3.OperationalError as e:
            raise RuntimeError(
                "Something went wrong when opening temporary database file."
            ) from e

        return (tmp_f, connection)

    def open(self, file: File):
        """Open the provided stream as the active database.
        Closes previously opened database if any.
        Raises TypeError if db_file is not a binary I/O stream or path.
        Raises OSError or RuntimeError if file or SQLite operations fail."""
        if not isinstance(file, (io.BufferedIOBase, str, bytes, os.PathLike)):
            raise TypeError(
                f"file should be binary stream or file path, not {type(file)}"
            )
        self._file = file

        (tmp_f, connection) = self._connect_copy(file)

        # Get tables
        cursor = connection.execute(r"SELECT `name` FROM `sqlite_master` WHERE type='table';")
        tables: list[str] = [table_name for (table_name,) in cursor]
        
        for table in tables:
            # See if table has a matching defined row type and attribute in ProjectDatabase
            row_class = globals().get(table + "Row")
            table_attr = "_" + table
            if not row_class or not hasattr(self, table_attr):
                continue

            # Reset the attribute for this table
            setattr(self, table_attr, type(getattr(self, table_attr))())
            attribute = getattr(self, table_attr)

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
                    setattr(self, table_attr, new_row)
                    break
        cursor.close()
        connection.close()
        del tmp_f

    def write(self, file: File | None = None):
        """Write to file. Default (file=None) is the currently opened file. file must be an existing database file"""
        if file == None:
            if not self.is_open():
                raise FileNotFoundError("Tried to write to currently open file, but no file is open")
            assert self._file is not None
            file = self._file

        # Read existing data from file. This lets us initialise the database
        (tmp_f, connection) = self._connect_copy(file)

        # Write rows
        with connection:
            for table_name in TERRAMETER_DATABASE_TABLE_NAMES:
                attribute_name = "_" + table_name
                if not hasattr(self, attribute_name):
                    continue
                data = getattr(self, attribute_name)
                
                # Normalise non-list attributes
                if not isinstance(data, list):
                    data = [data] 
                
                # Clear existing rows
                connection.execute(f"DELETE FROM `{table_name}`")
                if len(data) == 0:
                    continue
                
                for row in data:
                    row_dict: dict[str, Any] = row.__dict__
                    column_names = ",".join([key.removeprefix("_") for key in row_dict.keys()])
                    values = tuple(row_dict.values())
                    query = f"INSERT INTO `{table_name}` ({column_names}) VALUES({",".join(["?"] * len(values))})"
                    connection.execute(query, values)
        connection.close()
        
        # Copy contents of temporary file to the provided file
        with open(file=tmp_f.name, mode="rb") as tmpfs:
            tmpfs.seek(0)
            new_data = tmpfs.read()

        del tmp_f

        if isinstance(file, Path):
            with open(file, "wb") as dbf:
                dbf.truncate(0)
                dbf.seek(0)
                dbf.write(new_data)
        elif isinstance(file, io.BufferedIOBase):
            file.truncate(0)
            file.seek(0)
            file.write(new_data)
            file.flush()
    
    def close(self):
        self._file = None
    
    def get_AcqSetting(self, key1: int, key2: int, name: str) -> int | float | list[float] | None:
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
                    row.Value = " ".join([str(x) for x in value])
                else:
                    row.Value = str(value)
                return
        # Setting not found; add it
        new_row = AcqSettingsRow()
        new_row.key1 = key1
        new_row.key2 = key2
        new_row.Auto = auto
        self._AcqSettings.append(new_row)

    def tasks(self) -> list[TasksRow]:
        return self._Tasks


@cache
def default_project_database() -> bytes:
    con = sqlite3.connect(":memory:")

    file_path = os.path.join(os.path.dirname(__file__), "project_schema.sql")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        con.executescript(content)

    return con.serialize()


if __name__ == "__main__":
    # Testing script
    import pathlib

    # Find path to reference database file
    relative_path = "reference/reference_measurement_data/project.db"
    path = pathlib.Path(__file__).parents[1].resolve().joinpath(relative_path).as_posix()

    def check_output():
        # Validate some of the data to see that it's been loaded correctly. 
        # Should not be called if database has been altered
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
        assert {'ID': 194, 'TaskID': 1, 'DPKEY': "19;0;0;37;0;0;29;0;0;31;0;0;-2"} in dp_abmn
    
    print("Running with file path")
    db = ProjectDatabase(path)
    db.close()
    check_output()
    
    print("Running with bad argument type")
    raised_correct_exception = False
    try:
        db = ProjectDatabase([1,2,3])  # type: ignore
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
    
    print("Running with BytesIO")
    file = io.BytesIO()
    with open(path, "rb") as f:
        file.write(f.read())
    file.flush()
    file.seek(0)
    db = ProjectDatabase(file)
    check_output()
    assert db.get_AcqSetting(1,-1,"CurrentLimitHighAmpere") == 0.05
    db.set_AcqSetting(1,-1,"CurrentLimitHighAmpere", 0.06)
    assert db.get_AcqSetting(1,-1,"CurrentLimitHighAmpere") == 0.06
    db.write()
    db.close()
    db = ProjectDatabase()
    db.open(file)
    stored_value = db.get_AcqSetting(1, -1, "CurrentLimitHighAmpere")
    assert stored_value == 0.06
    
    print("Tests done!")