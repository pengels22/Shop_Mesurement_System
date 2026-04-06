from __future__ import annotations

from pathlib import Path
import time

import cv2
import numpy as np
from flask import Blueprint, Response, current_app, jsonify, request, send_file

from Core.services.camera_service import (
    CameraService,
    JPEG_EXTENSION,
    MJPEG_BOUNDARY,
    MJPEG_CONTENT_TYPE,
    MJPEG_LINE_BREAK,
)
from Core.services.file_service import FileService
from Core.services.measurement_service import MeasurementService
from Core.utils.naming import sanitize_name, ui_normalize_spaces

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_SERVER_ERROR = 500
DEFAULT_MEASUREMENT_TYPE = 'simple'
DEFAULT_PIXELS_PER_INCH = 33.0

api_blueprint = Blueprint('api', __name__, url_prefix='/api')


def get_project_service():
    return current_app.config['PROJECT_SERVICE']


def get_csv_service():
    return current_app.config['CSV_SERVICE']


def get_image_service():
    return current_app.config['IMAGE_SERVICE']


def get_measurement_service():
    return current_app.config['MEASUREMENT_SERVICE']


def get_camera_services() -> dict:
    return current_app.config.get('CAMERA_SERVICES') or {'top': current_app.config['CAMERA_SERVICE']}


def ensure_camera_id(camera_id: str | None) -> str:
    if camera_id in ('top', 'side'):
        return camera_id
    return 'top'


def get_camera_service(camera_id: str | None = 'top'):
    camera_id = ensure_camera_id(camera_id)
    services = get_camera_services()
    return services.get(camera_id) or services.get('top')


def rebuild_runtime_services() -> None:
    """Reload camera profile + calibration and refresh runtime services so changes apply immediately."""
    config_service = current_app.config['CONFIG_SERVICE']
    capture_root = Path(current_app.config['CAPTURE_ROOT_DIRECTORY'])
    mask_profile = config_service.load_mask()
    camera_profile = config_service.load_camera_profile()
    calibration_settings = config_service.load_calibration()

    camera_services = {
        'top': CameraService(capture_root, camera_profile.get('top', {}), mask_profile, calibration_settings.get('top')),
        'side': CameraService(capture_root, camera_profile.get('side', {}), mask_profile, calibration_settings.get('side')),
    }
    current_app.config['CAMERA_SERVICES'] = camera_services
    current_app.config['CAMERA_SERVICE'] = camera_services['top']

    ppi_map = {
        'top': float(calibration_settings.get('top', {}).get('pixels_per_inch', calibration_settings.get('pixels_per_inch', DEFAULT_PIXELS_PER_INCH))),
        'side': float(calibration_settings.get('side', {}).get('pixels_per_inch', calibration_settings.get('pixels_per_inch', DEFAULT_PIXELS_PER_INCH))),
    }
    current_app.config['MEASUREMENT_SERVICE'] = MeasurementService(ppi_map)


def json_error(status: str, message: str, http_code: int, **extra_fields) -> tuple[Response, int]:
    payload = {'ok': False, 'status': status, 'message': message}
    payload.update(extra_fields)
    return jsonify(payload), http_code


@api_blueprint.get('/health')
def health() -> Response:
    return jsonify({'ok': True, 'status': 'healthy'})


@api_blueprint.get('/camera/stream')
def camera_stream() -> Response:
    camera_id = ensure_camera_id(request.args.get('camera'))
    camera_service = get_camera_service(camera_id)
    return Response(camera_service.mjpeg_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')


def _preview_generator(index: int):
    capture = cv2.VideoCapture(index)
    if not capture or not capture.isOpened():
        while True:
            time.sleep(0.5)
            yield MJPEG_BOUNDARY + MJPEG_CONTENT_TYPE + b'' + MJPEG_LINE_BREAK
    try:
        while True:
            success, frame = capture.read()
            if not success or frame is None:
                time.sleep(0.2)
                continue
            ok, encoded = cv2.imencode(JPEG_EXTENSION, frame)
            if not ok:
                continue
            jpg_bytes = encoded.tobytes()
            yield MJPEG_BOUNDARY + MJPEG_CONTENT_TYPE + jpg_bytes + MJPEG_LINE_BREAK
    finally:
        capture.release()


@api_blueprint.get('/camera/preview')
def camera_preview() -> Response:
    try:
        index = int(request.args.get('index', -1))
    except ValueError:
        return json_error('validation_error', 'index must be an integer', HTTP_BAD_REQUEST)
    if index < 0:
        return json_error('validation_error', 'index must be >= 0', HTTP_BAD_REQUEST)
    return Response(_preview_generator(index), mimetype='multipart/x-mixed-replace; boundary=frame')


@api_blueprint.get('/camera/preview.jpg')
def camera_preview_jpg() -> Response:
    """
    Return a single JPEG frame for lightweight previews (avoids long-lived MJPEG streams that can crash Safari).
    """
    try:
        index = int(request.args.get('index', -1))
    except ValueError:
        return json_error('validation_error', 'index must be an integer', HTTP_BAD_REQUEST)
    if index < 0:
        return json_error('validation_error', 'index must be >= 0', HTTP_BAD_REQUEST)

    cap = cv2.VideoCapture(index)
    if not cap or not cap.isOpened():
        if cap:
            cap.release()
        return json_error('camera_unavailable', f'Camera {index} not available', 503)
    success, frame = cap.read()
    cap.release()
    if not success or frame is None:
        return json_error('frame_error', f'Camera {index} did not return a frame', 503)

    ok, encoded = cv2.imencode(JPEG_EXTENSION, frame)
    if not ok:
        return json_error('encode_error', 'Failed to encode frame', 500)

    return Response(encoded.tobytes(), mimetype='image/jpeg')


@api_blueprint.post('/camera/capture')
def capture_frame() -> Response:
    payload = request.get_json(silent=True) or {}
    camera_id = ensure_camera_id(request.args.get('camera') or payload.get('camera'))
    camera_service = get_camera_service(camera_id)
    try:
        frame_id, frame_path, image_width, image_height = camera_service.capture_frame()
    except Exception as exc:  # pylint: disable=broad-except
        current_app.logger.error("Camera capture failed for %s: %s", camera_id, exc, exc_info=True)
        return json_error('capture_failed', f'Camera {camera_id} failed to capture: {exc}', HTTP_SERVER_ERROR)

    return jsonify({
        'ok': True,
        'camera': camera_id,
        'image_frame_id': frame_id,
        'image_path': str(frame_path),
        'image_width': image_width,
        'image_height': image_height,
    })


@api_blueprint.get('/camera/devices')
def list_camera_devices() -> Response:
    max_index = int(request.args.get('max', 5))
    config_profile = current_app.config['CONFIG_SERVICE'].load_camera_profile()
    active = {
        'top': config_profile.get('top', {}).get('camera_index'),
        'side': config_profile.get('side', {}).get('camera_index'),
    }
    active_indices = {idx for idx in (active['top'], active['side']) if idx is not None}
    devices = []
    for index in range(max_index + 1):
        cap = cv2.VideoCapture(index)
        available = cap is not None and cap.isOpened()
        if cap:
            cap.release()
        devices.append({
            'index': index,
            'label': f'Camera {index}',
            'available': bool(available or index in active_indices),
        })

    # Ensure active indices are present even if beyond max_index
    for idx in active_indices:
        if not any(device['index'] == idx for device in devices):
            devices.append({'index': idx, 'label': f'Camera {idx}', 'available': True})

    return jsonify({'ok': True, 'devices': devices, 'active': active})


@api_blueprint.get('/camera/profile')
def get_camera_profile() -> Response:
    profile = current_app.config['CONFIG_SERVICE'].load_camera_profile()
    return jsonify({'ok': True, 'profile': profile})


@api_blueprint.post('/camera/profile')
def update_camera_profile() -> Response:
    payload = request.get_json(force=True)
    config_service = current_app.config['CONFIG_SERVICE']
    profile = config_service.load_camera_profile()

    if 'top_index' in payload:
        profile.setdefault('top', {})['camera_index'] = int(payload['top_index'])
    if 'side_index' in payload:
        profile.setdefault('side', {})['camera_index'] = int(payload['side_index'])

    config_service.save_camera_profile(profile)
    rebuild_runtime_services()
    return jsonify({'ok': True, 'profile': profile})


@api_blueprint.get('/calibration')
def get_calibration() -> Response:
    calibration = current_app.config['CONFIG_SERVICE'].load_calibration()
    return jsonify({'ok': True, 'calibration': calibration})


@api_blueprint.post('/calibration')
def update_calibration() -> Response:
    payload = request.get_json(force=True)
    camera_id = ensure_camera_id(payload.get('camera'))
    if camera_id not in ('top', 'side'):
        return json_error('validation_error', 'camera must be top or side', HTTP_BAD_REQUEST)

    config_service = current_app.config['CONFIG_SERVICE']
    calibration = config_service.load_calibration()
    camera_cal = calibration.get(camera_id, {})

    if 'pixels_per_inch' in payload:
        ppi = float(payload['pixels_per_inch'])
        if ppi <= 0:
            return json_error('validation_error', 'pixels_per_inch must be positive', HTTP_BAD_REQUEST)
        camera_cal['pixels_per_inch'] = ppi

    for key in ('camera_matrix', 'dist_coeffs', 'homography'):
        if key in payload:
            camera_cal[key] = payload[key]

    calibration[camera_id] = camera_cal
    config_service.save_calibration(calibration)
    rebuild_runtime_services()

    return jsonify({'ok': True, 'calibration': calibration})


@api_blueprint.post('/calibration/solve')
def solve_calibration() -> Response:
    """
    Accept 5 clicked points (top, right, bottom, left, center) and compute pixels_per_inch + homography.
    The physical layout is a cross with outer points 12\" apart (6\" from center on each axis).
    """
    payload = request.get_json(force=True)
    camera_id = ensure_camera_id(payload.get('camera'))
    points = payload.get('points') or []
    if len(points) != 5:
        return json_error('validation_error', 'Five points are required', HTTP_BAD_REQUEST)

    try:
        src = np.array([[float(p['x']), float(p['y'])] for p in points], dtype=np.float64)
    except Exception:
        return json_error('validation_error', 'Points must have numeric x and y', HTTP_BAD_REQUEST)

    # Expected order: top, right, bottom, left, center
    dst = np.array([
        [0.0, -6.0],   # top (inches)
        [6.0, 0.0],    # right
        [0.0, 6.0],    # bottom
        [-6.0, 0.0],   # left
        [0.0, 0.0],    # center
    ], dtype=np.float64)

    # Compute pixels-per-inch from opposing pairs
    def dist(a, b):
        return float(np.linalg.norm(src[a] - src[b]))

    px_lr = dist(1, 3)  # right-left
    px_tb = dist(2, 0)  # bottom-top
    if px_lr <= 0 or px_tb <= 0:
        return json_error('validation_error', 'Point distances are degenerate', HTTP_BAD_REQUEST)
    pixels_per_inch = (px_lr / 12.0 + px_tb / 12.0) / 2.0

    # Homography from image pixels -> inch space
    H, status = cv2.findHomography(src, dst, 0)
    if H is None:
        return json_error('solve_failed', 'Could not compute homography', HTTP_SERVER_ERROR)

    config_service = current_app.config['CONFIG_SERVICE']
    calibration = config_service.load_calibration()
    camera_cal = calibration.get(camera_id, {})
    camera_cal['pixels_per_inch'] = float(pixels_per_inch)
    camera_cal['homography'] = H.tolist()
    calibration[camera_id] = camera_cal
    config_service.save_calibration(calibration)
    rebuild_runtime_services()

    return jsonify({
        'ok': True,
        'camera': camera_id,
        'pixels_per_inch': pixels_per_inch,
        'homography': H.tolist(),
    })




@api_blueprint.get('/camera/capture/<frame_id>')
def get_captured_frame(frame_id: str) -> Response:
    camera_id = ensure_camera_id(request.args.get('camera'))
    camera_service = get_camera_service(camera_id)
    try:
        frame_path = camera_service.capture_root / f'{frame_id}.png'
    except Exception:
        return json_error('capture_not_found', 'Capture not found', HTTP_NOT_FOUND)
    if not frame_path.exists():
        return json_error('capture_not_found', 'Capture not found', HTTP_NOT_FOUND)
    return send_file(frame_path)


@api_blueprint.post('/projects')
def create_project() -> Response:
    payload = request.get_json(force=True)
    project_name = ui_normalize_spaces(payload.get('project_name', ''))
    if not project_name:
        return json_error('validation_error', 'project_name is required', HTTP_BAD_REQUEST)

    project_service = get_project_service()
    project_record = project_service.create_or_update_project(payload)
    return jsonify({'ok': True, 'status': 'saved', 'project': project_record.to_dict()})


@api_blueprint.get('/projects')
def list_projects() -> Response:
    project_service = get_project_service()
    active_project = project_service.get_active_project()
    return jsonify({'ok': True, 'projects': project_service.list_projects(), 'active_project': active_project})


@api_blueprint.post('/projects/activate')
def activate_project() -> Response:
    payload = request.get_json(force=True)
    project_name = ui_normalize_spaces(payload.get('project_name', ''))
    if not project_name:
        return json_error('validation_error', 'project_name is required', HTTP_BAD_REQUEST)

    project_service = get_project_service()
    try:
        project_record = project_service.activate_project_by_name(project_name)
    except FileNotFoundError as exc:
        return json_error('not_found', str(exc), HTTP_NOT_FOUND)

    return jsonify({'ok': True, 'status': 'active', 'project': project_record})


@api_blueprint.get('/projects/active')
def active_project() -> Response:
    project_service = get_project_service()
    project_record = project_service.get_active_project()
    if not project_record:
        return json_error('no_active_project', 'No active project set', HTTP_NOT_FOUND)
    return jsonify({'ok': True, 'project': project_record})


@api_blueprint.get('/projects/active/parts')
def list_active_parts() -> Response:
    project_service = get_project_service()
    csv_service = get_csv_service()

    active_project = project_service.get_active_project()
    if not active_project:
        return json_error('no_active_project', 'No active project set', HTTP_NOT_FOUND)

    csv_path = Path(active_project['project_directory']) / active_project['csv_filename']
    grouped_rows = csv_service.read_grouped(csv_path)
    parts = []

    for grouped_row in grouped_rows:
        file_stem = sanitize_name(grouped_row['part_name'])
        part_json_path = Path(active_project['default_save_location']) / f'{file_stem}.json'
        part_data = FileService.read_json(part_json_path, {})
        grouped_row['measurement_type'] = part_data.get('measurement_type', DEFAULT_MEASUREMENT_TYPE)
        if part_data.get('measurements'):
            grouped_row['measurements'] = [
                {
                    'label': measurement.get('label'),
                    'value_in': measurement.get('value_in'),
                    'color': measurement.get('color'),
                }
                for measurement in part_data.get('measurements', [])
            ]
        parts.append(grouped_row)

    return jsonify({'ok': True, 'project_name': active_project['project_name'], 'parts': parts})


@api_blueprint.get('/parts/image/<path:filename>')
def get_part_image(filename: str) -> Response:
    project_service = get_project_service()
    active_project = project_service.get_active_project()
    if not active_project:
        return json_error('no_active_project', 'No active project set', HTTP_NOT_FOUND)

    image_path = Path(active_project['default_save_location']) / filename
    if not image_path.exists():
        return json_error('not_found', 'Image not found', HTTP_NOT_FOUND)

    return send_file(image_path)


@api_blueprint.post('/parts/check-name')
def check_part_name() -> Response:
    payload = request.get_json(force=True)
    project_name = ui_normalize_spaces(payload.get('project_name', ''))
    part_name = ui_normalize_spaces(payload.get('part_name', ''))

    if not project_name or not part_name:
        return json_error('validation_error', 'project_name and part_name are required', HTTP_BAD_REQUEST)

    project_service = get_project_service()
    project_record = project_service.get_project_by_name(project_name)
    if not project_record:
        return json_error('not_found', 'Project not found', HTTP_NOT_FOUND)

    file_stem = sanitize_name(part_name)
    exists = (Path(project_record['default_save_location']) / f'{file_stem}.json').exists()
    return jsonify({'ok': True, 'exists': exists, 'file_stem': file_stem})


@api_blueprint.post('/parts/save')
def save_part() -> Response:
    payload = request.get_json(force=True)

    project_service = get_project_service()
    csv_service = get_csv_service()
    image_service = get_image_service()
    measurement_service = get_measurement_service()
    camera_id = ensure_camera_id(payload.get('camera') or payload.get('camera_id'))
    camera_service = get_camera_service(camera_id)

    active_project = project_service.get_active_project()
    if not active_project:
        return json_error('no_active_project', 'No active project set', HTTP_NOT_FOUND)

    project_name = ui_normalize_spaces(payload.get('project_name', ''))
    if project_name != active_project['project_name']:
        return json_error('project_mismatch', 'Payload project_name does not match active project', HTTP_BAD_REQUEST)

    part_name = ui_normalize_spaces(payload.get('part_name', ''))
    if not part_name:
        return json_error('validation_error', 'part_name is required', HTTP_BAD_REQUEST)

    frame_id = payload.get('image_frame_id')
    if not frame_id:
        return json_error('validation_error', 'image_frame_id is required', HTTP_BAD_REQUEST)

    overwrite_existing = bool(payload.get('overwrite', False))
    image_width = int(payload.get('image_width', 0) or 0)
    image_height = int(payload.get('image_height', 0) or 0)
    measurement_type = payload.get('measurement_type', DEFAULT_MEASUREMENT_TYPE)
    measurements = payload.get('measurements', [])

    file_stem = sanitize_name(part_name)
    if not file_stem:
        return json_error('validation_error', 'part_name is invalid after sanitization', HTTP_BAD_REQUEST)

    parts_directory = Path(active_project['default_save_location'])
    image_filename = f'{file_stem}.png'
    json_filename = f'{file_stem}.json'
    image_path = parts_directory / image_filename
    json_path = parts_directory / json_filename
    csv_path = Path(active_project['project_directory']) / active_project['csv_filename']

    if (image_path.exists() or json_path.exists()) and not overwrite_existing:
        return json_error(
            'part_exists',
            f"A part named '{part_name}' already exists.",
            HTTP_CONFLICT,
            part_name=part_name,
            file_stem=file_stem,
        )

    try:
        frame = camera_service.load_captured_frame(frame_id)
    except (FileNotFoundError, RuntimeError) as exc:
        return json_error('capture_not_found', str(exc), HTTP_NOT_FOUND)

    if not image_width or not image_height:
        image_height, image_width = frame.shape[:2]

    try:
        validated_measurements, validation_errors = measurement_service.validate_measurements(measurements, image_width, image_height, camera_id=camera_id)
    except ValueError as exc:
        return json_error('validation_error', str(exc), HTTP_BAD_REQUEST)

    if validation_errors:
        return json_error(
            'validation_error',
            validation_errors[0]['message'],
            HTTP_BAD_REQUEST,
            errors=validation_errors,
        )

    try:
        image_service.render_annotated_image(frame, part_name, validated_measurements, image_path)
    except RuntimeError as exc:
        return json_error('write_error', str(exc), HTTP_SERVER_ERROR)

    part_payload = {
        'part_name': part_name,
        'file_stem': file_stem,
        'image_filename': image_filename,
        'measurement_type': measurement_type,
        'camera': camera_id,
        'measurements': validated_measurements,
    }
    FileService.write_json(json_path, part_payload)

    if overwrite_existing:
        csv_service.remove_part_rows(csv_path, part_name)
    csv_service.append_part_rows(csv_path, part_name, image_filename, validated_measurements)

    response_measurements = []
    for measurement in validated_measurements:
        response_measurements.append({
            'label': measurement['label'],
            'color': measurement['color'],
            'value_in': measurement['value_in'],
        })

    return jsonify({
        'ok': True,
        'status': 'saved',
        'project_name': active_project['project_name'],
        'part_name': part_name,
        'file_stem': file_stem,
        'image_filename': image_filename,
        'camera': camera_id,
        'json_filename': json_filename,
        'csv_filename': active_project['csv_filename'],
        'measurement_count': len(validated_measurements),
        'measurements': response_measurements,
    })


@api_blueprint.post('/parts/delete')
def delete_part() -> Response:
    payload = request.get_json(force=True)

    project_service = get_project_service()
    csv_service = get_csv_service()

    active_project = project_service.get_active_project()
    if not active_project:
        return json_error('no_active_project', 'No active project set', HTTP_NOT_FOUND)

    part_name = ui_normalize_spaces(payload.get('part_name', ''))
    if not part_name:
        return json_error('validation_error', 'part_name is required', HTTP_BAD_REQUEST)

    file_stem = sanitize_name(part_name)
    image_path = Path(active_project['default_save_location']) / f'{file_stem}.png'
    json_path = Path(active_project['default_save_location']) / f'{file_stem}.json'
    csv_path = Path(active_project['project_directory']) / active_project['csv_filename']

    FileService.delete_if_exists(image_path)
    FileService.delete_if_exists(json_path)
    csv_service.remove_part_rows(csv_path, part_name)

    return jsonify({'ok': True, 'status': 'deleted', 'part_name': part_name})
