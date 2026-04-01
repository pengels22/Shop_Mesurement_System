from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JSON_INDENT = 2
JSON_ENCODING = 'utf-8'


class FileService:
    @staticmethod
    def ensure_dir(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def read_json(path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        with path.open('r', encoding=JSON_ENCODING) as file_handle:
            return json.load(file_handle)

    @staticmethod
    def write_json(path: Path, data: Any) -> None:
        FileService.ensure_dir(path.parent)
        with path.open('w', encoding=JSON_ENCODING) as file_handle:
            json.dump(data, file_handle, indent=JSON_INDENT)

    @staticmethod
    def delete_if_exists(path: Path) -> None:
        if path.exists():
            path.unlink()
