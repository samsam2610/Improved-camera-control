"""
Camera Control
Copyright M. Mathis Lab
Written by  Gary Kane - https://github.com/gkane26
post-doctoral fellow @ the Adaptive Motor Control Lab
https://github.com/AdaptiveMotorControlLab

camera class for imaging source cameras - helps load correct settings
"""
import time

import src.camera_control.tisgrabber as ic
import ctypes
import numpy as np
from pathlib import Path
import os
import json
import cv2
import copy
import threading
from collections import deque


path = Path(os.path.realpath(__file__))
# Navigate to the outer parent directory and join the filename
dets_file = os.path.normpath(str(path.parents[2] / 'config-files' / 'camera_details.json'))
cam_details = json.load(open(dets_file, 'r'))


class ICCam(ctypes.Structure):

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
        self.windowPos = {'x': None, 'y': None, 'width': None, 'height': None}
        self.add_filters()
        # self.set_ROI()
        self.vid_file = VideoRecordingSession(cam_num=self.cam_num)

    def add_filters(self, top=None, left=None, height=None, width=None):
        top = top if top is not None else self.crop['top']
        left = left if left is not None else self.crop['left']
        height = height if height is not None else self.crop['height']
        width = width if width is not None else self.crop['width']
        
        if self.rotate != 0:
            h_r = self.cam.CreateFrameFilter(b'Rotate Flip')
            self.cam.AddFrameFilter(h_r)
            self.cam.FilterSetParameter(h_r, b'Rotation Angle', self.rotate)

        h_c = self.cam.CreateFrameFilter(b'ROI')
        self.cam.AddFrameFilter(h_c)
        self.cam.FilterSetParameter(h_c, b'Top', top)
        self.cam.FilterSetParameter(h_c, b'Left', left)
        self.cam.FilterSetParameter(h_c, b'Height', height)
        self.cam.FilterSetParameter(h_c, b'Width', width)
        self.size = (self.crop['width'], self.crop['height'])

    def set_ROI(self):
        # result_roi = self.cam.SetPropertySwitch("Auto Functions ROI", "Enabled", True)
        result_left = self.cam.SetPropertyAbsoluteValue("Auto Functions ROI", "Left", int(self.crop['left']))
        result_right = self.cam.SetPropertyAbsoluteValue("Auto Functions ROI", "Top", int(self.crop['top']))
        result_width = self.cam.SetPropertyAbsoluteValue("Auto Functions ROI", "Width", int(self.crop['width']))
        result_height = self.cam.SetPropertyAbsoluteValue("Auto Functions ROI", "Height", int(self.crop['height']))
        print(f'For cam {self.cam_num}, the ROI was set with results: {result_left}, {result_right}, {result_width}, {result_height}')
        
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
        # self.set_ROI()
        self.cam.StartLive()
    
    
    def get_crop(self):
        return (self.crop['top'],
                self.crop['left'],
                self.crop['height'],
                self.crop['width'])
        
    def set_frame_rate(self, fps):
        result = self.cam.SetFrameRate(fps)
        return result

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
            self.cam.SetPropertyAbsoluteValue("Gain", "Value", val)
        except:
            pass

    def get_exposure(self):
        exposure = [0]
        self.cam.GetPropertyAbsoluteValue("Exposure", "Value", exposure)
        return round(exposure[0], 5)

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
        # print(f'Cam {self.cam_num} is starting. Please wait...')
        # result = self.cam.StartLive()
        # print(f'Cam {self.cam_num} started with result: {result}')
        
        result = self.cam.SetPropertySwitch("Trigger", "Enable", True)
        print(f'Cam {self.cam_num} trigger enabled with result: {result}')
        if not self.cam.callback_registered:
            # self.cam.SetFrameReadyCallback()
            self.set_frame_callback_video()
            
    def frame_ready(self):
        self.cam.ResetFrameReady()
        self.cam.WaitTillFrameReady(100000)

    def disable_trigger(self):
        print(f'Cam {self.cam_num} is being suspended. Please wait...')
        result = self.cam.SuspendLive()
        print(f'Cam {self.cam_num} stopped with result: {result}')
        
        result = self.cam.SetContinuousMode(1)
        print(f'Cam {self.cam_num} continuous mode set with result: {result}')
      
        #
        result = self.cam.SetPropertySwitch("Trigger", "Enable", False)
        print(f'Cam {self.cam_num} trigger disabled with result: {result}')

        result = self.cam.StartLive()
        print(f'Cam {self.cam_num} started again with result: {result}')

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

    def set_up_video_trigger(self, video_file, fourcc, fps, dim, trackingCoords=None):
        if self.vid_file is not None:
            self.vid_file.release()
        buffer_size, width, height, bpp = self.cam.GetFrameData()
        self.vid_file.set_params(video_file=video_file, fourcc=fourcc, fps=fps, dim=dim, buffer_size=buffer_size, width=width, height=height, bitsperpixel=bpp, trackingCoords=trackingCoords)
        print(f'Trigger capturing mode vid file is ready for {self.cam_num}')
        return self.vid_file
    
    def delete_video_file(self):
        if self.vid_file is not None:
            self.vid_file.delete()
            self.vid_file.reset()
            print(f'Trigger capturing mode vid file is deleted for cam {self.cam_num}')
            
    def release_video_file(self):
        if self.vid_file is not None:
            frame_times = copy.deepcopy(self.vid_file.frame_times)
            frame_num = copy.deepcopy(self.vid_file.frame_num)
            tracking_value = copy.deepcopy(self.vid_file.tracking_value)
            self.vid_file.release()
            
            print(f'Flipping vertical back for cam {self.cam_num}')
            self.set_flip_vertical(state=False)
            
            self.vid_file.reset()
            print(f'Trigger capturing mode vid file is released for cam {self.cam_num}')
            return frame_times, frame_num, tracking_value
        else:
            return None, None, None
            
    def create_frame_callback_video(self):
        def frame_callback_video(handle_ptr, pBuffer, framenumber, pData):
            callback_time = time.perf_counter()
            image = ctypes.cast(pBuffer,
                                ctypes.POINTER(
                                    ctypes.c_ubyte * pData.buffer_size))
            np_frame = np.frombuffer(image.contents, dtype=np.uint8)
            np_frame = np_frame.reshape((pData.height, pData.width, pData.bitsperpixel))
            pData.acquire_frame(frame=np_frame, time_data=callback_time, frame_num=framenumber)
            # write_thread = threading.Thread(target=pData.write, args=(np_frame, callback_time, framenumber))
            # write_thread.daemon = True
            # write_thread.start()
            # np_frame = cv2.flip(np_frame, 0)
            # pData.write(frame=np.ndarray(buffer=image.contents,
            #                         dtype=np.uint8,
            #                         shape=(pData.height,
            #                            pData.width,
            #                            pData.bitsperpixel)),
            #             time_data=time.perf_counter(),
            #             frame_num=framenumber)
       
        return ic.TIS_GrabberDLL.FRAMEREADYCALLBACK(frame_callback_video)
    
    def set_frame_callback_video(self):
        """
        Set up the frame callback function pointer for the camera
        Be careful to set it only once, otherwise it will hang the camera.
        """
        
        if not self.cam.callback_registered:
            print('Cam {self.cam_num} callback not registered yet')
            print(f'Setting up video callback function pointer for cam {self.cam_num}')
            CallbackfunctionPtr = self.create_frame_callback_video()

            if self.vid_file is None:
                print(f'Cam {self.cam_num} video file is not set up yet')
                return 0
            
            result = self.cam.SetFrameReadyCallback(CallbackfunctionPtr, self.vid_file)
            print(f'Cam {self.cam_num} frame ready callback result: {result}')
            
            return 1
        else:
            print(f'Cam {self.cam_num} callback already registered')
        
        print(f'Cam {self.cam_num} video callback set up {self.cam.callback_registered}')
        
    def set_recording_status(self, state=False):
        self.vid_file.set_recording_status(state)
        print(f'Cam {self.cam_num} recording status set to {state}')
        
    def get_window_position(self):
        err, self.windowPos['x'], self.windowPos['y'], self.windowPos['width'], self.windowPos['height'] = self.cam.GetWindowPosition()
        if err != 1:
            print("Error getting window position")
            
    def set_window_position(self, x=None, y=None, width=None, height=None):
        self.windowPos['x'] = x if x is not None else self.windowPos['x']
        self.windowPos['y'] = y if y is not None else self.windowPos['y']
        self.windowPos['width'] = width if width is not None else self.windowPos['width']
        self.windowPos['height'] = height if height is not None else self.windowPos['height']
        self.cam.SetWindowPosition(self.windowPos['x'], self.windowPos['y'], self.windowPos['width'], self.windowPos['height'])
    
    def turn_off_continuous_mode(self):
        # self.get_window_position()
        self.cam.SuspendLive()
        self.cam.SetContinuousMode(0)
        self.cam.StartLive()
        return 1
        
    def turn_on_continuous_mode(self):
        # self.get_window_position()
        self.cam.SuspendLive()
        self.cam.SetContinuousMode(1)
        self.cam.StartLive()
        return 1
    
    def set_flip_vertical(self, state: bool=True):
        if state:
            print(f'Getting offset value for {self.cam_num}')
            x_offset, y_offset = self.get_partial_scan()
            
            print(f'Flipping vertical for {self.cam_num}')
            self.cam.SetPropertySwitch("Flip Vertical", "Enable", True)
            self.cam.close()
            self.cam = ic.TIS_CAM()
            self.cam.open(self.cam.GetDevices()[self.cam_num].decode())
            self.cam.SetVideoFormat(Format=self.formats)
            self.add_filters(top=0)
            self.cam.StartLive()
        else:
            print(f'Flipping vertical back for {self.cam_num}')
            self.cam.SetPropertySwitch("Flip Vertical", "Enable", False)
            self.cam.close()
            self.cam = ic.TIS_CAM()
            self.cam.open(self.cam.GetDevices()[self.cam_num].decode())
            self.cam.SetVideoFormat(Format=self.formats)
            self.add_filters()
            self.cam.StartLive()
            
    def get_flip_vertical(self):
        flip_vertical = [0]
        self.cam.GetPropertySwitch("Flip Vertical", "Value", flip_vertical)
        return flip_vertical[0]
    
    
    def start(self, show_display=1, setPosition=False):
        self.cam.SetContinuousMode(0)
        print(f'Flipping vertical back for cam {self.cam_num}')
        self.cam.SetPropertySwitch("Flip Vertical", "Enable", False)
        self.cam.StartLive(show_display)
        # self.cam.SetDefaultWindowPosition(default=0)
        
        if setPosition:
            if self.windowPos['x'] is not None:
                self.set_window_position(self.windowPos['x'], self.windowPos['y'], self.windowPos['width'], self.windowPos['height'])

    def close(self, getPosition=False):
        if getPosition:
            self.get_window_position()
        self.cam.StopLive()
        

class VideoRecordingSession(ctypes.Structure):
    def __init__(self, cam_num):
        self.cam_num = cam_num
        self.recording_status = False
        self.vid_out = None
        self.frame_times = []
        self.frame_num = []
        self.tracking_value = None
    
    def set_recording_status(self, status: bool):
        if self.vid_out is None:
            print(f'Cam {self.cam_num} video file not set up yet')
            return None
        self.recording_status = status
        print(f'Cam {self.cam_num} internal recording status set to {status}')
        if status is True:
            self.start_processing()
        return 1
    
    def set_params(self, video_file: str=None, fourcc: str=None, fps: int=None, dim=None, buffer_size: int=None, width=None, height=None, bitsperpixel=None, trackingCoords=None):
        if fourcc is not None:
            self.fourcc = cv2.VideoWriter_fourcc(*fourcc)
        
        if fps is not None:
            self.fps = fps
        
        if dim is not None:
            self.dim = dim
        
        if buffer_size is not None:
            self.buffer_size = buffer_size
            
        if width is not None:
            self.width = width
        
        if height is not None:
            self.height = height
            
        if bitsperpixel is not None:
            self.bitsperpixel = bitsperpixel
            
        if trackingCoords is not None:
            self.tracking_x_value = trackingCoords[0]
            self.tracking_y_value = trackingCoords[1]
            self.tracking_value = []
            self.tracking_point = True
        else:
            self.tracking_point = False
            self.tracking_value = None
        
        if video_file is not None:
            self.video_file = video_file
            self.vid_out = cv2.VideoWriter(self.video_file, self.fourcc, self.fps, self.dim)
            self.frame_times = []
            self.frame_num = []
            self.frame_buffer = deque(maxlen=50)
            self.frame_buffer_length = 0
            self.frame_count = 0
            self.buffer_lock = threading.Lock()
            self.recording_status = False

        return 1
        
    def reset(self):
        self.vid_out = None
        self.frame_times = []
        self.frame_num = []
        self.recording_status = False
        self.tracking_value = None
        self.tracking_point = False
       
    def delete(self):
        os.remove(self.video_file)
        self.video_file = None
        
    def release(self):
        if self.vid_out is None:
            print(f'Cam {self.cam_num} video file not set up yet')
            return None
        self.vid_out.release()
        self.vid_out = None
        self.recording_status = False
        self.frame_times = []
        self.frame_num = []
        self.tracking_value = None
        self.tracking_point = False
        return 1
    
    def get_current_stats(self):
        return self.frame_count, self.frame_buffer_length
    
    def write_frame(self):
        # with self.buffer_lock:
        self.frame_buffer_length = len(self.frame_buffer)
        while self.frame_buffer_length > 0:
            frame, time_data, frame_num = self.frame_buffer.popleft()
            self.vid_out.write(frame)
            self.frame_times.append(time_data)
            self.frame_num.append(frame_num)
            self.frame_buffer_length = len(self.frame_buffer)
            self.frame_count += 1
            if self.tracking_point:
                x = self.tracking_x_value
                y = self.tracking_y_value
                self.tracking_value.append(cv2.getRectSubPix(frame, (1, 1), (x, y))[0, 0])
    
    def acquire_frame(self, frame, time_data, frame_num):
        # self.vid_out.write(frame)
        # self.frame_times.append(time_data)
        # self.frame_num.append(frame_num)
        # with self.buffer_lock:
        self.frame_buffer.append((frame, time_data, frame_num))
        
        return 1
    
    def start_processing(self):
        self.recording_status = True
        print(f'Cam {self.cam_num} thread is started')
        processing_thread = threading.Thread(target=self._process_frames, daemon=True)
        processing_thread.start()
        
    def _process_frames(self):
        while self.recording_status:
            self.write_frame()
            time.sleep(0.005)