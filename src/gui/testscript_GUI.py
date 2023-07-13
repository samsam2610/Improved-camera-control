from camera_control_GUI_improved import CamGUI

class CamGUI_auto(object):
    def __init__(self, CamGUI_instance: CamGUI):
        self.CamGUI = CamGUI_instance
        
    def auto_init_cam(self):
        delay = 1000  # Delay between invocations in milliseconds

        for i, button in enumerate(self.CamGUI.cam_init_button):
            self.CamGUI.window.after(delay * i, button.invoke)
    
