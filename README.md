# install
download zip file to your computer. 

create conda environment with `conda env create -f improved_camera_env.yml --name improved_camera_env`

activate environment wiht `conda activate improved_camera_env`

then run `pip install git+https://github.com/morefigs/py-ic-imaging-control`

then run `pip install -e .` (in main directory)

then run `python write_camera_details.py` and `python write_calib_details.py` (generates config files for defaults)

then should work with `python cort_camera_control_gui.py` or any of the cam_gui.py files

# Usage
For debugging mode on non-camera computer, navigate to the `src` folder and then use this command to enter debugging mode and skip the initial camera activation check 
`python camera_control_GUI_improved.py -ni -d`