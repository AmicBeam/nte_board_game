@echo off
setlocal
chcp 65001 >nul

rem 只需要修改下面这一行的玩家 UID，然后双击运行。
set "PLAYER_UID=1425257712"

cd /d "%~dp0\.."

if "%PLAYER_UID%"=="" (
    echo PLAYER_UID 不能为空。
    pause
    exit /b 1
)

python scripts\manage_shaft_test_whitelist.py add "%PLAYER_UID%"
if errorlevel 1 (
    echo.
    echo 加入白名单失败，请检查 UID、Python 环境和数据库路径。
    pause
    exit /b 1
)

python scripts\manage_shaft_test_whitelist.py status "%PLAYER_UID%"
echo.
echo 操作完成。
pause
