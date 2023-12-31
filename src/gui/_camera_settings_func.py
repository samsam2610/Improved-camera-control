import time
from tkinter import Label, Button, Tk
import cv2
import math
from PIL import Image, ImageTk

def show_camera_error(self):
    error_message = "No camera is found! \nPlease initialize camera before setting gain."
    show_error_window(error_message)


def show_video_error(self):
    error_message = "Video writer is not initialized. \nPlease set up video first."
    show_error_window(error_message)


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
    
    self.cam[num].set_gain(float(self.gain[num].get()))
    self.gain_current_label[num]['text'] = f"Current: {self.gain[num].get()} db"
    get_frame_rate_list(self, num)


def set_exposure(self, num):
    # check if camera set up
    if is_camera_set_up(self, num) is False:
        show_camera_error(self)
        return
    
    self.cam[num].set_exposure(float(self.exposure[num].get()))
    self.exposure_current_label[num]['text'] = f"Current: {self.exposure[num].get()} (-{str(round(math.log2(1/float((self.exposure[num].get())))))}) s"
    get_frame_rate_list(self, num)


def get_frame_dimensions(self, num):
    if is_camera_set_up(self, num) is False:
        show_camera_error(self)
        return
    
    frame_dimension = self.cam[num].get_video_format()
    return frame_dimension


def get_formats(self, num):
    # check if camera set up
    if is_camera_set_up(self, num) is False:
        show_camera_error(self)
        return
    
    (width, height) = self.cam[num].get_formats()
    self.format_width[num].set(width)
    self.format_height[num].set(height)


def set_formats(self, num):
    # check if camera set up
    if is_camera_set_up(self, num) is False:
        show_camera_error(self)
        return
   
    width = self.format_width[num].get()
    height = self.format_height[num].get()
    self.cam[num].set_formats(width=width, height=height)
    time.sleep(0.5)  # wait for camera to set format
    frame_rate_list = self.cam[num].get_frame_rate_list()
    self.framerate_list[num]['values'] = frame_rate_list
    get_formats(self, num)
    

def get_fov(self, num):
    crop_details = self.cam_details[str(num)]['crop']
    for fov_label in self.fov_labels:
        self.fov_dict[num][fov_label].set(crop_details[fov_label])


def set_fov(self, num):
    if is_camera_set_up(self, num) is False:
        show_camera_error(self)
        return
    
    for fov_label in self.fov_labels:
        self.cam_details[str(num)]['crop'][fov_label] = self.fov_dict[num][fov_label].get()
    
    self.cam[num].set_crop(top=self.cam_details[str(num)]['crop']['top'],
                           left=self.cam_details[str(num)]['crop']['left'],
                           height=self.cam_details[str(num)]['crop']['height'],
                           width=self.cam_details[str(num)]['crop']['width'])
    
    frame_rate_list = self.cam[num].get_frame_rate_list()
    self.framerate_list[num]['values'] = frame_rate_list


def reset_fov(self, num):
    pass


def check_frame_coord(self, num):
    def click_event(event, x, y, flags, params):

        # checking for left mouse clicks
        if event == cv2.EVENT_LBUTTONDOWN:

            # displaying the coordinates
            # on the Shell
            print(x, ' ', y)

            # displaying the coordinates
            # on the image window
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
            cv2.putText(frame, str(x) + ',' +
                        str(y), (x, y), font,
                        1, (255, 0, 0), 2)
            cv2.imshow(f"Camera {num}", frame)

    frame = self.cam[num].get_image()
    if frame is not None:
        # Create a window and set the mouse callback
        cv2.namedWindow(f"Camera {num}")
        cv2.imshow(f"Camera {num}", frame)
        cv2.setMouseCallback(f"Camera {num}", click_event)
        
        # wait for a key to be pressed to exit
        cv2.waitKey(0)

        # close the window
        cv2.destroyAllWindows()


def track_frame_coord(self, num):
    self.tracking_points[num] = [self.x_tracking_value[num].get(), self.y_tracking_value[num].get()]
    self.tracking_points_status[num]['text'] = f"Tracking point: {self.tracking_points[num][0], self.tracking_points[num][1]}"


def reset_track_frame_coord(self, num):
    self.tracking_points[num] = [None, None]
    self.tracking_points_status[num]['text'] = f"Tracking point: {self.tracking_points[num][0], self.tracking_points[num][1]}"


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
        show_camera_error(self)
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
        set_x_offset(self, None, num)
        set_y_offset(self, None, num)


def toggle_polarity(self, num):
    if is_camera_set_up(self, num) is False:
        self.show_camera_error()
        return
    
    self.cam[num].set_trigger_polarity(value=int(self.polarity[num].get()))


def toggle_flip_vertical(self, num):
    if is_camera_set_up(self, num) is False:
        self.show_camera_error()
        return
    
    self.cam[num].set_flip_vertical(state=self.flip_vertical[num].get())


def set_partial_scan_limit(self, num):
    frame_dimension = get_frame_dimensions(self, (num))
    self.x_offset_scale[num].config(to=1440)
    self.x_offset_spinbox[num].config(to=1440)
    self.y_offset_scale[num].config(to=1080)
    self.y_offset_spinbox[num].config(to=1080)


def get_frame_rate_list(self, num):
    frame_rate_list = self.cam[num].get_frame_rate_list()
    self.framerate_list[num]['values'] = frame_rate_list


def get_current_frame_rate(self, num):
    if is_camera_set_up(self, num) is False:
        show_camera_error(self)
        return
    current_frame_rate = self.cam[num].get_frame_rate()
    self.current_framerate[num].set(int(current_frame_rate))
    return current_frame_rate


def set_frame_rate(self, num, framerate=None, initCamera=False):
    if is_camera_set_up(self, num) is False:
        show_camera_error(self)
        return
    
    if framerate is None:
        selected_frame_rate = self.framerate_list[num].get()
    else:
        selected_frame_rate = framerate
    if initCamera:
        result = self.cam[num].set_frame_rate(int(selected_frame_rate))
        self.framerate[num].set(selected_frame_rate)
    else:
        self.cam[num].close()
        result = self.cam[num].set_frame_rate(int(selected_frame_rate))
        self.framerate[num].set(selected_frame_rate)
        current_framerate = get_current_frame_rate(self, num)
        self.cam[num].start()
        print(f'Selected: {selected_frame_rate}. Frame rate set to {current_framerate} fps. Result: {result}')
