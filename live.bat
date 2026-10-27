@echo off
rem Capri Live: reads your TikTok LIVE chat so Capri can answer questions from it.
rem   live.bat          the chat app (asks for your TikTok username)
rem   live.bat mock     starts with fake chat, for testing without going live
cd /d "%~dp0"
set "ERU_PY=D:\ERU AI\LocalAIVtuber2\backend\runtime\python.exe"
if not exist .deps-live\TikTokLive (
  echo Installing TikTokLive into .deps-live ...
  "%ERU_PY%" -m pip install --target .deps-live TikTokLive
)
if /i "%1"=="mock" ( start "" "%ERU_PY:python.exe=pythonw.exe%" live.py --mock & goto :eof )
start "" "%ERU_PY:python.exe=pythonw.exe%" live.py
