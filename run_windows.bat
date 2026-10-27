@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 (echo Installation failed. & pause & exit /b 1)
py app.py
if errorlevel 1 pause
