import os
from tkinter import Entry, Label, Button, Tk
import numpy as np
import threading
import cv2


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
        if delete or (not frames_taken):
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
