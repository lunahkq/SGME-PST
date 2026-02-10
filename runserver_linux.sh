#!/usr/bin/env bash
cd "$(dirname "$0")"

# Ejecuta runserver.py con el python del entorno virtual
# runserver.py se encarga de la logica de background y logs
./venv/bin/python runserver.py

