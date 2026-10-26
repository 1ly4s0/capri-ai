@echo off
rem Starts Capri.
rem   run.bat          on your desktop (no console; log in data\capri.log)
rem   run.bat debug    same, with a console
rem   run.bat video    plays and records video.txt (press F9 when it says READY)
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup.bat first.
  pause
  exit /b 1
)
if not exist config.yaml copy config.example.yaml config.yaml >nul
if /i "%1"=="debug" ( .venv\Scripts\python.exe launch.py & goto :eof )
if /i "%1"=="video" ( .venv\Scripts\python.exe launch.py --video & goto :eof )
start "" .venv\Scripts\pythonw.exe launch.py
