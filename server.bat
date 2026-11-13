@echo off
title nastava server
cd /d "%~dp0"

rem Serves the archive on this PC (pages\serve.py).
rem
rem   server.bat          dev mode: no build. The pages are rendered when opened, from the templates as they are, so
rem                       a template, CSS or JS edit shows on the next reload; a change to nastava.db or build.py
rem                       restarts the server by itself (~15 s). The text search is the last build's.
rem   server.bat build    build first (build.py, with Pagefind: a fresh text search), then dev mode
rem   server.bat built    the last build in pages\.build\site, exactly as deployed (builds if there is none)
rem
rem The attachments link to nastava.mas.bg.ac.rs, as on the live site.

rem 15497 was drawn at random from 10000-49151, so no other repo's dev server picks it by habit or by a shared
rem scheme: below Windows' outgoing-connection range (49152+), and outside the ranges Windows reserved on this PC
rem (netsh int ipv4 show excludedportrange protocol=tcp) when it was drawn. pages\serve.py defaults to it too.
set "PORT=15497"

rem Admin is needed once, to add the firewall rule that lets phones on the LAN connect; reading it needs none.
netsh advfirewall firewall show rule name="Nastava Port %PORT%" >nul 2>&1
if not errorlevel 1 goto ready
net session >nul 2>&1
if errorlevel 1 (
  powershell -Command "Start-Process cmd '/c \"%~f0\" %*' -Verb RunAs"
  exit /b
)
netsh advfirewall firewall add rule name="Nastava Port %PORT%" dir=in action=allow protocol=tcp localport=%PORT% >nul

:ready
if not exist "nastava.db" (
  echo [err]  no nastava.db - run "bash ci/state.sh pull" or "uv run nastava.py sync" first
  goto fail
)
set "MODE="
if /i "%~1"=="built" set "MODE=--built"
if /i "%~1"=="build" goto build
if /i not "%~1"=="built" goto serve
if exist "pages\.build\site\pagefind\pagefind.js" goto serve

:build
uv run pages/build.py nastava.db pages/.build || goto fail

:serve
rem Free the port, but only from a previous run of this script: every process whose command line names this repo's
rem pages\serve.py (launched by absolute path below, so the match holds): dev mode's watcher and its server both, or
rem the watcher would start the server again. Anything else on the port is reported and left alone, and serve.py then
rem fails to bind and says so.
powershell -NoProfile -Command ^
  "$mine = '%~dp0pages\serve.py';" ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Replace('/','\') -like ('*' + $mine + '*') } |" ^
  "  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue };" ^
  "Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue |" ^
  "  Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -ne 0 } | ForEach-Object {" ^
  "    $p = Get-CimInstance Win32_Process -Filter \"ProcessId = $_\" -ErrorAction SilentlyContinue;" ^
  "    if ($p) {" ^
  "      Write-Host ('Port %PORT% is held by PID ' + $p.ProcessId + ': ' + $p.Name) -ForegroundColor Yellow;" ^
  "      Write-Host ('  ' + $p.CommandLine) -ForegroundColor DarkGray;" ^
  "      Write-Host '  Not this project''s server - leaving it alone.' -ForegroundColor Yellow" ^
  "    }" ^
  "  }"

rem serve.py prints the Local and Network addresses and a QR of the Network one for a phone on the same Wi-Fi, and
rem opens the browser once the site answers (--open). uv: dev mode renders with build.py's libraries (Jinja...).
uv run "%~dp0pages\serve.py" %PORT% %MODE% --open
pause
exit /b 0

:fail
echo.
pause
exit /b 1
