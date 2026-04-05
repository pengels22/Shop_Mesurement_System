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
    def __init__(self, capture_root: Path, camera_profile: dict, mask_profile: dict | None = None, calibration_settings: dict | None = None):
        self.capture_root = FileService.ensure_dir(capture_root)
        self.mask_profile = mask_profile or {}
        self.camera_index = int(camera_profile.get('camera_index', DEFAULT_CAMERA_INDEX))
        self.width = int(camera_profile.get('resolution_width', DEFAULT_WIDTH))
        self.height = int(camera_profile.get('resolution_height', DEFAULT_HEIGHT))
        self.fps = int(camera_profile.get('fps', DEFAULT_FPS))
        self.backend_code = self._resolve_backend(camera_profile.get('backend'))
        self._homography = None
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
        # Optional planar homography (top-down warp)
        if calibration_settings:
            homography = calibration_settings.get('homography')
            if homography and isinstance(homography, list) and len(homography) == 3 and len(homography[0]) == 3:
                try:
                    self._homography = np.array(homography, dtype=np.float64)
                except Exception:
                    self._homography = None
        # no color mask by default; masking can be reintroduced later in ImageService

    @staticmethod
    def _resolve_backend(backend_value):
        """Map friendly backend names to OpenCV constants."""
        if backend_value is None:
            return None
        if isinstance(backend_value, int):
            return backend_value
        if isinstance(backend_value, str):
            key = backend_value.strip().lower()
            mapping = {
                'avfoundation': getattr(cv2, 'CAP_AVFOUNDATION', None),
                'dshow': getattr(cv2, 'CAP_DSHOW', None),
                'v4l2': getattr(cv2, 'CAP_V4L2', None),
                'msmf': getattr(cv2, 'CAP_MSMF', None),
                'any': getattr(cv2, 'CAP_ANY', None),
            }
            return mapping.get(key)
        return None

    def _create_capture(self):
        cap = None
        if self.backend_code is not None:
            cap = cv2.VideoCapture(self.camera_index, self.backend_code)
        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(self.camera_index)
        if cap is None or not cap.isOpened():
            return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        return cap

    def _open(self, force_new: bool = False) -> cv2.VideoCapture:
        if force_new:
            try:
                if self._capture is not None:
                    self._capture.release()
            except Exception:
                pass
            self._capture = None

        if self._capture is None or not self._capture.isOpened():
            self._capture = self._create_capture()
        return self._capture

    def _apply_mask(self, frame: np.ndarray) -> np.ndarray:
        if not isinstance(frame, np.ndarray):
            return frame
        mask_cfg = self.mask_profile or {}

        # simple top strip removal
        top_ignore = int(mask_cfg.get('top_ignore_pixels') or 0)
        if top_ignore > 0:
            top_ignore = min(top_ignore, frame.shape[0] - 1)
            frame[:top_ignore, :] = 0

        crop_fraction = mask_cfg.get('crop_fraction')
        if isinstance(crop_fraction, dict):
            h, w = frame.shape[:2]
            x0 = int(max(0.0, min(1.0, float(crop_fraction.get('x0', 0.0)))) * w)
            y0 = int(max(0.0, min(1.0, float(crop_fraction.get('y0', 0.0)))) * h)
            x1 = int(max(0.0, min(1.0, float(crop_fraction.get('x1', 1.0)))) * w)
            y1 = int(max(0.0, min(1.0, float(crop_fraction.get('y1', 1.0)))) * h)
            x1 = max(x0 + 1, min(w, x1))
            y1 = max(y0 + 1, min(h, y1))
            frame = frame[y0:y1, x0:x1]
        return frame

    def _apply_homography(self, frame: np.ndarray) -> np.ndarray:
        if self._homography is None or not isinstance(frame, np.ndarray):
            return frame
        try:
            h, w = frame.shape[:2]
            warped = cv2.warpPerspective(frame, self._homography, (w, h), flags=cv2.INTER_LINEAR)
            return warped
        except Exception:
            return frame

    def get_frame(self) -> np.ndarray:
        for attempt in range(3):
            capture_device = self._open(force_new=attempt > 0)
            if capture_device is None or not capture_device.isOpened():
                time.sleep(0.1)
                continue
            success, frame = capture_device.read()
            if success and frame is not None:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(f'Could not read frame from camera index {self.camera_index} after retries')
        if self._use_undistort and self._map1 is not None and self._map2 is not None:
            try:
                frame = cv2.remap(frame, self._map1, self._map2, interpolation=cv2.INTER_LINEAR)
            except Exception:
                pass
        frame = self._apply_homography(frame)
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
        frame = self._apply_homography(frame)
        return frame

    def mjpeg_generator(self) -> Generator[bytes, None, None]:
        while True:
            try:
                frame = self.get_frame()
            except Exception:
                # try to recover by reopening the capture
                try:
                    if self._capture is not None:
                        self._capture.release()
                except Exception:
                    pass
                self._capture = None
                time.sleep(0.3)
                continue

            success, encoded_frame = cv2.imencode(JPEG_EXTENSION, frame)
            if not success:
                time.sleep(0.05)
                continue
            jpg_bytes = encoded_frame.tobytes()
            yield MJPEG_BOUNDARY + MJPEG_CONTENT_TYPE + jpg_bytes + MJPEG_LINE_BREAK
