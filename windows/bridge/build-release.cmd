@echo off
rem Doppelklick-Starter fuer den Release-Build (Version aus pyproject.toml, Kanal "Release").
rem Nutzt build-test.cmd/build-test.ps1 mit -Release; verweigert bei geaendertem Arbeitsbaum.
rem Argumente wie bei build-test.cmd (-Python, -Inno).
setlocal
set "BUILD_RELEASE=1"
call "%~dp0build-test.cmd" %*
exit /b %ERRORLEVEL%
