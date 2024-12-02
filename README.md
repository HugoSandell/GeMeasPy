# pyGMON

## **G**eophysical **MON**itoring

This pack contains tools for automated geophysical monitoring. The tools were initialy developed through my studies and are published under GNU GPL v.3.

### Data collection module
The module uses a computer (Windows or LINUX) to control the Terrameter LS and acquire data. The computer shall have enough space to hold several datasets for redundancy in case the remote connection breaks.


**Setup procedure**
1. Create the neccesary files
1. The "settings/connection_settings.json" file should contain the Terrameters ssh connection (hostname, port, username, password, look_for_keys)
2. The "settings/server_backup_settings.json" file should contain the backup's server ssh connection (hostname, port, username, password, look_for_keys)
3. The "settings/config.py" should contain the variables: TERRAMETER_PROJECTS_FOLDER, LOCAL_PATH_TO_DATA, REMOTE_BACKUP, SERVER_BACKUP_FOLDER, FILE_TRANSFER_DICTIONARY
4. The "settings/monitoring_task_list.txt should contain the name, spread and protocol files for each Task.
2. Use a scheduler to run the scripts every X minutes
1. On windows you call a batch file from taskscheduler
2. On LINUX you can call a bash file with crontab
3. Ensure there is enough space on the local pc and if needed setup procedures to remove the data frequently.
