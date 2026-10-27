@echo off
rem Capri for TikTok LIVE, without Claude open. Double-click it.
rem   stream.bat         closes any Capri already running, then starts Capri (stream mode, Capri Stage window)
rem                      and Capri Live (the chat app), both in the background at lower CPU priority so
rem                      TikTok LIVE Studio and VTube Studio stay smooth
rem   stream.bat stop    closes both
rem Works from anywhere (a copy on the Desktop is fine): it always runs from the Capri folder.
setlocal
set "CAPRI=%~dp0"
set "ERU_PY=D:\ERU AI\LocalAIVtuber2\backend\runtime\python.exe"
set "ERU_PYW=D:\ERU AI\LocalAIVtuber2\backend\runtime\pythonw.exe"
cd /d "%CAPRI%"

if not exist "%ERU_PYW%" (
  echo ERU AI's Python wasn't found at "%ERU_PYW%".
  pause
  goto :eof
)

echo Closing any Capri that's already running ...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*.exe' -and $_.CommandLine -match 'launch\.py|live\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
if /i "%1"=="stop" (
  echo Capri is off. See you next stream.
  ping -n 3 127.0.0.1 >nul
  goto :eof
)

if not exist .deps-live\TikTokLive (
  echo Installing TikTokLive for the chat app ...
  "%ERU_PY%" -m pip install --target .deps-live TikTokLive
)

set "PYTORCH_JIT=0"
echo Starting Capri ...
rem --stream: stream mode for this run only (she sits still, Capri Stage shows up); run.bat stays normal
start "" /belownormal "%ERU_PYW%" launch.py --stream
ping -n 3 127.0.0.1 >nul
echo Starting Capri Live ...
start "" /belownormal "%ERU_PYW%" live.py
echo.
echo Capri is booting (her brain takes about 15-40 s). Then:
echo   1. Go live on TikTok
echo   2. In Capri Live, hit Connect
echo   3. In TikTok LIVE Studio, capture the "Capri Stage" window
echo To turn her off: run "stream.bat stop" (or quit her from the tray icon and close Capri Live).
ping -n 9 127.0.0.1 >nul
