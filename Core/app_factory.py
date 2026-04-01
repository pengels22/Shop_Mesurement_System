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

DEFAULT_PIXELS_PER_INCH = 100.0
TEMPLATE_FOLDER_RELATIVE = '../Web/Templates'
STATIC_FOLDER_RELATIVE = '../Web/Static'


def create_app(base_dir: Path | None = None) -> Flask:
    resolved_base_dir = base_dir or Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str((resolved_base_dir / TEMPLATE_FOLDER_RELATIVE).resolve()),
        static_folder=str((resolved_base_dir / STATIC_FOLDER_RELATIVE).resolve()),
        static_url_path='/static',
    )

    config_directory = resolved_base_dir / 'Core' / 'config'
    projects_root_directory = resolved_base_dir / 'Core' / 'projects'
    capture_root_directory = resolved_base_dir / 'Core' / 'tmp' / 'captures'

    config_service = ConfigService(config_directory)
    calibration_settings = config_service.load_calibration()
    camera_profile = config_service.load_camera_profile()

    pixels_per_inch = float(calibration_settings.get('pixels_per_inch', DEFAULT_PIXELS_PER_INCH) or DEFAULT_PIXELS_PER_INCH)

    app.config['BASE_DIR'] = str(resolved_base_dir)
    app.config['CONFIG_SERVICE'] = config_service
    app.config['PROJECT_SERVICE'] = ProjectService(projects_root_directory)
    app.config['CSV_SERVICE'] = CsvService()
    app.config['IMAGE_SERVICE'] = ImageService()
    app.config['MEASUREMENT_SERVICE'] = MeasurementService(pixels_per_inch)
    app.config['CAMERA_SERVICE'] = CameraService(capture_root_directory, camera_profile)

    app.register_blueprint(page_blueprint)
    app.register_blueprint(api_blueprint)

    return app
