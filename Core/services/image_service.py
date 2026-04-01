from __future__ import annotations

from pathlib import Path
from typing import Dict
from typing import List
from typing import Tuple

import cv2
import numpy as np

from Core.utils.constants import COLOR_MAP
from Core.utils.constants import EXTRA_COLORS
from Core.utils.constants import IMAGE_PANEL_BACKGROUND
from Core.utils.constants import IMAGE_PANEL_HEIGHT_OFFSET
from Core.utils.constants import IMAGE_PANEL_LEFT_MARGIN
from Core.utils.constants import IMAGE_PANEL_LINE_SPACING
from Core.utils.constants import IMAGE_PANEL_MIN_WIDTH
from Core.utils.constants import IMAGE_PANEL_NAME_FONT_SCALE
from Core.utils.constants import IMAGE_PANEL_TEXT_COLOR
from Core.utils.constants import IMAGE_PANEL_VALUE_FONT_SCALE
from Core.utils.constants import LINE_CIRCLE_RADIUS
from Core.utils.constants import LINE_THICKNESS


class ImageService:
    @staticmethod
    def bgr_for(label: str) -> Tuple[int, int, int]:
        if label in COLOR_MAP:
            return COLOR_MAP[label][1]
        measurement_index = int(label[1:]) - 1
        return EXTRA_COLORS[measurement_index % len(EXTRA_COLORS)][1]

    def render_annotated_image(self, frame: np.ndarray, part_name: str, measurements: List[Dict], output_path: Path) -> None:
        image_canvas = frame.copy()
        image_height, image_width = image_canvas.shape[:2]
        panel_width = max(IMAGE_PANEL_MIN_WIDTH, int(image_width * 0.22))
        info_panel = np.full((image_height, panel_width, 3), IMAGE_PANEL_BACKGROUND, dtype=np.uint8)

        cv2.putText(
            info_panel,
            part_name,
            (IMAGE_PANEL_LEFT_MARGIN, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            IMAGE_PANEL_NAME_FONT_SCALE,
            IMAGE_PANEL_TEXT_COLOR,
            2,
            cv2.LINE_AA,
        )

        panel_row_y = IMAGE_PANEL_HEIGHT_OFFSET
        for measurement in measurements:
            color_bgr = self.bgr_for(measurement['label'])
            start_point = (int(round(measurement['start_px']['x'])), int(round(measurement['start_px']['y'])))
            end_point = (int(round(measurement['end_px']['x'])), int(round(measurement['end_px']['y'])))

            cv2.line(image_canvas, start_point, end_point, color_bgr, LINE_THICKNESS, cv2.LINE_AA)
            cv2.circle(image_canvas, start_point, LINE_CIRCLE_RADIUS, color_bgr, -1, cv2.LINE_AA)
            cv2.circle(image_canvas, end_point, LINE_CIRCLE_RADIUS, color_bgr, -1, cv2.LINE_AA)

            cv2.putText(
                info_panel,
                measurement['label'],
                (IMAGE_PANEL_LEFT_MARGIN, panel_row_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                IMAGE_PANEL_VALUE_FONT_SCALE,
                color_bgr,
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                info_panel,
                f"{measurement['value_in']:.4f}",
                (74, panel_row_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                IMAGE_PANEL_VALUE_FONT_SCALE,
                IMAGE_PANEL_TEXT_COLOR,
                2,
                cv2.LINE_AA,
            )
            panel_row_y += IMAGE_PANEL_LINE_SPACING

        annotated_image = np.hstack([info_panel, image_canvas])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output_path), annotated_image):
            raise RuntimeError(f'Failed to save annotated image to {output_path}')
