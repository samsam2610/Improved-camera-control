import os
from tkinter import Entry, Label, Button, Tk
import numpy as np
import threading
import cv2
import ffmpy


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
    # self.frame_times = []
    
    for i in range(len(self.cam)):
        self.ts_file.append(self.vid_file[i].replace('.avi', '.npy'))
        self.ts_file[i] = self.ts_file[i].replace(self.cam_name_no_space[i], 'TIMESTAMPS_' + self.cam_name_no_space[i])
        self.ts_file_csv.append(self.vid_file[i].replace('.avi', '.csv'))
        self.ts_file_csv[i] = self.ts_file_csv[i].replace(self.cam_name_no_space[i],
                                                          'TIMESTAMPS_' + self.cam_name_no_space[i])
        self.current_file_label['text'] = subject_name
        # self.frame_times.append([])
    
    # empty out the video's stat message
    self.save_msg = ""


def save_vid(self, compress=False, delete=False):
    self.toggle_video_recording(force_termination=True)
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
        if delete or (not frames_taken):
            os.remove(self.vid_file[i])
        else:
            np.save(str(self.ts_file[i]), np.array(self.frame_times[i]))
            np.savetxt(str(self.ts_file_csv[i]), np.array(self.frame_times[i]), delimiter=",")
            saved_files.append(self.vid_file[i])
            saved_files.append(self.ts_file[i])
            if compress:
                threading.Thread(target=lambda: compress_vid(self, i)).start()
    
    if len(saved_files) > 0:
        if len(self.frame_times) > 1:
            cam0_times = np.array(self.frame_times[0])
            cam1_times = np.array(self.frame_times[1])
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

    jitter1 = np.diff(cam1)
    jitter2 = np.diff(cam2)

    if frameDiff > 0:
        temp_text = "Missing" + str(frameDiff) + "frames\n"
        return_text.append(temp_text)
    else:
        temp_text = 'No missing frames'
        return_text.append(temp_text)
    
    tolerance = (1 / frameRate) * 0.5
    
    # Find frames that are too long or short
    droppedFrames1 = np.where(
        np.logical_or(jitter1 < 1 / frameRate - tolerance, jitter1 > 1 / frameRate + tolerance))
    droppedFrames2 = np.where(
        np.logical_or(jitter2 < 1 / frameRate - tolerance, jitter2 > 1 / frameRate + tolerance))
    
    # if np.size(droppedFrames1) > 0:
    #     temp_text = "These frames may not be exactly synchronized (jitter1): " + str(droppedFrames1)
    # else:
    #     temp_text = "Frames cam 1 are synced!"
    # return_text.append(temp_text)
    #
    # if np.size(droppedFrames2) > 0:
    #     temp_text = "These frames may not be exactly synchronized (jitter2): " + str(droppedFrames2)
    # else:
    #     temp_text = "Frames from cam 2 are synced!"
    # return_text.append(temp_text)
    
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

