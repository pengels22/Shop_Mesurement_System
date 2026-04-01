from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Dict
from typing import List


@dataclass
class Measurement:
    label: str
    color: str
    start_px: Dict[str, float]
    end_px: Dict[str, float]
    length_px: float
    value_in: float

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Part:
    part_name: str
    file_stem: str
    image_filename: str
    measurement_type: str
    measurements: List[Measurement] = field(default_factory=list)

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['measurements'] = [measurement.to_dict() for measurement in self.measurements]
        return data
