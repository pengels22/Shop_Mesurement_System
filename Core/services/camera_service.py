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
        return frame

    def mjpeg_generator(self) -> Generator[bytes, None, None]:
        while True:
            frame = self.get_frame()
            success, encoded_frame = cv2.imencode(JPEG_EXTENSION, frame)
            if not success:
                continue
            jpg_bytes = encoded_frame.tobytes()
            yield MJPEG_BOUNDARY + MJPEG_CONTENT_TYPE + jpg_bytes + MJPEG_LINE_BREAK
