@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BuildDependencies\Build.ps1" -Run
exit /b %errorlevel%
