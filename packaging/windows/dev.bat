@echo off
setlocal
REM Convenience wrapper for dev.ps1
powershell -ExecutionPolicy Bypass -File "%~dp0dev.ps1" %*
endlocal

