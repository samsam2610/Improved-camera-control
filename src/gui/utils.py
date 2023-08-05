#!/usr/bin/env python3

import os
import os.path
import sys

import cv2
from cv2 import aruco
import numpy as np
import toml
from pathlib import Path
import json


from src.aniposelib.boards import CharucoBoard, Checkerboard

ARUCO_DICTS = {
    (4, 50): aruco.DICT_4X4_50,
    (5, 50): aruco.DICT_5X5_50,
    (6, 50): aruco.DICT_6X6_50,
    (7, 50): aruco.DICT_7X7_50,
    (4, 100): aruco.DICT_4X4_100,
    (5, 100): aruco.DICT_5X5_100,
    (6, 100): aruco.DICT_6X6_100,
    (7, 100): aruco.DICT_7X7_100,
    (4, 250): aruco.DICT_4X4_250,
    (5, 250): aruco.DICT_5X5_250,
    (6, 250): aruco.DICT_6X6_250,
    (7, 250): aruco.DICT_7X7_250,
    (4, 1000): aruco.DICT_4X4_1000,
    (5, 1000): aruco.DICT_5X5_1000,
    (6, 1000): aruco.DICT_6X6_1000,
    (7, 1000): aruco.DICT_7X7_1000
}

dkey = (4, 50)
aruco_dict = aruco.getPredefinedDictionary(ARUCO_DICTS[dkey])


DEFAULT_CONFIG = {
    'video_extension': 'avi',
    'converted_video_speed': 1,
    'calibration': {
        'animal_calibration': False,
        'calibration_init': None,
        'fisheye': False
    },
    'manual_verification': {
        'manually_verify': False
    },
    'triangulation': {
        'ransac': False,
        'optim': False,
        'scale_smooth': 2,
        'scale_length': 2,
        'scale_length_weak': 1,
        'reproj_error_threshold': 5,
        'score_threshold': 0.8,
        'n_deriv_smooth': 3,
        'constraints': [],
        'constraints_weak': []
    },
    'pipeline': {
        'videos_raw': 'videos-raw',
        'videos_raw_mp4': 'videos-raw-mp4',
        'pose_2d': 'pose-2d',
        'pose_2d_filter': 'pose-2d-filtered',
        'pose_2d_projected': 'pose-2d-proj',
        'pose_3d': 'pose-3d',
        'pose_3d_filter': 'pose-3d-filtered',
        'videos_labeled_2d': 'videos-labeled',
        'videos_labeled_2d_filter': 'videos-labeled-filtered',
        'calibration_videos': 'calibration',
        'calibration_results': 'calibration',
        'videos_labeled_3d': 'videos-3d',
        'videos_labeled_3d_filter': 'videos-3d-filtered',
        'angles': 'angles',
        'summaries': 'summaries',
        'videos_combined': 'videos-combined',
        'videos_compare': 'videos-compare',
        'videos_2d_projected': 'videos-2d-proj',
    },
    'filter': {
        'enabled': False,
        'type': 'medfilt',
        'medfilt': 13,
        'offset_threshold': 25,
        'score_threshold': 0.05,
        'spline': True,
        'n_back': 5,
        'multiprocessing': False
    },
    'filter3d': {
        'enabled': False
    }
}


def full_path(path):
    path_user = os.path.expanduser(path)
    path_full = os.path.abspath(path_user)
    path_norm = os.path.normpath(path_full)
    return path_norm


def load_config(fname):
    if fname is None:
        fname = 'config.toml'

    if os.path.exists(fname):
        config = toml.load(fname)
        print("Loaded config from {}".format(fname))
    else:
        config = dict()
        print("No config file found, using defaults")

    # put in the defaults
    if 'path' not in config:
        if os.path.exists(fname) and os.path.dirname(fname) != '':
            config['path'] = os.path.dirname(fname)
        else:
            config['path'] = os.getcwd()

    config['path'] = full_path(config['path'])

    if 'project' not in config:
        config['project'] = os.path.basename(config['path'])

    for k, v in DEFAULT_CONFIG.items():
        if k not in config:
            config[k] = v
        elif isinstance(v, dict):  # handle nested defaults
            for k2, v2 in v.items():
                if k2 not in config[k]:
                    config[k][k2] = v2

    return config


def get_calibration_board(config):
    calib = config['calibration']
    board_size = calib['board_size']
    board_type = calib['board_type'].lower()

    manual_verification = config['manual_verification']
    manually_verify = manual_verification['manually_verify']

    if board_type == 'aruco':
        raise NotImplementedError("aruco board is not implemented with the current pipeline")
    elif board_type == 'charuco':
        board = CharucoBoard(
            board_size[0], board_size[1],
            calib['board_square_side_length'],
            calib['board_marker_length'],
            calib['board_marker_bits'],
            calib['board_marker_dict_number'],
            manually_verify=manually_verify)



    elif board_type == 'checkerboard':
        board = Checkerboard(board_size[0], board_size[1],
                             calib['board_square_side_length'], manually_verify=manually_verify)
    else:
        raise ValueError("board_type should be one of "
                         "'aruco', 'charuco', or 'checkerboard' not '{}'".format(
            board_type))

    return board


def draw_axis(frame, camera_matrix, dist_coeff, board, aruco_dict, params, verbose=True):
    try:
        corners, ids, rejected_points = cv2.aruco.detectMarkers(frame, aruco_dict, parameters=params)

        if corners is None or ids is None:
            print('No corner detected')
            return None
        if len(corners) != len(ids) or len(corners) == 0:
            print('Incorrect corner or no corner detected!')
            return None

        corners, ids, rejectedCorners, recoveredIdxs = cv2.aruco.refineDetectedMarkers(frame, board, corners, ids,
                                                                                       rejected_points, camera_matrix,
                                                                                       dist_coeff, parameters=params)

        if len(corners) == 0:
            return None

        ret, c_corners, c_ids = cv2.aruco.interpolateCornersCharuco(corners, ids,
                                                                    frame, board,
                                                                    cameraMatrix=camera_matrix, distCoeffs=dist_coeff)

        if c_corners is None or c_ids is None or len(c_corners) < 5:
            print('No corner detected after interpolation!')
            return None

        n_corners = c_corners.size // 2
        reshape_corners = np.reshape(c_corners, (n_corners, 1, 2))

        ret, p_rvec, p_tvec = cv2.aruco.estimatePoseCharucoBoard(reshape_corners,
                                                                 c_ids,
                                                                 board,
                                                                 camera_matrix,
                                                                 dist_coeff)

        if p_rvec is None or p_tvec is None:
            print('Cant detect rotation!')
            return None
        if np.isnan(p_rvec).any() or np.isnan(p_tvec).any():
            print('Rotation is not usable')
            return None

        cv2.aruco.drawAxis(image=frame, cameraMatrix=camera_matrix, distCoeffs=dist_coeff,
                           rvec=p_rvec, tvec=p_tvec, length=20)

        cv2.aruco.drawDetectedCornersCharuco(frame, reshape_corners, c_ids)
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)
        # cv2.aruco.drawDetectedMarkers(frame, rejected_points, borderColor=(100, 0, 240))

    except cv2.error as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        return None

    if verbose:
        print('Translation : {0}'.format(p_tvec))
        print('Rotation    : {0}'.format(p_rvec))
        print('Distance from camera: {0} m'.format(np.linalg.norm(p_tvec)))

    return frame


def load(fname):
    master_dict = toml.load(fname)
    keys = sorted(master_dict.keys())
    items = [master_dict[k] for k in keys if k != 'metadata']
    item = items[0]
    return True, \
        np.array(item['matrix'], dtype='float64'), \
        np.array(item['distortions'], dtype='float64'), \
        np.array(item['rotation'], dtype='float64'), \
        np.array(item['translation'], dtype='float64')


def write_camera_details(cams=None, output_dir=None):
    path = Path(os.path.realpath(__file__))
    # Navigate to the outer parent directory and join the filename
    out = os.path.normpath(str(path.parents[2] / 'config-files' / 'camera_details.json'))

    cam_0 = {'name': 'cam1',
             'crop': {'top': 210, 'left': 8, 'height': 550, 'width': 900},
             'rotate': 0,
             'exposure': 0.002,
             'gain': 100,
             'offset': {'x': 0, 'y': 0},
             'output_dir': 'E:\\live_videos'}

    cam_1 = {'name': 'cam2',
             'crop': {'top': 130, 'left': 92, 'height': 550, 'width': 900},
             'rotate': 0,
             'exposure': 0.002,
             'gain': 100,
             'offset': {'x': 0, 'y': 0},
             'output_dir': 'E:\\live_videos'}

    subs = ['test1', 'test2', 'test3']  # optional, can manually enter subject for each session.

    labview = ['Dev1/port0/line0']  # optional, can manually enter for each session

    details = {'cams': 2,
               '0': cam_0,
               '1': cam_1,
               'subjects': subs,
               'labview': labview}

    if cams is None:
        cams = details

    if output_dir is None:
        output_dir = out

    cam_details = {}
    for i, cam in enumerate(cams):
        cam_name = f'cam{i + 1}'
        crop_details = cam.get('crop', {})
        crop = {
            'top': crop_details.get('top', 0),
            'left': crop_details.get('left', 0),
            'height': crop_details.get('height', 0),
            'width': crop_details.get('width', 0)
        }
        offset_details = cam.get('offset', {})
        offset = {
            'x': offset_details.get('x', 0),
            'y': offset_details.get('y', 0)
        }
        cam_details[str(i)] = {
            'name': cam_name,
            'crop': crop,
            'rotate': cam.get('rotate', 0),
            'exposure': cam.get('exposure', 0.002),
            'gain': cam.get('gain', 100),
            'offset': offset,
            'output_dir': cam.get('output_dir', '')
        }

    details = {
        'cams': len(cams),
        **cam_details,
        'subjects': [],
        'labview': []
    }

    with open(output_dir, 'w') as handle:
        json.dump(details, handle, indent=4)
