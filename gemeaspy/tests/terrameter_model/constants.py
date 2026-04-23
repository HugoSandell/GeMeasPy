TERRAMETER_INTRO = """
01:08:36: Debug: === Create datamanager === 0x3c7d20
Release:   2.8.2
Build date:Tue Sep 12 16:34:53 CEST 2023
Build no:
####### INITIALIZATION STEP 1 (basic stuff, splash screen)
Licens: File /home/root/ls123456789.lic
licence: Customer id: 2663432a38efebff2a83654b49645c
Connection board version=2
Checking for a license to run monitor.
STEP1 Ready
####### INITIALIZATION STEP 2 (start threads, init GUI)
Initialize FPGA
***** FPGA::Configure: Open /dev/fpga_config.0 failed!
FPGA firmware version: 10
gpio:*** Error: Can not open device /dev/fpga_config.0 ErrNo=2
fluke: is NOT requested to be used.
GPS: (ttyinfo) 0N0 9600 /dev/ttyS3
Relay Board #1:  36310189 Rev: 3 Snr:2330
Relay Board #2:  36310189 Rev: 3 Snr:2325
Relay Board #3:  36310189 Rev: 3 Snr:2329
Relay Board #4:  36310189 Rev: 3 Snr:2328
Exception: extio.cpp:103 open failed!
can't set max speed hzspi mode: 0
bits per word: 8
max speed: 1000000 Hz (1000 KHz)
***** Unable to open /dev/input/uinput
Adjust bus matrix
AHB Matrix reg= 0x00000080, was=0xffffffff,want=0x00000300 *** Not possible with this driver
AHB Matrix reg= 0x00000084, was=0xffffffff,want=0x00000000 *** Not possible with this driver
AHB Matrix reg= 0x000000a8, was=0xffffffff,want=0x00000300 *** Not possible with this driver
AHB Matrix reg= 0x000000ac, was=0xffffffff,want=0x00000000 *** Not possible with this driver
AHB Matrix reg= 0x000000b0, was=0xffffffff,want=0x00000300 *** Not possible with this driver
AHB Matrix reg= 0x000000b4, was=0xffffffff,want=0x00000000 *** Not possible with this driver
AHB Matrix reg= 0x000000b8, was=0xffffffff,want=0x00000300 *** Not possible with this driver
AHB Matrix reg= 0x000000bc, was=0xffffffff,want=0x00000000 *** Not possible with this driver
gpio:*** Error: Can not open device /dev/fpga_config.0 ErrNo=2
TxSpi: Detected protocol version 5
TXspi speed=800000
---- Assume correct cid=126
Product:36310201
Rev:    2
SNR:    651
SW:3.7.2(1137)
TxSpi::txrxRestart
CPU Board:  363101255 Rev: 255 Snr:65535
Connection Board:  36310192 Rev: 4 Snr:1583
8Ch Board:  36310196 Rev: 2 Snr:8
---- Assume correct cid=0
POST EVENT
GPS: (ttyinfo) 0N0 9600 /dev/ttyS3
TerrameterApp: Waiting for all threads to be initialized...
####### INITIALIZATION STEP 3 (show GUI)
############################################
##     ABEM Terrameter Console
##
##     Commands:
##     g    Get
##     s    Set
##     L    List all Projects
##     P    Create a new project
##     O    Open a project
##     T    Create a new task
##     S    Create a new station
##     W    Write settings to xml file
##     w    Read settings from xml file
##     R    Show recent measure results
##     A    Show all results
##     m    Start/Stop (m)easuring process
##     G    Print GPS information
##     I    Set system time from GPS
##     0    Some debug test
##     U    Prepare transmitter for software update
##     ?    Help = Show this message
##     H    Help = Show this message
##     Q    Quit
##
############################################"""

TERRAMETER_OUTRO = """############################################
## User requested to quit the application ##
############################################
"""

TERRAMETER_CID_ERROR = """**** Cid error expect 211 cid=3 (0xd3 != 0x03)
------TXSPI ERROR ----- request id:211  mt:M_NULL
TXSPI:IN  <-- MyId=210 TxId=205 M_GET_VALUE 0
TXSPI:OUT --> MyId=211 TxId=204 M_NULL 0
TXSPI:IN  <-- MyId=3 TxId=209 M_NULL 2  *Missing ack*
          * RX:09d105080300ea0000000000
TXSPI:OUT --> MyId=212 TxId=205 M_REQ_VALUE 0
---- Assume correct cid=212"""
"""Example of error that is repeated when two instances of terrameter are launched"""

TERRAMETER_NO_PROJECT_ERROR = "No active project! Press P to create a new project."


def TERRAMETER_UNKNOWN_COMMAND(command: str):
    return f"""*** Unknown Command ({command[0] or ' '})
    Type ? for a list of known commands."""


TERRAMETER_DEFAULT_SETTINGS = {
    "SampleRateHz": 1000.0,
    "BaseFreqHz": 50.0,
    "SP_TimeSec": 1.0,
    "Acq_DelaySec": 0.1,
    "Acq_TimeSec": 0.1,
    "IPSP_TimeSec": 0.5,
    "IP_OffTimeSec": 0.5,
    "IP_MinOffTimeSec": 0.5,
    "AGC_TimeSec": 0.06,
    "SNR_TimeSec": 0.0,
    "ErrorLimit": 0.01,
    "IP_WindowSecList": [0.01, 0.02, 0.02],
    "MeasureMode": 2,
    "Measure_SNR": False,
    "DoInitialAGC": False,
    "AutoStack": True,
    "StackLimitsLow": 1,
    "StackLimitsHigh": 1,
    "NumberOfPulses": 4,
    "StackNorm": 0,
    "CurrentLimitLowAmpere": 0.001,
    "CurrentLimitHighAmpere": 0.2,
    "VoltageLimitLowVolt": 0.0,
    "VoltageLimitHighVolt": 400.0,
    "PowerLimitLowWatt": 0.0,
    "PowerLimitHighWatt": 250.0,
    "PowerLossLimitHighWatt": 25.0,
    "MarginLimitHigh": 1.2,
    "ElectrodeResistanceBadLimitLowOhm": 1000.0,
    "ElectrodeResistanceBadLimitHighOhm": 300000.0,
    "ElectrodeTestCurrentAmpere": 0.02,
    "ElectrodeTest": 1,
    "Fullwaveform": 1,
    "LogTemperature": 2,
    "LogSelfPotential": 2,
    "LogShortNormal": 1,
    "LogLongNormal": 1,
    "LogLateral18foot": 1,
    "LogFluidResistivity": 1,
    "BoreholeStepUp": 1,
    "BoreholeStepDown": 1
}

KILLALL_HELP = """Usage: killall [OPTION]... [--] NAME...
       killall -l, --list
       killall -V, --version

  -e,--exact          require exact match for very long names
  -I,--ignore-case    case insensitive process name match
  -g,--process-group  kill process group instead of process
  -y,--younger-than   kill processes younger than TIME
  -o,--older-than     kill processes older than TIME
  -i,--interactive    ask for confirmation before killing
  -l,--list           list all known signal names
  -q,--quiet          don't print complaints
  -r,--regexp         interpret NAME as an extended regular expression
  -s,--signal SIGNAL  send this signal instead of SIGTERM
  -u,--user USER      kill only process(es) running as USER
  -v,--verbose        report if the signal was successfully sent
  -V,--version        display version information
  -w,--wait           wait for processes to die
  -n,--ns PID         match processes that belong to the same namespaces
                      as PID
  -Z,--context REGEXP kill only process(es) having context
                      (must precede other arguments)"""