@echo off
setlocal
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
py scripts\build.py --installer
if errorlevel 1 exit /b 1
echo Installer created in output\GameSenseSetup-Windows.exe
