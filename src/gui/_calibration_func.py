import cv2
import numpy as np
import threading
import traceback
import os


def detect_raw_board_on_thread(self, num, barrier):
    """
    Draws calibration on a separate thread for a given camera.

    Parameters:
    - num: The camera number.
    - barrier: A threading.Barrier object used to synchronize multiple threads.

    Returns:
    None

    Example usage:
    draw_calibration_on_thread(0, barrier)
    """
    # window_name = f'Camera {num}'
    # cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    # cv2.resizeWindow(window_name, 640, 480)
    from utils import aruco_dict
    from cv2 import aruco
    params = aruco.DetectorParameters()
    params.cornerRefinementMethod = aruco.CORNER_REFINE_CONTOUR
    params.adaptiveThreshWinSizeMin = 100
    params.adaptiveThreshWinSizeMax = 1000
    params.adaptiveThreshWinSizeStep = 50
    params.adaptiveThreshConstant = 0
    
    # while cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) > 0:
    while self.detection_window_status:
        try:
            barrier.wait(timeout=15)
        except threading.BrokenBarrierError:
            print(f'Barrier broken for cam {num}. Proceeding...')
            break
        frame_current = self.cam[num].get_image()
        if frame_current is not None:
            self.frame_count_test[num] += 1
            if self.cgroup_test is not None:
                drawn_frame = draw_axis(frame_current,
                                                aruco_dict=aruco_dict, params=params,
                                                camera_matrix=self.cgroup_test.cameras[num].get_camera_matrix(),
                                                dist_coeff=self.cgroup_test.cameras[num].get_distortions(),
                                                rotation=self.cgroup_test.cameras[num].get_rotation(),
                                                translation=self.cgroup_test.cameras[num].get_translation(),
                                                board=self.board_calibration.board)
            else:
                drawn_frame = draw_axis(frame_current, aruco_dict=aruco_dict, params=params)
                
            if drawn_frame is not None:
                frame_current = drawn_frame
            self.frame_queue.put((frame_current, num, self.frame_count_test[num]))


def draw_detection_on_thread(self, num):
    frame_groups = {}  # Dictionary to store frame groups by thread_id
    frame_counts = {}  # array to store frame counts for each thread_id
    from src.aniposelib.boards import merge_rows, extract_points

    window_name = f'Detection'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 2160, 660)
    
    # Define the font settings
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.5
    thickness = 1
    
    self.detection_window_status = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) > 0
    try:
        while self.detection_window_status:
            # Retrieve frame information from the queue
            frame, thread_id, frame_count,  = self.frame_queue.get()
            if thread_id not in frame_groups:
                frame_groups[thread_id] = []  # Create a new group for the thread_id if it doesn't exist
                frame_counts[thread_id] = 0
                
            # Append frame information to the corresponding group
            frame_groups[thread_id].append((frame, frame_count))
            frame_counts[thread_id] += 1
            
            # Process the frame group (frames with the same thread_id)
            # dumping the mix and match rows into detections.pickle to be pickup by calibrate_on_thread
            try:
                if all(count >= 2 for count in frame_counts.values()):
                    frames = []
                    for num in range(len(self.cam)):
                        frame_group = frame_groups[num]
                        frame = frame_group[-1][0]
                        frames.append(frame)
                    
                    frame = cv2.hconcat(frames)
                    cv2.putText(frame, 'Detection', (30, 50), font, font_scale, (0, 255, 0), thickness)
                    cv2.imshow(window_name, frame)
                    cv2.waitKey(1)
                    
                    
            except Exception as e:
                traceback.print_exc()
                print("Exception occurred:", type(e).__name__, "| Exception value:", e,
                      ''.join(traceback.format_tb(e.__traceback__)))
            
            self.detection_window_status = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) > 0
            
    except Exception as e:
        print("Exception occurred:", type(e).__name__, "| Exception value:", e,
              ''.join(traceback.format_tb(e.__traceback__)))
              
    
def draw_axis(frame, aruco_dict, params, camera_matrix=None, dist_coeff=None, rotation=None, translation=None, board=None, verbose=True):
    """
    """
    try:
        corners, ids, rejected_points = cv2.aruco.detectMarkers(frame, aruco_dict, parameters=params)
        
        if corners is None or ids is None:
            print('No corner detected')
            return None
        if len(corners) != len(ids) or len(corners) == 0:
            print('Incorrect corner or no corner detected!')
            return None
        
        if camera_matrix is None or dist_coeff is None:
            print('Camera matrix or distortion coefficients not provided!')
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            return frame
        
        corners, ids, rejectedCorners, recoveredIdxs = cv2.aruco.refineDetectedMarkers(frame, board, corners, ids,
                                                                                       rejected_points, camera_matrix,
                                                                                       dist_coeff, parameters=params)

        if len(corners) == 0:
            print('No corner detected after refinement!')
            return None

        ret, c_corners, c_ids = cv2.aruco.interpolateCornersCharuco(corners, ids,
                                                                    frame, board,
                                                                    cameraMatrix=camera_matrix, distCoeffs=dist_coeff)
        print(f'Corners:', c_corners)
        if c_corners is None or c_ids is None or len(c_corners) < 5:
            print('No corner detected after interpolation!')
            return None

        n_corners = c_corners.size // 2
        reshape_corners = np.reshape(c_corners, (n_corners, 1, 2))


        ret, p_rvec, p_tvec = cv2.aruco.estimatePoseCharucoBoard(reshape_corners,
                                                                    c_ids,
                                                                    board,
                                                                    camera_matrix,
                                                                    dist_coeff,
                                                                    rotation,
                                                                    translation)

        if p_rvec is None or p_tvec is None:
            print('Cant detect rotation!')
            return None
        if np.isnan(p_rvec).any() or np.isnan(p_tvec).any():
            print('Rotation is not usable')
            return None

        cv2.drawFrameAxes(image=frame,
                            cameraMatrix=camera_matrix,
                            distCoeffs=dist_coeff,
                            rvec=rotation,
                            tvec=translation,
                            length=20)

        cv2.aruco.drawDetectedCornersCharuco(frame, reshape_corners, c_ids)
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)
        cv2.aruco.drawDetectedMarkers(frame, rejected_points, borderColor=(100, 0, 240))

    except cv2.error as e:
        import sys
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        traceback.print_exc()
        return None

    # if verbose:
    #     print('Translation : {0}'.format(p_tvec))
    #     print('Rotation    : {0}'.format(p_rvec))
    #     print('Distance from camera: {0} m'.format(np.linalg.norm(p_tvec)))

    return frame
    

def detect_markers_on_thread(self, num, barrier):
    while self.reproject_window_status:
        try:
            barrier.wait(timeout=15)
        except threading.BrokenBarrierError:
            print(f'Barrier broken for cam {num}. Proceeding...')
            break
        
        self.frame_count_test[num] += 1
        frame_current = self.cam[num].get_image()

        # detect the marker as the frame is acquired
        corners, ids = self.board_calibration.detect_image(frame_current)
        if corners is not None:
            key = self.frame_count_test[num]
            row = {
                'framenum': key,
                'corners': corners,
                'ids': ids
            }

            row = self.board_calibration.fill_points_rows([row])
            self.all_rows_test[num].extend(row)

        # putting frame into the frame queue along with following information
        self.frame_queue.put((frame_current, num, self.frame_count_test[num]))  # the id of the capturing camera

        frame_current = self.cam[num].get_image()
        
        
def draw_reprojection_on_thread(self, num):
    frame_groups = {}  # Dictionary to store frame groups by thread_id
    frame_counts = {}  # array to store frame counts for each thread_id
    from src.aniposelib.boards import merge_rows, extract_points

    window_name = f'Reprojection'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 2160, 660)
    
    # Define the font settings
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.5
    thickness = 1
    
    self.reproject_window_status = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) > 0
    try:
        while self.reproject_window_status:
            # Retrieve frame information from the queue
            frame, thread_id, frame_count,  = self.frame_queue.get()
            if thread_id not in frame_groups:
                frame_groups[thread_id] = []  # Create a new group for the thread_id if it doesn't exist
                frame_counts[thread_id] = 0

            # Append frame information to the corresponding group
            frame_groups[thread_id].append((frame, frame_count))
            frame_counts[thread_id] += 1
            
            # Process the frame group (frames with the same thread_id)
            # dumping the mix and match rows into detections.pickle to be pickup by calibrate_on_thread
            try:
                if all(count >= 2 for count in frame_counts.values()):
                    all_rows = [row[-2:] for row in self.all_rows_test]
                    for i, (row, cam) in enumerate(zip(all_rows, self.cgroup_test.cameras)):
                        all_rows[i] = self.board_calibration.estimate_pose_rows(cam, row)
                        
                    merged = merge_rows(all_rows)
                    imgp, extra = extract_points(merged, self.board_calibration, min_cameras=2)
                    p3ds = self.cgroup_test.triangulate(imgp)
                   
                    # Project the 3D points back to 2D
                    try:
                        p2ds = self.cgroup_test.project(p3ds)
                    except Exception as e:
                        print("Exception occurred:", type(e).__name__, "| Exception value:", e,
                              ''.join(traceback.format_tb(e.__traceback__)))
                        print('#########')
                    
                    # Draw the reprojection
                    frames = []
                    for num in range(len(self.cam)):
                        frame_group = frame_groups[num]
                        frame = frame_group[-1][0]
                        c_corners = all_rows[num][0]['corners']
                        ids = all_rows[num][0]['ids']
                        
                        n_corners = c_corners.size // 2
                        reshape_corners = np.reshape(c_corners, (n_corners, 1, 2))
                        cv2.aruco.drawDetectedCornersCharuco(frame, reshape_corners, ids, cornerColor=(0, 255, 0))
                   
                        p_ids = extra['ids']
                        p_corners = p2ds[num].astype('float32')
                        np_corners = p_corners.size // 2
                        reshape_np_corners = np.reshape(p_corners, (np_corners, 1, 2))
                        frames.append(cv2.aruco.drawDetectedCornersCharuco(frame, reshape_np_corners, p_ids, cornerColor=(0, 0, 255)))

                    frame = cv2.hconcat(frames)
                    
                    # Add the text to the frame
                    cv2.putText(frame, 'Detection', (30, 50), font, font_scale, (0, 255, 0), thickness)
                    cv2.putText(frame, 'Reprojection', (30, 100), font, font_scale, (0, 0, 255), thickness)

                    cv2.imshow(window_name, frame)
                    cv2.waitKey(1)
                    
                    # Clear the processed frames from the group
                    frame_groups = {}
                    frame_count = {}
            except Exception as e:
                print("Exception occurred:", type(e).__name__, "| Exception value:", e,
                      ''.join(traceback.format_tb(e.__traceback__)))
                frames = []
                for num in range(len(self.cam)):
                    frame_group = frame_groups[num]
                    frame = frame_group[-1][0]
                    frames.append(frame)
                
                frame = cv2.hconcat(frames)
                cv2.putText(frame, 'No board detected', (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 1)
                cv2.imshow(window_name, frame)
                cv2.waitKey(1)
                
            self.reproject_window_status = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) > 0
        
    except Exception as e:
        print("Exception occurred:", type(e).__name__, "| Exception value:", e,
              ''.join(traceback.format_tb(e.__traceback__)))
 
