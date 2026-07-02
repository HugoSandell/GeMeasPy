"""Class definitions for database tables"""
from datetime import datetime, timezone
import typing

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
        self.DataValue: float = 0.0
        self.DataSDev: float = 0.0
        self.ADValue: float = 0.0 # Scheme says int, but table holds real numbers?
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
        self.DPKEY: str 
        self.APosX: float = 0.0
        self.APosY: float = 0.0
        self.APosZ: float = 0.0
        self.BPosX: float = 0.0
        self.BPosY: float = 0.0
        self.BPosZ: float = 0.0
        self.MPosX: float = 0.0
        self.MPosY: float = 0.0
        self.MPosZ: float = 0.0
        self.NPosX: float = 0.0
        self.NPosY: float = 0.0
        self.NPosZ: float = 0.0
        self.FocusX: float = 0.0
        self.FocusY: float = 0.0
        self.FocusZ: float = 0.0
        self.Ready: int = 0
        self.Note: str | None = ""
        self.Mode: int = 0
        self.ModeValue: float | None = None
    
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
        self.ExcludeSet: bool = True

class DatatypeRow:
    def __init__(self):
        self.ID: int = 0
        self.Name: str = ""
        self.Unit: str = ""
        self.Explanation: str = ""

class ElectrodeTestDataRow:
    def __init__(self):
        self.ID: int = 0
        self.TaskID: int = 0
        self.StationID: int = 0
        self.SwitchNumber: int = 0
        self.SwitchAddress: int = 0
        self.PosX: float = 0.0
        self.PosY: float = 0.0
        self.PosZ: float = 0.0
        self.ResistanceValue: float = 0.0
        self.CurrentValue: float = 0.0
        self.TestStatus: int = 0
        self.UserSetting: int = 0
        self.TxStatus: int = 0
        self.Time: datetime = datetime.now(timezone.utc)
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
        self.DataValue: float = 0.0
        self.DataSDev: float = 0.0
        self.Status: int = 0
        self.N: int = 0

class GPSPositionsRow:
    def __init__(self):
        self.Id: int = 0
        self.PositionID: int = -1
        self.GPSSOURCE: int = 0
        self.smask: int = 0
        self.utc: datetime = datetime.now(timezone.utc)
        self.sig: int = 0
        self.fix: int = 0
        self.PDOP: float = 0.0
        self.HDOP: float = 0.0
        self.VDOP: float = 0.0
        self.LAT: float = 0.0
        self.LON: float = 0.0
        self.ELV: float = 0.0
        self.SPEED: float = 0.0
        self.DIRECTION: float = 0.0
        self.INUSE: int = 0
        self.INVIEW: int = 0
        self.satinfo: str = ""

class LogRow:
    def __init__(self):
        self.ID: int = 0
        self.Time: datetime = datetime.now(timezone.utc)
        self.PosLatitude: float = 0.0
        self.PosLongitude: float = 0.0
        self.PosQuality: int = 0
        self.IntPowerVolt: float = 0.0
        self.ExtPowerVolt: float = 0.0
        self.Temp: float = 0.0
        self.Light: float = 0.0
        self.SourceTypeID: int = 0
        self.SourceID: str = ""
        self.TaskID: int = 0
        self.MeasureID: int = 0
        self.WhatEnglish: str = ""
        self.What: str = ""
        self.Data: bytes = b""
        self.EventClass: int = 0
        self.EventClassId: str = ""

class MeasuresRow:
    def __init__(self):
        self.ID: int = 0
        self.StationID: int = 0
        self.PosLatitude: float = 0.0
        self.PosLongitude: float = 0.0
        self.PosQuality: int = 0
        self.Time: datetime = datetime.now(timezone.utc)
        self.IntPowerVolt: float = 0.0
        self.ExtPowerVolt: float = 0.0
        self.Temp: float = 0.0
        self.Light: float = 0.0
        self.SessionID: float = -1
        self.PositionId: int | None = None
    
class PositionsRow:
    def __init__(self):
        self.Id: int = 0
        self.TaskId: int = -1
        self.PositionType: int = 0
        self.PosX: float = 0.0
        self.PosY: float = 0.0
        self.PosZ: float = 0.0
        self.IsRemote: int = 0
        self.MeasureID: int = -1
        self.MeasurePhase: int = 0
        self.MeasureTime: float = 0.0
    
class ProjectSchemaVersionRow:
    def __init__(self):
        self.Version: int = 4
        self.Comment: str = "Towed"

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
        self.PosX: float = 0.0
        self.PosY: float = 0.0
        self.PosZ: float = 0.0
        self.SpacingX: float = 1
        self.SpacingY: float = 1
        self.SpacingZ: float = 1
        self.ArrayCode: int = -1
        self.Time: datetime = datetime.now(timezone.utc)

class sqlite_sequenceRow:
    def __init__(self):
        self.name = ""
        self.seq = ""

TERRAMETER_DATABASE_TABLE_NAMES: list[str] = ["AcqSettings", "CommonScemaVersion", "DPV", "DP_ABMN", 
                                              "DP_MEASURE", "DatasetItems", "Datasets", "Datatype", 
                                              "ElectrodeTestData", "Electrodes", "EventSources", 
                                              "ExternalData", "GPSPositions", "Log", "Measures", 
                                              "Positions", "ProjectShemaVersion", "Sessions", 
                                              "Stations", "TaskSettings", "Tasks", "sqlite_sequence"]