@echo off
rem Capri, from source. First run: makes a Python environment in .venv and installs the packages
rem (PySide6, numpy, sound, OCR; no torch). Then setup asks, right here in this window, what she gets:
rem brain, ears, voice, eyes (y/n), and downloads it.
rem   start.bat           start her (setup the first time)
rem   start.bat --setup   run setup again
cd /d "%~dp0"
rem .venv\installed.txt is written only once every package is in (a closed or failed install resumes next time)
if exist .venv\installed.txt goto run
if exist .venv\Scripts\python.exe goto install
set "PY="
for %%v in (3.12 3.11 3.10 3.13) do if not defined PY py -%%v -c "" >nul 2>nul && set "PY=py -%%v"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto nopython
echo Making the Python environment ...
%PY% -m venv .venv || goto fail
:install
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
echo Installing packages (a few minutes the first time) ...
.venv\Scripts\python.exe -m pip install -r portable\requirements.txt || goto fail
rem her cloned voice; --no-deps: its Chinese extra won't build without a compiler, and the rest is in requirements
.venv\Scripts\python.exe -m pip install --no-deps genie-tts==2.0.2 || goto fail
echo ok> .venv\installed.txt
:run
.venv\Scripts\python.exe -m capri.setup_cli %*
if errorlevel 2 (
  pause
  goto :eof
)
start "" .venv\Scripts\pythonw.exe capri_dev.py
goto :eof
:nopython
echo Capri needs Python 3.10-3.13 (64-bit): https://www.python.org/downloads/
pause
exit /b 1
:fail
echo Setup failed.
pause
exit /b 1
