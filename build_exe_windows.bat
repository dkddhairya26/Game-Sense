@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 (pause & exit /b 1)
py -m PyInstaller --noconfirm --clean --windowed --name GameSense --collect-all matplotlib --collect-all PySide6 app.py
if errorlevel 1 (pause & exit /b 1)
echo Executable created in dist\GameSense\GameSense.exe
pause
