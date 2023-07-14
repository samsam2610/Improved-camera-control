
from tkinter import Label, Button, Tk


def show_camera_error(self):
    error_message = "No camera is found! \nPlease initialize camera before setting gain."
    self.show_error_window(error_message)
    
    
def show_video_error(self):
    error_message = "Video writer is not initialized. \nPlease set up video first."
    self.show_error_window(error_message)


def show_error_window(message):
    error_window = Tk()
    Label(error_window, text=message).pack()
    Button(error_window, text="Ok", command=error_window.destroy).pack()
    error_window.mainloop()
    error_window.destroy()
    
    
def is_camera_set_up(self, num):
    return self.cam[num] is not None
    
    
def set_gain(self, num):
    if is_camera_set_up(self, num) is False:
        self.show_camera_error()
        return
        
    self.cam[num].set_gain(int(self.gain[num].get()))
    self.get_frame_rate_list(num)
    
    
def set_exposure(self, num):
    # check if camera set up
    if is_camera_set_up(self, num) is False:
        self.show_camera_error()
        return
    
    self.cam[num].set_exposure(float(self.exposure[num].get()))
    self.get_frame_rate_list(num)


def get_frame_dimensions(self, num):
    if is_camera_set_up(self, num) is False:
        self.show_camera_error()
        return
    
    frame_dimension = self.cam[num].get_video_format()
    return frame_dimension
    
    
def get_formats(self, num):
    # check if camera set up
    if is_camera_set_up(self, num) is False:
        self.show_camera_error()
        return

    return self.cam[num].get_formats()


def set_formats(self, num):
    # check if camera set up
    if is_camera_set_up(self, num) is False:
        self.show_camera_error()
        return

    self.cam[num].set_formats(str(self.formats[num].get()))
    self.get_frame_rate_list(num)


def get_fov(self, num):
    crop_details = self.cam_details[str(num)]['crop']
    for fov_label in self.fov_labels:
        self.fov_dict[num][fov_label].set(crop_details[fov_label])


def set_fov(self, num):
    if is_camera_set_up(self, num) is False:
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
    if is_camera_set_up(self, num) is False:
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
    if is_camera_set_up(self, num) is False:
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
    if is_camera_set_up(self, num) is False:
        self.show_camera_error()
        return
    current_frame_rate = self.cam[num].get_frame_rate()
    self.current_framerate[num].set(int(current_frame_rate))
    return current_frame_rate
    
    
def set_frame_rate(self, num, framerate=None, initCamera=False):
    if is_camera_set_up(self, num) is False:
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
