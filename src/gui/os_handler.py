import os
import glob

def generate_folder():
    trial_path = locate_new_exp()
    dir_name = f'{trial_path}\\live_videos'
    
    os.mkdir(dir_name)
    
    return get_base_name(trial_path), dir_name

def locate_new_exp():
    tank_path = 'D:\\TDT\\Synapse\\Tanks'
    exp_path = get_latest_folder(tank_path)
    trial_path = get_latest_file(exp_path)
    
    return trial_path
    
def get_base_name(path):
    return path.split('\\')[-1]
    
def get_latest_folder(dir_path):

    list_of_files = glob.glob(f'{dir_path}\\*') # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getmtime)
    
    return latest_file
    
def get_latest_file(dir_path):

    list_of_files = glob.glob(f'{dir_path}\\*') # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)

    return latest_file