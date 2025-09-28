@echo off
setlocal enabledelayedexpansion

REM Build frozen binaries with PyInstaller (requires pyinstaller installed)
REM 1) Create venv and install deps: python -m venv venv && venv\Scripts\pip install -r requirements.txt pyinstaller
REM 2) Run this script: packaging\windows\build.bat

if not exist venv\Scripts\python.exe (
  echo venv not found. Please create it and install deps first.
  exit /b 1
)

set PY=venv\Scripts\python.exe
set PYI=venv\Scripts\pyinstaller.exe

echo Building udemy-downloader.exe...
"%PYI%" --noconsole --onefile --name udemy-downloader main.py || goto :error

echo Building serp-companion.exe...
"%PYI%" --noconsole --onefile --name serp-companion native_host\host.py || goto :error

if not exist dist (
  echo dist folder not found
  exit /b 1
)

mkdir bin 2>nul
copy /Y dist\udemy-downloader.exe bin\udemy-downloader.exe >nul
copy /Y dist\serp-companion.exe bin\serp-companion.exe >nul

echo Success. Binaries in bin\
exit /b 0

:error
echo Build failed.
exit /b 1

