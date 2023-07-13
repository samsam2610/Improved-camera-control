from camera_control_GUI_improved import CamGUI
import time
class CamGUI_Tests(CamGUI):
    def __init__(self, debug_mode=False, init_cam_bool=True):
        super().__init__(debug_mode, init_cam_bool)
        
    def auto_init_cam(self):
        delay = 1000  # Delay between invocations in milliseconds
        self.window.mainloop()
        time.sleep(2)
        for i, button in enumerate(self.cam_init_button):
            self.window.after(delay * i, button.invoke)
    
