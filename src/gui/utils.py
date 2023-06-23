#!/usr/bin/env python3

import os
import os.path
import toml
from src.aniposelib.boards import CharucoBoard, Checkerboard

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
    else:
        config = dict()

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
        elif isinstance(v, dict): # handle nested defaults
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