@echo off
SET port=8000

FOR /F "tokens=5" %%T IN ('netstat -ano ^| findstr :%port%') DO (
    TASKKILL /PID %%T /F >nul 2>&1
)

echo Servidor Django detenido (si estaba usando el puerto %port%).
