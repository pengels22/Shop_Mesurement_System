from __future__ import annotations

from pathlib import Path

from flask import Flask

from Core.routes.api_routes import api_blueprint
from Core.routes.page_routes import page_blueprint
from Core.services.camera_service import CameraService
from Core.services.config_service import ConfigService
from Core.services.csv_service import CsvService
from Core.services.image_service import ImageService
from Core.services.measurement_service import MeasurementService
from Core.services.project_service import ProjectService


DEFAULT_PIXELS_PER_INCH = 33

PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = PROJECT_ROOT_DIR / 'Core'
WEB_DIR = PROJECT_ROOT_DIR / 'Web'
TEMPLATE_FOLDER = WEB_DIR / 'Templates'
STATIC_FOLDER = WEB_DIR / 'Static'
CONFIG_DIRECTORY = CORE_DIR / 'config'
PROJECTS_ROOT_DIRECTORY = CORE_DIR / 'projects'
CAPTURE_ROOT_DIRECTORY = CORE_DIR / 'tmp' / 'captures'


def create_app(base_dir: Path | None = None) -> Flask:
    resolved_project_root = base_dir or PROJECT_ROOT_DIR

    core_dir = resolved_project_root / 'Core'
    web_dir = resolved_project_root / 'Web'
    template_folder = web_dir / 'Templates'
    static_folder = web_dir / 'Static'
    config_directory = core_dir / 'config'
    projects_root_directory = core_dir / 'projects'
    capture_root_directory = core_dir / 'tmp' / 'captures'

    app = Flask(
        __name__,
        template_folder=str(template_folder.resolve()),
        static_folder=str(static_folder.resolve()),
        static_url_path='/static',
    )

    config_service = ConfigService(config_directory)
    calibration_settings = config_service.load_calibration()
    camera_profile = config_service.load_camera_profile()

    pixels_per_inch = float(
        calibration_settings.get('pixels_per_inch', DEFAULT_PIXELS_PER_INCH)
        or DEFAULT_PIXELS_PER_INCH
    )

    app.config['BASE_DIR'] = str(resolved_project_root)
    app.config['CONFIG_SERVICE'] = config_service
    app.config['PROJECT_SERVICE'] = ProjectService(projects_root_directory)
    app.config['CSV_SERVICE'] = CsvService()
    app.config['IMAGE_SERVICE'] = ImageService()
    app.config['MEASUREMENT_SERVICE'] = MeasurementService(pixels_per_inch)
    app.config['CAMERA_SERVICE'] = CameraService(capture_root_directory, camera_profile)

    app.register_blueprint(page_blueprint)
    app.register_blueprint(api_blueprint)

    return app
