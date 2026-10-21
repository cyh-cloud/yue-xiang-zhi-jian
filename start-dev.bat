@echo off
chcp 65001 >nul
title Yuexiang Zhi Jiang - dev launcher
cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo ==================================================
echo   Yuexiang Zhi Jiang  ^(Vue SPA + Flask API^)
echo ==================================================
echo.

rem ---------- locate python with flask ----------
set "PY="
if exist "C:\Users\c'y'h\.workbuddy\binaries\python\envs\default\Scripts\python.exe" set "PY=C:\Users\c'y'h\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not defined PY if exist "C:\Users\c'y'h\AppData\Local\Programs\Python\Python39\python.exe" set "PY=C:\Users\c'y'h\AppData\Local\Programs\Python\Python39\python.exe"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [ERROR] Python not found. Install Python 3 and add it to PATH.
  pause
  exit /b 1
)

rem ---------- check node deps ----------
if not exist "%ROOT%\frontend\node_modules\vite\package.json" (
  echo [ERROR] frontend dependencies missing.
  echo   Run first:
  echo   cd /d "%ROOT%\frontend"
  echo   npm install --cache "%LOCALAPPDATA%\npm-cache-yx" --registry=https://registry.npmmirror.com
  pause
  exit /b 1
)

rem keep npm cache on a writable path (default one is under Program Files)
set "npm_config_cache=%LOCALAPPDATA%\npm-cache-yx"
rem do not let the backend pop a browser tab by itself
set "OPEN_BROWSER=0"

echo python : %PY%
echo root   : %ROOT%
echo.
echo backend  -> http://127.0.0.1:5000  ^(API only^)
echo frontend -> http://127.0.0.1:5173  ^(open this one^)
echo.

pushd "%ROOT%\backend"
start "yx-backend" cmd /k ""%PY%" run.py"
popd

pushd "%ROOT%\frontend"
start "yx-frontend" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"
popd

echo waiting for services ...
timeout /t 6 >nul
start "" "http://127.0.0.1:5173"

echo.
echo Two windows opened: yx-backend and yx-frontend.
echo Close those windows to stop the services.
echo.
pause >nul
