@echo off
title nastava server
cd /d "%~dp0"

rem Serves the built archive (pages\.build\site) on this PC, the way GitHub Pages serves it.
rem /static/ comes live from pages\static (pages\serve.py): CSS and JS edits need no build, only a reload.
rem
rem   server.bat          serve; builds first if there is no build yet
rem   server.bat build    rebuild from nastava.db (build.py + Pagefind), then serve
rem
rem The attachment links (/files/, /i/) go through the Cloudflare Worker, so they work only on the live site.

rem Admin is only needed for the firewall rule that lets phones on the LAN connect.
net session >nul 2>&1
if errorlevel 1 (
  powershell -Command "Start-Process cmd '/c \"%~f0\" %*' -Verb RunAs"
  exit /b
)

if /i "%~1"=="build" goto build
if exist "pages\.build\site\pagefind\pagefind.js" goto serve

:build
if not exist "nastava.db" (
  echo [err]  no nastava.db - run "uv run nastava.py sync" and "uv run documents.py sync" first
  goto fail
)
uv run pages/build.py nastava.db pages/.build || goto fail
call npx -y pagefind@1.6.0 --site pages/.build/site || goto fail

:serve
rem Kill anything already listening on port 3000 so we always start fresh
for /f "tokens=5" %%p in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":3000 "') do taskkill /F /PID %%p >nul 2>&1
netsh advfirewall firewall delete rule name="Nastava Port 3000" >nul 2>&1
netsh advfirewall firewall add rule name="Nastava Port 3000" dir=in action=allow protocol=tcp localport=3000 >nul
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
  for /f "tokens=* delims= " %%b in ("%%a") do set "LOCAL_IP=%%b"
)
echo.
echo ============================================
echo   Local:   http://localhost:3000
echo   Network: http://%LOCAL_IP%:3000
echo ============================================
echo.
start "" "http://localhost:3000"
python pages\serve.py 3000
pause
exit /b 0

:fail
echo.
pause
exit /b 1
