from __future__ import annotations

from pathlib import Path
from typing import Dict
from typing import List

from Core.models.project_model import Project
from Core.services.file_service import FileService
from Core.utils.constants import CSV_HEADER_LINE
from Core.utils.constants import DEFAULT_CSV_FILENAME
from Core.utils.constants import DEFAULT_PARTS_DIRECTORY_NAME
from Core.utils.naming import sanitize_name
from Core.utils.naming import ui_normalize_spaces

ACTIVE_PROJECT_FILENAME = 'active_project.json'
PROJECT_CONFIG_FILENAME = 'project.json'


class ProjectService:
    def __init__(self, projects_root: Path):
        self.projects_root = FileService.ensure_dir(projects_root)
        self.active_project_path_file = self.projects_root / ACTIVE_PROJECT_FILENAME

    def create_or_update_project(self, payload: Dict) -> Project:
        project_name = ui_normalize_spaces(payload['project_name'])
        project_stem = sanitize_name(project_name)

        requested_project_directory = ui_normalize_spaces(payload.get('project_directory', '').strip())
        requested_save_location = ui_normalize_spaces(payload.get('default_save_location', '').strip())
        project_description = ui_normalize_spaces(payload.get('project_description', '').strip())
        notes = ui_normalize_spaces(payload.get('notes', '').strip())
        csv_filename = ui_normalize_spaces(payload.get('csv_filename', DEFAULT_CSV_FILENAME).strip()) or DEFAULT_CSV_FILENAME

        if requested_project_directory:
            root_path = Path(requested_project_directory)
            if not root_path.is_absolute():
                root_path = self.projects_root / sanitize_name(requested_project_directory)
        else:
            root_path = self.projects_root / project_stem

        if requested_save_location:
            parts_path = Path(requested_save_location)
            if not parts_path.is_absolute():
                parts_path = root_path / sanitize_name(requested_save_location)
        else:
            parts_path = root_path / DEFAULT_PARTS_DIRECTORY_NAME

        project_record = Project(
            project_name=project_name,
            project_directory=str(root_path),
            project_description=project_description,
            default_save_location=str(parts_path),
            notes=notes,
            csv_filename=csv_filename,
        )

        FileService.ensure_dir(root_path)
        FileService.ensure_dir(parts_path)
        FileService.write_json(root_path / PROJECT_CONFIG_FILENAME, project_record.to_dict())

        csv_path = root_path / project_record.csv_filename
        if not csv_path.exists():
            csv_path.write_text(CSV_HEADER_LINE, encoding='utf-8')

        self.set_active_project(root_path)
        return project_record

    def list_projects(self) -> List[Dict]:
        projects = []
        for project_json_path in sorted(self.projects_root.glob(f'*/{PROJECT_CONFIG_FILENAME}')):
            project_data = FileService.read_json(project_json_path)
            if project_data:
                projects.append(project_data)
        return projects

    def get_project_by_name(self, project_name: str) -> Dict | None:
        normalized_project_name = ui_normalize_spaces(project_name)
        for project_data in self.list_projects():
            if project_data.get('project_name') == normalized_project_name:
                return project_data
        return None

    def set_active_project(self, project_path: Path) -> None:
        FileService.write_json(self.active_project_path_file, {'active_project_path': str(project_path)})

    def get_active_project(self) -> Dict | None:
        active_project_data = FileService.read_json(self.active_project_path_file, {})
        active_project_path = active_project_data.get('active_project_path')
        if not active_project_path:
            return None
        project_json_path = Path(active_project_path) / PROJECT_CONFIG_FILENAME
        return FileService.read_json(project_json_path)

    def activate_project_by_name(self, project_name: str) -> Dict:
        project_data = self.get_project_by_name(project_name)
        if not project_data:
            raise FileNotFoundError(f'Project {project_name} not found')
        self.set_active_project(Path(project_data['project_directory']))
        return project_data
