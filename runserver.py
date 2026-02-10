#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path
import platform

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

system = platform.system()
log_file = BASE_DIR / "runserver_silent.log"

# Determinación robusta del intérprete Python
# 1. Si estamos corriendo ya dentro del venv, usar sys.executable
# 2. Si no, buscar 'venv' o '.venv' en BASE_DIR

possible_venvs = ["venv", ".venv"]
python_exec = None

# Chequear si sys.executable parece estar dentro de un venv local
if any(venv in sys.executable for venv in possible_venvs):
    python_exec = Path(sys.executable)
else:
    # Buscar carpetas de entorno virtual
    for venv_name in possible_venvs:
        venv_path = BASE_DIR / venv_name
        if venv_path.exists():
            if system == "Windows":
                candidate = venv_path / "Scripts" / "pythonw.exe" 
                # Fallback a python.exe si pythonw.exe no existe (raro pero posible)
                if not candidate.exists():
                    candidate = venv_path / "Scripts" / "python.exe"
            else:
                candidate = venv_path / "bin" / "python"
            
            if candidate.exists():
                python_exec = candidate
                break

# Fallback final: usar el python del sistema si no se encuentra venv (no recomendado pero funcional)
if python_exec is None:
    python_exec = "python"
    print("ADVERTENCIA: No se detectó entorno virtual (venv/.venv). Usando python del sistema.")

with open(log_file, "a", encoding="utf-8") as f:
    f.write(f"=== Lanzando servidor ({system}) ===\n")
    f.write(f"Python: {python_exec}\n")
    f.flush()
    
    # En Windows, usamos DETACHED_PROCESS para que sea verdaderamente background si se lanza desde doble click
    creationflags = 0
    if system == "Windows":
        creationflags = subprocess.CREATE_NO_WINDOW

    process = subprocess.Popen(
        [str(python_exec), "manage.py", "runserver", "0.0.0.0:8000", "--noreload"],
        stdout=f,
        stderr=f,
        creationflags=creationflags
    )
    
    # Wait for the subprocess to finish so the file handle 'f' remains open
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()

