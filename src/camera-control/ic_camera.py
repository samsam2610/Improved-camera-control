"""
Camera Control
Copyright M. Mathis Lab
Written by  Gary Kane - https://github.com/gkane26
post-doctoral fellow @ the Adaptive Motor Control Lab
https://github.com/AdaptiveMotorControlLab

camera class for imaging source cameras - helps load correct settings
"""

from pyicic.IC_ImagingControl import *
import numpy as np
import os
import json
import cv2

path = os.path.dirname(os.path.realpath(__file__))
dets_file = os.path.normpath(path + '/camera_details.json')
with open(dets_file) as f:
    cam_details = json.load(f)

class ICCam(object):

    def __init__(self, cam_num=0, rotate=None, crop=None, exposure=None, gain=None, formats='Y800 (1024x768)'):
        '''
        Params
        ------
        'Y800 (1024x768)' THIS IS WHAT I USUALLY USE FOR TREADMILL
        cam_num = int; camera number (int)
            default = 0
        crop = dict; contains ints named top, left, height, width for cropping
            default = None, uses default parameters specific to camera
        '''

        self.ic_ic = IC_ImagingControl()
        self.ic_ic.init_library()

        self.cam_num = cam_num
        self.rotate = rotate if rotate is not None else cam_details[str(self.cam_num)]['rotate']
        self.crop = crop if crop is not None else cam_details[str(self.cam_num)]['crop']
        self.exposure = exposure if exposure is not None else cam_details[str(self.cam_num)]['exposure']
        self.gain = gain if gain is not None else cam_details[str(self.cam_num)]['gain']

        self.cam = self.ic_ic.get_device(self.ic_ic.get_unique_device_names()[self.cam_num])
        self.cam.open()
        self.cam.set_video_format(formats)
        self.add_filters()

    def add_filters(self):
        if self.rotate != 0:
            h_r = self.cam.create_frame_filter('Rotate Flip')
            self.cam.add_frame_filter_to_device(h_r)
            self.cam.frame_filter_set_parameter(h_r, 'Rotation Angle', self.rotate)

        h_c = self.cam.create_frame_filter('ROI')
        self.cam.add_frame_filter_to_device(h_c)
        self.cam.frame_filter_set_parameter(h_c, 'Top', self.crop['top'])
        self.cam.frame_filter_set_parameter(h_c, 'Left', self.crop['left'])
        self.cam.frame_filter_set_parameter(h_c, 'Height', self.crop['height'])
        self.cam.frame_filter_set_parameter(h_c, 'Width', self.crop['width'])
        self.size = (self.crop['width'], self.crop['height'])

        self.cam.gain.auto = False
        self.cam.exposure.auto = False
        self.cam.exposure.value = self.exposure
        self.cam.gain.value = self.gain


    def set_gain(self, val):
        try:
            val = int(round(val))
            val = val if val < self.cam.gain.max-1 else self.cam.gain.max-1
            val = val if val > self.cam.gain.min else self.cam.gain.min
            self.cam.gain.value = val
        except:
            pass

   
    def set_exposure(self, val):
        try:
            val = int(round(val))
            val = val if val < self.cam.exposure.max-1 else self.cam.exposure.max-1
            val = val if val > self.cam.exposure.min else self.cam.exposure.min
            self.cam.exposure.value = val
        except:
            pass

    def get_exposure(self):
        return self.cam.exposure.value

    def get_gain(self):
        return self.cam.gain.value
    def get_image(self):
        data, width, height, depth = self.cam.get_image_data()
        frame = np.ndarray(buffer=data,
                           dtype=np.uint8,
                           shape=(height, width, depth))
        return cv2.flip(frame,0)

    def get_image_dimensions(self):
        _, width, height, _ = self.cam.get_image_data()
        return (width, height)

    def start(self, show_display=True):
        self.cam.enable_continuous_mode(True)
        self.cam.start_live(show_display=show_display)

    def get_formats(self):
        return self.cam.list_video_formats()

    def set_formats(self, fformat):
        self.cam.stop_live()
        self.cam.set_video_format(fformat)
        self.add_filters()
        self.start()

    def enable_trigz(self):
        self.cam.enable_trigger(True) # camera will wait for trigger
        if not self.cam.callback_registered:
            self.cam.register_frame_ready_callback() # needed to wait for frame ready callback

    def disable_trigz(self):
        self.cam.enable_trigger(False)
        
    def frame_ready(self):
        self.cam.reset_frame_ready()
        self.cam.wait_til_frame_ready(100000)

    def close(self):
        self.cam.stop_live()
        self.cam.close()
