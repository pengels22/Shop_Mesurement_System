from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict
from typing import List

from Core.utils.constants import CSV_ENCODING
from Core.utils.constants import CSV_HEADER
from Core.utils.constants import CSV_VALUE_PRECISION


class CsvService:
    @staticmethod
    def append_part_rows(csv_path: Path, part_name: str, image_filename: str, measurements: List[Dict]) -> None:
        file_exists = csv_path.exists()
        with csv_path.open('a', newline='', encoding=CSV_ENCODING) as file_handle:
            writer = csv.writer(file_handle)
            if not file_exists:
                writer.writerow(CSV_HEADER)
            for measurement in measurements:
                writer.writerow([
                    part_name,
                    measurement['label'],
                    f"{measurement['value_in']:.{CSV_VALUE_PRECISION}f}",
                    image_filename,
                ])

    @staticmethod
    def remove_part_rows(csv_path: Path, part_name: str) -> None:
        if not csv_path.exists():
            return
        with csv_path.open('r', newline='', encoding=CSV_ENCODING) as file_handle:
            all_rows = list(csv.reader(file_handle))
        if not all_rows:
            return
        header_row = all_rows[0]
        data_rows = all_rows[1:]
        filtered_rows = [row for row in data_rows if row and row[0] != part_name]
        with csv_path.open('w', newline='', encoding=CSV_ENCODING) as file_handle:
            writer = csv.writer(file_handle)
            writer.writerow(header_row or CSV_HEADER)
            writer.writerows(filtered_rows)

    @staticmethod
    def read_grouped(csv_path: Path) -> List[Dict]:
        if not csv_path.exists():
            return []

        grouped_parts: Dict[str, Dict] = {}
        with csv_path.open('r', newline='', encoding=CSV_ENCODING) as file_handle:
            reader = csv.DictReader(file_handle)
            for row in reader:
                part_name = row['PartName']
                grouped_parts.setdefault(part_name, {
                    'part_name': part_name,
                    'image_filename': row['ImageFilename'],
                    'measurements': [],
                })
                grouped_parts[part_name]['measurements'].append({
                    'label': row['Measurement'],
                    'value_in': float(row['Value']),
                })
        return list(grouped_parts.values())
