from camera_control_GUI_improved import CamGUI
import time
class CamGUI_Tests(CamGUI):
    def __init__(self, debug_mode=False, init_cam_bool=True):
        super().__init__(debug_mode, init_cam_bool)
        
    def init_cams(self):
        for i, button in enumerate(self.camera_init_button):
            time.sleep(1)
            button.invoke()
            
    def show_calibration_live(self):
        time.sleep(1)
        self.reprojection_checkbutton.invoke()
        # time.sleep(1)
        # self.test_calibration_live_button.invoke()
       
    def test_experimental_func(self):
        time.sleep(1)
        self.setup_trigger_recording_button.invoke()
        
    def auto_init_cam(self):
        print("Initialize camera in test mode")
        
        self.window.after(2000, self.init_cams)
        self.window.after(3000, self.show_calibration_live)
        self.window.after(1000, self.test_experimental_func)
        self.window.mainloop()
 

