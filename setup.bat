@echo off
rem One-time setup: a Python environment in .venv, everything Capri needs, and her models (~7.2 GB download).
rem   setup.bat                              downloads the brain into models\
rem   setup.bat --model-path D:\x\model.gguf uses a GGUF you already have instead
cd /d "%~dp0"

set "PY="
for %%v in (3.11 3.12 3.10) do (
  if not defined PY ( py -%%v -c "" >nul 2>nul && set "PY=py -%%v" )
)
if not defined PY (
  echo Capri needs Python 3.10, 3.11 or 3.12 ^(64-bit^). Get it from https://www.python.org/downloads/ and run setup.bat again.
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo Making the Python environment with %PY% ...
  %PY% -m venv .venv || goto fail
)
set "VPY=.venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip --quiet || goto fail
echo Installing Capri's packages ...
"%VPY%" -m pip install -r requirements.txt || goto fail
echo Installing her brain engine (llama.cpp with CUDA) ...
"%VPY%" -m pip install "llama-cpp-python==0.3.4" --prefer-binary --only-binary llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 || goto fail
"%VPY%" tools\setup.py %* || goto fail
echo.
echo All set. Start her with run.bat
pause
exit /b 0

:fail
echo.
echo Setup failed (see the error above). Fix it and run setup.bat again: it picks up where it stopped.
pause
exit /b 1
