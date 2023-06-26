"""
Camera Control
Copyright M. Mathis Lab
Written by  Gary Kane - https://github.com/gkane26
post-doctoral fellow @ the Adaptive Motor Control Lab
https://github.com/AdaptiveMotorControlLab

GUI to record from imaging source cameras during experiments

Modified by people at Dr. Tresch's lab
"""

from tkinter import Entry, Label, Button, StringVar, IntVar, Tk, END, Radiobutton, filedialog, ttk
import numpy as np
import datetime
import os, sys
from pathlib import Path
import math
import time
import cv2
import ffmpy
import threading
import json
import argparse

fourcc_codes = ["DIVX", "XVID", "Y800"]


class CamGUI(object):

    def __init__(self, debug_mode=False, init_cam_bool=True):
        self.running_config = {}
        self.running_config['debug_mode'] = debug_mode
        self.running_config['init_cam_bool'] = init_cam_bool
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
        self.selectCams()

    def browse_output(self):
        filepath = filedialog.askdirectory(initialdir='/')
        self.dir_output.set(filepath)
        
    def browse_codec(self, event):
        self.video_codec =  self.video_codec_entry.get()
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
            Button(cam_on_window, text="Ok", command=lambda:cam_on_window.quit()).pack()
            cam_on_window.mainloop()
            cam_on_window.destroy()
            return

        if len(self.cam) >= num+1:
            self.cam[num].close()
            self.cam[num] = None

        # create camera object
        cam_num = self.camera[num].get()
        names = np.array(self.cam_names)
        cam_num = np.where(names == cam_num)[0][0]
        if len(self.cam) >= num+1:
            self.cam_name[num] = names[cam_num]
            self.cam[num] = ICCam(cam_num)
        else:
            self.cam_name.append(names[cam_num])
            self.cam.append(ICCam(cam_num))
        self.cam[num].start()
        self.exposure[num].set(self.cam[num].get_exposure())
        self.gain[num].set(self.cam[num].get_gain())
        # reset output directory
        self.dir_output.set(self.output_entry['values'][cam_num])
        exposure_text = f'real_exposure: {self.exposure[num].get()}' 
        self.current_exposure[num]['text'] = exposure_text
        setup_window.destroy()
    
    def check_frame(self, timeStampFile1, timeStampFile2, frameRate):
        #timestamps should be in seconds
        return_text=[]
        frameRate = float(frameRate)
        cam1 = timeStampFile1
        cam2 = timeStampFile2
        
        #need to do this only when we're doing sync with synapse
        cam1 = cam1[1:]
        cam2 = cam2[1:]

        #Normalize
        cam1 = cam1 - cam1[0]
        cam2 = cam2 - cam2[0]
        
        # Find how many frames belong in both videos based on the longer one
        # One shorter video indicates frame drops
        numFrames = np.maximum(np.size(cam1),np.size(cam2))
        
        #Number of missing frames
        frameDiff = abs(np.size(cam1) - np.size(cam2))
        if frameDiff > 0: # if there are missing frames

            temp_text = "Missing" + str(frameDiff) + "frames\n"
            return_text.append(temp_text)

        elif frameDiff == 0: #if there are same frames in both videos, check jitter
            jitter1 = np.diff(cam1)
            jitter2 = np.diff(cam2)
            temp_text='No missing frames'
            return_text.append(temp_text)

            tolerance = (1/frameRate)*.5
            
            #Find frames that are too long or short
            droppedFrames = np.where(np.logical_or(jitter1 < 1/frameRate - tolerance, jitter1 > 1/frameRate + tolerance))
            #droppedFrames2 = np.where(np.logical_or(jitter2 < 1/frameRate - tolerance, jitter2 > 1/frameRate + tolerance))
            if np.size(droppedFrames) > 0:
                temp_text = "These frames may not be exactly synchronized: " + str(droppedFrames)
            else: 
                temp_text = "frames are synced!"
            return_text.append(temp_text)

        return return_text

    def set_gain(self, num):
        # check if camera set up
        if len(self.cam) < num+1:
            cam_check_window = Tk()
            Label(cam_check_window, text="No camera is found! \nPlease initialize camera before setting gain.").pack()
            Button(cam_check_window, text="Ok", command=lambda:cam_check_window.quit()).pack()
            cam_check_window.mainloop()
            cam_check_window.destroy()
        else:
            self.cam[num].set_gain(int(self.gain[num].get()))

    def set_exposure(self, num):
        # check if camera set up
        if len(self.cam) < num+1:
            cam_check_window = Tk()
            Label(cam_check_window, text="No camera is found! \nPlease initialize camera before setting exposure.").pack()
            Button(cam_check_window, text="Ok", command=lambda:cam_check_window.quit()).pack()
            cam_check_window.mainloop()
            cam_check_window.destroy()
        else:
            self.cam[num].set_exposure(int(self.exposure[num].get()))
            exposure_text = f'real_exposure: {self.exposure[num].get()}'
            self.current_exposure[num]['text'] = exposure_text


    def get_formats(self, num):
        # check if camera set up
        if len(self.cam) < num+1:
            cam_check_window = Tk()
            Label(cam_check_window, text="No camera is found! \nPlease initialize camera before setting exposure.").pack()
            Button(cam_check_window, text="Ok", command=lambda:cam_check_window.quit()).pack()
            cam_check_window.mainloop()
            cam_check_window.destroy()
        else:
            return self.cam[num].get_formats()


    def set_formats(self, num):
        # check if camera set up
        if len(self.cam) < num+1:
            cam_check_window = Tk()
            Label(cam_check_window, text="No camera is found! \nPlease initialize camera before setting exposure.").pack()
            Button(cam_check_window, text="Ok", command=lambda:cam_check_window.quit()).pack()
            cam_check_window.mainloop()
            cam_check_window.destroy()
        else:
            self.cam[num].set_formats(str(self.formats[num].get()))


    def lv_interrupt(self, task_handle, signal_type, callback_data):

        try:
            return_code = 0
            if self.record_on.get():
                self.lv_ts.append(time.time())
                print("\nRecording timestamp %d" % len(self.lv_ts))
        except Exception as e:
            print(e)
            return_code = 1
        finally:
            return return_code
            
    def sync_setup(self):

        if len(self.vid_out) > 0:
            vid_open_window = Tk()
            Label(vid_open_window, text="Video is currently open! \nPlease release the current video (click 'Save Video', even if no frames have been recorded) before setting up a new one.").pack()
            Button(vid_open_window, text="Ok", command=lambda:vid_open_window.quit()).pack()
            vid_open_window.mainloop()
            vid_open_window.destroy()
            return

        # check if camera set up
        if len(self.cam) == 0:
            cam_check_window = Tk()
            Label(cam_check_window, text="No camera is found! \nPlease initialize camera before setting up video.").pack()
            Button(cam_check_window, text="Ok", command=lambda:cam_check_window.quit()).pack()
            cam_check_window.mainloop()
            cam_check_window.destroy()
        else:
            self.trigger_on = 1
            da_fps = str(self.fps.get())
            month = datetime.datetime.now().month
            month = str(month) if month >= 10 else '0'+str(month)
            day = datetime.datetime.now().day
            day = str(day) if day >= 10 else '0'+str(day)
            year = str(datetime.datetime.now().year)
            date = year+'-'+month+'-'+day
            self.out_dir = self.dir_output.get()
            if not os.path.isdir(os.path.normpath(self.out_dir)):
                os.makedirs(os.path.normpath(self.out_dir))

            # create output file names
            self.vid_file = []
            self.base_name = []
            self.ts_file = []
            self.ts_filecsv = []
            cam_name_nospace = []
            this_row = 3
            
            # subject_name, dir_name = generate_folder()
            subject_name = 'sam'
            dir_name = "E:\\tmp"
            for i in range(len(self.cam)):
                temp_exposure = str(self.exposure[i].get())
                temp_gain = str(self.gain[i].get())
                cam_name_nospace.append(self.cam_name[i].replace(' ', ''))
                self.base_name.append(cam_name_nospace[i] + '_' + subject_name + '_' + da_fps + 'f' + temp_exposure + 'e' + temp_gain + 'g')
                self.vid_file.append(os.path.normpath(dir_name + '/' + self.base_name[i] + '.avi'))

                # check if file exists, ask to overwrite or change attempt number if it does
                if i==0:
                    self.overwrite = False
                    if os.path.isfile(self.vid_file[i]):
                        self.ask_overwrite = Tk()
                        def quit_overwrite(ow):
                            self.overwrite=ow
                            self.ask_overwrite.quit()
                        Label(self.ask_overwrite, text="File already exists with attempt number = " + self.attempt.get() + ".\nWould you like to overwrite the file? ").pack()
                        Button(self.ask_overwrite, text="Overwrite", command=lambda:quit_overwrite(True)).pack()
                        Button(self.ask_overwrite, text="Cancel & pick new attempt number", command=lambda:quit_overwrite(False)).pack()
                        self.ask_overwrite.mainloop()
                        self.ask_overwrite.destroy()

                        if self.overwrite:
                            self.vid_file[i] = os.path.normpath(self.out_dir +'/' + self.base_name[i] + '.avi')
                        else:
                            return
                else:
                    #self.vid_file[i] = self.vid_file[0].replace(cam_name_nospace[0], cam_name_nospace[i])
                    print('')

                self.ts_file.append(self.vid_file[i].replace('.avi', '.npy'))
                self.ts_file[i] = self.ts_file[i].replace(cam_name_nospace[i], 'TIMESTAMPS_'+cam_name_nospace[i])
                self.ts_filecsv.append(self.vid_file[i].replace('.avi','.csv'))
                self.ts_filecsv[i] = self.ts_filecsv[i].replace(cam_name_nospace[i],'TIMESTAMPS_'+cam_name_nospace[i])
                self.current_file_label['text'] = subject_name

                # create video writer
                dim = self.cam[i].get_image_dimensions()
                if len(self.vid_out) >= i+1:
                    self.vid_out[i] = cv2.VideoWriter(self.vid_file[i], cv2.VideoWriter_fourcc(*self.video_codec), int(self.fps.get()), dim)
                else:
                    self.vid_out.append(cv2.VideoWriter(self.vid_file[i], cv2.VideoWriter_fourcc(*self.video_codec), int(self.fps.get()), dim))

                if self.lv_task is not None:
                    self.lv_file = self.ts_file[0].replace('TIMESTAMPS_'+cam_name_nospace[0], 'LABVIEW')

                # create video writer
                self.frame_times = []
                for i in self.ts_file:
                    self.frame_times.append([])
                self.lv_ts = []
                self.setup = True

    def set_up_vid(self):

        if len(self.vid_out) > 0:
            vid_open_window = Tk()
            Label(vid_open_window, text="Video is currently open! \nPlease release the current video (click 'Save Video', even if no frames have been recorded) before setting up a new one.").pack()
            Button(vid_open_window, text="Ok", command=lambda:vid_open_window.quit()).pack()
            vid_open_window.mainloop()
            vid_open_window.destroy()
            return

        # check if camera set up
        if len(self.cam) == 0:
            cam_check_window = Tk()
            Label(cam_check_window, text="No camera is found! \nPlease initialize camera before setting up video.").pack()
            Button(cam_check_window, text="Ok", command=lambda:cam_check_window.quit()).pack()
            cam_check_window.mainloop()
            cam_check_window.destroy()
        else:
            self.trigger_on=0
            da_fps = str(self.fps.get())
            month = datetime.datetime.now().month
            month = str(month) if month >= 10 else '0'+str(month)
            day = datetime.datetime.now().day
            day = str(day) if day >= 10 else '0'+str(day)
            year = str(datetime.datetime.now().year)
            date = year+'-'+month+'-'+day
            self.out_dir = self.dir_output.get()
            if not os.path.isdir(os.path.normpath(self.out_dir)):
                os.makedirs(os.path.normpath(self.out_dir))

            # create output file names
            self.vid_file = []
            self.base_name = []
            self.ts_file = []
            cam_name_nospace = []
            this_row = 3
            for i in range(len(self.cam)):
                temp_exposure = str(self.exposure[i].get())
                temp_gain = str(self.gain[i].get())
                cam_name_nospace.append(self.cam_name[i].replace(' ', ''))
                self.base_name.append(cam_name_nospace[i] + '_' + self.subject.get() + '_' + date + '_' + da_fps + 'f' + temp_exposure + 'e' + temp_gain + 'g')
                self.vid_file.append(os.path.normpath(self.out_dir + '/' + self.base_name[i] + self.attempt.get() + '.avi'))

                # check if file exists, ask to overwrite or change attempt number if it does
                if i==0:
                    self.overwrite = False
                    if os.path.isfile(self.vid_file[i]):
                        self.ask_overwrite = Tk()
                        def quit_overwrite(ow):
                            self.overwrite=ow
                            self.ask_overwrite.quit()
                        Label(self.ask_overwrite, text="File already exists with attempt number = " + self.attempt.get() + ".\nWould you like to overwrite the file? ").pack()
                        Button(self.ask_overwrite, text="Overwrite", command=lambda:quit_overwrite(True)).pack()
                        Button(self.ask_overwrite, text="Cancel & pick new attempt number", command=lambda:quit_overwrite(False)).pack()
                        self.ask_overwrite.mainloop()
                        self.ask_overwrite.destroy()

                        if self.overwrite:
                            self.vid_file[i] = os.path.normpath(self.out_dir +'/' + self.base_name[i] + self.attempt.get() + '.avi')
                        else:
                            return
                else:
                    #self.vid_file[i] = self.vid_file[0].replace(cam_name_nospace[0], cam_name_nospace[i])
                    print('')

                self.ts_file.append(self.vid_file[i].replace('.avi', '.npy'))
                self.ts_file[i] = self.ts_file[i].replace(cam_name_nospace[i], 'TIMESTAMPS_'+cam_name_nospace[i])
                self.current_file_label['text'] = self.subject.get() + '_' + date + '_' + self.attempt.get()

                # create video writer
                dim = self.cam[i].get_image_dimensions()
                if len(self.vid_out) >= i+1:
                    self.vid_out[i] = cv2.VideoWriter(self.vid_file[i], cv2.VideoWriter_fourcc(*self.video_codec), int(self.fps.get()), dim)
                else:
                    self.vid_out.append(cv2.VideoWriter(self.vid_file[i], cv2.VideoWriter_fourcc(*self.video_codec), int(self.fps.get()), dim))

                if self.lv_task is not None:
                    self.lv_file = self.ts_file[0].replace('TIMESTAMPS_'+cam_name_nospace[0], 'LABVIEW')

                # create video writer
                self.frame_times = []
                for i in self.ts_file:
                    self.frame_times.append([])
                self.lv_ts = []
                self.setup = True

    def record_on_thread(self, num):
        fps = int(self.fps.get())
        if self.trigger_on==1:
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
                print(e)

        start_time = time.perf_counter()
        next_frame = start_time

        try:
            while self.record_on.get():
                if time.perf_counter() >= next_frame:
                    self.frame_times[num].append(time.perf_counter())
                    self.vid_out[num].write(self.cam[num].get_image())
                    next_frame = max(next_frame + 1.0/fps, self.frame_times[num][-1] + 0.5/fps)
        except Exception as e:
            print(e)
            
    def calibrate_on_thread(self, num):
        fps = int(self.fps.get()) 
        start_time = time.perf_counter()
        next_frame = start_time

        try:
            while self.record_on.get():
                if time.perf_counter() >= next_frame:
                    self.vid_out[num].write(self.cam[num].get_image())
                    next_frame = max(next_frame + 1.0/fps, self.frame_times[num][-1] + 0.5/fps)
        except Exception as e:
            print(e)

    def start_calibration_process(self):
        from src.aniposelib.cameras import CameraGroup
        self.calibration_process_stats['text'] = 'Initializing calibration process...'
        from utils import load_config, get_calibration_board
        if self.running_config['debug_mode']:
            self.calibration_process_stats['text'] = 'Looking for config.toml directory ...'
            path = Path(os.path.realpath(__file__))
            # Navigate to the outer parent directory and join the filename
            config_toml_path = os.path.normpath(str(path.parents[2] / 'config-files' / 'config.toml'))
            config_anipose = load_config(config_toml_path)
            self.calibration_process_stats['text'] = 'Successfully found and loaded config. Determining calibration board ...'
            board_calibration = get_calibration_board(config=config_anipose)
            
            self.calibration_process_stats['text'] = 'Loaded calibration board. Initializing camera calibration objects ...'
            from src.aniposelib.cameras import CameraGroup
            self.cgroup = CameraGroup.from_names(self.cam_names)
            
            self.calibration_process_stats['text'] = 'Initialized camera object.'
    
    def start_record(self):
        if len(self.vid_out) == 0:
            remind_vid_window = Tk()
            Label(remind_vid_window, text="VideoWriter not initialized! \nPlease set up video and try again.").pack()
            Button(remind_vid_window, text="Ok", command=lambda:remind_vid_window.quit()).pack()
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
            Label(not_initialized_window, text="Video writer is not initialized. Please set up first to record a video.").pack()
            Button(not_initialized_window, text="Ok", command=lambda:not_initialized_window.quit()).pack()
            not_initialized_window.mainloop()
            not_initialized_window.destroy()

        else:

            # check for frames before saving. if any video has not taken frames, delete all videos
            frames_taken = all([len(i) > 0 for i in self.frame_times])

            # release video writer (saves file).
            # if no frames taken or delete specified, delete the file and do not save timestamp files; otherwise, save timestamp files.
            for i in range(len(self.vid_out)):
                self.vid_out[i].release()
                self.vid_out[i] = None
                if (delete) or (not frames_taken):
                    os.remove(self.vid_file[i])
                else:
                    np.save(str(self.ts_file[i]), np.array(self.frame_times[i]))
                    np.savetxt(str(self.ts_filecsv[i]),np.array(self.frame_times[i]),delimiter=",")
                    saved_files.append(self.vid_file[i])
                    saved_files.append(self.ts_file[i])
                    if compress:
                        threading.Thread(target=lambda:self.compress_vid(i)).start()

        if (len(self.lv_ts) > 0) and (not delete):
            np.save(str(self.lv_file), np.array(self.lv_ts))
            saved_files.append(self.lv_file)

        save_msg = ""
        if len(saved_files) > 0:
            if len(self.frame_times) > 1:
                cam0_times = np.array(self.frame_times[0])
                cam1_times = np.array(self.frame_times[1])
                fps = int(self.fps.get())
                check_frame_text = self.check_frame(cam0_times, cam1_times, fps)
                for texty in check_frame_text:
                    save_msg+= texty + '\n'
            save_msg += "The following files have been saved:"
            for i in saved_files:
                save_msg += "\n" + i

        elif delete:
            save_msg = "Video has been deleted, please set up a new video to take another recording."
        elif not frames_taken:
            save_msg = "Video was initialized but no frames were recorded.\nVideo has been deleted, please set up a new video to take another recording."

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
            self.number_of_cams_entry = Entry(select_cams_window, textvariable=self.number_of_cams).grid(sticky="nsew", row=0, column=1)
            Button(select_cams_window, text="Set Cameras", command=select_cams_window.quit).grid(sticky="nsew", row=1, column=0, columnspan=2)
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
        self.camera = []
        self.camera_entry = []
        self.current_exposure=[]
        self.exposure = []
        self.exposure_entry = []
        self.gain = []
        self.gain_entry = []
        self.format_list = ['Y16 (256x4)', 'Y16 (320x240)', 'Y16 (320x480)', 'Y16 (352x240)', 'Y16 (352x288)', 'Y16 (384x288)', 'Y16 (640x240)', 'Y16 (640x288)', 'Y16 (640x480)', 'Y16 (704x576)', 'Y16 (720x240)', 'Y16 (720x288)', 'Y16 (720x480)', 'Y16 (720x540)', 'Y16 (720x576)', 'Y16 (768x576)', 'Y16 (1024x768)', 'Y16 (1280x960)', 'Y16 (1280x1024)', 'Y16 (1440x1080)', 'Y800 (256x4)', 'Y800 (320x240)', 'Y800 (320x480)', 'Y800 (352x240)', 'Y800 (352x288)', 'Y800 (384x288)', 'Y800 (640x240)', 'Y800 (640x288)', 'Y800 (640x480)', 'Y800 (704x576)', 'Y800 (720x240)', 'Y800 (720x288)', 'Y800 (720x480)', 'Y800 (720x540)', 'Y800 (720x576)', 'Y800 (768x576)', 'Y800 (1024x768)', 'Y800 (1280x960)', 'Y800 (1280x1024)', 'Y800 (1440x1080)', 'RGB24 (256x4)', 'RGB24 (320x240)', 'RGB24 (320x480)', 'RGB24 (352x240)', 'RGB24 (352x288)', 'RGB24 (384x288)', 'RGB24 (640x240)', 'RGB24 (640x288)', 'RGB24 (640x480)', 'RGB24 (704x576)', 'RGB24 (720x240)', 'RGB24 (720x288)', 'RGB24 (720x480)', 'RGB24 (720x540)', 'RGB24 (720x576)', 'RGB24 (768x576)', 'RGB24 (1024x768)', 'RGB24 (1280x960)', 'RGB24 (1280x1024)', 'RGB24 (1440x1080)']
        self.formats = []
        self.format_entry = []

        if not isinstance(self.number_of_cams, int):
           self.number_of_cams = int(self.number_of_cams.get()) 

        for i in range(self.number_of_cams):
            # drop down menu to select camera
            Label(self.window, text="Camera "+str(i+1)+": ").grid(sticky="w", row=cur_row, column=0)
            self.camera.append(StringVar())
            self.camera_entry.append(ttk.Combobox(self.window, textvariable=self.camera[i]))
            self.camera_entry[i]['values'] = self.cam_names
            self.camera_entry[i].current(i)
            self.camera_entry[i].grid(row=cur_row, column=1)

            # inialize camera button
            if i==0:
                Button(self.window, text="Initialize Camera 1", command=lambda:self.init_cam(0)).grid(sticky="nsew", row=cur_row+1, column=0, columnspan=2)
            elif i==1:
                Button(self.window, text="Initialize Camera 2", command=lambda:self.init_cam(1)).grid(sticky="nsew", row=cur_row+1, column=0, columnspan=2)
            elif i==2:
                Button(self.window, text="Initialize Camera 3", command=lambda:self.init_cam(2)).grid(sticky="nsew", row=cur_row+1, column=0, columnspan=2)

            # change exposure
            self.exposure.append(StringVar())
            self.exposure_entry.append(Entry(self.window, textvariable=self.exposure[i]))
            self.exposure_entry[i].grid(sticky="nsew", row=cur_row, column=2)
            if i==0:
                Button(self.window, text="Set Exposure 1", command=lambda:self.set_exposure(0)).grid(sticky="nsew", row=cur_row+1, column=2)
            elif i==1:
                Button(self.window, text="Set Exposure 2", command=lambda:self.set_exposure(1)).grid(sticky="nsew", row=cur_row+1, column=2)
            elif i==2:
                Button(self.window, text="Set Exposure 3", command=lambda:self.set_exposure(2)).grid(sticky="nsew", row=cur_row+1, column=2)

            # change gain
            self.gain.append(StringVar())
            self.gain_entry.append(Entry(self.window, textvariable=self.gain[i]))
            self.gain_entry[i].grid(sticky="nsew", row=cur_row, column=3)
            if i==0:
                Button(self.window, text="Set Gain 1", command=lambda:self.set_gain(0)).grid(sticky="nsew", row=cur_row+1, column=3)
            elif i==1:
                Button(self.window, text="Set Gain 2", command=lambda:self.set_gain(1)).grid(sticky="nsew", row=cur_row+1, column=3)
            elif i==2:
                Button(self.window, text="Set Gain 3", command=lambda:self.set_gain(2)).grid(sticky="nsew", row=cur_row+1, column=3)
            
            #format
            Label(self.window, text="Format "+str(i+1)+": ").grid(sticky="w", row=cur_row, column=4)
            self.formats.append(StringVar())
            self.format_entry.append(ttk.Combobox(self.window, textvariable=self.formats[i]))
            self.format_entry[i]['values'] = self.format_list
            self.format_entry[i].current(i)
            self.format_entry[i].grid(row=cur_row, column=4)

            # inialize camera button
            if i==0:
                Button(self.window, text="Set format", command=lambda:self.set_formats(0)).grid(sticky="nsew", row=cur_row+1, column=4)
            elif i==1:
                Button(self.window, text="Set format", command=lambda:self.set_formats(1)).grid(sticky="nsew", row=cur_row+1, column=4)
            elif i==2:
                Button(self.window, text="Set format", command=lambda:self.set_formats(2)).grid(sticky="nsew", row=cur_row+1, column=0)
            cur_row += 1
            
            
            Label(self.window, text='').grid(row=cur_row+1, column=2, sticky="w")
            self.current_exposure.append(Label(self.window, text=""))
            self.current_exposure[i].grid(row=cur_row+1, column=2, sticky="w")
            cur_row += 1

            # empty row
            Label(self.window, text="").grid(row=cur_row+2, column=0)

            # end of camera loop
            cur_row = cur_row+3

        # empty row
        Label(self.window, text="").grid(row=cur_row, column=0)
        cur_row+=1

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
        self.attempt_entry['values'] = tuple(range(1,10))
        self.attempt_entry.grid(row=cur_row, column=1)
        cur_row += 1

        # type frame rate
        Label(self.window, text="Frame Rate: ").grid(sticky="w", row=cur_row, column=0)
        self.fps = StringVar()
        self.fps_entry = Entry(self.window, textvariable=self.fps)
        self.fps_entry.insert(END, '200')
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
                                              value=fourcc_codes,
                                              state="readonly")
        self.video_codec_entry.set("XVID") # default codec
        self.video_codec_entry.bind("<<ComboboxSelected>>", self.browse_codec)
        self.video_codec_entry.grid(row=cur_row, column=4)
        cur_row += 1

        # set up video
        Button(self.window, text="Set Up Video", command=self.set_up_vid).grid(sticky="nsew", row=cur_row, column=0, columnspan=1)        
        Button(self.window, text="SYNC_WITH_SYNAPSE", command=self.sync_setup).grid(sticky="nsew", row=cur_row, column=1, columnspan=1)
        Button(self.window, text="Start Calibration Process", command=self.start_calibration_process).grid(sticky="nsew", row=cur_row, column=2, columnspan=1) 
        cur_row += 1

        Label(self.window, text="Current file status: ").grid(row=cur_row, column=0, sticky="w")
        self.current_file_label = Label(self.window, text="")
        self.current_file_label.grid(row=cur_row, column=1, sticky="w")
        cur_row += 1

        # label for trigger receive text
        Label(self.window, text="Trigger status: ").grid(row=cur_row, column=0, sticky="w")
        self.received_pulse_label = Label(self.window, text="")
        self.received_pulse_label.grid(row=cur_row, column=1, sticky="w")
        cur_row += 1

        # label for calibration process status text
        Label(self.window, text="Calibration status: ").grid(row=cur_row, column=0, sticky="w")
        self.calibration_process_stats = Label(self.window, text='')
        self.calibration_process_stats.grid(row=cur_row, column=1, sticky="w") 
        cur_row += 1

        # empty row
        Label(self.window, text="").grid(row=cur_row, column=0)
        cur_row += 1

        # record button
        Label(self.window, text="Record: ").grid(sticky="w",row=cur_row, column=0)
        self.record_on = IntVar(value=0)
        self.button_on = Radiobutton(self.window, text="On", selectcolor='green', indicatoron=0, variable=self.record_on, value=1, command=self.start_record).grid(sticky="nsew", row=cur_row, column=1)
        self.button_off = Radiobutton(self.window, text="Off", selectcolor='red', indicatoron=0, variable=self.record_on, value=0).grid(sticky="nsew", row=cur_row+1, column=1)
        self.release_vid0 = Button(self.window, text="Save Video", command=lambda:self.save_vid(compress=False)).grid(sticky="nsew", row=cur_row, column=2)
        self.release_vid1 = Button(self.window, text="Compress & Save Video", command=lambda:self.save_vid(compress=True)).grid(sticky="nsew", row=cur_row+1, column=2)
        self.release_vid2 = Button(self.window, text="Delete Video", command=lambda:self.save_vid(delete=True)).grid(sticky="nsew", row=cur_row+2, column=2)
        cur_row += 3

        # close window/reset GUI
        Label(self.window).grid(row=cur_row, column=0)
        self.reset_button = Button(self.window, text="Reset GUI", command=self.selectCams).grid(sticky="nsew", row=cur_row+1, column=0, columnspan=2)
        self.close_button = Button(self.window, text="Close", command=self.close_window).grid(sticky="nsew", row=cur_row+2, column=0, columnspan=2)


    def runGUI(self):
        self.window.mainloop()


if __name__ == "__main__":
    # Create an argument parser
    parser = argparse.ArgumentParser(description="CamGUI")

    # Add optional arguments
    parser.add_argument("-d", "--debug", action="store_true", dest='debug_mode', help="Enable debug mode")
    parser.add_argument("-ni", "--no-init-cam", action="store_false", dest="init_cam_bool", help="Disable camera initialization")

    # Parse the command-line arguments
    args = parser.parse_args()

    # Create an instance of the CamGUI class with the parsed arguments
    cam_gui = CamGUI(debug_mode=args.debug_mode, init_cam_bool=args.init_cam_bool)
    cam_gui.runGUI() 