@echo off
setlocal
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
py scripts\build.py
if errorlevel 1 exit /b 1
echo Executable and dependencies created in dist\GameSense\
