@echo off
cd /d %~dp0

:: Intenta detectar venv o .venv
if exist "venv\Scripts\pythonw.exe" (
    set PYTHONW="venv\Scripts\pythonw.exe"
) else (
    if exist ".venv\Scripts\pythonw.exe" (
        set PYTHONW=".venv\Scripts\pythonw.exe"
    ) else (
        echo No se encontro entorno virtual (venv o .venv).
        pause
        exit /b 1
    )
)

:: Ejecuta el script de python usando el pythonw del entorno virtual
start "" %PYTHONW% "%cd%\runserver.py"

