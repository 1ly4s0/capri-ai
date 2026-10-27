@echo off
rem Starts Capri on your desktop. Uses ERU AI's embedded Python (it already has llama-cpp with CUDA, GPT-SoVITS,
rem qdrant and friends) and adds only what Capri needs on top, into .deps. Nothing inside ERU AI is changed.
rem   run.bat          normal
rem   run.bat debug    with a console for logs
rem   run.bat video    the scripted video in video.txt (console shows when it's ready, then press F9)
rem   run.bat video video_cheer.txt    another script
cd /d "%~dp0"
if not exist config.yaml copy config.example.yaml config.yaml >nul

set "ERU_PY=D:\ERU AI\LocalAIVtuber2\backend\runtime\python.exe"
if not exist "%ERU_PY%" (
  echo ERU AI's Python wasn't found at "%ERU_PY%". Capri needs ERU AI for her brain and voice.
  pause
  goto :eof
)
if not exist .deps\PySide6 (
  echo Installing Capri's extra packages into .deps ...
  "%ERU_PY%" -m pip install --target .deps PySide6-Essentials shiboken6 spotipy pyyaml soundfile soundcard winocr
)
rem added later: the beat ear (listens to your speakers so her hair vibes to music)
if not exist .deps\soundcard "%ERU_PY%" -m pip install --target .deps --no-deps soundcard
set "PYTORCH_JIT=0"
rem The embedded runtime ignores the current folder (._pth), so launch.py puts this folder on sys.path.
if /i "%1"=="debug" ( "%ERU_PY%" launch.py & goto :eof )
if /i "%1"=="video" if not "%~2"=="" ( "%ERU_PY%" launch.py --video --script "%~2" & goto :eof )
if /i "%1"=="video" ( "%ERU_PY%" launch.py --video & goto :eof )
start "" "%ERU_PY:python.exe=pythonw.exe%" launch.py
