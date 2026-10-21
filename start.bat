@echo off
chcp 65001 >nul
title Yuexiang Zhi Jiang
cd /d "%~dp0"

echo ==================================================
echo   Yuexiang Zhi Jiang - starting ...
echo ==================================================
echo.

rem -- pick a python that has flask installed --
set "PY="
if exist "C:\Users\c'y'h\AppData\Local\Programs\Python\Python39\python.exe" set "PY=C:\Users\c'y'h\AppData\Local\Programs\Python\Python39\python.exe"
if not defined PY if exist "C:\Users\c'y'h\.workbuddy\binaries\python\envs\default\Scripts\python.exe" set "PY=C:\Users\c'y'h\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo [ERROR] Python not found. Please install Python 3 and add it to PATH.
  pause
  exit /b 1
)

echo Using python: %PY%
echo.
echo If it says "Address already in use" / WinError 10048,
echo another copy is already running on port 5000.
echo Close that one first, then run this again.
echo.

"%PY%" run.py

echo.
echo Server stopped. Press any key to close.
pause >nul
