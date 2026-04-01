from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_file

from Core.services.file_service import FileService
from Core.utils.naming import sanitize_name, ui_normalize_spaces

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_SERVER_ERROR = 500
DEFAULT_MEASUREMENT_TYPE = 'simple'

api_blueprint = Blueprint('api', __name__, url_prefix='/api')


def get_project_service():
    return current_app.config['PROJECT_SERVICE']


def get_csv_service():
    return current_app.config['CSV_SERVICE']


def get_image_service():
    return current_app.config['IMAGE_SERVICE']


def get_measurement_service():
    return current_app.config['MEASUREMENT_SERVICE']


def get_camera_service():
    return current_app.config['CAMERA_SERVICE']


def json_error(status: str, message: str, http_code: int, **extra_fields) -> tuple[Response, int]:
    payload = {'ok': False, 'status': status, 'message': message}
    payload.update(extra_fields)
    return jsonify(payload), http_code


@api_blueprint.get('/health')
def health() -> Response:
    return jsonify({'ok': True, 'status': 'healthy'})


@api_blueprint.get('/camera/stream')
def camera_stream() -> Response:
    camera_service = get_camera_service()
    return Response(camera_service.mjpeg_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')


@api_blueprint.post('/camera/capture')
def capture_frame() -> Response:
    camera_service = get_camera_service()
    frame_id, frame_path, image_width, image_height = camera_service.capture_frame()
    return jsonify({
        'ok': True,
        'image_frame_id': frame_id,
        'image_path': str(frame_path),
        'image_width': image_width,
        'image_height': image_height,
    })


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
    camera_service = get_camera_service()

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
        validated_measurements, validation_errors = measurement_service.validate_measurements(measurements, image_width, image_height)
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
