#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
python3 scripts/build.py --installer
echo "Disk image created in output/GameSense-macOS.dmg"
