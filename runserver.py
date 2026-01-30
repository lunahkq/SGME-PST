#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path
import platform

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

system = platform.system()
log_file = BASE_DIR / "runserver_silent.log"

if system == "Windows":
    # venv de Windows
    python_exec = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
else:
    # venv de Linux
    python_exec = BASE_DIR / "venv" / "bin" / "python"

with open(log_file, "a", encoding="utf-8") as f:
    f.write(f"=== Lanzando servidor ({system}) ===\n")
    f.flush()
    subprocess.Popen(
        [str(python_exec), "manage.py", "runserver", "0.0.0.0:8000"],
        stdout=f,
        stderr=f
    )

