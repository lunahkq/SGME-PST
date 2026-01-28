import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

pythonw = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
log_file = BASE_DIR / "runserver_silent.log"

with open(log_file, "a", encoding="utf-8") as f:
    f.write("=== Lanzando servidor ===\n")
    f.flush()
    subprocess.Popen(
        [str(pythonw), "manage.py", "runserver", "0.0.0.0:8000"],
        stdout=f,
        stderr=f
    )

