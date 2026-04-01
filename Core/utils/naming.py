from __future__ import annotations

import re

WHITESPACE_PATTERN = r'\s+'
SAFE_CHARACTER_PATTERN = r'[^a-z0-9_]'
MULTIPLE_UNDERSCORES_PATTERN = r'_+'


def ui_normalize_spaces(value: str) -> str:
    normalized_value = value.strip()
    normalized_value = re.sub(WHITESPACE_PATTERN, '_', normalized_value)
    return normalized_value


def sanitize_name(value: str) -> str:
    sanitized_value = ui_normalize_spaces(value)
    sanitized_value = sanitized_value.lower()
    sanitized_value = re.sub(SAFE_CHARACTER_PATTERN, '', sanitized_value)
    sanitized_value = re.sub(MULTIPLE_UNDERSCORES_PATTERN, '_', sanitized_value).strip('_')
    return sanitized_value
