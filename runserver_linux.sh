#!/usr/bin/env bash
cd "$(dirname "$0")"

# Ejecuta runserver.py con el python del entorno virtual
# runserver.py se encarga de la logica de background y logs
nohup ./venv/bin/python runserver.py >/dev/null 2>&1 &

