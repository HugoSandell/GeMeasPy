# User/system inputs

## Execution arguments
* Taskfile 1 [str]
* (Taskfile 2, 3, 4...) [str...]

## Config.py
* LOG_FOLDER [str]
* TERRAMETER_PROJECTS_FOLDER [str] 
* TERRAMETER_MONITORING_FOLDER [str] 
* LOCAL_PATH_TO_DATA [str] 
* REMOTE_BACKUP [bool] 
* SERVER_BACKUP_FOLDER [str] 
* FILE_TRANSFER_DICTIONARY [str] 
* TERRAMETER_CONNECTION_FILE [str] 
* SERVER_BACKUP_CONNECTION_FILE [str] 

## connection_settings.json + server_backup_settings.json
* hostname [str]
* port [int]
* username [str]
* password [str]
* look_for_keys [bool]

## monitoring_task_list.txt
* Number of tasks [int]
* Relay mode [{0, 1, 2}]
* Task Identifier/name (per task) [str]
* Task_Name_For_Terrameter (per task) [str]
* Spread file (per task) [str]
* Protocol file (per task) [str]
* Settings file (per task) [str]
* X, Y, Z spacing (per task) [int int int]

# Terrameter input

## SSH
* Timings
* Running or not
* Random disconnect
* Random closing of connection
* Invalid password, user, protocol, etc.

## File system state
* Project name in monitoring folder
* Existing project(s)

## Terrameter software
* Random shutdown