@echo off
rem Doppelklick-Starter fuer den internen Testbuild (build-test.ps1).
rem Eine .ps1 kann ihre eigene Ausfuehrungsrichtlinie nicht umgehen, Windows prueft sie
rem vor der ersten Zeile. Dieser Starter ruft PowerShell deshalb mit -ExecutionPolicy Bypass
rem auf, nur fuer diesen einen Lauf; die Richtlinie des Systems bleibt unveraendert.
rem Ohne Argumente holt er den Pfad von Python 3.13 ueber den py-Launcher (py -3.13);
rem build-test.ps1 prueft danach selbst Version und 64 Bit.
rem Mit Argumenten gehen diese unveraendert durch, z. B.:
rem   build-test.cmd -Python C:\Python313\python.exe -Inno "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
setlocal
set "SCRIPT=%~dp0build-test.ps1"
if not "%~1"=="" goto run_args
set "PY="
for /f "usebackq delims=" %%P in (`py -3.13 -c "import sys; print(sys.executable)" 2^>nul`) do set "PY=%%P"
if not defined PY goto no_python
echo Python: %PY%
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -Python "%PY%"
set "RC=%ERRORLEVEL%"
goto done
:run_args
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
set "RC=%ERRORLEVEL%"
goto done
:no_python
echo Python 3.13 x64 nicht gefunden. Von python.org installieren (mit py-Launcher)
echo oder den Pfad angeben:  build-test.cmd -Python C:\...\python.exe
set "RC=1"
:done
echo.
if not "%RC%"=="0" goto failed
echo Fertig. Der Ordner dist-test wird geoeffnet.
if exist "%~dp0dist-test" start "" explorer.exe "%~dp0dist-test"
goto end
:failed
echo Build fehlgeschlagen (Exit %RC%). Meldung oben lesen.
:end
echo.
pause
exit /b %RC%
