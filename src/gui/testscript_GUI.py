from camera_control_GUI_improved import CamGUI
import time
class CamGUI_Tests(CamGUI):
    def __init__(self, debug_mode=False, init_cam_bool=True):
        super().__init__(debug_mode, init_cam_bool)
        
    def init_cams(self):
        for i, button in enumerate(self.camera_init_button):
            time.sleep(1)
            button.invoke()

    def auto_init_cam(self):
        print("Initialize camera in test mode")
        
        self.window.after(2, self.init_cams)
        self.window.mainloop()
 

