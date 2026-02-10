@echo off
cd /d %~dp0

:: Intenta detectar venv o .venv
if exist "venv\Scripts\pythonw.exe" (
    set "PYTHONW=venv\Scripts\pythonw.exe"
    goto :Found
)

if exist ".venv\Scripts\pythonw.exe" (
    set "PYTHONW=.venv\Scripts\pythonw.exe"
    goto :Found
)

echo No se encontro entorno virtual (venv o .venv).
pause
exit /b 1

:Found
echo Iniciando servidor Django en segundo plano...
echo Usando PythonW: %PYTHONW%
echo.

:: Ejecuta runserver.py con pythonw (sin ventana)
start "" "%PYTHONW%" "%cd%\runserver.py"

:: Cierra la ventana del batch inmediatamente
exit
