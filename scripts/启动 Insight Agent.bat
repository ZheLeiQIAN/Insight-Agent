@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 launcher.py
  pause
  exit /b
)
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python launcher.py
  pause
  exit /b
)
echo 未检测到 Python 3。
echo 请先安装 Python 3.9 或更高版本，然后重新双击启动。
echo 下载地址：https://www.python.org/downloads/
pause
