@echo off
rem Capri, from source. First run: makes a Python environment in .venv and installs the packages
rem (PySide6, numpy, sound, OCR; no torch). Then the setup window downloads her brain, ears and engine.
rem   start.bat           start her (setup window the first time)
rem   start.bat --setup   open the setup window again
cd /d "%~dp0"
if exist .venv\Scripts\pythonw.exe goto run
set "PY="
for %%v in (3.12 3.11 3.10) do if not defined PY py -%%v -c "" >nul 2>nul && set "PY=py -%%v"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto nopython
echo Making the Python environment ...
%PY% -m venv .venv || goto fail
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
echo Installing packages ...
.venv\Scripts\python.exe -m pip install -r portable\requirements.txt || goto fail
:run
start "" .venv\Scripts\pythonw.exe capri_dev.py %*
goto :eof
:nopython
echo Capri needs Python 3.10-3.12 (64-bit): https://www.python.org/downloads/
pause
exit /b 1
:fail
echo Setup failed.
pause
exit /b 1
