from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

DEFAULT_UNITS = 'inches'
DEFAULT_CSV_FILENAME = 'measurements.csv'


@dataclass
class Project:
    project_name: str
    project_directory: str
    project_description: str
    default_save_location: str
    notes: str
    csv_filename: str = DEFAULT_CSV_FILENAME
    units: str = DEFAULT_UNITS

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    @property
    def root_path(self) -> Path:
        return Path(self.project_directory)

    @property
    def parts_path(self) -> Path:
        return Path(self.default_save_location)
