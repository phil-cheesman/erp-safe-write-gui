@echo off
cd /d "%~dp0"
python -m estship_uploader
if errorlevel 1 pause
