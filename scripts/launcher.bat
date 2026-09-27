@echo off
setlocal
chcp 65001 >nul
title Inventor drilling scripts
mode con: cols=80 lines=20

set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%launcher.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo Command finished with error code %EXIT_CODE%.
) else (
    echo Command finished successfully.
)
pause
exit /b %EXIT_CODE%
