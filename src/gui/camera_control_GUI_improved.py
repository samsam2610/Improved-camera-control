"""
Camera Control
Copyright M. Mathis Lab
Written by  Gary Kane - https://github.com/gkane26
post-doctoral fellow @ the Adaptive Motor Control Lab
https://github.com/AdaptiveMotorControlLab

GUI to record from imaging source cameras during experiments

Modified by people at Dr. Tresch's lab
"""

import argparse
import copy
import datetime
import json
import math
import os
import pickle
import queue
import threading
import time
import traceback
from pathlib import Path
from tkinter import Entry, Label, Button, StringVar, IntVar,\
    Tk, END, Radiobutton, filedialog, ttk, Frame, Scale, HORIZONTAL, Spinbox, Checkbutton, DoubleVar, messagebox
from idlelib.tooltip import Hovertip

from matplotlib import pyplot as plt
import matplotlib.animation as animation
from matplotlib import style
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import cv2
import ffmpy
import numpy as np


# noinspection PyNoneFunctionAssignment,PyAttributeOutsideInit
class CamGUI(object):

    def __init__(self, debug_mode=False, init_cam_bool=True):
        self.running_config = {'debug_mode': debug_mode, 'init_cam_bool': init_cam_bool}
        if self.running_config['init_cam_bool']:
            from src.camera_control.ic_camera import ICCam
            print('Importing camera library')
        else:
            print('Camera library is not import. It will be imported when you initialize the camera')

        path = Path(os.path.realpath(__file__))
        # Navigate to the outer parent directory and join the filename
        dets_file = os.path.normpath(str(path.parents[2] / 'config-files' / 'camera_details.json'))

        with open(dets_file) as f:
            self.cam_details = json.load(f)
        self.mouse_list = self.cam_details['subjects'] if 'subjects' in self.cam_details else []
        self.cam_names = ()
        self.output_dir = ()
        for i in range(self.cam_details['cams']):
            self.cam_names = self.cam_names + (self.cam_details[str(i)]['name'],)
            self.output_dir = self.output_dir + (self.cam_details[str(i)]['output_dir'],)

        self.window = None
        self.calibration_capture_toggle_status = False
        self.selectCams()

    def browse_output(self):
        filepath = filedialog.askdirectory(initialdir='/')
        self.dir_output.set(filepath)

    def browse_codec(self, event):
        self.video_codec = self.video_codec_entry.get()
        print("Changed FourCC code:", self.video_codec)

    def init_cam(self, num):
        # create pop up window during setup
        setup_window = Tk()
        Label(setup_window, text="Setting up camera, please wait...").pack()
        setup_window.update()
        if not self.running_config['init_cam_bool']:
            from src.camera_control.ic_camera import ICCam
            print('Forced import camera library')

        if bool(self.toggle_video_recording_status.get()):
            setup_window.destroy()
            cam_on_window = Tk()
            Label(cam_on_window, text="Video is recording, cannot reinitialize camera!").pack()
            Button(cam_on_window, text="Ok", command=lambda: cam_on_window.quit()).pack()
            cam_on_window.mainloop()
            cam_on_window.destroy()
            return

        if len(self.cam) >= num + 1:
            if isinstance(self.cam[num], ICCam):
                self.cam[num].close()
                self.cam[num] = None

        # create camera object
        cam_num = self.camera[num].get()
        names = np.array(self.cam_names)
        cam_num = np.where(names == cam_num)[0][0]

        # if len(self.cam) >= num + 1:
        self.cam_name[num] = names[cam_num]
        self.cam[num] = ICCam(cam_num, exposure=self.exposure[cam_num].get(), gain=self.gain[cam_num].get())
        
        # self.cam[num].start()
        self.set_frame_rate(num, framerate=100, initCamera=True)

        # set gain and exposure using the values from the json
        self.cam[num].set_exposure(float(self.cam_details[str(num)]['exposure']))
        self.cam[num].set_gain(int(self.cam_details[str(num)]['gain']))
        self.cam[num].start()
        # get the gain and exposure values to reflect that onto the GUI
        self.exposure[num].set(self.cam[num].get_exposure())
        self.gain[num].set(self.cam[num].get_gain())
        
        self.get_fov(num)
        self.set_partial_scan_limit(num)
        self.get_frame_rate_list(num)
        
        self.get_current_frame_rate(num)
        self.trigger_status_label[num]['text'] = 'Disabled'
        
        [x_offset_value, y_offset_value] = self.cam[num].get_partial_scan()
        self.x_offset_value[num].set(x_offset_value)
        self.y_offset_value[num].set(y_offset_value)
        
        polarity = self.cam[num].get_trigger_polarity()
        self.polarity[num].set(polarity)
        
        # reset output directory
        self.dir_output.set(self.output_entry['values'][cam_num])
        setup_window.destroy()

    @staticmethod
    def check_frame(timeStampFile1, timeStampFile2, frameRate):
        # Timestamps should be in seconds
        return_text = []
        frameRate = float(frameRate)
        cam1 = timeStampFile1
        cam2 = timeStampFile2

        # Need to do this only when we're doing sync with synapse
        cam1 = cam1[1:]
        cam2 = cam2[1:]

        # Normalize
        cam1 = cam1 - cam1[0]
        cam2 = cam2 - cam2[0]

        # Find how many frames belong in both videos based on the longer one
        # One shorter video indicates frame drops
        numFrames = np.maximum(np.size(cam1), np.size(cam2))

        # Number of missing frames
        frameDiff = abs(np.size(cam1) - np.size(cam2))
        if frameDiff > 0:  # if there are missing frames

            temp_text = "Missing" + str(frameDiff) + "frames\n"
            return_text.append(temp_text)

        elif frameDiff == 0:  # if there are same frames in both videos, check jitter
            jitter1 = np.diff(cam1)
            jitter2 = np.diff(cam2)
            temp_text = 'No missing frames'
            return_text.append(temp_text)
            
            tolerance = (1 / frameRate) * 0.5
            
            # Find frames that are too long or short
            droppedFrames1 = np.where(
                np.logical_or(jitter1 < 1 / frameRate - tolerance, jitter1 > 1 / frameRate + tolerance))
            droppedFrames2 = np.where(
                np.logical_or(jitter2 < 1 / frameRate - tolerance, jitter2 > 1 / frameRate + tolerance))
            
            if np.size(droppedFrames1) > 0:
                temp_text = "These frames may not be exactly synchronized (jitter1): " + str(droppedFrames1)
            else:
                temp_text = "Frames cam 1 are synced!"
            return_text.append(temp_text)
            
            if np.size(droppedFrames2) > 0:
                temp_text = "These frames may not be exactly synchronized (jitter2): " + str(droppedFrames2)
            else:
                temp_text = "Frames from cam 2 are synced!"
            return_text.append(temp_text)
            
            mean_jitter1 = np.mean(jitter1)
            median_jitter1 = np.median(jitter1)
            std_jitter1 = np.std(jitter1)
            outliers_jitter1 = np.where(
                np.logical_or(jitter1 < mean_jitter1 - 2 * std_jitter1, jitter1 > mean_jitter1 + 2 * std_jitter1))
            
            mean_jitter2 = np.mean(jitter2)
            median_jitter2 = np.median(jitter2)
            std_jitter2 = np.std(jitter2)
            outliers_jitter2 = np.where(
                np.logical_or(jitter2 < mean_jitter2 - 2 * std_jitter2, jitter2 > mean_jitter2 + 2 * std_jitter2))
            
            temp_text = "Cam 1: Mean={:.6f}s, Median={:.6f}s, Std={:.6f}s".format(
                mean_jitter1, median_jitter1, std_jitter1)
            return_text.append(temp_text)
            
            temp_text = "Cam 2: Mean={:.6f}s, Median={:.6f}s, Std={:.6f}s".format(
                mean_jitter2, median_jitter2, std_jitter2)
            return_text.append(temp_text)
            
            # Calculate differences between cam_time_1 and cam_time_2
            cam_time_1_diff = cam1 - cam1[0]
            cam_time_2_diff = cam2 - cam2[0]
            
            # Calculate mean, mode, median, and standard deviation of the differences
            mean_diff = np.mean(cam_time_1_diff - cam_time_2_diff)
            median_diff = np.median(cam_time_1_diff - cam_time_2_diff)
            std_diff = np.std(cam_time_1_diff - cam_time_2_diff)
            
            temp_text = "Difference: Mean={:.6f}, Median={:.6f}, Std={:.6f}".format(
                mean_diff, median_diff, std_diff)
            return_text.append(temp_text)

        return return_text

    def show_camera_error(self):
        error_message = "No camera is found! \nPlease initialize camera before setting gain."
        self.show_error_window(error_message)
        
    def show_video_error(self):
        error_message = "Video writer is not initialized. \nPlease set up video first."
        self.show_error_window(error_message)

    @staticmethod
    def show_error_window(message):
        error_window = Tk()
        Label(error_window, text=message).pack()
        Button(error_window, text="Ok", command=error_window.destroy).pack()
        error_window.mainloop()
        error_window.destroy()
        
    def is_camera_set_up(self, num):
        return self.cam[num] is not None
        
    def set_gain(self, num):
        if self.is_camera_set_up(num) is False:
            self.show_camera_error()
            return
            
        self.cam[num].set_gain(int(self.gain[num].get()))
        self.get_frame_rate_list(num)
        
    def set_exposure(self, num):
        # check if camera set up
        if self.is_camera_set_up(num) is False:
            self.show_camera_error()
            return
        
        self.cam[num].set_exposure(float(self.exposure[num].get()))
        self.get_frame_rate_list(num)

    def get_frame_dimensions(self, num):
        if self.is_camera_set_up(num) is False:
            self.show_camera_error()
            return
        
        frame_dimension = self.cam[num].get_video_format()
        return frame_dimension
        
    def get_formats(self, num):
        # check if camera set up
        if self.is_camera_set_up(num) is False:
            self.show_camera_error()
            return

        return self.cam[num].get_formats()

    def set_formats(self, num):
        # check if camera set up
        if self.is_camera_set_up(num) is False:
            self.show_camera_error()
            return

        self.cam[num].set_formats(str(self.formats[num].get()))
        self.get_frame_rate_list(num)

    def get_fov(self, num):
        crop_details = self.cam_details[str(num)]['crop']
        for fov_label in self.fov_labels:
            self.fov_dict[num][fov_label].set(crop_details[fov_label])

    def set_fov(self, num):
        if self.is_camera_set_up(num) is False:
            self.show_camera_error()
            return
        
        for fov_label in self.fov_labels:
            self.cam_details[str(num)]['crop'][fov_label] = self.fov_dict[num][fov_label].get()
            
        self.cam[num].set_crop(top=self.cam_details[str(num)]['crop']['top'],
                               left=self.cam_details[str(num)]['crop']['left'],
                               height=self.cam_details[str(num)]['crop']['height'],
                               width=self.cam_details[str(num)]['crop']['width'])
        
        self.get_frame_rate_list(num)
    
    def reset_fov(self, num):
        pass
        
    def set_x_offset(self, i, num):
        self.cam[num].set_auto_center(value=self.auto_center[num].get())
        x_offset = self.x_offset_value[num].get()
        self.cam[num].set_partial_scan(x_offset=int(x_offset))
        self.x_offset_value[num].set(x_offset)
    
    def set_y_offset(self, i, num):
        self.cam[num].set_auto_center(value=self.auto_center[num].get())
        y_offset = self.y_offset_value[num].get()
        self.cam[num].set_partial_scan(y_offset=int(y_offset))
        self.y_offset_value[num].set(y_offset)
        
    def toggle_auto_center(self, num):
        if self.is_camera_set_up(num) is False:
            self.show_camera_error()
            return
        
        current_auto_center_status = self.auto_center[num].get()
        self.cam[num].set_auto_center(value=current_auto_center_status)
        state = "normal" if current_auto_center_status == 0 else "disabled"
        self.x_offset_scale[num].config(state=state)
        self.x_offset_spinbox[num].config(state=state)
        self.y_offset_scale[num].config(state=state)
        self.y_offset_spinbox[num].config(state=state)
        
        if current_auto_center_status == 0:
            self.set_partial_scan_limit(num)
            self.set_x_offset(None, num)
            self.set_y_offset(None, num)
       
    def toggle_polarity(self, num):
        if self.is_camera_set_up(num) is False:
            self.show_camera_error()
            return

        self.cam[num].set_trigger_polarity(value=int(self.polarity[num].get()))
        
    def set_partial_scan_limit(self, num):
        frame_dimension = self.get_frame_dimensions(num)
        self.x_offset_scale[num].config(to=frame_dimension[0])
        self.x_offset_spinbox[num].config(to=frame_dimension[0])
        self.y_offset_scale[num].config(to=frame_dimension[1])
        self.y_offset_spinbox[num].config(to=frame_dimension[1])
        
    def get_frame_rate_list(self, num):
        frame_rate_list = self.cam[num].get_frame_rate_list()
        self.framerate_list[num]['values'] = frame_rate_list
        
    def get_current_frame_rate(self, num):
        if self.is_camera_set_up(num) is False:
            self.show_camera_error()
            return
        current_frame_rate = self.cam[num].get_frame_rate()
        self.current_framerate[num].set(int(current_frame_rate))
        return current_frame_rate
        
    def set_frame_rate(self, num, framerate=None, initCamera=False):
        if self.is_camera_set_up(num) is False:
            self.show_camera_error()
            return
        
        if framerate is None:
            selected_frame_rate = self.framerate_list[num].get()
        else:
            selected_frame_rate = framerate
        if initCamera:
            result = self.cam[num].set_frame_rate(int(selected_frame_rate))
            self.framerate[num].set(selected_frame_rate)
        else:
            self.cam[num].close(getPosition=True)
            result = self.cam[num].set_frame_rate(int(selected_frame_rate))
            self.framerate[num].set(selected_frame_rate)
            current_framerate = self.get_current_frame_rate(num)
            self.cam[num].start()
            print(f'Selected: {selected_frame_rate }. Frame rate set to {current_framerate} fps. Result: {result}')
        
    def release_trigger(self):
        for num in range(len(self.cam)):
            self.cam[num].disable_trigger()
    
    def snap_image(self):
        for num in range(len(self.cam)):
            self.cam[num].get_image()

    def create_video_files(self, overwrite=False):
        if not os.path.isdir(os.path.normpath(self.dir_output.get())):
            os.makedirs(os.path.normpath(self.dir_output.get()))

        # check if file exists, ask to overwrite or change attempt number if it does
        for i in range(len(self.cam)):
            if i == 0:
                self.overwrite = overwrite
                if os.path.isfile(self.vid_file[i]) and not self.overwrite:
                    self.ask_overwrite = Tk()

                    def quit_overwrite(ow):
                        self.overwrite = ow
                        self.ask_overwrite.quit()

                    Label(self.ask_overwrite,
                          text="File already exists with attempt number = " +
                               self.attempt.get() +
                               ".\nWould you like to overwrite the file? ").pack()
                    Button(self.ask_overwrite, text="Overwrite", command=lambda: quit_overwrite(True)).pack()
                    Button(self.ask_overwrite, text="Cancel & pick new attempt number",
                           command=lambda: quit_overwrite(False)).pack()
                    self.ask_overwrite.mainloop()
                    self.ask_overwrite.destroy()

                    if self.overwrite:
                        self.vid_file[i] = os.path.normpath(self.dir_output.get() + '/' +
                                                            self.base_name[i] +
                                                            self.attempt.get() +
                                                            '.avi')
                    else:
                        return
            else:
                # self.vid_file[i] = self.vid_file[0].replace(cam_name_nospace[0], cam_name_nospace[i])
                print('')

            # create video writer
            dim = self.cam[i].get_image_dimensions()
            fourcc = cv2.VideoWriter_fourcc(*self.video_codec)
            if len(self.vid_out) >= i + 1:
                self.vid_out[i] = cv2.VideoWriter(self.vid_file[i], fourcc, int(self.fps.get()), dim)
            else:
                self.vid_out.append(cv2.VideoWriter(self.vid_file[i], fourcc, int(self.fps.get()), dim))
                
            self.toggle_video_recording_button['state'] = 'normal'
            self.toggle_video_recording_button['text'] = 'Click to start recording'

    def create_output_files(self, subject_name='Sam'):
        # create output file names
        self.ts_file = []
        self.ts_file_csv = []
        self.frame_times = []

        for i in range(len(self.cam)):
            self.ts_file.append(self.vid_file[i].replace('.avi', '.npy'))
            self.ts_file[i] = self.ts_file[i].replace(self.cam_name_no_space[i], 'TIMESTAMPS_' + self.cam_name_no_space[i])
            self.ts_file_csv.append(self.vid_file[i].replace('.avi', '.csv'))
            self.ts_file_csv[i] = self.ts_file_csv[i].replace(self.cam_name_no_space[i],
                                                              'TIMESTAMPS_' + self.cam_name_no_space[i])
            self.current_file_label['text'] = subject_name
            self.frame_times.append([])
        
        # empty out the video's stat message
        self.save_msg = ""
     
    def sync_setup(self):

        if len(self.vid_out) > 0:
            vid_open_window = Tk()
            Label(vid_open_window,
                  text="Video is currently open! "
                       "\nPlease release the current video"
                       " (click 'Save Video', even if no frames have been recorded)"
                       " before setting up a new one.").pack()
            Button(vid_open_window, text="Ok", command=lambda: vid_open_window.quit()).pack()
            vid_open_window.mainloop()
            vid_open_window.destroy()
            return

        # check if camera set up
        if len(self.cam) == 0:
            self.show_camera_error()
            return
        
        self.trigger_on = 1
        da_fps = str(self.fps.get())
        month = datetime.datetime.now().month
        month = str(month) if month >= 10 else '0' + str(month)
        day = datetime.datetime.now().day
        day = str(day) if day >= 10 else '0' + str(day)
        year = str(datetime.datetime.now().year)
        date = year + '-' + month + '-' + day
        
        # Preallocate vid_file dir
        self.vid_file = []
        self.base_name = []
        self.cam_name_no_space = []

        # subject_name, dir_name = generate_folder()
        subject_name = self.subject.get()
        if subject_name is None:
            subject_name = 'Sam'
            
        for num in range(len(self.cam)):
            temp_exposure = str(round(math.log2(1/float((self.exposure[num].get())))))
            temp_gain = str(round(float(self.gain[num].get())))
            self.cam_name_no_space.append(self.cam_name[num].replace(' ', ''))
            self.base_name.append(self.cam_name_no_space[num] + '_' +
                                  subject_name + '_' +
                                  str(int(da_fps)) + 'f' +
                                  temp_exposure + 'e' +
                                  temp_gain + 'g')
            self.vid_file.append(os.path.normpath(self.dir_output.get() +
                                                  '/' +
                                                  self.base_name[num] +
                                                  '.avi'))
            self.trigger_status_label[num]['text'] = 'Trigger Ready'
            self.trigger_status_indicator[num]['bg'] = 'red'

            # Check if video files already exist, if yes, ask to change or overwrite
        self.create_video_files()
        self.create_output_files(subject_name=subject_name)
        
        self.setup = True

    def set_up_vid(self):
        if len(self.vid_out) > 0:
            vid_open_window = Tk()
            Label(vid_open_window,
                  text="Video is currently open! \n"
                       "Please release the current video (click 'Save Video', even if no frames have been recorded)"
                       " before setting up a new one.").pack()
            Button(vid_open_window, text="Ok", command=lambda: vid_open_window.quit()).pack()
            vid_open_window.mainloop()
            vid_open_window.destroy()
            return

        # check if camera set up
        if len(self.cam) == 0:
            self.show_camera_error()
            return
        
        self.trigger_on = 0
        da_fps = str(self.fps.get())
        month = datetime.datetime.now().month
        month = str(month) if month >= 10 else '0' + str(month)
        day = datetime.datetime.now().day
        day = str(day) if day >= 10 else '0' + str(day)
        year = str(datetime.datetime.now().year)
        date = year + '-' + month + '-' + day

        self.cam_name_no_space = []
        self.vid_file = []
        self.base_name = []
        this_row = 3
        for i in range(len(self.cam)):
            temp_exposure = str(round(math.log2(1/float(self.exposure[i].get()))))
            temp_gain = str(round(float(self.gain[i].get())))
            self.cam_name_no_space.append(self.cam_name[i].replace(' ', ''))
            self.base_name.append(self.cam_name_no_space[i] + '_'
                                  + self.subject.get() + '_'
                                  + date + '_'
                                  + str(int(da_fps)) + 'f'
                                  + temp_exposure + 'e'
                                  + temp_gain + 'g')
            self.vid_file.append(os.path.normpath(self.dir_output.get() + '/' +
                                                  self.base_name[i] +
                                                  self.attempt.get() +
                                                  '.avi'))

        self.create_video_files()
        subject_name = self.subject.get() + '_' + date + '_' + self.attempt.get()
        self.create_output_files(subject_name=subject_name)
        self.setup = True

    def record_on_thread(self, num, barrier=None):
        fps = int(self.fps.get())
        if self.trigger_on == 1:
            try:
                self.trigger_status_label[num]['text'] = 'Waiting for trigger...'
                self.trigger_status_indicator[num]['bg'] = 'yellow'
                trigger_start_time = time.perf_counter()
                self.cam[num].enable_trigger()
                self.cam[num].frame_ready()
                self.frame_times[num].append(time.perf_counter())
                trigger_wait_time = time.perf_counter() - trigger_start_time
                self.trigger_status_label[num]['text'] = f'Trigger received. Waited {trigger_wait_time:.4f}s...'
                self.trigger_status_indicator[num]['bg'] = 'green'
                self.cam[num].disable_trigger()
                start_in_one = math.trunc(time.perf_counter()) + 1
                while time.perf_counter() < start_in_one:
                    pass
            except Exception as e:
                print(f"Traceback: \n {traceback.format_exc()}")

        start_time = time.perf_counter()
        next_frame = start_time

        try:
            while bool(self.toggle_video_recording_status.get()):
                if time.perf_counter() >= next_frame:
                    if barrier is not None:
                        barrier.wait()
                    self.frame_times[num].append(time.perf_counter())
                    self.vid_out[num].write(self.cam[num].get_image())
                    next_frame = max(next_frame + 1.0 / fps, self.frame_times[num][-1] + 0.5 / fps)
        except Exception as e:
            print(f"Traceback: \n {traceback.format_exc()}")

    @staticmethod
    def clear_calibration_file(file_name):
        """_summary_

        Args:
            file_name (directory): directory to the calibration files: calibration.toml and detections.pickles
        """
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"Deleted calibration file: {file_name}")
        else:
            print(f"Calibration file '{file_name}' does not exist.")

    def set_calibration_buttons_group(self, state):
        """
        Sets the state of the calibration buttons group.

        :param state: The state to set for the buttons. Valid values are 'normal', 'active', 'disabled', 'pressed', or 'focus'.
        :type state: str
        """
        self.toggle_calibration_capture_button['state'] = state
        self.snap_calibration_button['state'] = state
        self.recalibrate_button['state'] = state
        self.update_calibration_button['state'] = state
        self.plot_calibration_error_button['state'] = state
        self.test_calibration_live_button['state'] = state
        
    def set_calibration_duration(self):
        self.calibration_duration_text = self.calibration_duration_entry.get()

        if self.calibration_duration_text == "Inf":
            self.calibration_duration = float('inf')
        else:
            try:
                self.calibration_duration = int(self.calibration_duration_text)
            except ValueError:
                messagebox.showerror("Error", "Invalid input. Please enter an integer value or 'Inf'.")
                return 0
        
        return 1
 
    def setup_calibration(self):
        """
        Method: setup_calibration

        This method initializes the calibration process. It performs the following steps:

        1. Initializes the calibration process by updating the status text.
        2. Looks for the config.toml directory if debug_mode is enabled.
        3. Loads the config file and determines the calibration board.
        4. Initializes camera calibration objects.
        5. Records frame sizes and initializes camera objects.
        6. Configures calibration buttons and toggle statuses.
        7. Clears previous calibration files.
        8. Sets calibration duration parameter.
        9. Creates a shared queue to store frames.
        10. Updates the boolean flag for detection updates.
        11. Synchronizes camera capture time using threading.Barrier.
        12. Creates output file names for the calibration videos.
        13. Sets frame sizes for the cameras.
        14. Starts the calibration process by recording frames, processing markers, and calibrating.

        Parameters:
        - None

        Return Type:
        - None
        """
        self.calibration_process_stats.set('Initializing calibration process...')
        from src.gui.utils import load_config, get_calibration_board
        if self.running_config['debug_mode']:
            self.calibration_process_stats.set('Looking for config.toml directory ...')
            path = Path(os.path.realpath(__file__))
            # Navigate to the outer parent directory and join the filename
            config_toml_path = os.path.normpath(str(path.parents[2] / 'config-files' / 'config.toml'))
            config_anipose = load_config(config_toml_path)
            self.calibration_process_stats.set('Successfully found and loaded config. Determining calibration board ...')
            self.board_calibration = get_calibration_board(config=config_anipose)

            self.calibration_process_stats.set('Loaded calibration board. '
                                               'Initializing camera calibration objects ...')
            from src.aniposelib.cameras import CameraGroup
            self.cgroup = CameraGroup.from_names(self.cam_names)
            self.calibration_process_stats.set('Initialized camera object.')
            self.frame_count = []
            self.all_rows = []

            self.calibration_process_stats.set('Cameras found. Recording the frame sizes')
            self.set_calibration_buttons_group(state='normal')
            
            self.calibration_capture_toggle_status = False
            self.calibration_toggle_status = False
            
            frame_sizes = []
            self.frame_times = []
            self.previous_frame_count = []
            self.current_frame_count = []
            self.frame_process_threshold = 2
            self.queue_frame_threshold = 1000
            # Check available detection file, if file available will delete it (for now)
            self.rows_fname = os.path.join(self.dir_output.get(), 'detections.pickle')
            self.calibration_out = os.path.join(self.dir_output.get(), 'calibration.toml')
            self.clear_calibration_file(self.rows_fname)
            self.clear_calibration_file(self.calibration_out)
            self.rows_fname_available = False
            
            # Set calibration parameter
            result = self.set_calibration_duration()
            if result == 0:
                return
            
            self.error_list = []
            # Create a shared queue to store frames
            self.frame_queue = queue.Queue(maxsize=self.queue_frame_threshold)

            # Boolean for detections.pickle is updated
            self.detection_update = False

            # create output file names
            self.vid_file = []
            self.base_name = []
            self.cam_name_no_space = []

            for i in range(len(self.cam)):
                # write code to create a list of base names for the videos
                self.cam_name_no_space.append(self.cam_name[i].replace(' ', ''))
                self.base_name.append(self.cam_name_no_space[i] + '_' + 'calibration_')
                self.vid_file.append(os.path.normpath(self.dir_output.get() +
                                                      '/' +
                                                      self.base_name[i] +
                                                      self.attempt.get() +
                                                      '.avi'))

                frame_sizes.append(self.cam[i].get_image_dimensions())
                self.frame_count.append(1)
                self.all_rows.append([])
                self.previous_frame_count.append(0)
                self.current_frame_count.append(0)

            # check if file exists, ask to overwrite or change attempt number if it does
            self.create_video_files(overwrite=True)
            self.create_output_files(subject_name='Sam')

            self.calibration_process_stats.set('Setting the frame sizes...')
            self.cgroup.set_camera_sizes_images(frame_sizes=frame_sizes)
            self.calibration_process_stats.set('Prepping done. Ready to capture calibration frames...')
            self.vid_start_time = time.perf_counter()
           
            self.recording_threads = []
            self.calibrating_thread = None

    def toggle_calibration_capture(self, termination=False):
        """
        Toggles the calibration capture on or off.

        Parameters:
        - self: The object instance.

        Returns:
        None

        Example usage:
        toggle_calibration_capture()

        Note:
        If `self.calibration_capture_toggle_status` is True, the method will toggle it to False and update the GUI elements accordingly.
        If `self.calibration_capture_toggle_status` is False, the method will set the calibration duration using the `set_calibration_duration()` method.
        If the result of `set_calibration_duration()` is 0, the method will return without performing any further actions.
        The method then initializes an empty list `self.current_all_rows` and sets `self.calibration_capture_toggle_status` to True.
        It updates the GUI elements to reflect the changes and disables certain buttons.
        """
        if self.calibration_capture_toggle_status or termination:
            self.calibration_capture_toggle_status = False
            
            print('Waiting for all the frames are done processing...')
            self.calibration_process_stats.set('Waiting for all the frames are done processing...')
            current_thread = threading.currentThread()
            for t in self.recording_threads:
                if t is not current_thread and t.is_alive():
                    print('Waiting for thread {} to finish...'.format(t.name))
                    t.join()
                
            print('All frames are done processing.')
            
            self.toggle_calibration_capture_button.config(text="Capture Off", background="red")
            self.calibration_process_stats.set('Done capturing calibration frames. Ready to be calibrated...')
            self.calibration_duration_entry['state'] = 'normal'
            self.added_board_value.set(f'{len(self.current_all_rows[0])}')
            self.plot_calibration_error_button['state'] = 'normal'
            self.test_calibration_live_button['state'] = 'normal'
        else:
            result = self.set_calibration_duration()
            if result == 0:
                return
            
            print('Starting threads to record calibration frames...')
            # cleaning up previous threads
            if not self.recording_threads == []:
                print('Clearing up previous threads...')
                for t in self.recording_threads:
                    t.join()
                self.recording_threads = []
                self.recording_threads_status = []
                self.frame_queue = queue.Queue(maxsize=self.queue_frame_threshold)
            else:
                print('Previous threads already cleared or empty.')
            
            # Setting capture toggle status
            self.calibration_capture_toggle_status = True
            
            # Sync camera capture time using threading.Barrier
            barrier = threading.Barrier(len(self.cam))
            
            for i in range(len(self.cam)):
                thread_name = f"Cam {i + 1} thread"
                self.recording_threads.append(threading.Thread(target=self.record_calibrate_on_thread, args=(i, barrier), name=thread_name))
                self.recording_threads[-1].daemon = True
                self.recording_threads[-1].start()
                self.recording_threads_status.append(True)
            thread_name = f"Marker processing thread"
            self.recording_threads.append(threading.Thread(target=self.process_marker_on_thread, name=thread_name))
            self.recording_threads[-1].daemon = True
            self.recording_threads[-1].start()

            self.current_all_rows = []
            for i in range(len(self.cam)):
                self.current_all_rows.append([])
            
            # GUI stuffs
            self.toggle_calibration_capture_button.config(text="Capture On", background="green")
            self.calibration_process_stats.set('Started capturing calibration frames...')
            self.calibration_duration_entry['state'] = 'disabled'
            self.plot_calibration_error_button['state'] = 'disabled'
            self.test_calibration_live_button['state'] = 'disabled'
            
    def snap_calibration_frame(self):
        """
        Take a snapshot of the calibration frame from each camera.

        Returns:
        None

        This method captures a single frame from each camera and then detects a marker in each frame. The marker detected frames are saved to the open videos. The detected corners and marker ids for each frame are stored in the `self.all_rows` list.

        During the capture process, the `self.frame_times` list is updated with the current time in order to track the frame acquisition time. The `self.frame_count` list is also incremented to keep track of the number of frames acquired for each camera.

        This method updates the following labels:
        - `self.frame_acquired_count_label`: shows the number of frames acquired for each camera
        - `self.board_detected_count_label`: shows the total number of detected frames for each camera
        """
        current_frames = []
        
        # capture a single frame from each camera first
        for num in range(len(self.cam)):
            self.frame_times[num].append(time.perf_counter())
            self.frame_count[num] += 1
            current_frames.append(self.cam[num].get_image())
            self.frame_acquired_count_label[num]['text'] = f'{self.frame_count[num]}'
            
        # then detect the marker and save those frames to the open videos
        for num in range(len(self.cam)):
            # detect the marker as the frame is acquired
            frame_current = current_frames[num]
            corners, ids = self.board_calibration.detect_image(frame_current)
            if corners is not None:
                key = self.frame_count[num]
                row = {
                    'framenum': key,
                    'corners': corners,
                    'ids': ids
                }

                row = self.board_calibration.fill_points_rows([row])
                self.all_rows[num].extend(row)
                self.current_all_rows[num].extend(row)
                self.board_detected_count_label[num]['text'] = f'{len(self.all_rows[num])}'
                self.frame_acquired_count_label[num]['text'] = f'{self.frame_count[num]}'
                self.vid_out[num].write(frame_current)
    
    def record_calibrate_on_thread(self, num, barrier):
        """
        Records frames from a camera on a separate thread for calibration purposes.

        :param num: The ID of the capturing camera.
        :param barrier: A threading.barrier object used to synchronize the start of frame capturing.

        :return: None

        """
        fps = int(self.fps.get())
        start_time = time.perf_counter()
        next_frame = start_time
        try:
            while self.calibration_capture_toggle_status and (time.perf_counter()-start_time < self.calibration_duration):
                if time.perf_counter() >= next_frame:
                    barrier.wait()
                    self.frame_times[num].append(time.perf_counter())
                    self.frame_count[num] += 1
                    frame_current = self.cam[num].get_image()
                    
                    # detect the marker as the frame is acquired
                    corners, ids = self.board_calibration.detect_image(frame_current)
                    if corners is not None:
                        key = self.frame_count[num]
                        row = {
                            'framenum': key,
                            'corners': corners,
                            'ids': ids
                        }

                        row = self.board_calibration.fill_points_rows([row])
                        self.all_rows[num].extend(row)
                        self.current_all_rows[num].extend(row)
                        self.board_detected_count_label[num]['text'] = f'{len(self.all_rows[num])}'
                        if num == 0:
                            self.calibration_current_duration_value.set(f'{time.perf_counter()-start_time:.2f}')
                    
                    # putting frame into the frame queue along with following information
                    self.frame_queue.put((frame_current,  # the frame itself
                                          num,  # the id of the capturing camera
                                          self.frame_count[num],  # the current frame count
                                          self.frame_times[num][-1]))  # captured time

                    next_frame = max(next_frame + 1.0/fps, self.frame_times[num][-1] + 0.5/fps)
            
            if (time.perf_counter() - start_time) > self.calibration_duration or self.calibration_capture_toggle_status:
                barrier.wait()
                print(f"Calibration capture on cam {num}: duration exceeded or toggle status is True. Terminating thread.")
                self.recording_threads_status[num] = False
                # self.toggle_calibration_capture(termination=True)
                
        except Exception as e:
            print("Exception occurred:", type(e).__name__, "| Exception value:", e, "| Thread ID:", num,
                  "| Frame count:", self.frame_count[num], "| Capture time:", self.frame_times[num][-1],
                  "| Traceback:", ''.join(traceback.format_tb(e.__traceback__)))

    def process_marker_on_thread(self):
        """
        Process marker on a separate thread.

        This method retrieves frame information from the frame queue and processes it. The frames are grouped by thread ID
        and stored in a dictionary called frame_groups. The method continuously loops until the calibration_capture_toggle_status
        is True or the frame queue is not empty.

        Parameters:
        - self: The current instance of the class.

        Returns:
        This method does not return any value.

        Raises:
        This method may raise an exception when an error occurs during processing.

        Example usage:
        process_marker_on_thread()
        """
        frame_groups = {}  # Dictionary to store frame groups by thread_id
        frame_counts = {}  # array to store frame counts for each thread_id
        try:
            while any(thread is True for thread in self.recording_threads_status):
                # Retrieve frame information from the queue
                frame, thread_id, frame_count, capture_time = self.frame_queue.get()
                if thread_id not in frame_groups:
                    frame_groups[thread_id] = []  # Create a new group for the thread_id if it doesn't exist
                    frame_counts[thread_id] = 0

                # Append frame information to the corresponding group
                frame_groups[thread_id].append((frame, frame_count, capture_time))
                frame_counts[thread_id] += 1
                self.frame_acquired_count_label[thread_id]['text'] = f'{frame_count}'
                self.vid_out[thread_id].write(frame)
                
                # Process the frame group (frames with the same thread_id)
                # dumping the mix and match rows into detections.pickle to be pickup by calibrate_on_thread
                if all(count >= self.frame_process_threshold for count in frame_counts.values()):
                    with open(self.rows_fname, 'wb') as file:
                        pickle.dump(self.all_rows, file)
                    self.rows_fname_available = True
                    
                    # Clear the processed frames from the group
                    frame_groups = {}
                    frame_count = {}
            
            # Process the remaining frames in the queue
            while not self.frame_queue.empty():
                print('Processing remaining frames in the queue')
                frame, thread_id, frame_count, capture_time = self.frame_queue.get()
                if thread_id not in frame_groups:
                    frame_groups[thread_id] = []
                    frame_counts[thread_id] = 0
                frame_groups[thread_id].append((frame, frame_count, capture_time))
                frame_counts[thread_id] += 1
                self.frame_acquired_count_label[thread_id]['text'] = f'{frame_count}'
                self.vid_out[thread_id].write(frame)
                
                if all(count >= self.frame_process_threshold for count in frame_counts.values()):
                    with open(self.rows_fname, 'wb') as file:
                        pickle.dump(self.all_rows, file)
                    self.rows_fname_available = True
                    print('Dumped rows into detections.pickle')
                    
                    frame_groups = {}
                    frame_count = {}
            
            # Clear the frame queue
            self.frame_queue.queue.clear()
            print('Cleared frame queue')
            
            if all(thread is False for thread in self.recording_threads_status):
                print('Terminating thread')
                self.toggle_calibration_capture(termination=True)
                
        except Exception as e:
            print("Exception occurred:", type(e).__name__, "| Exception value:", e, "| Thread ID:", thread_id,
                  "| Frame count:", frame_count, "| Capture time:", capture_time, "| Traceback:",
                  ''.join(traceback.format_tb(e.__traceback__)))

    def recalibrate(self):
        """
        Recalibrates the device.

        Recalibrates the device by updating the necessary calibration statuses. This method should be called when the calibration toggle status is "False".

        Parameters:
            None

        Returns:
            None
        """
        if self.calibration_toggle_status is False:
            self.recalibrate_status = True
            self.update_calibration_status = False
            self.calibration_toggle_status = True
            print(f'Recalibration status: {self.recalibrate_status}, Update calibration status: {self.update_calibration_status}, Calibration toggle status: {self.calibration_toggle_status}')
            
            if self.calibrating_thread is not None and self.calibrating_thread.is_alive():
                self.calibrating_thread.join()
            else:
                self.calibrating_thread = threading.Thread(target=self.calibrate_on_thread)
                self.calibrating_thread.daemon = True
                self.calibrating_thread.start()
 
    def update_calibration(self):
        """
         Updates the calibration status.

        If the calibration toggle status is False, it sets the update calibration status to True, recalibrate status to False,
        and calibration toggle status to True.

        Parameters:
            self (object): The instance of the class.

        Returns:
            None
        """
        if self.calibration_toggle_status is False:
            self.update_calibration_status = True
            self.recalibrate_status = False
            self.calibration_toggle_status = True
           
            if self.calibrating_thread is not None and self.calibrating_thread.is_alive():
                self.calibrating_thread.join()
            else:
                self.calibrating_thread = threading.Thread(target=self.calibrate_on_thread)
                self.calibrating_thread.daemon = True
                self.calibrating_thread.start()
    
    def calibrate_on_thread(self):
        """
        Calibrates the system on a separate thread.

        Parameters:
            None

        Returns:
            None
        """
        self.calibration_error = float('inf')
        print(f'Current error: {self.calibration_error}')
        try:
            if self.calibration_toggle_status:
                
                self.calibration_process_stats.set('Calibrating...')
                print(f'Current error: {self.calibration_error}')
                if self.recalibrate_status:
                    with open(self.rows_fname, 'rb') as f:
                        all_rows = pickle.load(f)
                    print('Loaded rows from detections.pickle')
                
                if self.update_calibration_status:
                    all_rows = copy.deepcopy(self.current_all_rows)
                    print('Loaded rows from current_all_rows')
                
                if self.calibration_error is None or self.calibration_error > 0.1:
                    init_matrix = True
                    print('Force init_matrix to True')
                else:
                    init_matrix = bool(self.init_matrix_check.get())
                    print(f'init_matrix: {init_matrix}')
                    
                # all_rows = [row[-100:] if len(row) >= 100 else row for row in all_rows]
                self.calibration_error = self.cgroup.calibrate_rows(all_rows, self.board_calibration,
                                                                    init_intrinsics=init_matrix,
                                                                    init_extrinsics=init_matrix,
                                                                    max_nfev=200, n_iters=6,
                                                                    n_samp_iter=200, n_samp_full=1000,
                                                                    verbose=True)
                
                # self.calibration_error_stats['text'] = f'Current error: {self.calibration_error}'
                self.cgroup.metadata['adjusted'] = False
                if self.calibration_error is not None:
                    self.cgroup.metadata['error'] = float(self.calibration_error)
                    self.calibration_error_value.set(f'{self.calibration_error:.5f}')
                    self.error_list.append(self.calibration_error)
                    print(f'Calibration error: {self.calibration_error}')
                else:
                    print('Failed to calibrate')
                    
                print('Calibration completed')
                self.cgroup.dump(self.calibration_out)
                print('Calibration result dumped')
                
                self.rows_fname_available = False
                self.calibration_toggle_status = False

        except Exception as e:
            print("Exception occurred:", type(e).__name__, "| Exception value:", e,
                  ''.join(traceback.format_tb(e.__traceback__)))

    def plot_calibration_error(self):
        """
        Plot the calibration error progression.

        This method creates a new window using the Tkinter library and plots the given list of calibration error values. The plot is displayed using Matplotlib embedded in the Tkinter window.

        Parameters:
        - None

        Return Type:
        - None

        Example Usage:
        plot_calibration_error()
        """
        root = Tk()
        root.title('Calibration Error')
        root.geometry('500x500')
        root.configure(background='white')
        
        error_list = self.error_list
        fig, ax = plt.subplots()

        # Plot the error values
        ax.plot(error_list)

        # Customize the plot
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Error')
        ax.set_title('Error Progression')

        # Display the plot
        import tkinter as tk
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        
        canvas = FigureCanvasTkAgg(fig, master=root)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        
        toolbar = NavigationToolbar2Tk(canvas, root)
        toolbar.update()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        
        root.mainloop()
        
    def test_calibration_live(self):
        
        calibration_file = self.calibration_out
        if not os.path.exists(calibration_file):
            messagebox.showerror('Error', 'Calibration file not found!')
            return
        
        from src.aniposelib.cameras import CameraGroup
        self.cgroup_test = CameraGroup.load(calibration_file)# cgroup_test is loaded with the calibration file
        barrier = threading.Barrier(len(self.cam))
        
        t = []
        for i in range(len(self.cam)):
            t.append(threading.Thread(target=self.draw_calibration_on_thread, args=(i, barrier)))
            t[-1].daemon = True
            t[-1].start()
           
    def draw_calibration_on_thread(self, num, barrier):
        """
        Draws calibration on a separate thread for a given camera.

        Parameters:
        - num: The camera number.
        - barrier: A threading.Barrier object used to synchronize multiple threads.

        Returns:
        None

        Example usage:
        draw_calibration_on_thread(0, barrier)
        """
        window_name = f'Camera {num}'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 640, 480)
        from utils import aruco_dict
        from cv2 import aruco
        params = aruco.DetectorParameters()
        params.cornerRefinementMethod = aruco.CORNER_REFINE_CONTOUR
        params.adaptiveThreshWinSizeMin = 100
        params.adaptiveThreshWinSizeMax = 1000
        params.adaptiveThreshWinSizeStep = 50
        params.adaptiveThreshConstant = 0
        
        while cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) > 0:
            barrier.wait()
            frame_current = self.cam[num].get_image()
            if frame_current is None:
                drawn_frame = self.draw_axis(frame_current, camera_matrix=self.cgroup_test.cameras[num].get_camera_matrix(),
                                                dist_coeff=self.cgroup_test.cameras[num].get_distortion(),
                                                board=self.board_calibration, aruco_dict=aruco_dict, params=params)
                cv2.imshow(window_name, drawn_frame)
    
    @staticmethod
    def draw_axis(frame, camera_matrix, dist_coeff, board, aruco_dict, params, verbose=True):
        """
        """
        try:
            corners, ids, rejected_points = cv2.aruco.detectMarkers(frame, aruco_dict, parameters=params)

            if corners is None or ids is None:
                print('No corner detected')
                return None
            if len(corners) != len(ids) or len(corners) == 0:
                print('Incorrect corner or no corner detected!')
                return None

            corners, ids, rejectedCorners, recoveredIdxs = cv2.aruco.refineDetectedMarkers(frame, board, corners, ids,
                                                                                           rejected_points, camera_matrix,
                                                                                           dist_coeff, parameters=params)

            if len(corners) == 0:
                return None

            ret, c_corners, c_ids = cv2.aruco.interpolateCornersCharuco(corners, ids,
                                                                        frame, board,
                                                                        cameraMatrix=camera_matrix, distCoeffs=dist_coeff)

            if c_corners is None or c_ids is None or len(c_corners) < 5:
                print('No corner detected after interpolation!')
                return None

            n_corners = c_corners.size // 2
            reshape_corners = np.reshape(c_corners, (n_corners, 1, 2))

            ret, p_rvec, p_tvec = cv2.aruco.estimatePoseCharucoBoard(reshape_corners,
                                                                        c_ids,
                                                                        board,
                                                                        camera_matrix,
                                                                        dist_coeff)

            if p_rvec is None or p_tvec is None:
                print('Cant detect rotation!')
                return None
            if np.isnan(p_rvec).any() or np.isnan(p_tvec).any():
                print('Rotation is not usable')
                return None

            cv2.aruco.drawAxis(image=frame, cameraMatrix=camera_matrix, distCoeffs=dist_coeff,
                               rvec=p_rvec, tvec=p_tvec, length=20)

            cv2.aruco.drawDetectedCornersCharuco(frame, reshape_corners, c_ids)
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            # cv2.aruco.drawDetectedMarkers(frame, rejected_points, borderColor=(100, 0, 240))

        except cv2.error as e:
            import sys
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            return None

        if verbose:
            print('Translation : {0}'.format(p_tvec))
            print('Rotation    : {0}'.format(p_rvec))
            print('Distance from camera: {0} m'.format(np.linalg.norm(p_tvec)))

        return frame
    
    def toggle_video_recording(self, set_status=None):
        if set_status is not None:
            toggle_status = not set_status
        else:
            toggle_status = bool(self.toggle_video_recording_status.get())
        
        if toggle_status:
            self.toggle_video_recording_status = IntVar(value=0)
            self.toggle_video_recording_button.config(text="Capture Off", background="red")
            if self.toggle_continuous_mode.get() == 1:
                for i in range(len(self.cam)):
                    self.cam[i].turn_off_continuous_mode()
        
        else: # start recording videos and change button text
            self.toggle_video_recording_status = IntVar(value=1)
            self.toggle_video_recording_button.config(text="Capture On", background="green")
            
            self.vid_start_time = time.perf_counter()
            if int(self.force_frame_sync.get()):
                barrier = threading.Barrier(len(self.cam))
            else:
                barrier = None
                
            if self.toggle_continuous_mode.get() == 1:
                for i in range(len(self.cam)):
                    self.cam[i].turn_on_continuous_mode()
                    
            t = []
            for i in range(len(self.cam)):
                t.append(threading.Thread(target=self.record_on_thread, args=(i, barrier)))
                t[-1].daemon = True
                t[-1].start()

    def compress_vid(self, ind):
        ff_input = dict()
        ff_input[self.vid_file[ind]] = None
        ff_output = dict()
        out_file = self.vid_file[ind].replace('avi', 'mp4')
        ff_output[out_file] = '-c:v libx264 -crf 17'
        ff = ffmpy.FFmpeg(inputs=ff_input, outputs=ff_output)
        ff.run()

    def display_recorded_stats(self):
        save_window = Tk()
        Label(save_window, text=self.save_msg).pack()
        Button(save_window, text="Close", command=lambda: save_window.quit()).pack()
        save_window.mainloop()
        save_window.destroy()
        
    def save_vid(self, compress=False, delete=False):
        self.toggle_video_recording(set_status='False')
        self.toggle_video_recording_button['state'] = 'disabled'
        self.toggle_video_recording_button.config(text="Capture Disabled", background="red")
        
        saved_files = []
        for num in range(len(self.cam)):
            self.trigger_status_label[num]['text'] = 'Disabled'
            self.trigger_status_indicator[num]['bg'] = 'gray'
            
        # check that videos have been initialized
        if len(self.vid_out) == 0:
            self.show_video_error()
            return

        # check for frames before saving. if any video has not taken frames, delete all videos
        frames_taken = all([len(i) > 0 for i in self.frame_times])

        # release video writer (saves file).
        # if no frames taken or delete specified,
        # delete the file and do not save timestamp files; otherwise, save timestamp files.
        for i in range(len(self.vid_out)):
            self.vid_out[i].release()
            self.vid_out[i] = None
            if (delete) or (not frames_taken):
                os.remove(self.vid_file[i])
            else:
                np.save(str(self.ts_file[i]), np.array(self.frame_times[i]))
                np.savetxt(str(self.ts_file_csv[i]), np.array(self.frame_times[i]), delimiter=",")
                saved_files.append(self.vid_file[i])
                saved_files.append(self.ts_file[i])
                if compress:
                    threading.Thread(target=lambda: self.compress_vid(i)).start()
            
        if len(saved_files) > 0:
            if len(self.frame_times) > 1:
                cam0_times = np.array(self.frame_times[0])
                cam1_times = np.array(self.frame_times[1])
                fps = int(self.fps.get())
                check_frame_text = self.check_frame(cam0_times, cam1_times, fps)
                for texty in check_frame_text:
                    self.save_msg += texty + '\n'
            self.save_msg += "The following files have been saved:"
            for i in saved_files:
                self.save_msg += "\n" + i
                
            self.attempt.set(str(int(self.attempt.get()) + 1))

        elif delete:
            self.save_msg = "Video has been deleted, please set up a new video to take another recording."
        elif not frames_taken:
            self.save_msg = 'Video was initialized but no frames were recorded.\n' \
                       'Video has been deleted, please set up a new video to take another recording.'

        if self.save_msg:
            self.display_recorded_stats()

        self.vid_out = []
        self.frame_times = []
        self.current_file_label['text'] = ""
        self.received_pulse_label['text'] = ""
        self.set_calibration_buttons_group(state='disabled')

    def close_window(self):

        if not self.setup:
            self.done = True
            self.window.destroy()
        else:
            self.done = True
            self.window.destroy()

    def selectCams(self):

        if self.window is not None:
            self.window.quit()
            self.window.destroy()

        self.setup = False
        self.done = False
        self.vid_out = []
        self.cam = []
        self.cam_name = []
        self.lv_task = None

        if not self.running_config['debug_mode']:
            # set up window
            select_cams_window = Tk()
            select_cams_window.title("Select Cameras")

            # number of cameras
            Label(select_cams_window, text="How many cameras?").grid(sticky="w", row=0, column=0)
            self.number_of_cams = StringVar(value="1")
            self.number_of_cams_entry = Entry(select_cams_window, textvariable=self.number_of_cams).\
                grid(sticky="nsew", row=0, column=1)
            Button(select_cams_window, text="Set Cameras", command=select_cams_window.quit).\
                grid(sticky="nsew", row=1, column=0, columnspan=2)
            select_cams_window.mainloop()
            select_cams_window.destroy()
        else:
            self.number_of_cams_entry = "2"
            self.number_of_cams = 2

        for i in range(self.number_of_cams):
            self.cam.append(None)
            self.cam_name.append([])
            
        self.createGUI()

    def createGUI(self):

        self.window = Tk()
        self.window.title("Camera Control")
        self.window.minsize(width=800, height=500)

        cur_row = 0
        numberOfScreenUnits = 100
        self.camera = []
        self.camera_entry = []
        self.current_exposure = []
        self.exposure = []
        self.exposure_entry = []
        self.gain = []
        self.gain_entry = []
        self.format_list = ['Y16 (256x4)', 'Y16 (320x240)', 'Y16 (320x480)', 'Y16 (352x240)', 'Y16 (352x288)',
                            'Y16 (384x288)', 'Y16 (640x240)', 'Y16 (640x288)', 'Y16 (640x480)', 'Y16 (704x576)',
                            'Y16 (720x240)', 'Y16 (720x288)', 'Y16 (720x480)', 'Y16 (720x540)', 'Y16 (720x576)',
                            'Y16 (768x576)', 'Y16 (1024x768)', 'Y16 (1280x960)', 'Y16 (1280x1024)', 'Y16 (1440x1080)',
                            'Y800 (256x4)', 'Y800 (320x240)', 'Y800 (320x480)', 'Y800 (352x240)', 'Y800 (352x288)',
                            'Y800 (384x288)', 'Y800 (640x240)', 'Y800 (640x288)', 'Y800 (640x480)', 'Y800 (704x576)',
                            'Y800 (720x240)', 'Y800 (720x288)', 'Y800 (720x480)', 'Y800 (720x540)', 'Y800 (720x576)',
                            'Y800 (768x576)', 'Y800 (1024x768)', 'Y800 (1280x960)', 'Y800 (1280x1024)',
                            'Y800 (1440x1080)', 'RGB24 (256x4)', 'RGB24 (320x240)', 'RGB24 (320x480)',
                            'RGB24 (352x240)', 'RGB24 (352x288)', 'RGB24 (384x288)', 'RGB24 (640x240)',
                            'RGB24 (640x288)', 'RGB24 (640x480)', 'RGB24 (704x576)', 'RGB24 (720x240)',
                            'RGB24 (720x288)', 'RGB24 (720x480)', 'RGB24 (720x540)', 'RGB24 (720x576)',
                            'RGB24 (768x576)', 'RGB24 (1024x768)', 'RGB24 (1280x960)', 'RGB24 (1280x1024)',
                            'RGB24 (1440x1080)']
        self.fourcc_codes = ["DIVX", "XVID", "Y800"]
        self.formats = []
        self.format_entry = []
        
        self.framerate = []
        self.framerate_list = []
        self.current_framerate = []
        
        self.x_offset_value = []
        self.x_offset_scale = []
        self.x_offset_spinbox = []
        
        self.y_offset_value = []
        self.y_offset_scale = []
        self.y_offset_spinbox = []
        
        self.auto_center = []
        self.frame_acquired_count_label = []
        self.board_detected_count_label = []
        
        self.polarity = []
        
        self.trigger_status_indicator = []
        self.trigger_status_label = []
        
        self.fov_dict = []
        self.fov_labels = ['top', 'left', 'height', 'width']

        if not isinstance(self.number_of_cams, int):
            self.number_of_cams = int(self.number_of_cams.get())

        for i in range(self.number_of_cams):
            # drop down menu to select camera
            # Add title label to the frame
            title_label = Label(self.window, text="Camera " + str(i + 1) + " Settings: ", font=("Arial", 12, "bold"))
            title_label.grid(row=cur_row, column=0, padx=1, pady=1, sticky="w")
            cur_row += 1

            init_camera_frame = Frame(self.window, borderwidth=1, relief="raised")
            
            Label(init_camera_frame, text="Camera name: ", width=10, justify="left", anchor="w").\
                grid(sticky="w", row=0, column=0, padx=5, pady=3)
            self.camera.append(StringVar())
            self.camera_entry.append(ttk.Combobox(init_camera_frame, textvariable=self.camera[i], width=10, justify="left"))
            self.camera_entry[i]['values'] = self.cam_names
            self.camera_entry[i].current(i)
            self.camera_entry[i].grid(row=0, column=1, padx=5, pady=3)

            # initialize camera button
            Button(init_camera_frame, text=f"Initialize Camera {i+1}", command=lambda index_cam=i: self.init_cam(index_cam), width=14).\
                grid(sticky="nsew", row=0, column=2, padx=5, pady=3)

            # format
            Label(init_camera_frame, text="Format: ", width=10, justify="left", anchor="w").\
                grid(sticky="w", row=1, column=0, padx=5, pady=3)
            self.formats.append(StringVar())
            self.format_entry.append(ttk.Combobox(init_camera_frame, textvariable=self.formats[i], width=15, justify="left"))
            self.format_entry[i]['values'] = self.format_list
            self.format_entry[i].current(i)
            self.format_entry[i].grid(row=1, column=1, padx=5, pady=3)

            # Set camera format
            Button(init_camera_frame, text="Set Format", command=lambda index_cam=i: self.set_formats(index_cam), width=14).\
                grid(sticky="nsew", row=1, column=2, padx=5, pady=3)
            
            init_camera_frame.grid(row=cur_row, column=0, padx=2, pady=3, sticky="w")

            # change exposure
            capture_settings_frame = Frame(self.window, borderwidth=1, relief="raised")
            Label(capture_settings_frame, text='Exposure (s):', width=8, justify="left", anchor="w").\
                grid(row=0, column=0, sticky="nsew", padx=5, pady=3)
            
            self.exposure.append(StringVar())
            self.exposure_entry.append(Entry(capture_settings_frame, textvariable=self.exposure[i], width=7, justify="left"))
            self.exposure_entry[i].grid(sticky="nsew", row=0, column=1, columnspan=2, padx=5, pady=3)

            Button(capture_settings_frame, text=f"Set Exposure {i+1}", command=lambda index_cam=i: self.set_exposure(index_cam), width=14).\
                grid(sticky="nsew", row=0, column=3, padx=5, pady=3)
            
            # change gain
            Label(capture_settings_frame, text='Gain:', width=8, justify="left", anchor="w").\
                grid(sticky="nsew", row=1, column=0, padx=5, pady=3)
                
            self.gain.append(StringVar())
            self.gain_entry.append(Entry(capture_settings_frame, textvariable=self.gain[i], width=7, justify="left"))
            self.gain_entry[i].\
                grid(sticky="nsew", row=1, column=1, columnspan=2, padx=5, pady=3)
            
            Button(capture_settings_frame, text=f"Set Gain {i+1}", command=lambda index_cam=i: self.set_gain(index_cam), width=14).\
                grid(sticky="nsew", row=1, column=3, pady=3, padx=5)
            
            capture_settings_frame.\
                grid(row=cur_row, column=1, padx=2, pady=3, sticky="nsew")
            
            capture_settings_frame.pack_propagate(False)
            
            # set FOV format
            fov_current_dict = {'top': IntVar(),
                                'left': IntVar(),
                                'height': IntVar(),
                                'width': IntVar()}
            self.fov_dict.append(fov_current_dict)
            
            fov_settings_frame = Frame(self.window, borderwidth=1, relief="raised")
            Label(fov_settings_frame, text='Top').grid(row=0, column=0, padx=5, pady=3)
            Entry(fov_settings_frame, textvariable=self.fov_dict[i]['top'], width=5).\
                grid(sticky="nsew", row=0, column=1, padx=5, pady=3)

            Label(fov_settings_frame, text='Left').grid(row=0, column=2, padx=5, pady=3)
            Entry(fov_settings_frame, textvariable=self.fov_dict[i]['left'], width=5).\
                grid(sticky="nsew", row=0, column=3, padx=5, pady=3)

            Label(fov_settings_frame, text='Height').grid(row=1, column=0, padx=5, pady=3)
            Entry(fov_settings_frame, textvariable=self.fov_dict[i]['height'], width=5).\
                grid(sticky="nsew", row=1, column=1, padx=5, pady=3)

            Label(fov_settings_frame, text='Width').grid(row=1, column=2, padx=5, pady=3)
            Entry(fov_settings_frame, textvariable=self.fov_dict[i]['width'], width=5).\
                grid(sticky="nsew", row=1, column=3, padx=5, pady=3)
            
            reset_fov_button = Button(fov_settings_frame, text="Reset FOV", command=lambda index_cam=i: self.get_fov(index_cam), width=14)
            reset_fov_button.grid(sticky="nsew", row=0, column=5, padx=5, pady=3)
            
            set_fov_button = Button(fov_settings_frame, text="Set FOV", command=lambda index_cam=i: self.set_fov(index_cam), width=14)
            set_fov_button.grid(sticky="nsew", row=1, column=5, padx=5, pady=3)

            fov_settings_frame.grid(row=cur_row, column=2, padx=2, pady=3, sticky="nsew")
            fov_settings_frame.pack_propagate(False)
            cur_row += 1
        
            camera_status_frame = Frame(self.window)
            # label for frame acquired count
            Label(camera_status_frame, text="Frame acquired #: ").\
                grid(row=0, column=0, sticky="w", padx=5, pady=3)
            self.frame_acquired_count_label.append(Label(camera_status_frame, text="0", width=5))
            self.frame_acquired_count_label[i].\
                grid(row=0, column=1, sticky="nw", padx=5, pady=3)

            # label for frame acquired count
            Label(camera_status_frame, text="Detected board #: ").\
                grid(row=0, column=2, sticky="w", padx=5, pady=3)
            self.board_detected_count_label.append(Label(camera_status_frame, text="0", width=5))
            self.board_detected_count_label[i].\
                grid(row=0, column=3, sticky="nw", padx=5, pady=3)
            
            # label for trigger status
            self.trigger_status_indicator.append(Label(camera_status_frame, text="Trigger status: ", bg="gray"))
            self.trigger_status_indicator[i].\
                grid(row=1, column=0, sticky="w", padx=5, pady=3)
            self.trigger_status_label.append(Label(camera_status_frame, text="Disabled", width=30, anchor="w"))
            self.trigger_status_label[i].\
                grid(row=1, column=1, columnspan=3, sticky="w", padx=5, pady=3)
            
            camera_status_frame.\
                grid(row=cur_row, column=0, padx=2, pady=3, sticky="w")
            camera_status_frame.pack_propagate(False)
            
            # framerate list frame
            framerate_frame = Frame(self.window, borderwidth=1, relief="raised")
            Label(framerate_frame, text="Frame Rate (fps): ").\
                grid(row=0, column=0, sticky="w", padx=5, pady=3)
            self.framerate.append(IntVar())
            self.framerate_list.append(ttk.Combobox(framerate_frame, textvariable=self.framerate[i], width=5, justify="left"))
            self.framerate_list[i]['value'] = [100, 200]
            self.framerate_list[i].current(0)
            self.framerate_list[i].grid(row=0, column=1, sticky="w", padx=5, pady=3)
            
            Button(framerate_frame, text="Update Frame Rate", command=lambda index_cam=i: self.set_frame_rate(index_cam), width=14).\
                grid(row=0, column=3, sticky="nsew", padx=3, pady=3)
           
            Label(framerate_frame, text="Current Frame Rate: ").\
                    grid(row=1, column=0, sticky="w", padx=5, pady=3)
            self.current_framerate.append(IntVar())
            Label(framerate_frame, textvariable=self.current_framerate[i], width=5).\
                    grid(row=1, column=1, sticky="w", padx=5, pady=3)
            
            framerate_frame.\
                grid(row=cur_row, column=1, padx=2, pady=3, sticky="new")
            framerate_frame.pack_propagate(False)
            
            # partial offset scan box
            partial_scan_frame = Frame(self.window, borderwidth=1, relief="raised")
            Label(partial_scan_frame, text="X Offset (px): ").\
                grid(row=0, column=0, sticky="w", padx=5, pady=3)
            
            try:
                current_x_offset = self.cam_details[i]['offset']['x']
                self.x_offset_value.append(DoubleVar(current_x_offset))
            except:
                self.x_offset_value.append(DoubleVar())
            self.x_offset_scale.append(Scale(partial_scan_frame, from_=0.0, to=200.0, orient=HORIZONTAL, resolution=1, variable=self.x_offset_value[i], command=lambda index_cam=i, idx=i: self.set_x_offset(index_cam, idx), width=6, length=150))
            self.x_offset_scale[i].grid(row=0, column=1, columnspan=2, sticky="new", padx=5, pady=3)
            
            self.x_offset_spinbox.append(Spinbox(partial_scan_frame, from_=0.0, to=100.0, increment=1, textvariable=self.x_offset_value[i], command=lambda index_cam=i, idx=i: self.set_x_offset(index_cam, idx), width=5))
            self.x_offset_spinbox[i].grid(row=0, column=4, columnspan=1, sticky="w", padx=5, pady=3)
            
            Label(partial_scan_frame, text="Y Offset (px): ").\
                grid(row=1, column=0, sticky="w", padx=5, pady=3)
            
            try:
                current_y_offset = self.cam_details[i]['offset']['y']
                self.y_offset_value.append(DoubleVar(current_y_offset))
            except:
                self.y_offset_value.append(DoubleVar())
            self.y_offset_value.append(DoubleVar())
            self.y_offset_scale.append(Scale(partial_scan_frame, from_=0.0, to=200.0, resolution=1, orient=HORIZONTAL, variable=self.y_offset_value[i], command=lambda index_cam=i, idx=i: self.set_y_offset(index_cam, idx), width=6, length=150))
            self.y_offset_scale[i].grid(row=1, column=1, columnspan=2, sticky="nw", padx=5, pady=3)
            
            self.y_offset_spinbox.append(Spinbox(partial_scan_frame, from_=0.0, to=100.0, increment=1, textvariable=self.y_offset_value[i], command=lambda index_cam=i, idx=i: self.set_y_offset(index_cam, idx), width=5))
            self.y_offset_spinbox[i].grid(row=1, column=4, columnspan=1, sticky="w", padx=5, pady=3)
            
            self.auto_center.append(IntVar())
            Checkbutton(partial_scan_frame, text="Auto-center", variable=self.auto_center[i], command=lambda index_cam=i: self.toggle_auto_center(index_cam)).\
                grid(row=0, column=5, sticky="w", padx=5, pady=3)
            
            self.polarity.append(IntVar())
            Checkbutton(partial_scan_frame, text="Polarity", variable=self.polarity[i], command=lambda index_cam=i: self.toggle_polarity(index_cam), onvalue=1, offvalue=0).\
                grid(row=1, column=5, sticky="w", padx=5, pady=3)
            
            partial_scan_frame.\
                grid(row=cur_row, column=2, padx=2, pady=3, sticky="nsew")
            partial_scan_frame.pack_propagate(False)
            cur_row += 1

            # empty row
            Label(self.window, text="").grid(row=cur_row + 2, column=0)

            # end of camera loop
            cur_row = cur_row + 3

        video_setting_label = Label(self.window, text="Video Settings: ", font=("Arial", 12, "bold"))
        video_setting_label.grid(row=cur_row, column=0, padx=1, pady=1, sticky="w")
        cur_row += 1
        
        # subject name
        video_info_frame = Frame(self.window, borderwidth=1, relief="raised")
        Label(video_info_frame, text="Subject: ").\
            grid(sticky="nw", row=0, column=0, padx=5, pady=3)
        self.subject = StringVar(value='Mouse')
        self.subject_entry = ttk.Combobox(video_info_frame, textvariable=self.subject, width=15)
        self.subject_entry['values'] = tuple(self.mouse_list)
        self.subject_entry.\
            grid(sticky="nw", row=0, column=1, padx=5, pady=3)

        # attempt
        Label(video_info_frame, text="Attempt: ").grid(sticky="nsew", row=0, column=2, padx=5, pady=3)
        self.attempt = StringVar(value="1")
        self.attempt_entry = ttk.Combobox(video_info_frame, textvariable=self.attempt, width=5)
        self.attempt_entry['values'] = tuple(range(1, 10))
        self.attempt_entry.\
            grid(sticky="nw", row=0, column=3, padx=5, pady=3)

        # type frame rate
        Label(video_info_frame, text="Frame Rate: ").\
            grid(sticky="nw", row=1, column=0, padx=5, pady=3)
        self.fps = StringVar()
        self.fps_entry = Entry(video_info_frame, textvariable=self.fps, width=5)
        self.fps_entry.insert(END, '100')
        self.fps_entry.\
            grid(sticky="nw", row=1, column=1, padx=5, pady=3)

        # select video encoder codec
        Label(video_info_frame, text="Video codec:").\
            grid(sticky="nw", row=1, column=2, padx=5, pady=3)
        self.video_codec = StringVar()
        self.video_codec_entry = ttk.Combobox(video_info_frame,
                                              value=self.fourcc_codes,
                                              state="readonly", width=5)
        self.video_codec_entry.set("XVID")  # default codec
        self.video_codec_entry.bind("<<ComboboxSelected>>", self.browse_codec)
        self.video_codec_entry.\
            grid(sticky="nw", row=1, column=3, padx=5, pady=3)
        self.video_codec = self.video_codec_entry.get()  # add default video codec
        Hovertip(self.video_codec_entry, "Select video codec for video recording")

        # output directory
        Label(video_info_frame, text="Output Directory: ", width=15, justify="left", anchor="w").\
            grid(sticky="nw", row=3, column=0, padx=5, pady=3)
        self.dir_output = StringVar()
        self.output_entry = ttk.Combobox(video_info_frame, textvariable=self.dir_output, width=15)
        self.output_entry['values'] = self.output_dir
        self.output_entry.\
            grid(sticky="nw", row=3, column=1, columnspan=2, padx=5, pady=3)
        self.browse_dir_button = Button(video_info_frame, text="Browse", command=self.browse_output)
        self.browse_dir_button.\
            grid(sticky="nw", row=3, column=3, padx=5, pady=3)
        Hovertip(self.browse_dir_button, "Select output directory for video recording")
        video_info_frame.grid(row=cur_row, column=0, padx=2, pady=3, sticky="nsew")

        # set up video
        setup_video_label = Label(self.window, text="Setup Videos: ", font=("Arial", 12, "bold"))
        setup_video_label.grid(row=cur_row-1, column=1, padx=1, pady=1, sticky="nw")
        
        setup_video_frame = Frame(self.window, borderwidth=1, relief="raised")
        Button(setup_video_frame, text="Setup Recording", command=self.set_up_vid, width=14).\
            grid(sticky="nsew", row=0, column=0, columnspan=1, rowspan=1, padx=5, pady=3)
        Button(setup_video_frame, text="Setup Trigger", command=self.sync_setup, width=14).\
            grid(sticky="nsew", row=1, column=0, columnspan=1, padx=5, pady=3)
        Button(setup_video_frame, text="Snap A Frame", command=self.snap_image, width=14).\
            grid(sticky="nsew", row=2, column=0, columnspan=1, padx=5, pady=3)
        # trigger
        self.trigger_on = IntVar(value=0)
        self.trigger_button_on = Radiobutton(setup_video_frame, text=" Trigger On", selectcolor='green', indicatoron=0,
                                             variable=self.trigger_on, value=1)
        self.trigger_button_on.\
            grid(sticky="nsew", row=0, column=1, padx=5, pady=3)
        self.trigger_button_off = Radiobutton(setup_video_frame, text="Trigger Off", selectcolor='red', indicatoron=0,
                                              variable=self.trigger_on, value=0)
        self.trigger_button_off.\
            grid(sticky="nsew", row=1, column=1, padx=5, pady=3)
        
        self.release_trigger_button = Button(setup_video_frame, text="Release Trigger", command=self.release_trigger)
        self.release_trigger_button.\
            grid(sticky="nsew", row=2, column=1, columnspan=1, padx=5, pady=3)
        Hovertip(self.release_trigger_button, "Release trigger to if stuck in trigger mode")
        
        setup_video_frame.grid(row=cur_row, column=1, padx=2, pady=3, sticky="nsew")

        # record videos
        record_video_label = Label(self.window, text="Record Videos: ", font=("Arial", 12, "bold"))
        record_video_label.grid(row=cur_row-1, column=2, padx=1, pady=1, sticky="nw")
        
        # recording buttons
        record_video_frame = Frame(self.window, borderwidth=1, relief="raised")
        self.toggle_video_recording_status = IntVar(value=0)
        self.toggle_video_recording_button = Button(record_video_frame, text="Capture Disabled",
                                                    background="red", state="disabled", width=14, command=self.toggle_video_recording)
        self.toggle_video_recording_button.grid(sticky="nsew", row=0, column=0, padx=5, pady=3)
        Hovertip(self.toggle_video_recording_button, "Start/Stop recording video")
        
        # set recording properties
        self.force_frame_sync = IntVar(value=1)
        self.force_frame_sync_button = Checkbutton(record_video_frame, text="Force Frame Sync", variable=self.force_frame_sync,
                                                   onvalue=1, offvalue=0, width=13)
        self.force_frame_sync_button.grid(sticky="nsew", row=1, column=0, padx=5, pady=3)
        Hovertip(self.force_frame_sync_button, "Force frame sync for camera captured on threads")

        self.toggle_continuous_mode = IntVar(value=0)
        self.toggle_continuous_mode_button = Checkbutton(record_video_frame, text="Continuous Mode", variable=self.toggle_continuous_mode,
                                                         onvalue=1, offvalue=0, width=13)
        self.toggle_continuous_mode_button.grid(sticky="nsew", row=2, column=0, padx=5, pady=3)
        Hovertip(self.toggle_continuous_mode_button, "Toggle continuous mode during video recording")
        
        # save videos
        self.release_vid0 = Button(record_video_frame, text="Save Video",
                                   command=lambda: self.save_vid(compress=False), width=14).\
            grid(sticky="nsew", row=0, column=2, padx=5, pady=3)

        self.release_vid2 = Button(record_video_frame, text="Delete Video",
                                   command=lambda: self.save_vid(delete=True), width=14)
        self.release_vid2.grid(sticky="nsew", row=1, column=2, padx=5, pady=3)
        Hovertip(self.release_vid2, "Delete video if not needed")
    
        self.display_stats_button = Button(record_video_frame, text="Display stats", command=self.display_recorded_stats, width=10)
        self.display_stats_button.grid(sticky="nsew", row=2, column=2, columnspan=1, padx=5, pady=3)
        Hovertip(self.display_stats_button, "Display stats of recorded videos")

        record_video_frame.grid(row=cur_row, column=2, padx=2, pady=3, sticky="nsew")
        cur_row += 2
        
        ## calibrate video section
        calibration_label = Label(self.window, text="Calibration: ", font=("Arial", 12, "bold"))
        calibration_label.grid(row=cur_row, column=0, padx=1, pady=1, sticky="nw")
        cur_row += 1
        calibration_frame = Frame(self.window, borderwidth=1, relief="raised")
        
        #  calibration duration
        calibration_duration_frame = Frame(calibration_frame)
        Label(calibration_duration_frame, text="Capture Duration(s): ").\
            grid(sticky="nsew", row=0, column=0, columnspan=1, padx=0, pady=0)
        self.calibration_duration_entry = Entry(calibration_duration_frame, width=5)
        self.calibration_duration_entry.insert(0, "30")
        self.calibration_duration_entry.grid(sticky="nsew", row=0, column=1, columnspan=1, padx=0, pady=0)
        calibration_duration_frame.grid(row=0, column=0, padx=5, pady=3, sticky="nsew")
        
        self.setup_calibration_button = Button(calibration_frame, text="Setup Calibration", command=self.setup_calibration)
        self.setup_calibration_button.\
            grid(sticky="nsew", row=1, column=0, columnspan=1, padx=5, pady=3)
        Hovertip(self.setup_calibration_button, "Press this button to setup calibration. ")

        self.toggle_calibration_capture_button = Button(calibration_frame, text="Capture Off", command=self.toggle_calibration_capture,
                                                            background="red", state="disabled", width=14)
        self.toggle_calibration_capture_button.\
            grid(sticky="nsew", row=0, column=1, columnspan=1, padx=5, pady=3)
        Hovertip(self.toggle_calibration_capture_button, "Press this button to start capturing frames for calibration. ")
        
        self.snap_calibration_button = Button(calibration_frame, text="Snap Frame", command=self.snap_calibration_frame, state="disabled")
        self.snap_calibration_button.\
            grid(sticky="nsew", row=1, column=1, columnspan=1, padx=5, pady=3)
        Hovertip(self.snap_calibration_button, "Press this button to snap a frame for calibration. ")
        
        self.update_calibration_button = Button(calibration_frame, text="Update Calibration", command=self.update_calibration, state="disabled")
        self.update_calibration_button.\
            grid(sticky="nsew", row=1, column=2, columnspan=1, padx=5, pady=3)
        Hovertip(self.update_calibration_button, "Press this button calibrate using the frames in the buffer. ")
        
        self.recalibrate_button = Button(calibration_frame, text="Full Calibration", command=self.recalibrate, state="disabled")
        self.recalibrate_button.\
            grid(sticky="nsew", row=0, column=2, columnspan=1, padx=5, pady=3)
        Hovertip(self.recalibrate_button, "Press this button to calibrate using all the frames. ")
        
        self.init_matrix_check = IntVar(value=0)
        self.init_matrix_checkbutton = Checkbutton(calibration_frame, text="Re-Init Matrix", variable=self.init_matrix_check,
                                                onvalue=1, offvalue=0, width=11)
        self.init_matrix_checkbutton.grid(sticky="nw", row=0, column=3, padx=5, pady=3)
        Hovertip(self.init_matrix_checkbutton, "Check this button to force re-initialize the calibration matrix. ")
        
        added_board_frame = Frame(calibration_frame)
        Label(added_board_frame, text="Added Board #: ").\
            grid(sticky="nsew", row=0, column=0, columnspan=1, padx=0, pady=0)
        self.added_board_value = StringVar(value="0")
        self.added_board_label = Label(added_board_frame, width=5, textvariable=self.added_board_value)
        self.added_board_label.grid(sticky="nsew", row=0, column=1, columnspan=1, padx=0, pady=0)
        added_board_frame.grid(row=1, column=3, padx=5, pady=3, sticky="nsew")
        
        self.plot_calibration_error_button = Button(calibration_frame, text="Plot Calibration Error", command=self.plot_calibration_error)
        self.plot_calibration_error_button.\
            grid(sticky="nsew", row=0, column=4, columnspan=1, padx=5, pady=3)
        Hovertip(self.plot_calibration_error_button, "Press this button to plot the calibration error. ")
        
        self.test_calibration_live_button = Button(calibration_frame, text="Test Calibration Live", command=self.test_calibration_live, state="disabled")
        self.test_calibration_live_button.\
            grid(sticky="nsew", row=1, column=4, columnspan=1, padx=5, pady=3)
        
        calibration_frame.grid(row=cur_row, column=0, columnspan=3, padx=2, pady=3, sticky="nw")
        
        # calibration result
        calibration_result_label = Label(self.window, text="Calibration Stats: ", font=("Arial", 12, "bold"))
        calibration_result_label.grid(row=cur_row-1, column=2, padx=1, pady=1, sticky="nw")
        
        calibration_result_frame = Frame(self.window)
        
        # label for calibration process status text
        Label(calibration_result_frame, text="Calibration status: ")\
            .grid(sticky="wn", row=0, column=0, columnspan=1, padx=0, pady=0)
        self.calibration_process_stats = StringVar()
        self.calibration_process_label = Label(calibration_result_frame, textvariable=self.calibration_process_stats)
        self.calibration_process_label.grid(sticky="nsew", row=0, column=1, columnspan=1, padx=0, pady=0)

        Label(calibration_result_frame, text="Calibration Error: ").\
            grid(sticky="wn", row=1, column=0, columnspan=1, padx=0, pady=0)
        self.calibration_error_value = StringVar()
        self.calibration_error_label = Label(calibration_result_frame, textvariable=self.calibration_error_value)
        self.calibration_error_label.grid(sticky="wn", row=1, column=1, columnspan=1, padx=0, pady=0)
        
        Label(calibration_result_frame, text="Current Duration (s): ").\
            grid(sticky="wn", row=2, column=0, columnspan=1, padx=0, pady=0)
        self.calibration_current_duration_value = StringVar()
        self.calibration_current_duration_label = Label(calibration_result_frame, textvariable=self.calibration_current_duration_value)
        self.calibration_current_duration_label.grid(sticky="wn", row=2, column=1, columnspan=1, padx=0, pady=0)
        
        calibration_result_frame.grid(row=cur_row, column=2, padx=2, pady=3, sticky="nw")
        cur_row += 1

        # File status
        Label(self.window, text="Current file status: ").grid(row=cur_row, column=0, sticky="w")
        self.current_file_label = Label(self.window, text="")
        self.current_file_label.grid(row=cur_row, column=1, sticky="w")
        cur_row += 1

        # label for trigger receive text
        Label(self.window, text="Trigger status: ").grid(row=cur_row, column=0, sticky="w")
        self.received_pulse_label = Label(self.window, text="", wraplength=numberOfScreenUnits)
        self.received_pulse_label.grid(row=cur_row, column=1, sticky="w")
        cur_row += 1


        cur_row += 1

        # label for calibration process status text
        Label(self.window, text="Calibration error: ").grid(row=cur_row, column=0, sticky="w")
        self.calibration_error_stats = Label(self.window, text='', wraplength=numberOfScreenUnits)
        self.calibration_error_stats.grid(row=cur_row, column=1, sticky="w")
        cur_row += 1

        # empty row
        Label(self.window, text="").grid(row=cur_row, column=0)
        cur_row += 1

        
        cur_row += 3

        # close window/reset GUI
        Label(self.window).grid(row=cur_row, column=0)
        self.reset_button = Button(self.window, text="Reset GUI", command=self.selectCams).grid(sticky="nsew",
                                                                                                row=cur_row + 1,
                                                                                                column=0, columnspan=2)
        self.close_button = Button(self.window, text="Close", command=self.close_window).grid(sticky="nsew",
                                                                                              row=cur_row + 2, column=0,
                                                                                              columnspan=2)

    def runGUI(self):
        self.window.mainloop()


if __name__ == "__main__":
    # Create an argument parser
    parser = argparse.ArgumentParser(description="CamGUI")

    # Add optional arguments
    parser.add_argument("-d", "--debug", action="store_true", dest='debug_mode', help="Enable debug mode")
    parser.add_argument("-ni", "--no-init-cam", action="store_false", dest="init_cam_bool",
                        help="Disable camera initialization")

    # Parse the command-line arguments
    args = parser.parse_args()

    # Create an instance of the CamGUI class with the parsed arguments
    try:
        cam_gui = CamGUI(debug_mode=args.debug_mode, init_cam_bool=args.init_cam_bool)
    except Exception as e:
        print("Error creating CamGUI instance: %s" % str(e))
        exit(1)
    try:
        cam_gui.runGUI()
    except Exception as e:
        print("Error running CamGUI: %s" % str(e))
        exit(1)
