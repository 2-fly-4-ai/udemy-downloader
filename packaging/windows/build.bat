@echo off
setlocal enabledelayedexpansion

REM Build frozen binaries with PyInstaller.
REM Works with local venv (recommended) or system Python (CI/maintainer machines).

set PY=
set PYI_CMD=

REM Prefer repo venv if present
if exist venv\Scripts\python.exe (
  set "PY=venv\Scripts\python.exe"
) else (
  REM Try Windows launcher
  where py >nul 2>&1 && (
    for /f "tokens=*" %%P in ('py -3 -c "import sys;print(sys.executable)"') do set "PY=%%P"
  )
  if not defined PY (
    REM Fallback to python on PATH
    where python >nul 2>&1 && set "PY=python"
  )
)

if not defined PY (
  echo Could not find Python. Install Python 3 and ensure it is on PATH.
  exit /b 1
)

REM Use module invocation so we don't depend on pyinstaller.exe path
set "PYI_CMD=%PY% -m PyInstaller"

echo Using Python: %PY%
echo Checking PyInstaller...
%PY% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo PyInstaller is not installed for this interpreter. Install it with:
  echo   %PY% -m pip install -r requirements.txt pyinstaller
  exit /b 1
)

echo Building udemy-downloader.exe...
%PYI_CMD% --noconsole --onefile --name udemy-downloader main.py || goto :error

echo Building serp-companion.exe...
%PYI_CMD% --noconsole --onefile --name serp-companion native_host\host.py || goto :error

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
