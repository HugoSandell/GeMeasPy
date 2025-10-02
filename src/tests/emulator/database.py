"""Terrameter LS2 project database file utilities."""
import sqlite3
from datetime import datetime, timezone
from typing import *
import os 
import tempfile
import errno

Path: TypeAlias = str | bytes | os.PathLike 
FileDescriptorOrPath: TypeAlias = int | Path

class AcqSettingsRow:
    def __init__(self):
        self.Setting: str = ""
        self.Value: int | float | str = 0
        self.key1: int = 1   
        self.key2: int = -1
        self.Auto: int = 0

class DPVRow:
    def __init__(self):
        self.ID: int = 0
        self.TaskID: int = 0
        self.MeasureID: int = 0
        self.DPID: int = 0
        self.Channel: int = 0
        self.SeqNum: int = 0
        self.DatatypeID: int = 0
        self.DataValue: float = 0
        self.DataSDev: float = 0
        self.ADValue: float = 0 # Scheme says int, but table holds real numbers?
        self.ADRange: int = 0
        self.Status: int = 0
        self.N: int = 0
        self.MCycles: int = 1
        self.DataSDevType: int = 0

class CommonSchemaVersionRow:
    def __init__(self):
        self.Version: int = 3
        self.Comment: str = "Utveckling"

class DP_ABMNRow:
    def __init__(self):
        self.ID = 0
        self.TaskID = 0
        self.DPKey: list[int] = [0] * 13
        self.APosX: float = 0
        self.APosY: float = 0
        self.APosZ: float = 0
        self.BPosX: float = 0
        self.BPosY: float = 0
        self.BPosZ: float = 0
        self.MPosX: float = 0
        self.MPosY: float = 0
        self.MPosZ: float = 0
        self.NPosX: float = 0
        self.NPosY: float = 0
        self.NPosZ: float = 0
        self.FocusX: float = 0
        self.FocusY: float = 0
        self.FocusZ: float = 0
        self.Ready: int = 0
        self.Note: str = None
        self.Mode: int = 0
        self.ModeValue: float = None

class DP_MEASURERow:
    def __init__(self):
        self.ID: int = 0
        self.DPID: int = 0
        self.MeasureID: int = 0
        self.Ready: int = 0

class DatasetItemsRow:
    def __init__(self):
        self.Id: int = 0
        self.DataSetsId: int = 0
        self.MeasureID: int = 0
        self.DPID: int = 0

class DatasetsRow:
    def __init__(self):
        self.Id: int = 0
        self.Name: str = ""
        self.ExcludeSet: bool = 1


class ElectrodeTestDataRow:
    def __init__(self):
        self.ID: int = 0
        self.TaskID: int = 0
        self.StationID: int = 0
        self.SwitchNumber: int = 0
        self.SwitchAddress: int = 0
        self.PosX: float = 0
        self.PosY: float = 0
        self.PosZ: float = 0
        self.ResistanceValue: float = 0
        self.CurrentValue: float = 0
        self.TestStatus: int = 0
        self.UserSetting: int = 0
        self.TxStatus: int = 0
        self.Time: datetime = 0
        self.PositionId: int = 0

class ElectrodesRow:
    def __init__(self):
        self.ID: int = 0
        self.SpreadID: int = 0
        self.PosX: int = 0
        self.PosY: int = 0
        self.PosZ: int = 0
        self.CurrentElectrode: int = 0
        self.PotentialElectrode: int = 0
        self.RemoteElectrode: int = 0
        self.SwitchNumber: int = 0
        self.SwitchAddress: int = 0
        self.Cable: int = 0
        self.Takeout: str = ""

class EventSourcesRow:
    def __init__(self):
        self.ID: int = 0
        self.Name: str = ""

class ExternalDataRow:
    def __init__(self):
        self.ID: int = 0
        self.TaskID: int = 0
        self.InstrID: str = ""
        self.MeasureID: int = 0
        self.PhaseID: int = 0
        self.PhaseType: int = 0
        self.PhasePolarity: int = 0
        self.DatatypeID: int = 0
        self.DataValue: float = 0
        self.DataSDev: float = 0
        self.Status: int = 0
        self.N: int = 0

class GPSPositionsRow:
    def __init__(self):
        raise NotImplementedError()

class LogRow:
    def __init__(self):
        raise NotImplementedError()

class MeasuresRow:
    def __init__(self):
        self.ID: int = 0
        self.StationID: int = 0
        self.PosLatitude: float = 0
        self.PosLongitude: float = 0
        self.PosQuality: int = 0
        self.Time: datetime = datetime.now(timezone.utc)
        self.IntPowerVolt: float = 0
        self.ExtPowerVolt: float = 0
        self.Temp: float = 0
        self.Light: float = 0
        self.SessionID: float = -1
        self.PositionId: int = None
    
class PositionsRow:
    def __init__(self):
        self.Id: int = 0
        self.TaskId: int = -1
        self.PositionType: int = 0
        self.PosX: float = 0
        self.PosY: float = 0
        self.PosZ: float = 0
        self.IsRemote: int = 0
        self.MeasureID: int = -1
        self.MeasurePhase: int = 0
        self.MeasureTime: float = 0
    
class ProjectSchemaVersionRow:
    def __init__(self):
        raise NotImplementedError()

class SessionsRow:
    def __init__(self):
        self.ID: int = 0
        self.Time: datetime = datetime.now(timezone.utc)
        self.TaskID: int = 0
        self.InstrumentSerial: str = ""
        self.InstrumentSoftware: str = ""
        self.TransmitterSerial: str = ""
        self.TransmitterSoftware: str = ""

class StationsRow:
    def __init__(self):
        self.ID: int = 0
        self.TaskID: int = 0
        self.SpreadPositionID: int = 0
        self.PosX: int = 0
        self.PosY: int = 0
        self.PosZ: int = 0
        self.Time: datetime = datetime.now(timezone.utc)

class TaskSettingsRow:
    def __init__(self):
        self.key1: int = 0
        self.key2: int = 0
        self.Setting: str = ""
        self.Value= ""
        self.Auto: int = 0

class TasksRow:
    def __init__(self):
        self.ID: int = 0
        self.Name: str = ""
        self.Active: int = 0
        self.PosX: float = 0
        self.PosY: float = 0
        self.PosZ: float = 0
        self.SpacingX: float = 1
        self.SpacingY: float = 1
        self.SpacingZ: float = 1
        self.ArrayCode: int = -1
        self.Time: datetime = datetime.now(timezone.utc)

class sqlite_sequenceRow:
    def __init__(self):
        self.name = ""
        self.seq = ""

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
            
            attribute = self.__getattribute__("_" + table)
            
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


if __name__ == "__main__":
    # Testing script
    # Swap print function to capture stdout
    from io import StringIO
    from builtins import print as realprint
    output_capture = StringIO()
    def fakeprint(*args, **kwargs):
        kwargs["file"] = output_capture
        realprint(*args, **kwargs)
    #print = fakeprint

    path = r"C:\Users\Hugo\GeoSuite\GeMeasPy\src\tests\reference\reference_measurement_data\project.db"    

    def check_output():
        settings = [{'Setting': s.Setting, 'Value': s.Value, 'key1': s.key1, 'key2': s.key2, 'Auto': s.Auto} for s in db._AcqSettings]
        assert {'Setting': 'IP_OffTimeSec', 'Value': '1.000000', 'key1': 1, 'key2': -1, 'Auto': 0} in settings
        assert {'Setting': 'Measure_SNR', 'Value': '0', 'key1': 1, 'key2': -1, 'Auto': 0} in settings
        assert {'Setting': 'BoreholeStepDown', 'Value': '1', 'key1': 1, 'key2': -1, 'Auto': 0} in settings
        assert {'Setting': 'IP_MinOffTimeSec', 'Value': '1.000000', 'key1': 2, 'key2': -1, 'Auto': 0} in settings
        assert {'Setting': 'Fullwaveform', 'Value': '0', 'key1': 2, 'key2': -1, 'Auto': 0} in settings

    
    realprint("Running with file descriptor")
    f = open(path, "r+b")
    db = ProjectDatabase(f.fileno())
    db.close()
    assert not f.closed
    f.close()
    check_output()
    
    realprint("Running with file path")
    db = ProjectDatabase(path)
    db.close()
    check_output()
        
    realprint("Running with file opened with `with` keyword")
    with open(path, "r+b") as f:
        db = ProjectDatabase(f.fileno())
        db.close()
    check_output()
    
    realprint("Running with bad argument type")
    raised_correct_exception = False
    try:
        db = ProjectDatabase([1,2,3])
        db.close()
    except Exception as e:
        if isinstance(e, TypeError):
            raised_correct_exception = True
    assert raised_correct_exception
    
    realprint("Running with nonexistent file")
    raised_correct_exception = False
    try:
        db = ProjectDatabase("file/that/does/not/exists.txt")
    except FileNotFoundError:
        raised_correct_exception = True
    assert raised_correct_exception
    
    realprint("Tests done!")