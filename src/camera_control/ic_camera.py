"""
Camera Control
Copyright M. Mathis Lab
Written by  Gary Kane - https://github.com/gkane26
post-doctoral fellow @ the Adaptive Motor Control Lab
https://github.com/AdaptiveMotorControlLab

camera class for imaging source cameras - helps load correct settings
"""

import src.camera_control.tisgrabber as ic
import numpy as np
from pathlib import Path
import os
import json
import cv2
import ctypes as C

path = Path(os.path.realpath(__file__))
# Navigate to the outer parent directory and join the filename
dets_file = os.path.normpath(str(path.parents[2] / 'config-files' / 'camera_details.json'))
cam_details = json.load(open(dets_file, 'r'))


class ICCam(object):

    def __init__(self, cam_num=0, rotate=None, crop=None, exposure=None, gain=None, formats='Y800 (1024x768)'):
        '''
        Params
        ------
        cam_num = int; camera number (int)
            default = 0
        crop = dict; contains ints named top, left, height, width for cropping
            default = None, uses default parameters specific to camera
        '''

        self.cam_num = cam_num
        self.rotate = rotate if rotate is not None else cam_details[str(self.cam_num)]['rotate']
        self.crop = crop if crop is not None else cam_details[str(self.cam_num)]['crop']
        self.exposure = exposure if exposure is not None else cam_details[str(self.cam_num)]['exposure']
        self.gain = gain if gain is not None else cam_details[str(self.cam_num)]['gain']
        self.formats = formats if formats is not None else cam_details[str(self.cam_num)]['formats']

        self.cam = ic.TIS_CAM()
        self.cam.open(self.cam.GetDevices()[cam_num].decode())
        self.cam.SetVideoFormat(Format=self.formats)
        self.add_filters()

    def add_filters(self):
        if self.rotate != 0:
            h_r = self.cam.CreateFrameFilter(b'Rotate Flip')
            self.cam.AddFrameFilter(h_r)
            self.cam.FilterSetParameter(h_r, b'Rotation Angle', self.rotate)

        h_c = self.cam.CreateFrameFilter(b'ROI')
        self.cam.AddFrameFilter(h_c)
        self.cam.FilterSetParameter(h_c, b'Top', self.crop['top'])
        self.cam.FilterSetParameter(h_c, b'Left', self.crop['left'])
        self.cam.FilterSetParameter(h_c, b'Height', self.crop['height'])
        self.cam.FilterSetParameter(h_c, b'Width', self.crop['width'])
        self.size = (self.crop['width'], self.crop['height'])

    def set_crop(self, top=None, left=None, height=None, width=None):
        self.crop['top'] = top if top is not None else self.crop['top']
        self.crop['left'] = left if left is not None else self.crop['left']
        self.crop['height'] = height if height is not None else self.crop['height']
        self.crop['width'] = width if width is not None else self.crop['width']
        self.cam.close()
        self.cam = ic.TIS_CAM()
        self.cam.open(self.cam.GetDevices()[self.cam_num].decode())
        self.cam.SetVideoFormat(Format=self.formats)
        self.add_filters()
        self.cam.StartLive()
        
    def get_crop(self):
        return (self.crop['top'],
                self.crop['left'],
                self.crop['height'],
                self.crop['width'])
        
    def set_frame_rate(self, fps):
        return self.cam.SetFrameRate(fps)

    def get_frame_rate(self):
        return self.cam.GetFrameRate()
    
    def get_frame_rate_list(self):
        return self.cam.GetAvailableFrameRates()
        
    def set_exposure(self, val):
        val = 1 if val > 1 else val
        val = 0 if val < 0 else val
        self.cam.SetPropertyAbsoluteValue("Exposure", "Value", val)

    def set_gain(self, val):
        try:
            val = int(round(val))
            val = val if val < self.cam.gain.max - 1 else self.cam.gain.max - 1
            val = val if val > self.cam.gain.min else self.cam.gain.min
            self.cam.SetPropertyAbsoluteValue("Gain", "Value", val)
        except:
            pass

    def get_exposure(self):
        exposure = [0]
        self.cam.GetPropertyAbsoluteValue("Exposure", "Value", exposure)
        return round(exposure[0], 3)

    def get_gain(self):
        gain = [0]
        self.cam.GetPropertyAbsoluteValue("Gain", "Value", gain)
        return round(gain[0], 3)

    def get_image(self):
        self.cam.SnapImage()
        frame = self.cam.GetImageEx()
        return cv2.flip(frame, 0)

    def get_image_dimensions(self):
        im = self.get_image()
        height = im.shape[0]
        width = im.shape[1]
        return (width, height)
    
    def get_video_format(self):
        width = self.cam.GetVideoFormatWidth()
        height = self.cam.GetVideoFormatHeight()
        return (width, height)

    def enable_trigger(self):
        self.cam.SetPropertySwitch("Trigger", "Enable", True)
        if not self.cam.callback_registered:
            self.cam.SetFrameReadyCallback()

    def frame_ready(self):
        self.cam.ResetFrameReady()
        self.cam.WaitTillFrameReady(100000)

    def disable_trigger(self):
        self.cam.SetPropertySwitch("Trigger", "Enable", False)

    def set_auto_center(self, value):
        self.cam.SetPropertySwitch("Partial scan", "Auto-center", value)
        
    def set_partial_scan(self, x_offset=None, y_offset=None):
        if x_offset is not None:
            self.cam.SetPropertyValue("Partial scan", "X Offset", x_offset)
            
        if y_offset is not None:
            self.cam.SetPropertyValue("Partial scan", "Y Offset", y_offset)
            
    def get_partial_scan(self):
        x_offset = self.cam.GetPropertyValue("Partial scan", "X Offset")
        y_offset = self.cam.GetPropertyValue("Partial scan", "Y Offset")
        return (x_offset, y_offset)
    
    def get_trigger_polarity(self):
        polarity = [0]
        self.cam.GetPropertySwitch("Trigger", "Polarity", Value=polarity)
        return polarity[0]
    
    def set_trigger_polarity(self, value):
        self.cam.SetPropertySwitch("Trigger", "Polarity", value)
        polarity = [0]
        self.cam.GetPropertySwitch("Trigger", "Polarity", Value=polarity)
        return polarity[0]
    
    def start(self, show_display=1):
        self.cam.SetContinuousMode(0)
        self.cam.StartLive(show_display)

    def close(self):
        self.cam.StopLive()
