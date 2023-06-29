import os
import subprocess
from src.gui.camera_control_GUI_improved import CamGUI
import tkinter as tk
import time

def test_camera_control_GUI_improved():
    conda_env = "improved_camera_env"  # Replace with the name of your conda environment

    # Get the absolute path of the script directory
    script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "gui"))

    # Construct the relative path to the script
    script_path = os.path.join(script_dir, "camera_control_GUI_improved.py")

    # Activate the conda environment and run the script with the desired arguments
    gui_process = subprocess.run(["conda", "run", "-n", conda_env, "python", script_path, "-d", "-ni"], capture_output=False)
    time.sleep(5)
    # Create an instance of the CamGUI class with the parsed arguments
    cam_gui = CamGUI(debug_mode=True, init_cam_bool=False)

    time.sleep(5)
    print('Clicking the setup_calibration button')
    cam_gui.setup_calibration()
    
    time.sleep(5)
    # Close the GUI process 
    gui_process.terminate()
