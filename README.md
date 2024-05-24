# install
download zip file to your computer. 

create conda environment with `conda env create -f improved_camera_env.yml --name improved_camera_env`

activate environment with `conda activate improved_camera_env`

run `pip install -e .` in the root directory of the project.

then run `python write_camera_details.py` and `python write_calib_details.py` (generates config files for defaults)

then should work with `python cort_camera_control_gui.py` or any of the cam_gui.py files

# Usage
For debugging mode on non-camera computer, navigate to the `src/gui` folder and then use this command to enter debugging mode and skip the initial camera activation check 
`python camera_control_GUI_improved.py -ni -d`