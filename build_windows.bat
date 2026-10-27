@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt pyinstaller
py -m PyInstaller --noconfirm --windowed --name GameSense --collect-all matplotlib app.py
echo Build created in dist\GameSense\
pause
