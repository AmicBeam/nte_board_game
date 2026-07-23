@echo off
setlocal EnableExtensions

rem Edit only the player UID below, then double-click this file.
set "PLAYER_UID=1425257712"

cd /d "%~dp0\.."

if "%PLAYER_UID%"=="" (
    echo PLAYER_UID must not be empty.
    pause
    exit /b 1
)

call :run_python scripts\manage_shaft_test_whitelist.py add "%PLAYER_UID%"
if errorlevel 1 (
    echo.
    echo Failed to add the account to the shaft test whitelist.
    echo Check PLAYER_UID, Python, and NTE_DATABASE_PATH.
    pause
    exit /b 1
)

call :run_python scripts\manage_shaft_test_whitelist.py status "%PLAYER_UID%"
if errorlevel 1 (
    echo.
    echo The whitelist was updated, but the status check failed.
    pause
    exit /b 1
)

echo.
echo Done.
pause
exit /b 0

:run_python
where py >nul 2>&1
if not errorlevel 1 (
    py -3 %*
    exit /b
)

where python >nul 2>&1
if errorlevel 1 (
    echo Python 3 was not found. Install Python or add it to PATH.
    exit /b 1
)

python %*
exit /b
