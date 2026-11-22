@echo off
setlocal
title RasaDesk Build
cd /d "%~dp0"

echo Checking files...
set MISSING=
if not exist rasadesk.py set MISSING=%MISSING% rasadesk.py
if not exist core.py set MISSING=%MISSING% core.py
if not exist winsvc.py set MISSING=%MISSING% winsvc.py
if not exist contacts.py set MISSING=%MISSING% contacts.py
if not exist server.py set MISSING=%MISSING% server.py
if not exist requirements.txt set MISSING=%MISSING% requirements.txt
if not exist installer.iss set MISSING=%MISSING% installer.iss
if not exist Vazirmatn-Regular.ttf set MISSING=%MISSING% Vazirmatn-Regular.ttf
if not exist Vazirmatn-Bold.ttf set MISSING=%MISSING% Vazirmatn-Bold.ttf
if not exist logo.png set MISSING=%MISSING% logo.png
if not exist rasadesk.ico set MISSING=%MISSING% rasadesk.ico
if defined MISSING goto :missing

set LICENSE=
if exist OFL.txt set LICENSE=--add-data "OFL.txt;."
echo [1/3] Installing libraries...
py -m pip install --disable-pip-version-check -r requirements.txt pyinstaller
if errorlevel 1 goto :err

echo [2/3] Building RasaDesk (folder build, required for the Windows service) and the relay server...
py -m PyInstaller --noconfirm --clean --noconsole --onedir --name RasaDesk --icon rasadesk.ico --add-data "rasadesk.ico;." --add-data "Vazirmatn-Regular.ttf;." --add-data "Vazirmatn-Bold.ttf;." %LICENSE% --add-data "logo.png;." --collect-all customtkinter --hidden-import win32timezone --hidden-import servicemanager --hidden-import win32serviceutil --hidden-import win32service --hidden-import win32event --hidden-import win32process --hidden-import win32profile --hidden-import win32security --hidden-import win32ts --hidden-import win32api --hidden-import pywintypes rasadesk.py
if errorlevel 1 goto :err
py -m PyInstaller --noconfirm --onefile --name RasaDeskServer server.py
if errorlevel 1 goto :err

echo [3/3] Creating installer...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" goto :noinno
"%ISCC%" installer.iss
if errorlevel 1 goto :err
echo.
echo DONE: installer\RasaDesk-Setup.exe
goto :end

:noinno
echo.
echo Inno Setup 6 was not found. Install it from https://jrsoftware.org/isdl.php
echo then run build.bat again. The program folder is already in dist\RasaDesk
goto :end

:missing
echo.
echo Missing files:%MISSING%
echo Copy them into this folder: %CD%
echo then run build.bat again.
goto :end

:err
echo.
echo BUILD FAILED - read the messages above.

:end
echo.
pause
