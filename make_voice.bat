@echo off
rem Drag a Capri clip (video or audio) onto this file, or: make_voice.bat clip.mp4 [start_sec end_sec]
cd /d "%~dp0"
"D:\ERU AI\LocalAIVtuber2\backend\runtime\python.exe" voices\make_ref.py %*
pause
