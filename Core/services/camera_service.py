from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Generator
from typing import Tuple

import cv2
import numpy as np

from Core.services.file_service import FileService

DEFAULT_CAMERA_INDEX = 0
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 15
JPEG_EXTENSION = '.jpg'
PNG_EXTENSION = '.png'
MJPEG_BOUNDARY = b'--frame\r\n'
MJPEG_CONTENT_TYPE = b'Content-Type: image/jpeg\r\n\r\n'
MJPEG_LINE_BREAK = b'\r\n'


class CameraService:
    def __init__(self, capture_root: Path, camera_profile: dict):
        self.capture_root = FileService.ensure_dir(capture_root)
        self.camera_index = int(camera_profile.get('camera_index', DEFAULT_CAMERA_INDEX))
        self.width = int(camera_profile.get('resolution_width', DEFAULT_WIDTH))
        self.height = int(camera_profile.get('resolution_height', DEFAULT_HEIGHT))
        self.fps = int(camera_profile.get('fps', DEFAULT_FPS))
        self._capture = None
        self._lock = threading.Lock()
        self._counter = 0
        # Load optional camera calibration for undistortion
        camera_matrix = camera_profile.get('camera_matrix')
        dist_coeffs = camera_profile.get('dist_coeffs')
        if camera_matrix and dist_coeffs:
            try:
                self.camera_matrix = np.array(camera_matrix, dtype=np.float64)
                self.dist_coeffs = np.array(dist_coeffs, dtype=np.float64)
                self._use_undistort = True
                # Precompute undistort maps for performance
                self._new_camera_matrix, _ = cv2.getOptimalNewCameraMatrix(
                    self.camera_matrix, self.dist_coeffs, (self.width, self.height), 1, (self.width, self.height)
                )
                self._map1, self._map2 = cv2.initUndistortRectifyMap(
                    self.camera_matrix, self.dist_coeffs, None, self._new_camera_matrix, (self.width, self.height), cv2.CV_16SC2
                )
            except Exception:
                self.camera_matrix = None
                self.dist_coeffs = None
                self._use_undistort = False
                self._map1 = None
                self._map2 = None
        else:
            self.camera_matrix = None
            self.dist_coeffs = None
            self._use_undistort = False
            self._map1 = None
            self._map2 = None
        # Color mask settings (expects dict with 'h_min','s_min','v_min','h_max','s_max','v_max', optional 'invert')
        color_mask = camera_profile.get('color_mask') if camera_profile else None
        if color_mask:
            try:
                self._color_mask = {
                    'h_min': int(color_mask.get('h_min', 0)),
                    's_min': int(color_mask.get('s_min', 0)),
                    'v_min': int(color_mask.get('v_min', 0)),
                    'h_max': int(color_mask.get('h_max', 179)),
                    's_max': int(color_mask.get('s_max', 255)),
                    'v_max': int(color_mask.get('v_max', 255)),
                    'invert': bool(color_mask.get('invert', False)),
                }
                self._use_color_mask = True
            except Exception:
                self._color_mask = None
                self._use_color_mask = False
        else:
            self._color_mask = None
            self._use_color_mask = False

    def _open(self) -> cv2.VideoCapture:
        if self._capture is None or not self._capture.isOpened():
            self._capture = cv2.VideoCapture(self.camera_index)
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._capture.set(cv2.CAP_PROP_FPS, self.fps)
        return self._capture

    def get_frame(self) -> np.ndarray:
        capture_device = self._open()
        success, frame = capture_device.read()
        if not success or frame is None:
            raise RuntimeError('Could not read frame from camera')
        if self._use_undistort and self._map1 is not None and self._map2 is not None:
            try:
                frame = cv2.remap(frame, self._map1, self._map2, interpolation=cv2.INTER_LINEAR)
            except Exception:
                pass
        if self._use_color_mask and self._color_mask is not None:
            try:
                frame = self._apply_color_mask(frame, self._color_mask)
            except Exception:
                pass
        return frame

    def capture_frame(self) -> Tuple[str, Path, int, int]:
        with self._lock:
            frame = self.get_frame()
            self._counter += 1
            frame_id = f"capture_{time.strftime('%Y%m%d_%H%M%S')}_{self._counter:03d}"
            frame_path = self.capture_root / f'{frame_id}{PNG_EXTENSION}'
            cv2.imwrite(str(frame_path), frame)
            image_height, image_width = frame.shape[:2]
            return frame_id, frame_path, image_width, image_height

    def load_captured_frame(self, frame_id: str) -> np.ndarray:
        frame_path = self.capture_root / f'{frame_id}{PNG_EXTENSION}'
        if not frame_path.exists():
            raise FileNotFoundError(f'Captured frame {frame_id} not found')
        frame = cv2.imread(str(frame_path))
        if frame is None:
            raise RuntimeError(f'Failed to load frame {frame_id}')
        if self._use_undistort and self._map1 is not None and self._map2 is not None:
            try:
                frame = cv2.remap(frame, self._map1, self._map2, interpolation=cv2.INTER_LINEAR)
            except Exception:
                pass
        if self._use_color_mask and self._color_mask is not None:
            try:
                frame = self._apply_color_mask(frame, self._color_mask)
            except Exception:
                pass
        return frame

    @staticmethod
    def _apply_color_mask(frame: np.ndarray, mask_cfg: dict) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower = np.array([mask_cfg['h_min'], mask_cfg['s_min'], mask_cfg['v_min']], dtype=np.uint8)
        upper = np.array([mask_cfg['h_max'], mask_cfg['s_max'], mask_cfg['v_max']], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        # Clean mask
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        if mask_cfg.get('invert'):
            mask = cv2.bitwise_not(mask)
        # Apply mask to frame: outside masked area -> black
        result = cv2.bitwise_and(frame, frame, mask=mask)
        return result

    def mjpeg_generator(self) -> Generator[bytes, None, None]:
        while True:
            frame = self.get_frame()
            success, encoded_frame = cv2.imencode(JPEG_EXTENSION, frame)
            if not success:
                continue
            jpg_bytes = encoded_frame.tobytes()
            yield MJPEG_BOUNDARY + MJPEG_CONTENT_TYPE + jpg_bytes + MJPEG_LINE_BREAK
