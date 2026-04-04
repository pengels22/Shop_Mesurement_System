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


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


class CameraService:
    def __init__(self, capture_root: Path, camera_profile: dict, mask_profile: dict | None = None):
        self.capture_root = FileService.ensure_dir(capture_root)
        self.camera_profile = camera_profile
        self.camera_index = int(camera_profile.get('camera_index', DEFAULT_CAMERA_INDEX))
        self.width = int(camera_profile.get('resolution_width', DEFAULT_WIDTH))
        self.height = int(camera_profile.get('resolution_height', DEFAULT_HEIGHT))
        self.fps = int(camera_profile.get('fps', DEFAULT_FPS))
        self.mask_profile = mask_profile or {}
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
        # no color mask by default; masking can be reintroduced later in ImageService

    def _open(self) -> cv2.VideoCapture:
        if self._capture is None or not self._capture.isOpened():
            self._capture = cv2.VideoCapture(self.camera_index)
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._capture.set(cv2.CAP_PROP_FPS, self.fps)
        return self._capture

    def close(self) -> None:
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None

    def _apply_mask(self, frame: np.ndarray) -> np.ndarray:
        """Apply masking and optional cropping to a frame.

        Supports two modes:
        - ignore_zones: list of dicts with x, y, width, height (pixels) to black out
        - crop or crop_fraction: dict specifying ROI; crop_fraction uses normalized 0-1 coordinates
        """
        if not isinstance(frame, np.ndarray):
            return frame

        output = frame
        height, width = output.shape[:2]
        mask_config = self.mask_profile or {}

        top_ignore = int(mask_config.get('top_ignore_pixels') or 0)
        if top_ignore > 0:
            clipped_top = _clamp(top_ignore, 0, height)
            output[:clipped_top, :] = 0

        for zone in mask_config.get('ignore_zones', []) or []:
            try:
                zx = int(zone.get('x', 0) or 0)
                zy = int(zone.get('y', 0) or 0)
                zw = int(zone.get('width', 0) or 0)
                zh = int(zone.get('height', 0) or 0)
            except Exception:
                continue
            if zw <= 0 or zh <= 0:
                continue
            x0 = _clamp(zx, 0, width)
            y0 = _clamp(zy, 0, height)
            x1 = _clamp(zx + zw, 0, width)
            y1 = _clamp(zy + zh, 0, height)
            if x1 > x0 and y1 > y0:
                output[y0:y1, x0:x1] = 0

        crop_fraction = mask_config.get('crop_fraction') or None
        crop_pixels = mask_config.get('crop') or None

        if crop_fraction:
            try:
                x0 = int((crop_fraction.get('x0', 0) or 0) * width)
                y0 = int((crop_fraction.get('y0', 0) or 0) * height)
                x1 = int((crop_fraction.get('x1', 1) or 1) * width)
                y1 = int((crop_fraction.get('y1', 1) or 1) * height)
            except Exception:
                x0 = y0 = 0
                x1, y1 = width, height
        elif crop_pixels:
            try:
                x0 = int(crop_pixels.get('x', 0) or 0)
                y0 = int(crop_pixels.get('y', 0) or 0)
                x1 = x0 + int(crop_pixels.get('width', width) or width)
                y1 = y0 + int(crop_pixels.get('height', height) or height)
            except Exception:
                x0 = y0 = 0
                x1, y1 = width, height
        else:
            x0 = y0 = 0
            x1, y1 = width, height

        x0 = _clamp(x0, 0, width)
        y0 = _clamp(y0, 0, height)
        x1 = _clamp(x1, x0 + 1, width)
        y1 = _clamp(y1, y0 + 1, height)

        if x0 == 0 and y0 == 0 and x1 == width and y1 == height:
            return output

        return output[y0:y1, x0:x1]

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
        return self._apply_mask(frame)

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
        return frame

    def mjpeg_generator(self) -> Generator[bytes, None, None]:
        while True:
            frame = self.get_frame()
            success, encoded_frame = cv2.imencode(JPEG_EXTENSION, frame)
            if not success:
                continue
            jpg_bytes = encoded_frame.tobytes()
            yield MJPEG_BOUNDARY + MJPEG_CONTENT_TYPE + jpg_bytes + MJPEG_LINE_BREAK
