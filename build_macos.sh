#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt pyinstaller
python3 -m PyInstaller --noconfirm --windowed --name GameSense --collect-all matplotlib app.py
echo "Build created in dist/GameSense.app"
