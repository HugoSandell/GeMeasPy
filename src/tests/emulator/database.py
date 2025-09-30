"""Terrameter LS2 project database file utilities."""
import sqlite3
from datetime import datetime, timezone
from typing import *
import io
import os 
import tempfile

class AcqSetting:
    def __init__(self):
        self.name: str = ""
        self.value: int | float = 0
        self.key1: int = 1   
        self.key2: int = -1

class DPVEntry:
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

class CommonSchemaVersion:
    def __init__(self):
        self.Version: int = 3
        self.Comment: str = "Utveckling"

class DP_ABMN:
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

class DP_MEASURE:
    def __init__(self):
        self.ID: int = 0
        self.DPID: int = 0
        self.MeasureID: int = 0
        self.Ready: int = 0

class DatasetItem:
    def __init__(self):
        self.Id: int = 0
        self.DataSetsId: int = 0
        self.MeasureID: int = 0
        self.DPID: int = 0

class Dataset:
    def __init__(self):
        self.Id: int = 0
        self.Name: str = ""
        self.ExcludeSet: bool = 1


class ElectrodeTestData:
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

class Electrode:
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

class EventSource:
    def __init__(self):
        self.ID: int = 0
        self.Name: str = ""

class ExternalData:
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

class GPSPosition:
    def __init__(self):
        raise NotImplementedError()

class LogEntry:
    def __init__(self):
        raise NotImplementedError()

class Measure:
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
    
class Position:
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
    
class ProjectSchemaVersion:
    def __init__(self):
        raise NotImplementedError()

class Session:
    def __init__(self):
        self.ID: int = 0
        self.Time: datetime = datetime.now(timezone.utc)
        self.TaskID: int = 0
        self.InstrumentSerial: str = ""
        self.InstrumentSoftware: str = ""
        self.TransmitterSerial: str = ""
        self.TransmitterSoftware: str = ""

class Station:
    def __init__(self):
        self.ID: int = 0
        self.TaskID: int = 0
        self.SpreadPositionID: int = 0
        self.PosX: int = 0
        self.PosY: int = 0
        self.PosZ: int = 0
        self.Time: datetime = datetime.now(timezone.utc)

class TaskSetting:
    def __init__(self):
        self.key1: int = 0
        self.key2: int = 0
        self.Setting: str = ""
        self.Value= ""
        self.Auto: int = 0

class Task:
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

class sqlite_sequence:
    def __init__(self):
        self.name = ""
        self.seq = ""

class ProjectDatabase:
    """Terrameter LS2 project database."""
    def __init__(self):
        self._AcqSettings: list[AcqSetting] = []
        self._CommonSchemaVersion: CommonSchemaVersion = CommonSchemaVersion()
        self._DP_ABMN: list[DP_ABMN] = []
        self._DatasetItems: list[DatasetItem] = []
        self._Datasets: list[Dataset] = []
        self._Electrodes: list[Electrode] = []
        self._Measures: list[Measure] = []
        self._Tasks: list[Task] = []
        self._Sessions: list[Session] = []
        self._Stations: list[Station] = []