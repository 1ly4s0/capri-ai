@echo off
rem Builds the portable dev version of Capri (Capri.exe + setup) into D:\CapriBuild\Capri-Dev, zipped as
rem D:\CapriBuild\Capri-Dev.zip. Only code and assets go in: never data\ (your memory, settings, chat logs).
rem The build uses its own Python env in D:\CapriBuild\venv (PySide6, numpy, sound, OCR; no torch).
setlocal
set "SRC=%~dp0"
set "B=D:\CapriBuild"
set "PY=%B%\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Making the build env in %B%\venv ...
  python -m venv "%B%\venv" || goto :fail
  "%PY%" -m pip install -q PySide6-Essentials numpy requests pyyaml sounddevice soundfile soundcard pillow winocr pywin32 pyinstaller || goto :fail
)
cd /d "%B%"
"%PY%" -m PyInstaller --noconfirm --clean --windowed --name Capri --distpath "%B%\dist" --workpath "%B%\work" ^
  --specpath "%B%" --icon "%SRC%assets\icons\capri.png" --add-data "%SRC%assets;assets" --paths "%SRC%." ^
  --collect-submodules capri --collect-all winocr --collect-all winrt ^
  --exclude-module torch --exclude-module transformers --exclude-module llama_cpp --exclude-module faster_whisper ^
  --exclude-module ctranslate2 --exclude-module TikTokLive --exclude-module tkinter --exclude-module matplotlib ^
  "%SRC%capri_dev.py" || goto :fail
set "OUT=%B%\Capri-Dev"
if exist "%OUT%" rmdir /s /q "%OUT%"
move "%B%\dist\Capri" "%OUT%" >nul || goto :fail
copy /y "%SRC%portable\config.yaml" "%OUT%\config.yaml" >nul
copy /y "%SRC%portable\README.txt" "%OUT%\README.txt" >nul
mkdir "%OUT%\models\llm" "%OUT%\models\whisper" "%OUT%\engines" 2>nul
if exist "%B%\Capri-Dev.zip" del "%B%\Capri-Dev.zip"
powershell -NoProfile -Command "Compress-Archive -Path '%OUT%' -DestinationPath '%B%\Capri-Dev.zip'" || goto :fail
echo.
echo Done: %OUT%  and  %B%\Capri-Dev.zip
goto :eof
:fail
echo Build failed.
exit /b 1
