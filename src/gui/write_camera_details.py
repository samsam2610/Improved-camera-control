"""
Camera Control
Copyright M. Mathis Lab
Written by  Gary Kane - https://github.com/gkane26
post-doctoral fellow @ the Adaptive Motor Control Lab
https://github.com/AdaptiveMotorControlLab

create json parameter file
"""

import os
from pathlib import Path
import json
import numpy as np

path = Path(os.path.realpath(__file__))
# Navigate to the outer parent directory and join the filename
out = os.path.normpath(str(path.parents[2] / 'config-files' / 'camera_details.json'))
# out = os.path.normpath(path.parent.absolute() + 'camera_details.json')

# Crop, rotation, and exposure are default parameters. Can be changed in the GUI.

cam_0 = {'name' : 'cam1',
        'crop' : {'top' : 210, 'left' : 8, 'height' : 550, 'width' : 900},
        'rotate' : 0,
        'exposure' : -11,
        'gain': 100,
        'output_dir' : 'E:\\live_videos'}

cam_1 = {'name' : 'cam2',
        'crop' : {'top' : 130, 'left' : 92, 'height' : 550, 'width' : 900},
        'rotate' : 0,
        'exposure' : -11,
        'gain': 100,
        'output_dir' : 'E:\\live_videos'}

subs = ['test1', 'test2', 'test3'] # optional, can manually enter subject for each session.

labview = ['Dev1/port0/line0'] # optional, can manually enter for each session

details = {'cams' : 2,
           '0' : cam_0,
           '1' : cam_1,
           'subjects' : subs,
           'labview' : labview}

with open(out, 'w') as handle:
    json.dump(details, handle)
