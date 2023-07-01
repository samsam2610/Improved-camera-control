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
from tkinter import Entry, Label, Button, StringVar, IntVar, Tk, END, Radiobutton, filedialog, ttk

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
        self.calibration_toggle_status = False
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

        if self.record_on.get():
            setup_window.destroy()
            cam_on_window = Tk()
            Label(cam_on_window, text="Video is recording, cannot reinitialize camera!").pack()
            Button(cam_on_window, text="Ok", command=lambda: cam_on_window.quit()).pack()
            cam_on_window.mainloop()
            cam_on_window.destroy()
            return

        if len(self.cam) >= num + 1:
            self.cam[num].close()
            self.cam[num] = None

        # create camera object
        cam_num = self.camera[num].get()
        names = np.array(self.cam_names)
        cam_num = np.where(names == cam_num)[0][0]

        if len(self.cam) >= num + 1:
            self.cam_name[num] = names[cam_num]
            self.cam[num] = ICCam(cam_num, exposure=self.exposure[cam_num].get(), gain=self.gain[cam_num].get())
        else:
            self.cam_name.append(names[cam_num])
            self.cam.append(ICCam(cam_num, exposure=self.exposure[cam_num].get(), gain=self.gain[cam_num].get()))
        self.cam[num].start()
        self.exposure[num].set(self.cam_details[str(num)]['exposure'])
        self.gain[num].set(self.cam_details[str(num)]['gain'])
        # self.exposure[num].set(self.cam[num].get_exposure())
        # self.gain[num].set(self.cam[num].get_gain())
        # reset output directory
        self.dir_output.set(self.output_entry['values'][cam_num])
        exposure_text = f'real_exposure: {self.exposure[num].get()}'
        self.current_exposure[num]['text'] = exposure_text
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

            tolerance = (1 / frameRate) * .5

            # Find frames that are too long or short
            droppedFrames = np.where(
                np.logical_or(jitter1 < 1 / frameRate - tolerance, jitter1 > 1 / frameRate + tolerance))
            # droppedFrames2 = np.where(np.logical_or(jitter2 < 1/frameRate - tolerance, jitter2 > 1/frameRate + tolerance))
            if np.size(droppedFrames) > 0:
                temp_text = "These frames may not be exactly synchronized: " + str(droppedFrames)
            else:
                temp_text = "frames are synced!"
            return_text.append(temp_text)

        return return_text

    def set_gain(self, num):
        # check if camera set up
        if len(self.cam) < num + 1:
            cam_check_window = Tk()
            Label(cam_check_window, text="No camera is found! \nPlease initialize camera before setting gain.").pack()
            Button(cam_check_window, text="Ok", command=lambda: cam_check_window.quit()).pack()
            cam_check_window.mainloop()
            cam_check_window.destroy()
        else:
            self.cam[num].set_gain(int(self.gain[num].get()))

    def set_exposure(self, num):
        # check if camera set up
        if len(self.cam) < num + 1:
            cam_check_window = Tk()
            Label(cam_check_window,
                  text="No camera is found! \nPlease initialize camera before setting exposure.").pack()
            Button(cam_check_window, text="Ok", command=lambda: cam_check_window.quit()).pack()
            cam_check_window.mainloop()
            cam_check_window.destroy()
        else:
            self.cam[num].set_exposure(float(self.exposure[num].get()))
            exposure_text = f'real_exposure: {self.exposure[num].get()}'
            self.current_exposure[num]['text'] = exposure_text

    def get_formats(self, num):
        # check if camera set up
        if len(self.cam) < num + 1:
            cam_check_window = Tk()
            Label(cam_check_window,
                  text="No camera is found! \nPlease initialize camera before setting exposure.").pack()
            Button(cam_check_window, text="Ok", command=lambda: cam_check_window.quit()).pack()
            cam_check_window.mainloop()
            cam_check_window.destroy()
        else:
            return self.cam[num].get_formats()

    def set_formats(self, num):
        # check if camera set up
        if len(self.cam) < num + 1:
            cam_check_window = Tk()
            Label(cam_check_window,
                  text="No camera is found! \nPlease initialize camera before setting exposure.").pack()
            Button(cam_check_window, text="Ok", command=lambda: cam_check_window.quit()).pack()
            cam_check_window.mainloop()
            cam_check_window.destroy()
        else:
            self.cam[num].set_formats(str(self.formats[num].get()))

    def create_video_files(self):
        # check if file exists, ask to overwrite or change attempt number if it does
        for i in range(len(self.cam)):
            if i == 0:
                self.overwrite = False
                if os.path.isfile(self.vid_file[i]):
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
                        self.vid_file[i] = os.path.normpath(
                            self.out_dir + '/' + self.base_name[i] + self.attempt.get() + '.avi')
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

    def sync_setup(self):

        if len(self.vid_out) > 0:
            vid_open_window = Tk()
            Label(vid_open_window,
                  text="Video is currently open! \nPlease release the current video (click 'Save Video', even if no frames have been recorded) before setting up a new one.").pack()
            Button(vid_open_window, text="Ok", command=lambda: vid_open_window.quit()).pack()
            vid_open_window.mainloop()
            vid_open_window.destroy()
            return

        # check if camera set up
        if len(self.cam) == 0:
            cam_check_window = Tk()
            Label(cam_check_window,
                  text="No camera is found! \nPlease initialize camera before setting up video.").pack()
            Button(cam_check_window, text="Ok", command=lambda: cam_check_window.quit()).pack()
            cam_check_window.mainloop()
            cam_check_window.destroy()
        else:
            self.trigger_on = 1
            da_fps = str(self.fps.get())
            month = datetime.datetime.now().month
            month = str(month) if month >= 10 else '0' + str(month)
            day = datetime.datetime.now().day
            day = str(day) if day >= 10 else '0' + str(day)
            year = str(datetime.datetime.now().year)
            date = year + '-' + month + '-' + day
            self.out_dir = self.dir_output.get()
            if not os.path.isdir(os.path.normpath(self.out_dir)):
                os.makedirs(os.path.normpath(self.out_dir))

            self.cam_name_no_space = []
            this_row = 3

            # Preallocate vid_file dir
            self.vid_file = []
            self.base_name = []

            # subject_name, dir_name = generate_folder()
            subject_name = 'sam'
            dir_name = "E:\\tmp"
            for i in range(len(self.cam)):
                temp_exposure = str(self.exposure[i].get())
                temp_gain = str(self.gain[i].get())
                self.cam_name_no_space.append(self.cam_name[i].replace(' ', ''))
                self.base_name.append(self.cam_name_no_space[i] + '_' +
                                      subject_name + '_' +
                                      da_fps + 'f' +
                                      temp_exposure + 'e' +
                                      temp_gain + 'g')
                self.vid_file.append(os.path.normpath(dir_name + '/' + self.base_name[i] + '.avi'))

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
            cam_check_window = Tk()
            Label(cam_check_window,
                  text="No camera is found! \nPlease initialize camera before setting up video.").pack()
            Button(cam_check_window, text="Ok", command=lambda: cam_check_window.quit()).pack()
            cam_check_window.mainloop()
            cam_check_window.destroy()
        else:
            self.trigger_on = 0
            da_fps = str(self.fps.get())
            month = datetime.datetime.now().month
            month = str(month) if month >= 10 else '0' + str(month)
            day = datetime.datetime.now().day
            day = str(day) if day >= 10 else '0' + str(day)
            year = str(datetime.datetime.now().year)
            date = year + '-' + month + '-' + day
            self.out_dir = self.dir_output.get()
            if not os.path.isdir(os.path.normpath(self.out_dir)):
                os.makedirs(os.path.normpath(self.out_dir))

            self.cam_name_no_space = []
            self.vid_file = []
            self.base_name = []
            this_row = 3
            for i in range(len(self.cam)):
                temp_exposure = str(self.exposure[i].get())
                temp_gain = str(self.gain[i].get())
                self.cam_name_no_space.append(self.cam_name[i].replace(' ', ''))
                self.base_name.append(self.cam_name_no_space[i] + '_'
                                      + self.subject.get() + '_'
                                      + date + '_'
                                      + da_fps + 'f'
                                      + temp_exposure + 'e'
                                      + temp_gain + 'g')
                self.vid_file.append(os.path.normpath(self.out_dir + '/' +
                                                      self.base_name[i] +
                                                      self.attempt.get() +
                                                      '.avi'))

            self.create_video_files()
            subject_name = self.subject.get() + '_' + date + '_' + self.attempt.get()
            self.create_output_files(subject_name=subject_name)
            self.setup = True

    def record_on_thread(self, num):
        fps = int(self.fps.get())
        if self.trigger_on == 1:
            try:
                self.cam[num].enable_trigger()
                self.cam[num].frame_ready()
                self.frame_times[num].append(time.perf_counter())
                self.received_pulse_label['text'] = 'pulse_receieved!'
                self.cam[num].disable_trigger()
                start_in_one = math.trunc(time.perf_counter()) + 1
                while time.perf_counter() < start_in_one:
                    pass
            except Exception as e:
                print(f"Traceback: \n {traceback.format_exc()}")

        start_time = time.perf_counter()
        next_frame = start_time

        try:
            while self.record_on.get():
                if time.perf_counter() >= next_frame:
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

    def setup_calibration(self):

        self.calibration_process_stats['text'] = 'Initializing calibration process...'
        from src.gui.utils import load_config, get_calibration_board
        if self.running_config['debug_mode']:
            self.calibration_process_stats['text'] = 'Looking for config.toml directory ...'
            path = Path(os.path.realpath(__file__))
            # Navigate to the outer parent directory and join the filename
            config_toml_path = os.path.normpath(str(path.parents[2] / 'config-files' / 'config.toml'))
            config_anipose = load_config(config_toml_path)
            self.calibration_process_stats[
                'text'] = 'Successfully found and loaded config. Determining calibration board ...'
            self.board_calibration = get_calibration_board(config=config_anipose)

            self.calibration_process_stats['text'] = 'Loaded calibration board. ' \
                                                     'Initializing camera calibration objects ...'
            from src.aniposelib.cameras import CameraGroup
            self.cgroup = CameraGroup.from_names(self.cam_names)
            self.calibration_process_stats['text'] = 'Initialized camera object.'
            self.frame_count = []
            self.all_rows = []

            # check if camera set up
            if len(self.cam) == 0:
                cam_check_window = Tk()
                Label(cam_check_window,
                      text="No camera is found! \nPlease initialize camera before setting up video.").pack()
                Button(cam_check_window, text="Ok", command=lambda: cam_check_window.quit()).pack()
                cam_check_window.mainloop()
                cam_check_window.destroy()
            else:
                self.calibration_process_stats['text'] = 'Cameras found. Recording the frame sizes'
                self.toggle_calibration_button["state"] = "normal"
                self.calibration_toggle_status = False
                frame_sizes = []
                self.frame_times = []
                self.previous_frame_count = []
                self.current_frame_count = []
                self.frame_process_threshold = 10
                self.queue_frame_threshold = 1000
                # Check available detection file, if file available will delete it (for now)
                self.rows_fname = os.path.join(self.dir_output.get(), 'detections.pickle')
                self.calibration_out = os.path.join(self.dir_output.get(), 'calibration.toml')
                self.clear_calibration_file(self.rows_fname)
                self.clear_calibration_file(self.calibration_out)
                self.rows_fname_available = False

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
                self.create_video_files()
                self.create_output_files(subject_name='Sam')

                self.calibration_process_stats['text'] = 'Setting the frame sizes...'
                self.cgroup.set_camera_sizes_images(frame_sizes=frame_sizes)
                self.init_matrix = True
                self.calibration_process_stats['text'] = 'Prepping done. Starting calibration...'
                self.vid_start_time = time.perf_counter()
                t = []

                for i in range(len(self.cam)):
                    t.append(threading.Thread(target=self.record_calibrate_on_thread, args=(i,)))
                    t[-1].daemon = True
                    t[-1].start()
                t.append(threading.Thread(target=self.detect_marker_on_thread))
                t[-1].daemon = True
                t[-1].start()
                t.append(threading.Thread(target=self.calibrate_on_thread))
                t[-1].daemon = True
                t[-1].start()

    def toggle_calibration(self):
        if self.calibration_toggle_status:
            self.calibration_toggle_status = False
            self.toggle_calibration_button.config(text="Calibration Off", background="red")
        else:
            self.calibration_toggle_status = True
            self.toggle_calibration_button.config(text="Calibration On", background="green")

    def record_calibrate_on_thread(self, num):
        fps = int(self.fps.get())
        start_time = time.perf_counter()
        next_frame = start_time
        while True:
            try:
                while self.calibration_toggle_status:
                    if time.perf_counter() >= next_frame:
                        current_time = time.perf_counter
                        self.frame_times[num].append(time.perf_counter())
                        self.frame_count[num] += 1
                        # putting frame into the frame queue along with following information
                        self.frame_queue.put((self.cam[num].get_image(),  # the frame itself
                                              num,  # the id of the capturing camera
                                              self.frame_count[num],  # the current frame count
                                              self.frame_times[num][-1]))  # captured time

                        next_frame = max(next_frame + 1.0 / fps, self.frame_times[num][-1] + 0.5 / fps)
            except Exception as e:
                print("Exception occurred:", type(e).__name__, "| Exception value:", e, "| Thread ID:", num,
                      "| Frame count:", self.frame_count[num], "| Capture time:", self.frame_times[num][-1],
                      "| Traceback:", ''.join(traceback.format_tb(e.__traceback__)))

    def detect_marker_on_thread(self):
        frame_groups = {}  # Dictionary to store frame groups by thread_id
        frame_counts = {}  # array to store frame counts for each thread_id
        while True:
            try:
                while self.calibration_toggle_status:
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
                        self.calibration_process_stats['text'] = f'More than {self.frame_process_threshold} ' \
                                                                 f'frames acquired from each camera,' \
                                                                 f' detecting the markers...'
                        all_rows = []  # preallocate detected rows from all cameras, for each camera

                        # For each frame from each camera, detect the corners and ids, then add to rows,
                        # then to all_rows
                        for i in range(len(self.cam)):
                            rows = []
                            for frame_data in frame_groups[i]:
                                frame_current, frame_count_current, capture_time_current = frame_data

                                corners, ids = self.board_calibration.detect_image(frame_current)

                                if corners is not None:
                                    key = frame_count_current
                                    row = {
                                        'framenum': key,
                                        'corners': corners,
                                        'ids': ids
                                    }

                                    rows.append(row)

                            rows = self.board_calibration.fill_points_rows(rows)
                            self.board_detected_count_label[i]['text'] = f'{len(rows)}'
                            all_rows.append(rows)

                        # pre-check the quality of the detections
                        if len(all_rows) == len(self.cam):
                            # Check if the number of rows in those rows is the same
                            if len(all_rows[0]) == len(all_rows[1]):
                                self.calibration_process_stats['text'] = \
                                    "Detected the same number of rows from all cameras, saving the detections."
                                with open(self.rows_fname, 'ab') as file:
                                    pickle.dump(all_rows, file)
                                self.rows_fname_available = True

                            else:
                                self.rows_fname_available = False
                                self.calibration_process_stats['text'] = \
                                    f"The number of rows in the two rows is different. \
                                    cam_1 has {len(all_rows[0])} rows and cam_2 has {len(all_rows[1])} rows"
                        else:
                            print(f"Couldn't simultaneously detected rows from {len(self.cam)} cameras.")
                        # if the all_rows is empty, do not:
                        # update the detection file, and
                        # perform the calibration

                        # Clear the processed frames from the group
                        frame_groups = {}
                        frame_count = {}

            except Exception as e:
                print("Exception occurred:", type(e).__name__, "| Exception value:", e, "| Thread ID:", thread_id,
                      "| Frame count:", frame_count, "| Capture time:", capture_time, "| Traceback:",
                      ''.join(traceback.format_tb(e.__traceback__)))

    def calibrate_on_thread(self):
        self.calibration_error = float('inf')
        print(f'Current error: {self.calibration_error}')
        while True:
            try:
                if self.rows_fname_available:
                    print(f'Current error: {self.calibration_error}')
                    with open(self.rows_fname, 'rb') as f:
                        all_rows = pickle.load(f)

                    self.calibration_error = self.cgroup.calibrate_rows(all_rows, self.board_calibration,
                                                                        init_intrinsics=self.init_matrix,
                                                                        init_extrinsics=self.init_matrix,
                                                                        max_nfev=200, n_iters=6,
                                                                        n_samp_iter=200, n_samp_full=1000,
                                                                        verbose=True)

                    with open(self.cgroup_fname, "wb") as f:
                        cgroup = pickle.dump(cgroup)

                    self.init_matrix = False
                    # self.calibration_error_stats['text'] = f'Current error: {self.calibration_error}'
                    self.cgroup.metadata['adjusted'] = False
                    if self.calibration_error is not None:
                        self.cgroup.metadata['error'] = float(self.calibration_error)
                    self.cgroup.dump(self.calibration_out)
                    self.rows_fname_available = False

            except Exception as e:
                print("Exception occurred:", type(e).__name__, "| Exception value:", e,
                      ''.join(traceback.format_tb(e.__traceback__)))

    def start_record(self):
        if len(self.vid_out) == 0:
            remind_vid_window = Tk()
            Label(remind_vid_window, text="VideoWriter not initialized! \nPlease set up video and try again.").pack()
            Button(remind_vid_window, text="Ok", command=lambda: remind_vid_window.quit()).pack()
            remind_vid_window.mainloop()
            remind_vid_window.destroy()
        else:
            self.vid_start_time = time.perf_counter()
            t = []
            for i in range(len(self.cam)):
                t.append(threading.Thread(target=self.record_on_thread, args=(i,)))
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

    def save_vid(self, compress=False, delete=False):

        saved_files = []

        # check that videos have been initialized

        if len(self.vid_out) == 0:
            not_initialized_window = Tk()
            Label(not_initialized_window,
                  text="Video writer is not initialized. Please set up first to record a video.").pack()
            Button(not_initialized_window, text="Ok", command=lambda: not_initialized_window.quit()).pack()
            not_initialized_window.mainloop()
            not_initialized_window.destroy()

        else:

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

        save_msg = ""
        if len(saved_files) > 0:
            if len(self.frame_times) > 1:
                cam0_times = np.array(self.frame_times[0])
                cam1_times = np.array(self.frame_times[1])
                fps = int(self.fps.get())
                check_frame_text = self.check_frame(cam0_times, cam1_times, fps)
                for texty in check_frame_text:
                    save_msg += texty + '\n'
            save_msg += "The following files have been saved:"
            for i in saved_files:
                save_msg += "\n" + i

        elif delete:
            save_msg = "Video has been deleted, please set up a new video to take another recording."
        elif not frames_taken:
            save_msg = 'Video was initialized but no frames were recorded.\n' \
                       'Video has been deleted, please set up a new video to take another recording.'

        if save_msg:
            save_window = Tk()
            Label(save_window, text=save_msg).pack()
            Button(save_window, text="Close", command=lambda: save_window.quit()).pack()
            save_window.mainloop()
            save_window.destroy()

        self.vid_out = []
        self.frame_times = []
        self.current_file_label['text'] = ""
        self.received_pulse_label['text'] = ""

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
            self.number_of_cams_entry = Entry(select_cams_window, textvariable=self.number_of_cams).grid(sticky="nsew",
                                                                                                         row=0,
                                                                                                         column=1)
            Button(select_cams_window, text="Set Cameras", command=select_cams_window.quit).grid(sticky="nsew", row=1,
                                                                                                 column=0, columnspan=2)
            select_cams_window.mainloop()
            select_cams_window.destroy()
        else:
            self.number_of_cams_entry = "2"
            self.number_of_cams = 2

        self.createGUI()

    def createGUI(self):

        self.window = Tk()
        self.window.title("Camera Control")

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
        self.frame_acquired_count_label = []
        self.board_detected_count_label = []

        if not isinstance(self.number_of_cams, int):
            self.number_of_cams = int(self.number_of_cams.get())

        for i in range(self.number_of_cams):
            # drop down menu to select camera
            Label(self.window, text="Camera " + str(i + 1) + ": ").grid(sticky="w", row=cur_row, column=0)
            self.camera.append(StringVar())
            self.camera_entry.append(ttk.Combobox(self.window, textvariable=self.camera[i]))
            self.camera_entry[i]['values'] = self.cam_names
            self.camera_entry[i].current(i)
            self.camera_entry[i].grid(row=cur_row, column=1)

            # initialize camera button
            if i == 0:
                Button(self.window, text="Initialize Camera 1", command=lambda: self.init_cam(0)).grid(sticky="nsew",
                                                                                                       row=cur_row + 1,
                                                                                                       column=0,
                                                                                                       columnspan=2)
            elif i == 1:
                Button(self.window, text="Initialize Camera 2", command=lambda: self.init_cam(1)).grid(sticky="nsew",
                                                                                                       row=cur_row + 1,
                                                                                                       column=0,
                                                                                                       columnspan=2)
            elif i == 2:
                Button(self.window, text="Initialize Camera 3", command=lambda: self.init_cam(2)).grid(sticky="nsew",
                                                                                                       row=cur_row + 1,
                                                                                                       column=0,
                                                                                                       columnspan=2)

            # change exposure
            self.exposure.append(StringVar())
            self.exposure_entry.append(Entry(self.window, textvariable=self.exposure[i]))
            self.exposure_entry[i].grid(sticky="nsew", row=cur_row, column=2)
            if i == 0:
                Button(self.window, text="Set Exposure 1", command=lambda: self.set_exposure(0)).grid(sticky="nsew",
                                                                                                      row=cur_row + 1,
                                                                                                      column=2)
            elif i == 1:
                Button(self.window, text="Set Exposure 2", command=lambda: self.set_exposure(1)).grid(sticky="nsew",
                                                                                                      row=cur_row + 1,
                                                                                                      column=2)
            elif i == 2:
                Button(self.window, text="Set Exposure 3", command=lambda: self.set_exposure(2)).grid(sticky="nsew",
                                                                                                      row=cur_row + 1,
                                                                                                      column=2)

            # change gain
            self.gain.append(StringVar())
            self.gain_entry.append(Entry(self.window, textvariable=self.gain[i]))
            self.gain_entry[i].grid(sticky="nsew", row=cur_row, column=3)
            if i == 0:
                Button(self.window, text="Set Gain 1", command=lambda: self.set_gain(0)).grid(sticky="nsew",
                                                                                              row=cur_row + 1, column=3)
            elif i == 1:
                Button(self.window, text="Set Gain 2", command=lambda: self.set_gain(1)).grid(sticky="nsew",
                                                                                              row=cur_row + 1, column=3)
            elif i == 2:
                Button(self.window, text="Set Gain 3", command=lambda: self.set_gain(2)).grid(sticky="nsew",
                                                                                              row=cur_row + 1, column=3)

            # format
            Label(self.window, text="Format " + str(i + 1) + ": ").grid(sticky="w", row=cur_row, column=4)
            self.formats.append(StringVar())
            self.format_entry.append(ttk.Combobox(self.window, textvariable=self.formats[i]))
            self.format_entry[i]['values'] = self.format_list
            self.format_entry[i].current(i)
            self.format_entry[i].grid(row=cur_row, column=4)

            # inialize camera button
            if i == 0:
                Button(self.window, text="Set format", command=lambda: self.set_formats(0)).grid(sticky="nsew",
                                                                                                 row=cur_row + 1,
                                                                                                 column=4)
            elif i == 1:
                Button(self.window, text="Set format", command=lambda: self.set_formats(1)).grid(sticky="nsew",
                                                                                                 row=cur_row + 1,
                                                                                                 column=4)
            elif i == 2:
                Button(self.window, text="Set format", command=lambda: self.set_formats(2)).grid(sticky="nsew",
                                                                                                 row=cur_row + 1,
                                                                                                 column=0)
            cur_row += 1

            Label(self.window, text='').grid(row=cur_row + 1, column=2, sticky="w")
            self.current_exposure.append(Label(self.window, text=""))
            self.current_exposure[i].grid(row=cur_row + 1, column=2, sticky="w")
            cur_row += 2

            # label for frame acquired count
            Label(self.window, text="Frame acquired count: ", wraplength=numberOfScreenUnits).grid(row=cur_row, column=0, sticky="w")
            self.frame_acquired_count_label.append(Label(self.window, text=""))
            self.frame_acquired_count_label[i].grid(row=cur_row, column=1, sticky="w")

            # label for frame acquired count
            Label(self.window, text="Detected board count: ", wraplength=numberOfScreenUnits).grid(row=cur_row, column=2, sticky="w")
            self.board_detected_count_label.append(Label(self.window, text=""))
            self.board_detected_count_label[i].grid(row=cur_row, column=3, sticky="w")
            cur_row += 1

            # empty row
            Label(self.window, text="").grid(row=cur_row + 2, column=0)

            # end of camera loop
            cur_row = cur_row + 3

        # empty row
        Label(self.window, text="").grid(row=cur_row, column=0)
        cur_row += 1

        # subject name
        Label(self.window, text="Subject: ").grid(sticky="w", row=cur_row, column=0)
        self.subject = StringVar()
        self.subject_entry = ttk.Combobox(self.window, textvariable=self.subject)
        self.subject_entry['values'] = tuple(self.mouse_list)
        self.subject_entry.grid(row=cur_row, column=1)
        cur_row += 1

        # attempt
        Label(self.window, text="Attempt: ").grid(sticky="w", row=cur_row, column=0)
        self.attempt = StringVar(value="1")
        self.attempt_entry = ttk.Combobox(self.window, textvariable=self.attempt)
        self.attempt_entry['values'] = tuple(range(1, 10))
        self.attempt_entry.grid(row=cur_row, column=1)
        cur_row += 1

        # type frame rate
        Label(self.window, text="Frame Rate: ").grid(sticky="w", row=cur_row, column=0)
        self.fps = StringVar()
        self.fps_entry = Entry(self.window, textvariable=self.fps)
        self.fps_entry.insert(END, '100')
        self.fps_entry.grid(sticky="nsew", row=cur_row, column=1)
        cur_row += 1

        # output directory
        Label(self.window, text="Output Directory: ").grid(sticky="w", row=cur_row, column=0)
        self.dir_output = StringVar()
        self.output_entry = ttk.Combobox(self.window, textvariable=self.dir_output)
        self.output_entry['values'] = self.output_dir
        self.output_entry.grid(row=cur_row, column=1)
        Button(self.window, text="Browse", command=self.browse_output).grid(sticky="nsew", row=cur_row, column=2)

        # select video encoder codec
        Label(self.window, text="Video writer codec:").grid(sticky="w", row=cur_row, column=3)
        self.video_codec = StringVar()
        self.video_codec_entry = ttk.Combobox(self.window,
                                              value=self.fourcc_codes,
                                              state="readonly")
        self.video_codec_entry.set("XVID")  # default codec
        self.video_codec_entry.bind("<<ComboboxSelected>>", self.browse_codec)
        self.video_codec_entry.grid(row=cur_row, column=4)
        self.video_codec = self.video_codec_entry.get()  # add default video codec
        cur_row += 1

        # set up video
        Button(self.window, text="Set Up Video", command=self.set_up_vid).grid(sticky="nsew", row=cur_row, column=0,
                                                                               columnspan=1)
        Button(self.window, text="SYNC_WITH_SYNAPSE", command=self.sync_setup).grid(sticky="nsew", row=cur_row,
                                                                                    column=1, columnspan=1)
        Button(self.window, text="Setup Calibration", command=self.setup_calibration).grid(sticky="nsew", row=cur_row,
                                                                                           column=2, columnspan=1)
        self.toggle_calibration_button = Button(self.window, text="Calibration Off", command=self.toggle_calibration,
                                                background="red", state="disabled")
        self.toggle_calibration_button.grid(sticky="nsew", row=cur_row, column=3, columnspan=1)
        cur_row += 1

        Label(self.window, text="Current file status: ").grid(row=cur_row, column=0, sticky="w")
        self.current_file_label = Label(self.window, text="")
        self.current_file_label.grid(row=cur_row, column=1, sticky="w")
        cur_row += 1

        # label for trigger receive text
        Label(self.window, text="Trigger status: ").grid(row=cur_row, column=0, sticky="w")
        self.received_pulse_label = Label(self.window, text="", wraplength=numberOfScreenUnits)
        self.received_pulse_label.grid(row=cur_row, column=1, sticky="w")
        cur_row += 1

        # label for calibration process status text
        Label(self.window, text="Calibration status: ").grid(row=cur_row, column=0, sticky="w")
        self.calibration_process_stats = Label(self.window, text='')
        self.calibration_process_stats.grid(row=cur_row, column=1, columnspan=4, sticky="w")
        cur_row += 1

        # label for calibration process status text
        Label(self.window, text="Calibration error: ").grid(row=cur_row, column=0, sticky="w")
        self.calibration_error_stats = Label(self.window, text='', wraplength=numberOfScreenUnits)
        self.calibration_error_stats.grid(row=cur_row, column=1, sticky="w")
        cur_row += 1

        # empty row
        Label(self.window, text="").grid(row=cur_row, column=0)
        cur_row += 1

        # record button
        Label(self.window, text="Record: ").grid(sticky="w", row=cur_row, column=0)
        self.record_on = IntVar(value=0)
        self.button_on = Radiobutton(self.window, text="On", selectcolor='green', indicatoron=0,
                                     variable=self.record_on, value=1, command=self.start_record).grid(sticky="nsew",
                                                                                                       row=cur_row,
                                                                                                       column=1)
        self.button_off = Radiobutton(self.window, text="Off", selectcolor='red', indicatoron=0,
                                      variable=self.record_on, value=0).grid(sticky="nsew", row=cur_row + 1, column=1)
        self.release_vid0 = Button(self.window, text="Save Video", command=lambda: self.save_vid(compress=False)).grid(
            sticky="nsew", row=cur_row, column=2)
        self.release_vid1 = Button(self.window, text="Compress & Save Video",
                                   command=lambda: self.save_vid(compress=True)).grid(sticky="nsew", row=cur_row + 1,
                                                                                      column=2)
        self.release_vid2 = Button(self.window, text="Delete Video", command=lambda: self.save_vid(delete=True)).grid(
            sticky="nsew", row=cur_row + 2, column=2)
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
