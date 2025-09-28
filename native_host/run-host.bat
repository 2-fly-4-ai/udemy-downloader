@echo off
setlocal
set SCRIPT=%~dp0host.py

rem Prefer Python launcher if present
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 -u "%SCRIPT%"
  goto :eof
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python -u "%SCRIPT%"
  goto :eof
)

echo Python 3 not found on PATH. Install Python 3 and try again.
exit /b 1

