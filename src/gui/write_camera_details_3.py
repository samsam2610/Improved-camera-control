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

cam_0 = {'name': 'cam1',
         'crop': {'top': 210, 'left': 8, 'height': 400, 'width': 704},
         'rotate': 0,
         'exposure': 0.0001,
         'gain': 20,
         'offset': {'x': 366, 'y': 300},
         'output_dir': 'C:\\Data folder'}

cam_1 = {'name': 'cam2',
         'crop': {'top': 130, 'left': 92, 'height': 400, 'width': 704},
         'rotate': 0,
         'exposure': 0.0001,
         'gain': 20,
         'offset': {'x': 366, 'y': 300},
         'output_dir': 'C:\\Data folder'}

cam_2 = {'name': 'cam3',
         'crop': {'top': 130, 'left': 92, 'height': 400, 'width': 704},
         'rotate': 0,
         'exposure': 0.0001,
         'gain': 20,
         'offset': {'x': 366, 'y': 300},
         'output_dir': 'C:\\Data folder'}

subs = ['test1', 'test2', 'test3']  # optional, can manually enter subject for each session.

labview = ['Dev1/port0/line0']  # optional, can manually enter for each session

details = {'cams': 3,
           '0': cam_0,
           '1': cam_1,
           '2': cam_2,
           'subjects': subs,
           'labview': labview}

with open(out, 'w') as handle:
    json.dump(details, handle)
