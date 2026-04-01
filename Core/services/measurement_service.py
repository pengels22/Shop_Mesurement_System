from __future__ import annotations

import re
from typing import Dict
from typing import List
from typing import Tuple

from Core.utils.constants import COLOR_MAP
from Core.utils.constants import EXTRA_COLORS
from Core.utils.constants import MIN_LINE_MM
from Core.utils.constants import MM_PER_INCH
from Core.utils.geometry import line_length_px

AXIS_LABELS = {'X', 'Y', 'Z'}
M_LABEL_PATTERN = r'M(\d+)'


class MeasurementService:
    def __init__(self, pixels_per_inch: float):
        if pixels_per_inch <= 0:
            raise ValueError('pixels_per_inch must be positive')
        self.pixels_per_inch = float(pixels_per_inch)

    def expected_color(self, label: str) -> str:
        if label in COLOR_MAP:
            return COLOR_MAP[label][0]
        match = re.fullmatch(M_LABEL_PATTERN, label)
        if not match:
            raise ValueError(f'Invalid label: {label}')
        measurement_index = int(match.group(1)) - 1
        return EXTRA_COLORS[measurement_index % len(EXTRA_COLORS)][0]

    def normalize_m_labels(self, measurements: List[Dict]) -> List[Dict]:
        fixed_measurements = []
        extra_measurements = []

        for measurement in measurements:
            if measurement['label'] in AXIS_LABELS:
                fixed_measurements.append(dict(measurement))
            else:
                extra_measurements.append(dict(measurement))

        for measurement_number, measurement in enumerate(extra_measurements, start=1):
            measurement['label'] = f'M{measurement_number}'
            measurement['color'] = self.expected_color(measurement['label'])

        axis_order = {'X': 0, 'Y': 1, 'Z': 2}
        fixed_measurements = sorted(fixed_measurements, key=lambda item: axis_order[item['label']])
        return fixed_measurements + extra_measurements

    def validate_measurements(self, measurements: List[Dict], image_width: int, image_height: int) -> Tuple[List[Dict], List[Dict]]:
        if not measurements:
            raise ValueError('At least one measurement is required')

        normalized_measurements = self.normalize_m_labels(measurements)
        processed_measurements: List[Dict] = []
        validation_errors: List[Dict] = []
        seen_axis_labels = set()

        for measurement_index, measurement in enumerate(normalized_measurements):
            label = measurement['label']

            if label in AXIS_LABELS:
                if label in seen_axis_labels:
                    validation_errors.append({
                        'field': f'measurements[{measurement_index}]',
                        'code': 'duplicate_axis',
                        'message': f'{label} may only appear once',
                    })
                    continue
                seen_axis_labels.add(label)

            expected_color = self.expected_color(label)
            if measurement.get('color') != expected_color:
                validation_errors.append({
                    'field': f'measurements[{measurement_index}]',
                    'code': 'invalid_color',
                    'message': f'{label} must use color {expected_color}',
                })
                continue

            point_error = self._validate_points(measurement_index, measurement, image_width, image_height)
            if point_error:
                validation_errors.append(point_error)
                continue

            pixel_length = line_length_px(measurement['start_px'], measurement['end_px'])
            inches_value = pixel_length / self.pixels_per_inch
            millimeters_value = inches_value * MM_PER_INCH
            if millimeters_value < MIN_LINE_MM:
                validation_errors.append({
                    'field': f'measurements[{measurement_index}]',
                    'code': 'line_too_short',
                    'message': f'Measurement {label} is shorter than 1 mm.',
                })
                continue

            processed_measurements.append({
                'label': label,
                'color': expected_color,
                'start_px': {
                    'x': float(measurement['start_px']['x']),
                    'y': float(measurement['start_px']['y']),
                },
                'end_px': {
                    'x': float(measurement['end_px']['x']),
                    'y': float(measurement['end_px']['y']),
                },
                'length_px': round(pixel_length, 4),
                'value_in': round(inches_value, 4),
            })

        return processed_measurements, validation_errors

    @staticmethod
    def _validate_points(measurement_index: int, measurement: Dict, image_width: int, image_height: int) -> Dict | None:
        for point_name in ('start_px', 'end_px'):
            point = measurement.get(point_name) or {}
            x_position = float(point.get('x', -1))
            y_position = float(point.get('y', -1))
            if x_position < 0 or y_position < 0 or x_position > image_width or y_position > image_height:
                return {
                    'field': f'measurements[{measurement_index}].{point_name}',
                    'code': 'out_of_bounds',
                    'message': f'{point_name} is outside image bounds',
                }
        return None
