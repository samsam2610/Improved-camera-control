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
from tkinter import Entry, Label, Button, StringVar, IntVar, BooleanVar, \
    Tk, END, Radiobutton, filedialog, ttk, Frame, Scale, HORIZONTAL, Spinbox, Checkbutton, DoubleVar, messagebox
from idlelib.tooltip import Hovertip

from matplotlib import pyplot as plt
import matplotlib.ticker as ticker

import matplotlib.animation as animation
from matplotlib import style
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import cv2
import ffmpy
import numpy as np
from _video_files_func import create_video_files, create_output_files, save_vid, display_recorded_stats, check_frame
from _calibration_func import detect_raw_board_on_thread, draw_detection_on_thread, draw_reprojection_on_thread, detect_markers_on_thread
from _camera_settings_func import get_frame_rate_list, set_gain, set_exposure, get_frame_dimensions, get_formats, set_formats, \
    get_fov, set_fov, set_frame_rate, get_current_frame_rate, \
    set_partial_scan_limit, toggle_auto_center, toggle_polarity, toggle_flip_vertical, \
    set_x_offset, set_y_offset, \
    check_frame_coord, track_frame_coord, reset_track_frame_coord, \
    show_video_error, show_camera_error

from os_handler import *

# noinspection PyNoneFunctionAssignment,PyAttributeOutsideInit
class CamGUI(object):

    def __init__(self, debug_mode=False, init_cam_bool=True):
        # GUI placeholders
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
        self.camera = []
        self.camera_entry = []
        self.camera_init_button = []
        self.current_exposure = []
        self.exposure = []
        self.exposure_entry = []
        self.exposure_current_label = []
        
        self.gain = []
        self.gain_entry = []
        self.gain_current_label = []
        
        self.format_width = []
        self.format_height = []
        self.format_entry = []

        self.framerate = []
        self.framerate_list = []
        self.current_framerate = []

        self.x_tracking_value = []
        self.y_tracking_value = []
        self.tracking_points = []
        self.tracking_points_status = []
        
        self.x_offset_value = []
        self.x_offset_scale = []
        self.x_offset_spinbox = []

        self.y_offset_value = []
        self.y_offset_scale = []
        self.y_offset_spinbox = []

        self.auto_center = []
        self.flip_vertical = []
        self.frame_acquired_count_label = []
        self.board_detected_count_label = []

        self.polarity = []

        self.trigger_status_indicator = []
        self.trigger_status_label = []
        
        self.video_file_status = []
        self.video_file_indicator = []

        self.current_frame_count_label = []
        self.current_frame_buffer_length_label = []
        
        self.fov_dict = []
        self.fov_labels = ['top', 'left', 'height', 'width']

        self.test_calibration_live_toggle_status = []
        self.calibration_toggle_status = False
        self.calibrating_thread = None
        # Initialize GUI
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
        from src.camera_control.ic_camera import ICCam

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
        
        set_frame_rate(self, num, framerate=388, initCamera=True)
        get_formats(self, num)
        
        # set gain and exposure using the values from the json
        self.cam[num].set_exposure(float(format(self.cam_details[str(num)]['exposure'], '.6f')))
        self.cam[num].set_gain(int(self.cam_details[str(num)]['gain']))
        self.cam[num].start()
        
        # get the gain and exposure values to reflect that onto the GUI
        self.exposure[num].set(self.cam[num].get_exposure())
        self.exposure_current_label[num]['text'] = f"Current: {self.exposure[num].get()} (-{str(round(math.log2(1/float((self.exposure[num].get())))))}) s"
        
        self.gain[num].set(self.cam[num].get_gain())
        self.gain_current_label[num]['text'] = f"Current: {self.gain[num].get()} db"
        
        get_fov(self, num)
        set_partial_scan_limit(self, num)
        get_frame_rate_list(self, num)
        
        get_current_frame_rate(self, num)
        self.trigger_status_label[num]['text'] = 'Disabled'
        
        [x_offset_value, y_offset_value] = self.cam[num].get_partial_scan()
        self.x_offset_value[num].set(x_offset_value)
        self.y_offset_value[num].set(y_offset_value)
        
        polarity = self.cam[num].get_trigger_polarity()
        self.polarity[num].set(polarity)
        
        flip_vertical = self.cam[num].get_flip_vertical()
        self.flip_vertical[num].set(bool(flip_vertical))
       
        # reset output directory
        self.dir_output.set(self.output_entry['values'][cam_num])
        setup_window.destroy()

    def release_trigger(self):
        for num in range(len(self.cam)):
            self.cam[num].disable_trigger()
    
    # region Normal recording
    def snap_image(self):
        for num in range(len(self.cam)):
            self.cam[num].get_image()

    def set_up_vid_trigger(self):

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
            show_camera_error(self)
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
                                  self.setup_name.get() + '_' +
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
            
        create_video_files(self)
        create_output_files(self, subject_name=subject_name)
        
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
            show_camera_error(self)
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
                                  + self.setup_name.get() + '_'
                                  + date + '_'
                                  + str(int(da_fps)) + 'f'
                                  + temp_exposure + 'e'
                                  + temp_gain + 'g')
            self.vid_file.append(os.path.normpath(self.dir_output.get() + '/' +
                                                  self.base_name[i] +
                                                  self.attempt.get() +
                                                  '.avi'))

        create_video_files(self)
        subject_name = self.subject.get() + '_' + date + '_' + self.attempt.get()
        create_output_files(self, subject_name=subject_name)
        self.setup = True
   
    def set_up_vid_trigger_synapse(self):
        
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
            show_camera_error(self)
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

        subject_name, dir_name = generate_folder()
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
            self.vid_file.append(os.path.normpath(dir_name +
                                                  '/' +
                                                  self.base_name[num] +
                                                  '.avi'))
            self.trigger_status_label[num]['text'] = 'Trigger Ready'
            self.trigger_status_indicator[num]['bg'] = 'red'

        create_video_files(self)
        create_output_files(self, subject_name=subject_name)
        
        self.setup = True

    def toggle_video_recording(self, force_termination=False):
        toggle_status = bool(self.toggle_video_recording_status.get())
        
        if toggle_status or force_termination:
            self.recording_status.set('Stopping recording...')
            self.toggle_video_recording_status = IntVar(value=0)
            self.toggle_video_recording_button.config(text="Capture Off", background="red")
            if self.toggle_continuous_mode.get() == 1:
                for i in range(len(self.cam)):
                    self.cam[i].turn_off_continuous_mode()
            
            self.recording_status.set('Recording stopped.')
            
        else: # start recording videos and change button text
            self.recording_status.set('Starting recording...')
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
            
            self.recording_status.set('Recording stopped.')

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
            
            print(f"Recording stopped for camera {num}")
        except Exception as e:
            print(f"Traceback: \n {traceback.format_exc()}")

    # endregion Normal recording
    
    # region Calibration
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
        # self.recalibrate_button['state'] = state
        # self.update_calibration_button['state'] = state
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

    def load_calibration_settings(self, draw_calibration_board=True):
        from src.gui.utils import load_config, get_calibration_board
        from pathlib import Path
        
        calibration_stats_message = 'Looking for config.toml directory ...'
        self.calibration_process_stats.set(calibration_stats_message)
        print(calibration_stats_message)
        
        path = Path(os.path.realpath(__file__))
        # Navigate to the outer parent directory and join the filename
        config_toml_path = os.path.normpath(str(path.parents[2] / 'config-files' / 'config.toml'))
        config_anipose = load_config(config_toml_path)
        calibration_stats_message = 'Found config.toml directory. Loading config ...'
        print(calibration_stats_message)
        
        calibration_stats_message = 'Successfully found and loaded config. Determining calibration board ...'
        self.calibration_process_stats.set(calibration_stats_message)
        print(calibration_stats_message)
        
        self.board_calibration = get_calibration_board(config=config_anipose)
        calibration_stats_message = 'Successfully determined calibration board. Initializing camera calibration objects ...'
        self.calibration_process_stats.set(calibration_stats_message)
        print(calibration_stats_message)

        self.rows_fname = os.path.join(self.dir_output.get(), 'detections.pickle')
        self.calibration_out = os.path.join(self.dir_output.get(), 'calibration.toml')
        
        board_dir = os.path.join(self.dir_output.get(), 'board.png')
        if draw_calibration_board:
            numx, numy = self.board_calibration.get_size()
            size = numx*200, numy*200
            img = self.board_calibration.draw(size)
            cv2.imwrite(board_dir, img)
            
    def setup_calibration(self, override=False):
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
            self.load_calibration_settings()
            
            self.calibration_process_stats.set('Initializing camera calibration objects ...')
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
            
            if override:
                # Check available detection file, if file available will delete it (for now)
                self.clear_calibration_file(self.rows_fname)
                self.clear_calibration_file(self.calibration_out)
                self.rows_fname_available = False
            else:
                self.rows_fname_available = os.path.exists(self.rows_fname)
                
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
                self.base_name.append(self.cam_name_no_space[i] + '_' + 'calibration_' + self.setup_name.get() + '_')
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
                self.frame_times.append([])

            # check if file exists, ask to overwrite or change attempt number if it does
            create_video_files(self, overwrite=override)
            create_output_files(self, subject_name='Sam')

            self.calibration_process_stats.set('Setting the frame sizes...')
            self.cgroup.set_camera_sizes_images(frame_sizes=frame_sizes)
            self.calibration_process_stats.set('Prepping done. Ready to capture calibration frames...')
            self.calibration_status_label['bg'] = 'yellow'

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
            if self.toggle_continuous_mode.get() == 1:
                for i in range(len(self.cam)):
                    self.cam[i].turn_off_continuous_mode()
                    
            print('Waiting for all the frames are done processing...')
            self.calibration_process_stats.set('Waiting for all the frames are done processing...')
            current_thread = threading.currentThread()
            for t in self.recording_threads:
                if t is not current_thread and t.is_alive():
                    print('Waiting for thread {} to finish...'.format(t.name))
                    t.join()
                
            print('All frames are done processing.')
            
            self.toggle_calibration_capture_button.config(text="Capture Off", background="red")
            self.calibration_status_label['bg'] = 'green'
            self.calibration_process_stats.set('Done capturing calibration frames. Ready to be calibrated...')
            self.calibration_duration_entry['state'] = 'normal'
            self.added_board_value.set(f'{len(self.current_all_rows[0])}')
            self.plot_calibration_error_button['state'] = 'normal'
            self.test_calibration_live_button['state'] = 'normal'
            self.setup_calibration_button['state'] = 'normal'
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
                self.frame_queue = queue.Queue(maxsize=self.queue_frame_threshold)
            else:
                print('Previous threads already cleared or empty.')
            
            # Setting capture toggle status
            self.recording_threads_status = []
            self.calibration_capture_toggle_status = True
           
            if self.toggle_continuous_mode.get() == 1:
                for i in range(len(self.cam)):
                    self.cam[i].turn_on_continuous_mode()
                    
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
            self.calibration_status_label['bg'] = 'red'
            self.calibration_process_stats.set('Started capturing calibration frames...')
            self.calibration_duration_entry['state'] = 'disabled'
            self.plot_calibration_error_button['state'] = 'disabled'
            self.test_calibration_live_button['state'] = 'disabled'
            self.setup_calibration_button['state'] = 'disabled'
            
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
                self.board_detected_count_label[num]['text'] = f'{len(self.all_rows[num])}; {len(row)}'
                self.frame_acquired_count_label[num]['text'] = f'{self.frame_count[num]}'
                self.vid_out[num].write(frame_current)
        
        self.added_board_value.set(f'{len(self.current_all_rows[0])}')
    
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
                    try:
                        barrier.wait(timeout=1)
                    except threading.BrokenBarrierError:
                        print(f'Barrier broken for cam {num}. Proceeding...')
                        break
                        
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
                        self.board_detected_count_label[num]['text'] = f'{len(self.all_rows[num])}; {len(corners)}'
                        if num == 0:
                            self.calibration_current_duration_value.set(f'{time.perf_counter()-start_time:.2f}')
                    else:
                        print(f'No marker detected on cam {num} at frame {self.frame_count[num]}')
                    
                    # putting frame into the frame queue along with following information
                    self.frame_queue.put((frame_current,  # the frame itself
                                          num,  # the id of the capturing camera
                                          self.frame_count[num],  # the current frame count
                                          self.frame_times[num][-1]))  # captured time

                    next_frame = max(next_frame + 1.0/fps, self.frame_times[num][-1] + 0.5/fps)
                    
            barrier.abort()
            if (time.perf_counter() - start_time) > self.calibration_duration or self.calibration_capture_toggle_status:
                print(f"Calibration capture on cam {num}: duration exceeded or toggle status is True")
                self.recording_threads_status[num] = False
                # self.toggle_calibration_capture(termination=True)
                
        except Exception as e:
            print("Exception occurred:", type(e).__name__, "| Exception value:", e,
                  ''.join(traceback.format_tb(e.__traceback__)))

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
        from src.aniposelib.boards import extract_points, merge_rows, reverse_extract_points, reverse_merge_rows
        
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
                    print('Loaded rows from detections.pickle with size: ', len(all_rows))
                
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
        
    def toggle_test_calibration_live(self):
        print('')
        try:
            self.load_calibration_settings()
            calibration_file = self.calibration_out
        except:
            print('Calibration is not setup. Will attempt to load calibration file.')
            calibration_file = os.path.join(self.dir_output.get(), 'calibration.toml')
            
        if not os.path.exists(calibration_file):
            messagebox.showerror('Error', 'Calibration file not found!')
            return
        
        from src.aniposelib.cameras import CameraGroup
        
        # Load the calibration file
        try:
            self.cgroup_test = CameraGroup.load(calibration_file) # cgroup_test is loaded with the calibration file
            print('Calibration file loaded')
        except:
            self.cgroup_test = None
            print('Failed to load calibration file. Using none instead.')
        
        barrier = threading.Barrier(len(self.cam))
        t = []
        # recording_threads_status is a list of False with length of number of cameras
        self.frame_queue = queue.Queue(maxsize=10)
        self.test_calibration_live_threads_status = [True] * len(self.cam)
        self.all_rows_test = [[] for _ in range(len(self.cam))]
        self.frame_count_test = [0] * len(self.cam)
        
        if self.reprojection_check.get():
            self.reproject_window_status = True
            for i in range(len(self.cam)):
                t.append(threading.Thread(target=detect_markers_on_thread, args=(self, i, barrier)))
                t[-1].daemon = True
                t[-1].start()

            t.append(threading.Thread(target=draw_reprojection_on_thread, args=(self, i)))
            t[-1].daemon = True
            t[-1].start()
        else:
            self.detection_window_status = True
            for i in range(len(self.cam)):
                t.append(threading.Thread(target=detect_raw_board_on_thread, args=(self, i, barrier)))
                t[-1].daemon = True
                t[-1].start()
            
            t.append(threading.Thread(target=draw_detection_on_thread, args=(self, i)))
            t[-1].daemon = True
            t[-1].start()

    # endregion Calibration
    
    # region Trigger recording
    def setup_trigger_recording(self, overwrite=False):
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
            show_camera_error(self)
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
        
        if not os.path.isdir(os.path.normpath(self.dir_output.get())):
            os.makedirs(os.path.normpath(self.dir_output.get()))
            
        for i in range(len(self.cam)):
            temp_exposure = str(round(math.log2(1/float(self.exposure[i].get()))))
            temp_gain = str(round(float(self.gain[i].get())))
            self.cam_name_no_space.append(self.cam_name[i].replace(' ', ''))
            self.base_name.append(self.cam_name_no_space[i] + '_'
                                  + self.subject.get() + '_'
                                  + self.setup_name.get() + '_'
                                  + date + '_'
                                  + str(int(da_fps)) + 'f'
                                  + temp_exposure + 'e'
                                  + temp_gain + 'g')
            self.vid_file.append(os.path.normpath(self.dir_output.get() + '/' +
                                                  self.base_name[i] +
                                                  self.attempt.get() +
                                                  '.avi'))
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
                          text="File already exists with attempt number = " + self.attempt.get() + ".\nWould you like to overwrite the file? ").pack()
                    Button(self.ask_overwrite, text="Overwrite", command=lambda: quit_overwrite(True)).pack()
                    Button(self.ask_overwrite, text="Cancel & pick new attempt number",
                           command=lambda: quit_overwrite(False)).pack()
                    self.ask_overwrite.mainloop()
                    self.ask_overwrite.destroy()
                    
                    if self.overwrite:
                        self.vid_file[i] = os.path.normpath(
                            self.dir_output.get() + '/' + self.base_name[i] + self.attempt.get() + '.avi')
                    else:
                        return
            else:
                # self.vid_file[i] = self.vid_file[0].replace(cam_name_nospace[0], cam_name_nospace[i])
                print('')
        
            dim = self.cam[i].get_image_dimensions()
            # fourcc = cv2.VideoWriter_fourcc(*)
            if self.tracking_points[i][0] is None:
                self.vid_out.append(self.cam[i].set_up_video_trigger(self.vid_file[i], self.video_codec, int(self.fps.get()), dim))
            else:
                self.vid_out.append(self.cam[i].set_up_video_trigger(self.vid_file[i], self.video_codec, int(self.fps.get()), dim, self.tracking_points[i]))
                
            self.cam[i].set_frame_callback_video()
            
        subject_name = self.subject.get() + '_' + date + '_' + self.attempt.get()
        create_output_files(self, subject_name=subject_name)
        
        self.recording_trigger_toggle_status = False
        self.setup = True
        
    def toggle_trigger_recording(self, force_termination=False):
        
        """
        Toggle the trigger recording status.

        This method toggles the trigger recording status. If the trigger recording is enabled, the method will disable it, and vice versa.

        Parameters:
        - None

        Return Type:
        - None

        Example Usage:
        toggle_trigger_recording()
        """
        if self.recording_trigger_toggle_status or force_termination:
            for i in range(len(self.cam)):
                self.recording_trigger_status[i] = False
                
            print('Waiting for all the frames are done processing...')
            self.recording_status.set('Waiting for all the frames are done processing...')
            current_thread = threading.currentThread()
            for t in self.recording_trigger_thread:
                if t is not current_thread and t.is_alive():
                    print('Waiting for {} to finish...'.format(t.name))
                    t.join()
                    
            self.recording_trigger_toggle_status = False
            print('The cameras stopped gracefully!')
            self.recording_status.set('The cameras stopped gracefully!')
            self.toggle_trigger_recording_status = IntVar(value=0)
            self.toggle_trigger_recording_button.config(text="Capture Off", background="red")
        else:
            if self.setup is False:
                print('Please setup the trigger recording first!')
                return None
           
            # Set the cameras into appropriate modes before enable trigger
            for i in range(len(self.cam)):
                self.cam[i].set_flip_vertical(state=True)
                time.sleep(0.5)
                
            self.recording_status.set('Starting the trigger recording...')
            self.toggle_trigger_recording_status = IntVar(value=1)
            self.toggle_trigger_recording_button.config(text="Capture On", background="green")
            self.vid_start_time = time.perf_counter()
            
            # enable the trigger
            barrier = threading.Barrier(len(self.cam))
            self.recording_trigger_thread = []
            self.recording_trigger_status = [True for i in range(len(self.cam))]
            self.recording_trigger_toggle_status = True

            for i in range(len(self.cam)):
                thread_name = f"Cam {i + 1} thread"
                self.recording_trigger_thread.append(threading.Thread(target=self.enable_trigger_on_thread, args=(i, barrier), name=thread_name))
                self.recording_trigger_thread[-1].daemon = True
                self.recording_trigger_thread[-1].start()
    
    def enable_trigger_on_thread(self, num, barrier):
        try:
            barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            print(f'Barrier broken for cam {num}. Failed to sync start the trigger. Please try again!')
            return None
        
        self.cam[num].enable_trigger()
        self.cam[num].turn_off_continuous_mode()
        self.cam[num].set_recording_status(state=True)
        while self.recording_trigger_toggle_status:
            if not self.recording_trigger_status[num]:
                self.cam[num].disable_trigger()
                self.cam[num].set_recording_status(state=False)
                print(f'Kill thread for cam {num}')
                break
            time.sleep(0.1)
    
    def save_trigger_recording(self, compress=False, delete=False):
        """
        Save the trigger recording.

        This method saves the trigger recording. The trigger recording is saved as a .csv file.

        Parameters:
        - None

        Return Type:
        - None

        Example Usage:
        save_trigger_recording()
        """
        # self.toggle_trigger_recording(force_termination=True)
        # self.toggle_trigger_recording_button['state'] = 'disabled'
        # self.toggle_trigger_recording_button.config(text="Capture Disabled", background="red")
        
        saved_files = []
        for num in range(len(self.cam)):
            self.trigger_status_label[num]['text'] = 'Disabled'
            self.trigger_status_indicator[num]['bg'] = 'gray'
        
        # check for frames before saving. if any video has not taken frames, delete all videos
        # frames_taken = all([len(i) > 0 for i in self.frame_times])
        
        # release video writer (saves file).
        # if no frames taken or delete specified,
        # delete the file and do not save timestamp files; otherwise, save timestamp files.
        frame_time_list = []
        for i in range(len(self.vid_out)):
            frame_times, frame_num, tracking_value = self.cam[i].release_video_file()
            frame_times = [value - frame_times[0] for value in frame_times]
            print(f'Cam {i} frame times size is {len(frame_times)}')
            frame_time_list.append(frame_times)
            if delete:
                self.cam[i].delete_video_file()
            else:
                np.save(str(self.ts_file[i]), np.array(frame_time_list[i]))
                np.savetxt(str(self.ts_file_csv[i]), np.array(frame_time_list[i]), delimiter=",")
                saved_files.append(self.vid_file[i])
                saved_files.append(self.ts_file[i])
        
        if len(saved_files) > 0:
            if len(frame_times) > 1:
                cam0_times = np.array(frame_time_list[0])
                cam1_times = np.array(frame_time_list[1])
                fps = int(self.fps.get())
                check_frame_text = check_frame(cam0_times, cam1_times, fps)
                for texty in check_frame_text:
                    self.save_msg += texty + '\n'
            self.save_msg += "The following files have been saved:"
            for i in saved_files:
                self.save_msg += "\n" + i
            
            self.attempt.set(str(int(self.attempt.get()) + 1))
        
        elif delete:
            self.save_msg = "Video has been deleted, please set up a new video to take another recording."
        
        if self.save_msg:
            display_recorded_stats(self)
        self.frame_time_list = frame_time_list
        self.vid_out = []
        # self.frame_times = []
        # self.current_file_label['text'] = ""
        # self.received_pulse_label['text'] = ""
        self.set_calibration_buttons_group(state='disabled')
        
    def plot_trigger_recording(self, frame_time_list):
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
        
        fig, ax = plt.subplots()

        # Plot the error values
        for num in range(len(self.cam)):
            num_list = np.empty(len(frame_time_list[num]))
            num_list.fill(num*10**-4)

            # Plot the data for each cam
            plt.scatter(frame_time_list[num], num_list, marker='o', s=3, label=f'Camera {num+1}')
        
        # ax.plot(error_list)

        # Customize the plot
        x_interval = 0.001

        # plt.gca().xaxis.set_major_locator(ticker.MultipleLocator(base=0.))
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Error')
        ax.set_title('Error Progression')
        # Display the grid on the plot
        plt.grid(True)
        
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

    def display_recorded_stats(self):
        self.plot_trigger_recording(self.frame_time_list)
 
    # endregion Trigger recording
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
            self.number_of_cams = IntVar(value=1)
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
        self.window.minsize(width=300, height=500)

        cur_row = 0
        numberOfScreenUnits = 100
        
        if not isinstance(self.number_of_cams, int):
            self.number_of_cams = int(self.number_of_cams.get())

        for i in range(self.number_of_cams):
            # drop down menu to select camera
            # Camera recording status frame
            camera_record_status_frame = Frame(self.window)
            # Add title label to the frame
            title_label = Label(camera_record_status_frame, text="Camera " + str(i + 1) + " Settings: ", font=("Arial", 12, "bold"))
            title_label.grid(row=0, column=0, padx=1, pady=1, sticky="w")
            
            # label for trigger status
            self.trigger_status_indicator.append(Label(camera_record_status_frame, text="Trigger status: ", bg="gray"))
            self.trigger_status_indicator[i]. \
                grid(row=0, column=1, sticky="w", padx=5, pady=3)
            self.trigger_status_label.append(Label(camera_record_status_frame, text="Disabled", width=10, anchor="w"))
            self.trigger_status_label[i]. \
                grid(row=0, column=2, columnspan=3, sticky="w", padx=5, pady=3)
            
            camera_record_status_frame.grid(row=cur_row, column=0, padx=1, pady=1, sticky="w")

            # Add status of the camera and its video setting to the frame
            video_file_status_frame = Frame(self.window)
            self.video_file_indicator.append(Label(video_file_status_frame, text="Video File: ", width=8, justify="left", anchor="w", bg='gray'))
            self.video_file_indicator[i].grid(sticky="w", row=0, column=1, padx=3, pady=3)

            self.video_file_status.append(Label(video_file_status_frame, text="Not Available", width=40, justify="left", anchor="w"))
            self.video_file_status[i].grid(sticky="w", row=0, column=2, columnspan=3, padx=0, pady=0)

            video_file_status_frame.grid(row=cur_row, column=1, padx=1, pady=1, sticky="w")
            
            cur_row += 1

            init_camera_frame = Frame(self.window, borderwidth=1, relief="raised")
            
            Label(init_camera_frame, text="Camera name: ", width=10, justify="left", anchor="w").\
                grid(sticky="w", row=0, column=0, padx=1, pady=3)
            self.camera.append(StringVar())
            self.camera_entry.append(ttk.Combobox(init_camera_frame, textvariable=self.camera[i], width=10, justify="left"))
            self.camera_entry[i]['values'] = self.cam_names
            self.camera_entry[i].current(i)
            self.camera_entry[i].grid(row=0, column=1, padx=1, pady=3)

            # initialize camera button
            self.camera_init_button.append(Button(init_camera_frame, text=f"Initialize Camera {i+1}", command=lambda index_cam=i: self.init_cam(index_cam), width=14))
            self.camera_init_button[i].grid(sticky="nsew", row=0, column=2, padx=5, pady=3)

            # format
            format_frame = Frame(init_camera_frame)
            Label(format_frame, text="Width: ", width=5, justify="left", anchor="w").\
                grid(sticky="w", row=0, column=0, padx=1, pady=0)
            self.format_width.append(IntVar(value=1024))
            self.format_width_entry = Spinbox(format_frame, from_=0, to=2e3, increment=4, textvariable=self.format_width[i], width=5, justify="left")
            self.format_width_entry.grid(row=0, column=1, padx=1, pady=0, sticky="w")

            Label(format_frame, text="Height: ", width=5, justify="left", anchor="w").\
                grid(sticky="w", row=0, column=2, padx=1, pady=0)
            self.format_height.append(IntVar(value=768))
            self.format_height_entry = Spinbox(format_frame, from_=0, to=2e3, increment=4, textvariable=self.format_height[i], width=5, justify="left")
            self.format_height_entry.grid(row=0, column=3, padx=1, pady=0, sticky="w")
            
            format_frame.grid(row=1, column=0, padx=2, pady=2, sticky="nsew", columnspan=2)
            
            # Set camera format
            Button(init_camera_frame, text="Set Format", command=lambda index_cam=i: set_formats(self, index_cam), width=14).\
                grid(sticky="nsew", row=1, column=2, padx=5, pady=3)
            
            init_camera_frame.grid(row=cur_row, column=0, padx=2, pady=3, sticky="nsew")
            init_camera_frame.pack_propagate(False)

            # change exposure
            capture_settings_frame = Frame(self.window, borderwidth=1, relief="raised")
            Label(capture_settings_frame, text='Exposure (s):', width=10, justify="left", anchor="w").\
                grid(row=0, column=0, sticky="nsew", padx=5, pady=3)
            
            self.exposure.append(DoubleVar())
            self.exposure_entry.append(Spinbox(capture_settings_frame, from_=0.0001, to=1, increment=0.0001, textvariable=self.exposure[i], width=7, justify="left"))
            self.exposure_entry[i].grid(sticky="nsew", row=0, column=1, columnspan=2, padx=5, pady=3)

            Button(capture_settings_frame, text=f"Set Exposure {i+1}", command=lambda index_cam=i: set_exposure(self, index_cam), width=14).\
                grid(sticky="nsew", row=0, column=3, padx=5, pady=3)
            
            self.exposure_current_label.append(Label(capture_settings_frame, text=f"Current: {self.exposure[i].get()} (-{str(round(math.log2(1/float((self.exposure[i].get())))))}) s", width=18, justify="left", anchor="w"))
            self.exposure_current_label[i].grid(sticky="nsew", row=0, column=4, padx=5, pady=3)
            
            # change gain
            Label(capture_settings_frame, text='Gain (db):', width=8, justify="left", anchor="w").\
                grid(sticky="nsew", row=1, column=0, padx=5, pady=3)
                
            self.gain.append(DoubleVar())
            self.gain_entry.append(Spinbox(capture_settings_frame, from_=0, to=50, increment=0.1, textvariable=self.gain[i], width=7, justify="left"))
            self.gain_entry[i].\
                grid(sticky="nsew", row=1, column=1, columnspan=2, padx=5, pady=3)
            
            Button(capture_settings_frame, text=f"Set Gain {i+1}", command=lambda index_cam=i: set_gain(self, index_cam), width=14).\
                grid(sticky="nsew", row=1, column=3, pady=3, padx=5)
            
            self.gain_current_label.append(Label(capture_settings_frame, text=f"Current: {self.gain[i].get()} db", width=15, justify="left", anchor="w"))
            self.gain_current_label[i].grid(sticky="nsew", row=1, column=4, padx=5, pady=3)
            
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
            Spinbox(fov_settings_frame, from_=0, to=1e100, increment=1, textvariable=self.fov_dict[i]['top'], width=5).\
                grid(sticky="nsew", row=0, column=1, padx=5, pady=3)

            Label(fov_settings_frame, text='Left').grid(row=0, column=2, padx=5, pady=3)
            Spinbox(fov_settings_frame, from_=0, to=1e100, increment=1, textvariable=self.fov_dict[i]['left'], width=5).\
                grid(sticky="nsew", row=0, column=3, padx=5, pady=3)
            
            Label(fov_settings_frame, text='Width').grid(row=1, column=0, padx=5, pady=3)
            Spinbox(fov_settings_frame, from_=0, to=1e100, increment=1, textvariable=self.fov_dict[i]['width'], width=5).\
                grid(sticky="nsew", row=1, column=1, padx=5, pady=3)
            
            Label(fov_settings_frame, text='Height').grid(row=1, column=2, padx=5, pady=3)
            Spinbox(fov_settings_frame, from_=0, to=1e100, increment=1, textvariable=self.fov_dict[i]['height'], width=5).\
                grid(sticky="nsew", row=1, column=3, padx=5, pady=3)
            
            reset_fov_button = Button(fov_settings_frame, text="Reset FOV", command=lambda index_cam=i: get_fov(self, index_cam), width=10)
            reset_fov_button.grid(sticky="nsew", row=0, column=5, padx=5, pady=3)
            
            set_fov_button = Button(fov_settings_frame, text="Set FOV", command=lambda index_cam=i: set_fov(self, index_cam), width=10)
            set_fov_button.grid(sticky="nsew", row=1, column=5, padx=5, pady=3)

            fov_settings_frame.grid(row=cur_row, column=2, padx=2, pady=3, sticky="nsew")
            fov_settings_frame.pack_propagate(False)
            cur_row += 1
        
            # framerate list frame
            framerate_frame = Frame(self.window, borderwidth=1, relief="raised")
            Label(framerate_frame, text="Frame Rate (fps): ").\
                grid(row=0, column=0, sticky="w", padx=5, pady=3)
            self.framerate.append(IntVar())
            self.framerate_list.append(ttk.Combobox(framerate_frame, textvariable=self.framerate[i], width=5, justify="left"))
            self.framerate_list[i]['value'] = [100, 200]
            self.framerate_list[i].current(0)
            self.framerate_list[i].grid(row=0, column=1, sticky="w", padx=5, pady=3)
            
            Button(framerate_frame, text="Update Frame Rate", command=lambda index_cam=i: set_frame_rate(self, index_cam), width=14).\
                grid(row=0, column=3, sticky="nsew", padx=3, pady=3)
           
            Label(framerate_frame, text="Current Frame Rate: ").\
                    grid(row=1, column=0, sticky="w", padx=5, pady=3)
            self.current_framerate.append(IntVar())
            Label(framerate_frame, textvariable=self.current_framerate[i], width=5).\
                    grid(row=1, column=1, sticky="w", padx=5, pady=3)
            
            self.polarity.append(IntVar())
            Checkbutton(framerate_frame, text="Trigger Polarity", variable=self.polarity[i], command=lambda index_cam=i: toggle_polarity(self, index_cam), onvalue=1, offvalue=0).\
                grid(row=1, column=3, sticky="w", padx=5, pady=3)
 
            framerate_frame.\
                grid(row=cur_row, column=0, padx=2, pady=3, sticky="nsew")
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
            self.x_offset_scale.append(Scale(partial_scan_frame, from_=0.0, to=200.0, orient=HORIZONTAL, resolution=1, variable=self.x_offset_value[i], command=lambda index_cam=i, idx=i: set_x_offset(self, index_cam, idx), width=6, length=150))
            self.x_offset_scale[i].grid(row=0, column=1, columnspan=2, sticky="new", padx=5, pady=3)
            
            self.x_offset_spinbox.append(Spinbox(partial_scan_frame, from_=0.0, to=100.0, increment=1, textvariable=self.x_offset_value[i], command=lambda index_cam=i, idx=i: set_x_offset(self, index_cam, idx), width=5))
            self.x_offset_spinbox[i].grid(row=0, column=4, columnspan=1, sticky="w", padx=5, pady=3)
            
            Label(partial_scan_frame, text="Y Offset (px): ").\
                grid(row=1, column=0, sticky="w", padx=5, pady=3)
            
            try:
                current_y_offset = self.cam_details[i]['offset']['y']
                self.y_offset_value.append(DoubleVar(current_y_offset))
            except:
                self.y_offset_value.append(DoubleVar())
            self.y_offset_value.append(DoubleVar())
            self.y_offset_scale.append(Scale(partial_scan_frame, from_=0.0, to=200.0, resolution=1, orient=HORIZONTAL, variable=self.y_offset_value[i], command=lambda index_cam=i, idx=i: set_y_offset(self, index_cam, idx), width=6, length=150))
            self.y_offset_scale[i].grid(row=1, column=1, columnspan=2, sticky="nw", padx=5, pady=3)
            
            self.y_offset_spinbox.append(Spinbox(partial_scan_frame, from_=0.0, to=100.0, increment=1, textvariable=self.y_offset_value[i], command=lambda index_cam=i, idx=i: set_y_offset(self, index_cam, idx), width=5))
            self.y_offset_spinbox[i].grid(row=1, column=4, columnspan=1, sticky="w", padx=5, pady=3)
            
            self.auto_center.append(IntVar())
            Checkbutton(partial_scan_frame, text="Auto-center", variable=self.auto_center[i], command=lambda index_cam=i: toggle_auto_center(self, index_cam)).\
                grid(row=0, column=5, sticky="w", padx=5, pady=3)
            
            self.flip_vertical.append(BooleanVar())
            Checkbutton(partial_scan_frame, text="Flip Vertical", variable=self.flip_vertical[i], command=lambda index_cam=i: toggle_flip_vertical(self, index_cam)).\
                grid(row=1, column=5, sticky="w", padx=5, pady=3)
            
            partial_scan_frame.\
                grid(row=cur_row, column=1, padx=2, pady=3, sticky="nsew")
            partial_scan_frame.pack_propagate(False)

            coord_analysis_frame = Frame(self.window, borderwidth=1, relief="raised")
            
            check_frame_coor_button = Button(coord_analysis_frame, text="Check Frame Coord", command=lambda index_cam=i: check_frame_coord(self, index_cam), width=15)
            check_frame_coor_button.grid(sticky="nsew", row=0, column=0, padx=5, pady=3)
            
            coord_track_frame = Frame(coord_analysis_frame)
            Label(coord_track_frame, text="X: "). \
                grid(row=0, column=0, sticky="w", padx=1, pady=0)
            self.x_tracking_value.append(IntVar())
            x_tracking_entry = Spinbox(coord_track_frame, from_=0, to=1e100, increment=1, textvariable=self.x_tracking_value[i], width=5)
            x_tracking_entry.grid(row=0, column=1, sticky="w", padx=1, pady=0)

            Label(coord_track_frame, text="Y: "). \
                grid(row=0, column=2, sticky="w", padx=1, pady=0)
            self.y_tracking_value.append(IntVar())
            y_tracking_entry = Spinbox(coord_track_frame, from_=0, to=1e100, increment=1, textvariable=self.y_tracking_value[i], width=5)
            y_tracking_entry.grid(row=0, column=3, sticky="w", padx=1, pady=0)

            self.tracking_points.append([None, None])
            Button(coord_track_frame, text="Track", command=lambda index_cam=i: track_frame_coord(self, index_cam), width=10). \
                grid(row=0, column=4, sticky="w", padx=1, pady=0)
            
            Button(coord_track_frame, text="Reset", command=lambda index_cam=i: reset_track_frame_coord(self, index_cam), width=10). \
                grid(row=0, column=5, sticky="w", padx=1, pady=0)
            
            coord_track_frame.grid(row=1, column=0, padx=3, pady=3, sticky="nsew")
            coord_track_frame.pack_propagate(False)
            
            coord_analysis_frame.grid(row=cur_row, column=2, padx=2, pady=3, sticky="nsew")
            coord_analysis_frame.pack_propagate(False)
            
            cur_row += 1
            camera_status_frame = Frame(self.window)
            # label for frame acquired count
            Label(camera_status_frame, text="Frame acquired #: "). \
                grid(row=0, column=0, sticky="w", padx=5, pady=0)
            self.frame_acquired_count_label.append(Label(camera_status_frame, text="0", width=5))
            self.frame_acquired_count_label[i]. \
                grid(row=0, column=1, sticky="nw", padx=5, pady=0)

            # label for frame acquired count
            Label(camera_status_frame, text="Detected board #: "). \
                grid(row=0, column=2, sticky="w", padx=5, pady=0)
            self.board_detected_count_label.append(Label(camera_status_frame, text="0", width=5))
            self.board_detected_count_label[i]. \
                grid(row=0, column=3, sticky="nw", padx=5, pady=0)
            
            camera_status_frame. \
                grid(row=cur_row, column=0, padx=2, pady=0, sticky="w")
            camera_status_frame.pack_propagate(False)

            # tracking point status
            tracking_point_frame = Frame(self.window)
            self.tracking_points_status.append(Label(tracking_point_frame, text="Not Tracked", width=30, justify="left", anchor="w"))
            self.tracking_points_status[i].grid(row=0, column=0, columnspan=3, sticky="w", padx=1, pady=0)
            
            tracking_point_frame.grid(row=cur_row, column=2, padx=2, pady=0, sticky="w")
            tracking_point_frame.pack_propagate(False)
            
            cur_row += 1

            # empty row
            Label(self.window, text="").grid(row=cur_row, column=0)

            # end of camera loop
            cur_row = cur_row + 1

        video_setting_label = Label(self.window, text="Video Settings: ", font=("Arial", 12, "bold"))
        video_setting_label.grid(row=cur_row, column=0, padx=1, pady=1, sticky="w")
        cur_row += 1
        
        # Video info setting
        video_info_frame = Frame(self.window, borderwidth=1, relief="raised")
        
        # Video name setting
        video_name_frame = Frame(video_info_frame)
        
        # Subject name
        Label(video_name_frame, text="Subject: ").\
            grid(sticky="nw", row=0, column=0, padx=3, pady=0)
        self.subject = StringVar(value='Mouse')
        self.subject_entry = ttk.Combobox(video_name_frame, textvariable=self.subject, width=5)
        self.subject_entry['values'] = tuple(self.mouse_list)
        self.subject_entry.\
            grid(sticky="nw", row=0, column=1, padx=3, pady=0)

        # Experimental setup
        Label(video_name_frame, text="Setup: ").\
            grid(sticky="nw", row=0, column=2, padx=3, pady=0)
        self.setup_name = StringVar(value='Test')
        self.setup_entry = Entry(video_name_frame, textvariable=self.setup_name, width=10)
        self.setup_entry.\
            grid(sticky="nw", row=0, column=3, padx=3, pady=0)
        
        # attempt
        Label(video_name_frame, text="Attempt: ").grid(sticky="nw", row=0, column=4, padx=3, pady=0)
        self.attempt = StringVar(value="1")
        self.attempt_entry = ttk.Combobox(video_name_frame, textvariable=self.attempt, width=5)
        self.attempt_entry['values'] = tuple(range(1, 10))
        self.attempt_entry.\
            grid(sticky="nw", row=0, column=5, padx=3, pady=0)
        
        video_name_frame.grid(row=0, column=0, padx=5, pady=3, columnspan=4, sticky="nsew")
        
        # type frame rate
        Label(video_info_frame, text="Frame Rate: ").\
            grid(sticky="nw", row=1, column=0, padx=5, pady=3)
        self.fps = StringVar()
        self.fps_entry = Entry(video_info_frame, textvariable=self.fps, width=5)
        self.fps_entry.insert(END, '200')
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
            grid(sticky="nww", row=1, column=3, padx=5, pady=3)
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
        Button(setup_video_frame, text="Setup Trigger", command=self.set_up_vid_trigger, width=14).\
            grid(sticky="nsew", row=1, column=0, columnspan=1, padx=5, pady=3)
        Button(setup_video_frame, text="Sync With Synapse", command=self.set_up_vid_trigger_synapse, width=14).\
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

        self.toggle_continuous_mode = IntVar(value=1)
        self.toggle_continuous_mode_button = Checkbutton(record_video_frame, text="Continuous Mode", variable=self.toggle_continuous_mode,
                                                         onvalue=1, offvalue=0, width=13)
        self.toggle_continuous_mode_button.grid(sticky="nsew", row=2, column=0, padx=5, pady=3)
        Hovertip(self.toggle_continuous_mode_button, "Toggle continuous mode during video recording")
        
        # save videos
        self.release_vid0 = Button(record_video_frame, text="Save Video",
                                   command=lambda: save_vid(self, compress=False), width=14).\
            grid(sticky="nsew", row=0, column=2, padx=5, pady=3)

        self.release_vid2 = Button(record_video_frame, text="Delete Video",
                                   command=lambda: save_vid(self, delete=True), width=14)
        self.release_vid2.grid(sticky="nsew", row=1, column=2, padx=5, pady=3)
        Hovertip(self.release_vid2, "Delete video if not needed")
    
        self.display_stats_button = Button(record_video_frame, text="Display stats", command=lambda: display_recorded_stats(self), width=10)
        self.display_stats_button.grid(sticky="nsew", row=2, column=2, columnspan=1, padx=5, pady=3)
        Hovertip(self.display_stats_button, "Display stats of recorded videos")

        record_video_frame.grid(row=cur_row, column=2, padx=2, pady=3, sticky="nsew")
        
        cur_row += 1
        # empty row
        Label(self.window, text="").grid(row=cur_row, column=0)
        cur_row += 1

        # Experimental settings
        experimental_settings_label = Label(self.window, text="Experimental settings: ", font=("Arial", 12, "bold"))
        experimental_settings_label.grid(row=cur_row, column=0, padx=1, pady=1, sticky="nw")
        cur_row += 1

        experimental_functions_frame = Frame(self.window)
        self.setup_trigger_recording_button = Button(experimental_functions_frame, text="Setup Videos", width=14, command=self.setup_trigger_recording)
        self.setup_trigger_recording_button.grid(sticky="nsew", row=0, column=0, padx=5, pady=3)
        Hovertip(self.setup_trigger_recording_button, "Setup the video recording using trigger")

        self.toggle_trigger_recording_status = IntVar(value=0)
        self.toggle_trigger_recording_button = Button(experimental_functions_frame, text="Capture Disabled",
                                                      background="red", state="normal", width=14, command=self.toggle_trigger_recording)
        self.toggle_trigger_recording_button.grid(sticky="nsew", row=0, column=1, padx=5, pady=3)
        Hovertip(self.toggle_trigger_recording_button, "Start/Stop listening to trigger to capture frame")

        self.save_trigger_recording_button = Button(experimental_functions_frame, text="Save Videos", state="normal", width=14, command=self.save_trigger_recording)
        self.save_trigger_recording_button.grid(sticky="nsew", row=0, column=2, padx=5, pady=3)
        Hovertip(self.save_trigger_recording_button, "Save the trigger recording to file")

        self.delete_trigger_recording_button = Button(experimental_functions_frame, text="Delete Videos", state="normal", width=14, command=lambda: self.save_trigger_recording(delete=True))
        self.delete_trigger_recording_button.grid(sticky="nsew", row=0, column=3, padx=5, pady=3)
        Hovertip(self.delete_trigger_recording_button, "Delete the trigger recording")

        self.display_trigger_recording_stats = Button(experimental_functions_frame, text="Display stats", state="normal", width=14, command=self.display_recorded_stats)
        self.display_trigger_recording_stats.grid(sticky="nsew", row=0, column=4, padx=5, pady=3)
        Hovertip(self.display_trigger_recording_stats, "Display stats of recorded videos")

        experimental_functions_frame.grid(row=cur_row, column=0, columnspan=3, padx=2, pady=3, sticky="nw")
        
        # Recording stats
        recording_stats_label = Label(self.window, text="Recording Stats: ", font=("Arial", 12, "bold"))
        recording_stats_label.grid(row=cur_row-1, column=2, padx=1, pady=1, sticky="nw")
        
        recording_stats_frame = Frame(self.window)
        Label(recording_stats_frame, text="Current Status: ").\
            grid(sticky="nw", row=0, column=0, padx=5, pady=0)
        self.recording_status = StringVar(value="Not Recording")
        Label(recording_stats_frame, textvariable=self.recording_status, width=15).\
            grid(sticky="nw", row=0, column=1, padx=5, pady=0)
        
        Label(recording_stats_frame, text="Current Duration (s): ").\
            grid(sticky="nw", row=1, column=0, padx=5, pady=0)
        self.recording_duration = StringVar()
        Label(recording_stats_frame, textvariable=self.recording_duration, width=5).\
            grid(sticky="nw", row=1, column=1, padx=5, pady=0)
        
        recording_stats_frame.grid(row=cur_row, column=2, padx=2, pady=3, sticky="nw")
        
        cur_row += 1
        # empty row
        Label(self.window, text="").grid(row=cur_row, column=0)
        cur_row += 1
        
        ## calibrate video section
        calibration_label = Label(self.window, text="Calibration: ", font=("Arial", 12, "bold"))
        calibration_label.grid(row=cur_row, column=0, padx=1, pady=1, sticky="nw")
        cur_row += 1
        calibration_frame = Frame(self.window, borderwidth=1, relief="raised")
        
        #  calibration duration
        calibration_duration_frame = Frame(calibration_frame)
        Label(calibration_duration_frame, text="Capture Duration(s): ").\
            grid(sticky="nsew", row=0, column=0, columnspan=1, padx=0, pady=0)
        self.calibration_duration_entry = Entry(calibration_duration_frame, width=3)
        self.calibration_duration_entry.insert(0, "30")
        self.calibration_duration_entry.grid(sticky="nsew", row=0, column=1, columnspan=1, padx=0, pady=0)
        calibration_duration_frame.grid(row=0, column=0, padx=0, pady=3, sticky="nsew")
        
        self.setup_calibration_button = Button(calibration_frame, text="Setup Calibration", command=self.setup_calibration, width=3)
        self.setup_calibration_button.\
            grid(sticky="nsew", row=1, column=0, columnspan=1, padx=5, pady=3)
        Hovertip(self.setup_calibration_button, "Press this button to setup calibration. ")

        self.toggle_calibration_capture_button = Button(calibration_frame, text="Capture Off", command=self.toggle_calibration_capture,
                                                            background="red", state="disabled", width=10)
        self.toggle_calibration_capture_button.\
            grid(sticky="nsew", row=0, column=1, columnspan=1, padx=5, pady=3)
        Hovertip(self.toggle_calibration_capture_button, "Press this button to start capturing frames for calibration. ")
        
        self.snap_calibration_button = Button(calibration_frame, text="Snap Frame", command=self.snap_calibration_frame, state="disabled", width=10)
        self.snap_calibration_button.\
            grid(sticky="nsew", row=1, column=1, columnspan=1, padx=5, pady=3)
        Hovertip(self.snap_calibration_button, "Press this button to snap a frame for calibration. ")
        
        self.update_calibration_button = Button(calibration_frame, text="Update Calibration", command=self.update_calibration, state="disabled", width=15)
        self.update_calibration_button.\
            grid(sticky="nsew", row=1, column=2, columnspan=1, padx=5, pady=3)
        Hovertip(self.update_calibration_button, "Press this button calibrate using the frames in the buffer. ")
        
        self.recalibrate_button = Button(calibration_frame, text="Full Calibration", command=self.recalibrate, state="normal", width=15)
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
        added_board_frame.grid(row=1, column=3, padx=0, pady=3, sticky="nsew")
        
        self.plot_calibration_error_button = Button(calibration_frame, text="Plot Calibration Error", command=self.plot_calibration_error)
        self.plot_calibration_error_button.\
            grid(sticky="nsew", row=0, column=4, columnspan=1, padx=5, pady=3)
        Hovertip(self.plot_calibration_error_button, "Press this button to plot the calibration error. ")
        
        test_calibration_frame = Frame(calibration_frame)
        self.test_calibration_live_button = Button(test_calibration_frame, text="Try Calibration", command=self.toggle_test_calibration_live, state="normal", width=12)
        self.test_calibration_live_button.\
            grid(sticky="nw", row=0, column=0, columnspan=1, padx=0, pady=0)
        
        self.reprojection_check = IntVar(value=0)
        self.reprojection_checkbutton = Checkbutton(test_calibration_frame, text="Reproject", variable=self.reprojection_check,
                                                onvalue=1, offvalue=0, width=8)
        self.reprojection_checkbutton.grid(sticky="nw", row=0, column=1, padx=0, pady=0)
        
        test_calibration_frame.grid(row=1, column=4, padx=5, pady=3, sticky="nsew")
        
        calibration_frame.grid(row=cur_row, column=0, columnspan=2, padx=2, pady=3, sticky="nsew")
        calibration_frame.pack_propagate(False)
        
        # calibration result
        calibration_result_label = Label(self.window, text="Calibration Stats: ", font=("Arial", 12, "bold"))
        calibration_result_label.grid(row=cur_row-1, column=2, padx=1, pady=1, sticky="nw")
        
        calibration_result_frame = Frame(self.window)
        
        # label for calibration process status text
        self.calibration_status_label = Label(calibration_result_frame, text="Calibration status: ", bg="gray")
        self.calibration_status_label.grid(sticky="wn", row=0, column=0, columnspan=1, padx=0, pady=0)
        
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
        
        calibration_result_frame.grid(row=cur_row, column=2, padx=2, pady=3, sticky="nsew")
        calibration_result_frame.pack_propagate(False)
        cur_row += 1

        # close window/reset GUI
        Label(self.window).grid(row=cur_row, column=0)
        self.reset_button = (Button(self.window, text="Reset GUI", command=self.selectCams))
        self.reset_button.grid(sticky="nsew", row=cur_row + 1, column=0)
        
        self.close_button = Button(self.window, text="Close", command=self.close_window)
        self.close_button.grid(sticky="nsew", row=cur_row + 1, column=1)
    def runGUI(self):
        self.window.mainloop()


if __name__ == "__main__":
    # Create an argument parser
    parser = argparse.ArgumentParser(description="CamGUI")

    # Add optional arguments
    parser.add_argument("-d", "--debug", action="store_true", dest='debug_mode', help="Enable debug mode")
    parser.add_argument("-ni", "--no-init-cam", action="store_false", dest="init_cam_bool",
                        help="Disable camera initialization")
    parser.add_argument("-t", "--test", action="store_true", dest="test_mode", help="Enable test mode")

    # Parse the command-line arguments
    args = parser.parse_args()

    try:
        if args.test_mode:
            print("Running CamGUI test mode")
            from testscript_GUI import CamGUI_Tests
            cam_gui_auto = CamGUI_Tests(debug_mode=args.debug_mode, init_cam_bool=args.init_cam_bool)
            # cam_gui_auto.runGUI()
            cam_gui_auto.auto_init_cam()
            
        else:
            # Create an instance of the CamGUI class with the parsed arguments
            try:
                cam_gui = CamGUI(debug_mode=args.debug_mode, init_cam_bool=args.init_cam_bool)
                cam_gui.runGUI()
            except Exception as e:
                print("Error creating CamGUI instance: %s" % str(e))
                exit(1)

    except Exception as e:
        print("Error running CamGUI: %s" % str(e))
        exit(1)
