@echo off
cd /d "%~dp0.."

:: Intenta detectar venv o .venv
if exist "venv\Scripts\python.exe" (
    set "PYTHON=venv\Scripts\python.exe"
    goto :Found
)

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
    goto :Found
)

echo No se encontro entorno virtual (venv o .venv).
pause
exit /b 1

:Found
echo Recopilando archivos estaticos...
"%PYTHON%" manage.py collectstatic --noinput

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Archivos estaticos recopilados exitosamente!
) else (
    echo.
    echo Hubo un error al recopilar los archivos estaticos.
)

pause
