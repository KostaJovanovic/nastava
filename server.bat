@echo off
title nastava server
cd /d "%~dp0"

rem Serves the built archive (pages\.build\site) on this PC, the way GitHub Pages serves it.
rem /static/ comes live from pages\static (pages\serve.py): CSS and JS edits need no build, only a reload.
rem
rem   server.bat          serve; builds first if there is no build yet
rem   server.bat build    rebuild from nastava.db (build.py, with Pagefind), then serve
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
if /i "%~1"=="build" goto build
if exist "pages\.build\site\pagefind\pagefind.js" goto serve

:build
if not exist "nastava.db" (
  echo [err]  no nastava.db - run "bash ci/state.sh pull" or "uv run nastava.py sync" first
  goto fail
)
uv run pages/build.py nastava.db pages/.build || goto fail

:serve
rem Free the port, but only from a previous run of this script: a python process whose command line names this
rem repo's pages\serve.py (launched by absolute path below, so the match holds). Anything else on the port is
rem reported and left alone, and serve.py then fails to bind and says so.
powershell -NoProfile -Command ^
  "$mine = '%~dp0pages\serve.py';" ^
  "Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue |" ^
  "  Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -ne 0 } | ForEach-Object {" ^
  "    $p = Get-CimInstance Win32_Process -Filter \"ProcessId = $_\" -ErrorAction SilentlyContinue;" ^
  "    if ($p -and $p.CommandLine -and $p.CommandLine.Replace('/','\') -like ('*' + $mine + '*')) {" ^
  "      Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue" ^
  "    } elseif ($p) {" ^
  "      Write-Host ('Port %PORT% is held by PID ' + $p.ProcessId + ': ' + $p.Name) -ForegroundColor Yellow;" ^
  "      Write-Host ('  ' + $p.CommandLine) -ForegroundColor DarkGray;" ^
  "      Write-Host '  Not this project''s server - leaving it alone.' -ForegroundColor Yellow" ^
  "    }" ^
  "  }"

start "" "http://localhost:%PORT%"
rem serve.py prints the Local and Network addresses and a QR of the Network one for a phone on the same Wi-Fi.
python "%~dp0pages\serve.py" %PORT%
pause
exit /b 0

:fail
echo.
pause
exit /b 1
