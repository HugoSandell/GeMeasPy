# GeMeasPy

## **Ge**ophysical **Meas**urements **Py**thon

This pack contains tools for automated geophysical monitoring. The tools were initialy developed by Aristeidis Nivorlis ([Original repository on GitHub](https://github.com/anivorlis/GeMeasPy)) and are published under Apache 2.0

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
`python -m gemeaspy.acquisition <task_list_file> [task_list_file...]`

## Reset and backup scripts
If you have installed the project, you can run `gemeaspy_reset` and `gemeaspy_backup`.  
Otherwise run the following modules:   
`python -m gemeaspy.reset`  
`python -m gemeaspy.backup`

## Mutation analysis    
Ensure that the `gemeaspy/settings/config.py` file is present as per the above instructions. 
```
python -m gemeaspy.tests.mutate --strength t [--seed s] [--only generator] [--workers N]
```
Where valid inputs for `generator` is `acts` or `random`. If no generator is specified, all available generators will be run. `--seed` specifies the seed for the random number generator. `--workers` specifies how many worker threads will be used. The number of worker threads should not exceed the number of physical CPU cores available on the system. By default the number of workers is set to one less than the number of available physical cores, but you may need to set it lower if other processes are active on the system.   

`gemeaspy/tests/test_main.py` defines the maximum execution time of the acquisition module as `ACQUISITION_TIMEOUT`. This can be changed in the unlikely even that it be needed.


See [cosmic-ray documentation](https://cosmic-ray.readthedocs.io/en/latest/tutorials/intro/index.html) for more information.