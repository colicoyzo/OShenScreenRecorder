@echo off
setlocal
cd /d "%~dp0"
set "VENV=%~dp0.buildenv"
set "VPY=%VENV%\Scripts\python.exe"
if not exist "%VPY%" (
  echo Creating isolated build environment ...
  python -m venv "%VENV%" || goto :fail
)
echo Installing build dependencies into venv ...
"%VPY%" -m pip install --upgrade pip pyinstaller pillow soundcard imageio-ffmpeg || goto :fail
if not exist "%~dp0assets\app.ico" (
  echo Generating icon ...
  "%VPY%" make_icon.py || goto :fail
)
echo Building onedir app ...
"%VPY%" -m PyInstaller --noconfirm --clean --onedir --windowed --name OShenScreenRecorder --icon assets\app.ico --manifest oshen.manifest --add-data "assets\app.ico;assets" --hidden-import PIL._tkinter_finder --hidden-import soundcard.mediafoundation --collect-all soundcard --collect-all imageio_ffmpeg main.py || goto :fail
echo.
echo Build OK: %~dp0dist\OShenScreenRecorder\OShenScreenRecorder.exe
echo Verify:   dist\OShenScreenRecorder\OShenScreenRecorder.exe --selftest
exit /b 0
:fail
echo Build FAILED (check internet connection and pip).
exit /b 1
