from camera_control_GUI_improved import CamGUI


def auto_initialize(gui_object: CamGUI):
    try:
        gui_object.camera_init_button[0].invoke()
        gui_object.camera_init_button[1].invoke()
        
        return 0
    except:
        return 1
