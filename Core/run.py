from __future__ import annotations

from pathlib import Path

from Core import create_app

HOST = '0.0.0.0'
PORT = 5000
DEBUG_MODE = True

app = create_app(Path(__file__).resolve().parent.parent)


if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=DEBUG_MODE)
