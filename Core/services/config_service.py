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
DEFAULT_PIXELS_PER_INCH = 33.0
DEFAULT_TOP_IGNORE_PIXELS = 0
DEFAULT_SIDE_CAMERA_INDEX = 1
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
                'top': {
                    'camera_index': DEFAULT_CAMERA_INDEX,
                    'resolution_width': DEFAULT_RESOLUTION_WIDTH,
                    'resolution_height': DEFAULT_RESOLUTION_HEIGHT,
                    'fixed_mount_height_inches': DEFAULT_FIXED_MOUNT_HEIGHT_INCHES,
                    'fps': DEFAULT_FPS,
                },
                'side': {
                    'camera_index': DEFAULT_SIDE_CAMERA_INDEX,
                    'resolution_width': DEFAULT_RESOLUTION_WIDTH,
                    'resolution_height': DEFAULT_RESOLUTION_HEIGHT,
                    'fixed_mount_height_inches': DEFAULT_FIXED_MOUNT_HEIGHT_INCHES,
                    'fps': DEFAULT_FPS,
                },
            })

        if not self.calibration_path.exists():
            FileService.write_json(self.calibration_path, {
                'top': {
                    'pixels_per_inch': DEFAULT_PIXELS_PER_INCH,
                    'camera_matrix': None,
                    'dist_coeffs': None,
                    'homography': None,
                },
                'side': {
                    'pixels_per_inch': DEFAULT_PIXELS_PER_INCH,
                    'camera_matrix': None,
                    'dist_coeffs': None,
                    'homography': None,
                },
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
        raw_profile = self._load_json(self.camera_profile_path)
        normalized = self._normalize_camera_profile(raw_profile)
        if normalized != raw_profile:
            self.save_camera_profile(normalized)
        return normalized

    def save_camera_profile(self, profile: Dict[str, Any]) -> None:
        FileService.write_json(self.camera_profile_path, profile)

    def load_calibration(self) -> Dict[str, Any]:
        raw_calibration = self._load_json(self.calibration_path)
        normalized = self._normalize_calibration(raw_calibration)
        if normalized != raw_calibration:
            self.save_calibration(normalized)
        return normalized

    def save_calibration(self, calibration: Dict[str, Any]) -> None:
        FileService.write_json(self.calibration_path, calibration)

    def load_mask(self) -> Dict[str, Any]:
        return self._load_json(self.mask_path)

    def _default_camera_profile(self, index: int = DEFAULT_CAMERA_INDEX) -> Dict[str, Any]:
        return {
            'camera_index': index,
            'resolution_width': DEFAULT_RESOLUTION_WIDTH,
            'resolution_height': DEFAULT_RESOLUTION_HEIGHT,
            'fixed_mount_height_inches': DEFAULT_FIXED_MOUNT_HEIGHT_INCHES,
            'fps': DEFAULT_FPS,
        }

    def _default_calibration_profile(self, pixels_per_inch: float | None = None) -> Dict[str, Any]:
        return {
            'pixels_per_inch': pixels_per_inch or DEFAULT_PIXELS_PER_INCH,
            'camera_matrix': None,
            'dist_coeffs': None,
            'homography': None,
        }

    def _normalize_camera_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        if not profile:
            profile = {}

        if 'top' not in profile and 'camera_index' in profile:
            profile = {'top': profile}

        normalized = {
            'top': {**self._default_camera_profile(DEFAULT_CAMERA_INDEX), **(profile.get('top') or {})},
            'side': {**self._default_camera_profile(DEFAULT_SIDE_CAMERA_INDEX), **(profile.get('side') or {})},
        }
        return normalized

    def _normalize_calibration(self, calibration: Dict[str, Any]) -> Dict[str, Any]:
        if not calibration:
            calibration = {}

        if 'top' not in calibration and 'pixels_per_inch' in calibration:
            # legacy single-camera structure
            calibration = {'top': calibration}

        normalized = {
            'top': {**self._default_calibration_profile(calibration.get('top', {}).get('pixels_per_inch') if isinstance(calibration.get('top'), dict) else None), **(calibration.get('top') or {})},
            'side': {**self._default_calibration_profile(calibration.get('side', {}).get('pixels_per_inch') if isinstance(calibration.get('side'), dict) else None), **(calibration.get('side') or {})},
        }

        return normalized
