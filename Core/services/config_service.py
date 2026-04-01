from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Dict

from Core.services.file_service import FileService

DEFAULT_PROJECTS_ROOT = 'Core/projects'
DEFAULT_TEMP_CAPTURE_ROOT = 'Core/tmp/captures'
DEFAULT_CAMERA_INDEX = 0
DEFAULT_RESOLUTION_WIDTH = 1280
DEFAULT_RESOLUTION_HEIGHT = 720
DEFAULT_FIXED_MOUNT_HEIGHT_INCHES = 31.375
DEFAULT_FPS = 15
DEFAULT_PIXELS_PER_INCH = 100.0
DEFAULT_TOP_IGNORE_PIXELS = 0
DEFAULT_APP_CONFIG_FILENAME = 'app_config.json'
DEFAULT_CAMERA_PROFILE_FILENAME = 'camera_profile.json'
DEFAULT_CALIBRATION_FILENAME = 'calibration.json'
DEFAULT_MASK_FILENAME = 'mask.json'


class ConfigService:
    def __init__(self, config_directory: Path):
        self.config_directory = FileService.ensure_dir(config_directory)
        self.app_config_path = self.config_directory / DEFAULT_APP_CONFIG_FILENAME
        self.camera_profile_path = self.config_directory / DEFAULT_CAMERA_PROFILE_FILENAME
        self.calibration_path = self.config_directory / DEFAULT_CALIBRATION_FILENAME
        self.mask_path = self.config_directory / DEFAULT_MASK_FILENAME
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        if not self.app_config_path.exists():
            FileService.write_json(self.app_config_path, {
                'projects_root': DEFAULT_PROJECTS_ROOT,
                'temp_capture_root': DEFAULT_TEMP_CAPTURE_ROOT,
            })

        if not self.camera_profile_path.exists():
            FileService.write_json(self.camera_profile_path, {
                'camera_index': DEFAULT_CAMERA_INDEX,
                'resolution_width': DEFAULT_RESOLUTION_WIDTH,
                'resolution_height': DEFAULT_RESOLUTION_HEIGHT,
                'fixed_mount_height_inches': DEFAULT_FIXED_MOUNT_HEIGHT_INCHES,
                'fps': DEFAULT_FPS,
            })

        if not self.calibration_path.exists():
            FileService.write_json(self.calibration_path, {
                'pixels_per_inch': DEFAULT_PIXELS_PER_INCH,
                'camera_matrix': None,
                'dist_coeffs': None,
                'homography': None,
            })

        if not self.mask_path.exists():
            FileService.write_json(self.mask_path, {
                'ignore_zones': [],
                'top_ignore_pixels': DEFAULT_TOP_IGNORE_PIXELS,
            })

    def _load_json(self, path: Path) -> Dict[str, Any]:
        return FileService.read_json(path, {})

    def load_app_config(self) -> Dict[str, Any]:
        return self._load_json(self.app_config_path)

    def load_camera_profile(self) -> Dict[str, Any]:
        return self._load_json(self.camera_profile_path)

    def load_calibration(self) -> Dict[str, Any]:
        return self._load_json(self.calibration_path)

    def load_mask(self) -> Dict[str, Any]:
        return self._load_json(self.mask_path)
