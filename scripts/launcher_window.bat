@echo off
setlocal
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
pythonw "%SCRIPT_DIR%launcher_window.py" %*
exit /b %ERRORLEVEL%
