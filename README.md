# GeMeasPy

## **Ge**ophysical **Meas**urements **Py**thon

This pack contains tools for automated geophysical monitoring. The tools were initialy developed through my studies and are published under Apache 2.0

### Data collection module
The module uses a computer (Windows or LINUX) to control the Terrameter LS and acquire data. The computer shall have enough space to hold several datasets for redundancy in case the remote connection breaks.


**Setup procedure**
1. Create the neccesary files
2. The "settings/connection_settings.json" file should contain the Terrameters ssh connection (hostname, port, username, password, look_for_keys)
3. The "settings/server_backup_settings.json" file should contain the backup's server ssh connection (hostname, port, username, password, look_for_keys)
4. The "settings/config.py" should contain the variables: TERRAMETER_PROJECTS_FOLDER, LOCAL_PATH_TO_DATA, REMOTE_BACKUP, SERVER_BACKUP_FOLDER, FILE_TRANSFER_DICTIONARY
5. The "settings/monitoring_task_list.txt should contain the name, spread and protocol files for each Task.
6. Use a scheduler to run the scripts every X minutes
7. On windows you call a batch file from taskscheduler
8. On LINUX you can call a bash file with crontab
9. Ensure there is enough space on the local pc and if needed setup procedures to remove the data frequently.

**How to run data collection module**   
`python -m src.acquisition.main <task_list_file> [task_list_file...]`

**How to run mutation analysis**    
`python -m src.tests.mutate [generator...]`    
Where valid inputs for `generator` is `acts` or `random`. If no generator is specified, all available generators will be run.   

Finally the result can be displayed with   
`cr-report test_data/cosmicray_<generator>.sqlite`   
Where `<generator>` is the specific generator you want to see the results for.  
See [cosmic-ray documentation](https://cosmic-ray.readthedocs.io/en/latest/tutorials/intro/index.html) for more information.