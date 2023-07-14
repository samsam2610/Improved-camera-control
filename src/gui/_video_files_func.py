import os
from tkinter import Entry, Label, Button, Tk

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
