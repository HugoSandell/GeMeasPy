"""Class definitions for database tables"""
from datetime import datetime, timezone

class AcqSettingsRow:
    def __init__(self):
        self.Setting: str = ""
        self.Value: str = "0"
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
        self._DPKEY: list[int] = [0] * 13 
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
    
    # To handle str assignment, e.g: row.DPKEY = "1;0;0;1;...
    @property
    def DPKEY(self):
        return self._DPKEY
    @DPKEY.setter
    def DPKEY(self, value):
        if isinstance(value, list) and all([isinstance(x, int) for x in value]):
            self._DPKEY = value
            return
        elif isinstance(value, str):
            values_str = value.split(";")
            try:
                self._DPKEY = [int(x, 10) for x in values_str]
                return
            except:
                pass
        # No match
        raise TypeError("DPKEY value must be of type list[int] or str")

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
