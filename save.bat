@echo off
setlocal disabledelayedexpansion
cd /d "%~dp0"

rem Git helper for nastava (nastava.valjdakosta.com), adapted from mbrd's save.bat. mbrd's version stamps, bundle
rem and generated pages have no counterpart here (the build is git-ignored); its `release` is `deploy` here.
rem
rem   save.bat                          menu (numbered as mbrd's: 1 commit, 2 save, 3 deploy, 4 pull, 5 push)
rem   save.bat save                     add + commit, then ask before pushing
rem   save.bat commit                   add + commit, no push
rem   save.bat deploy [sync]            add + commit + push, then bash ci/deploy.sh [sync]: build and publish
rem   save.bat update [all]             no git: scrape the forum (all: every source), save the database, build and
rem                                     publish (ci/deploy.sh forum^|sync), no pause
rem   save.bat push                     push the current branch to its upstream
rem   save.bat pull                     git pull (current branch, from its upstream)
rem   save.bat quick "message"          add + commit + push, no menu, no prompts
rem   save.bat quick-commit "message"   add + commit, no push, no menu, no prompts
rem
rem quick / quick-commit never prompt, pause, pull or force-push: every question gets the answer that loses
rem nothing. A push that did not happen is exit 1, with the commit kept locally. An empty message becomes "update".
rem Exit code: 0 on success, 1 on any failure.

rem Read the arguments before delayed expansion is on: with it on, every "!" in
rem the commit message would be lost. Read back only as !MSG!, never re-parsed.
set "ACTION=%~1"
set "MSG=%~2"
setlocal enabledelayedexpansion

set "PROJECT=nastava"
set "DEFMSG=update"
set "COMMIT_ONLY=0"
set "QUICK=0"
set "DEPLOY=0"
set "DEPLOY_ARGS="
set "SAVE_ERROR=0"
call :resolvebranch

if /i "%ACTION%"=="quick"        (set "QUICK=1" & goto checkrepo)
if /i "%ACTION%"=="quick-commit" (set "QUICK=1" & set "COMMIT_ONLY=1" & goto checkrepo)
if /i "%ACTION%"=="save"         goto checkrepo
if /i "%ACTION%"=="commit"       (set "COMMIT_ONLY=1" & goto checkrepo)
if /i "%ACTION%"=="deploy" (
  set "DEPLOY=1"
  if /i "!MSG!"=="sync" set "DEPLOY_ARGS=sync"
  goto checkrepo
)
rem Without git, so work in progress is never committed; QUICK only drops the final pause (for a scheduled run).
if /i "%ACTION%"=="update" (
  set "QUICK=1"
  set "DEPLOY_ARGS=forum"
  if /i "!MSG!"=="all" set "DEPLOY_ARGS=sync"
  goto deploy
)
if /i "%ACTION%"=="push"         goto pushonly
if /i "%ACTION%"=="pull"         goto pull
if not "%ACTION%"=="" goto usage

:menu
echo.
echo === %PROJECT% ===
echo.
echo   1  commit       add + commit, no push
echo   2  save         add + commit, then ask before pushing
echo   3  deploy       add + commit + push, then build and publish the site
echo   4  pull         git pull
echo   5  push         push the current branch to its upstream
echo   6  deploy-sync  the same as 3, scraping first (ci/deploy.sh sync)
echo   7  update       scrape the forum, build and publish, no git
echo   8  quit
echo.
set "CHOICE="
set /p CHOICE=select [1-8]:
if "%CHOICE%"=="1" (set "COMMIT_ONLY=1" & goto checkrepo)
if "%CHOICE%"=="2" goto checkrepo
if "%CHOICE%"=="3" (set "DEPLOY=1" & goto checkrepo)
if "%CHOICE%"=="4" goto pull
if "%CHOICE%"=="5" goto pushonly
if "%CHOICE%"=="6" (set "DEPLOY=1" & set "DEPLOY_ARGS=sync" & goto checkrepo)
if "%CHOICE%"=="7" (set "DEPLOY_ARGS=forum" & goto deploy)
if "%CHOICE%"=="8" exit /b 0
echo [err]  invalid choice
goto menu


:usage
echo [err]  unknown action "%ACTION%"
echo        use: save.bat [save^|commit^|deploy [sync]^|update [all]^|push^|pull^|quick "message"^|quick-commit "message"]
exit /b 1


:checkrepo
if exist ".git" goto save
echo [err]  no git repository here
set "SAVE_ERROR=1"
goto end


:save
echo.
echo === git: save ===
echo.

rem An unfinished merge must never reach "git add ." - it would stage the
rem conflict markers and record the conflict as settled.
set "UNMERGED="
for /f "delims=" %%u in ('git diff --name-only --diff-filter=U 2^>nul') do set "UNMERGED=1"
if defined UNMERGED (
  echo [err]  unresolved merge conflicts - resolve these first:
  git diff --name-only --diff-filter=U
  set "SAVE_ERROR=1"
  goto end
)

echo [git]  stage
git add .
if errorlevel 1 (
  echo [err]  git add failed
  set "SAVE_ERROR=1"
  goto end
)
git diff --cached --quiet
if errorlevel 1 goto commit
echo [git]  nothing new to commit
if "%COMMIT_ONLY%"=="1" goto end
goto askpush

:commit
git status --short
rem quick modes already have their message (captured above, before delayed
rem expansion); the menu asks for one.
if "%QUICK%"=="1" goto writemsg
echo.
set "MSG="
set /p "MSG=commit message [%DEFMSG%]: "
:writemsg
if not defined MSG set "MSG=%DEFMSG%"
rem The message never goes through a command line: PowerShell writes it from
rem the environment to a UTF-8 file (no BOM) and git reads the file.
set "MSGFILE=%TEMP%\%PROJECT%-save-message.txt"
powershell -NoProfile -Command "[IO.File]::WriteAllText($env:MSGFILE, $env:MSG)"
if errorlevel 1 (
  echo [err]  could not write the commit message file
  set "SAVE_ERROR=1"
  goto end
)
git commit -F "%MSGFILE%"
if errorlevel 1 (
  del "%MSGFILE%" >nul 2>nul
  echo [err]  git commit failed
  set "SAVE_ERROR=1"
  goto end
)
del "%MSGFILE%" >nul 2>nul
call :resolvebranch
if "%COMMIT_ONLY%"=="1" (
  echo.
  echo [git]  committed locally, not pushed
  goto end
)

:askpush
rem quick and deploy were the answer to this question.
if "%QUICK%"=="1" goto push
if "%DEPLOY%"=="1" goto push
echo.
set "DOPUSH="
set /p DOPUSH=push now? (y/n):
if /i not "%DOPUSH%"=="y" (
  echo [git]  not pushed
  goto end
)
goto push


:pushonly
echo.
echo === git: push ===

rem Push the checked-out branch to its configured upstream (which may have a
rem different name, e.g. master tracking origin/main).
:push
echo.
if "%BRANCH%"=="" (
  echo [err]  no branch checked out ^(detached HEAD?^) - not pushing
  set "SAVE_ERROR=1"
  goto end
)
set "UPSTREAM="
for /f "delims=" %%u in ('git rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2^>nul') do set "UPSTREAM=%%u"
if defined UPSTREAM (
  echo [git]  push %BRANCH% to !UPSTREAM!
  set "PUSHARGS=-c push.default=upstream push"
  goto dopush
)
if "%REMOTE%"=="" (
  echo [err]  no remote configured - nothing pushed
  set "SAVE_ERROR=1"
  goto end
)
echo [git]  %BRANCH% has no upstream yet - pushing to %REMOTE%/%BRANCH% and tracking it
set "PUSHARGS=push -u %REMOTE% %BRANCH%"
:dopush
git %PUSHARGS%
if not errorlevel 1 goto pushed

rem A push can fail for reasons a pull or a force push cannot fix: a 403, a bad
rem credential, no network. Only a rejected push (the remote moved) is worth
rem offering them for. ls-remote hits the same endpoint: if it fails too, the
rem push never got as far as comparing histories.
git ls-remote %REMOTE% >nul 2>nul
if errorlevel 1 (
  echo.
  echo [err]  push failed - cannot reach or authenticate to %REMOTE%. A pull or force push will not fix it.
  echo        Check access to the remote, then push again. Any commit is saved locally.
  goto notpushed
)
echo.
echo [warn] push rejected - the remote has commits you don't
rem Both remedies rewrite something, the working tree or the remote; quick mode answers no to each.
if "%QUICK%"=="1" (
  echo [err]  quick mode does not pull or force push - the commit is saved locally.
  echo        Run "save.bat pull", resolve, then push again.
  goto notpushed
)
echo.
set "FETCH="
set /p FETCH=pull + merge the remote first? (y/n):
if /i "%FETCH%"=="y" (
  set "SAVE_ERROR=1"
  echo [git]  after the pull: resolve any conflicts, then push again
  goto pull
)
echo.
echo [warn] a force push discards whatever is on the remote that you do not have.
set "FORCE="
set /p FORCE=force push instead? (y/n):
if /i not "%FORCE%"=="y" goto notpushed
rem --force-with-lease, not --force: it refuses when the remote moved since the last fetch.
git %PUSHARGS% --force-with-lease
if not errorlevel 1 goto pushed
echo [err]  force push refused - the remote moved since the last fetch, or the push failed. Nothing overwritten.
goto notpushed

:pushed
echo [git]  pushed
if "%DEPLOY%"=="1" goto deploy
goto end

:notpushed
if "%DEPLOY%"=="1" echo [warn] nothing was pushed, so nothing was deployed
set "SAVE_ERROR=1"
goto end


rem `deploy`: once the push is in, build and publish the site from this PC (ci/deploy.sh; with `sync`, scrape
rem first). Run with Git's own bash: cmd's PATH has none, and C:\Windows\System32\bash.exe would be WSL.
:deploy
set "BASH="
for /f "delims=" %%g in ('where git 2^>nul') do if not defined BASH set "BASH=%%~dpg..\bin\bash.exe"
if not exist "%BASH%" (
  echo [err]  Git's bash.exe not found next to git.exe - run "bash ci/deploy.sh %DEPLOY_ARGS%" by hand
  set "SAVE_ERROR=1"
  goto end
)
echo.
echo === deploy: ci/deploy.sh %DEPLOY_ARGS% ===
echo.
"%BASH%" ci/deploy.sh %DEPLOY_ARGS%
if errorlevel 1 (
  echo.
  echo [err]  ci/deploy.sh failed or reported a failed step - see above
  set "SAVE_ERROR=1"
)
goto end


:pull
echo.
echo === git: pull ===
echo.
if "%BRANCH%"=="" (
  echo [err]  no branch checked out
  set "SAVE_ERROR=1"
  goto end
)
git rev-parse --abbrev-ref "@{u}" >nul 2>nul
if errorlevel 1 (
  echo [err]  %BRANCH% has no upstream to pull from
  set "SAVE_ERROR=1"
  goto end
)
git pull
if errorlevel 1 set "SAVE_ERROR=1"
goto end


rem The checked-out branch into %BRANCH% (empty with no repo or a detached HEAD),
rem and the remote to use into %REMOTE%: the branch's upstream, else origin, else
rem the first remote. Empty when there is none.
:resolvebranch
set "BRANCH="
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "BRANCH=%%b"
if /i "%BRANCH%"=="HEAD" set "BRANCH="
set "REMOTE="
if not "%BRANCH%"=="" for /f "delims=" %%r in ('git config branch.%BRANCH%.remote 2^>nul') do set "REMOTE=%%r"
if not "%REMOTE%"=="" exit /b 0
git remote get-url origin >nul 2>nul
if not errorlevel 1 (set "REMOTE=origin" & exit /b 0)
for /f "delims=" %%r in ('git remote 2^>nul') do if "!REMOTE!"=="" set "REMOTE=%%r"
exit /b 0


:end
echo.
if "%QUICK%"=="1" exit /b %SAVE_ERROR%
pause
exit /b %SAVE_ERROR%
