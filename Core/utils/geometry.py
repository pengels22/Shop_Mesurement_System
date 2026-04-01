from __future__ import annotations

from math import hypot
from typing import Dict


def line_length_px(start: Dict[str, float], end: Dict[str, float]) -> float:
    return hypot(float(end['x']) - float(start['x']), float(end['y']) - float(start['y']))
