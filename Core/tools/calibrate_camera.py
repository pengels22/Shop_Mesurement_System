"""Calibrate camera from chessboard images and save camera profile JSON.

Usage:
  python calibrate_camera.py --images ./calib_images --width 9 --height 6 --square-size-mm 25 --out ../../Core/config/camera_profile.json

Outputs a JSON with keys: camera_matrix (3x3 list) and dist_coeffs (list).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import cv2
import numpy as np


def find_image_files(folder: Path) -> List[Path]:
    exts = ('*.png', '*.jpg', '*.jpeg')
    files = []
    for ext in exts:
        files.extend(folder.glob(ext))
    return sorted(files)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--images', required=True, help='Folder with chessboard images')
    parser.add_argument('--width', type=int, required=True, help='Number of inner corners per chessboard row')
    parser.add_argument('--height', type=int, required=True, help='Number of inner corners per chessboard column')
    parser.add_argument('--square-size-mm', type=float, default=25.0, help='Square size in mm (optional)')
    parser.add_argument('--out', required=True, help='Output JSON path')
    args = parser.parse_args()

    folder = Path(args.images)
    images = find_image_files(folder)
    if not images:
        raise SystemExit('No images found in folder')

    pattern_size = (args.width, args.height)
    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    objp *= args.square_size_mm

    objpoints = []
    imgpoints = []

    for img_path in images:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(gray, pattern_size, None)
        if found:
            term = (cv2.TermCriteria_EPS + cv2.TermCriteria_MAX_ITER, 30, 0.001)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), term)
            objpoints.append(objp)
            imgpoints.append(corners2)

    if not objpoints:
        raise SystemExit('No chessboard patterns found in images')

    img_size = (int(gray.shape[1]), int(gray.shape[0]))
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, img_size, None, None)
    if not ret:
        raise SystemExit('Calibration failed')

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json_data = {
        'camera_matrix': camera_matrix.tolist(),
        'dist_coeffs': dist_coeffs.ravel().tolist(),
    }
    out.write_text(json.dumps(json_data, indent=2))
    print(f'Wrote camera profile to {out}')


if __name__ == '__main__':
    main()
