COLOR_MAP = {
    'X': ('red', (0, 0, 255)),
    'Y': ('blue', (255, 0, 0)),
    'Z': ('green', (0, 255, 0)),
}

EXTRA_COLORS = [
    ('yellow', (0, 255, 255)),
    ('purple', (255, 0, 255)),
    ('orange', (0, 165, 255)),
    ('cyan', (255, 255, 0)),
    ('magenta', (255, 0, 255)),
    ('lime', (0, 255, 128)),
    ('pink', (203, 192, 255)),
]

CSV_HEADER = ['PartName', 'Measurement', 'Value', 'ImageFilename']
CSV_HEADER_LINE = 'PartName,Measurement,Value,ImageFilename\n'
CSV_ENCODING = 'utf-8'
CSV_VALUE_PRECISION = 4
DEFAULT_CSV_FILENAME = 'measurements.csv'
DEFAULT_PARTS_DIRECTORY_NAME = 'parts'
MIN_LINE_MM = 1.0
MM_PER_INCH = 25.4
LINE_THICKNESS = 2
LINE_CIRCLE_RADIUS = 5
IMAGE_PANEL_MIN_WIDTH = 260
IMAGE_PANEL_BACKGROUND = 245
IMAGE_PANEL_LEFT_MARGIN = 16
IMAGE_PANEL_HEIGHT_OFFSET = 65
IMAGE_PANEL_LINE_SPACING = 28
IMAGE_PANEL_NAME_FONT_SCALE = 0.8
IMAGE_PANEL_VALUE_FONT_SCALE = 0.7
IMAGE_PANEL_TEXT_COLOR = (25, 25, 25)
