#!/bin/bash

# Obtener el directorio donde se encuentra el script y subir un nivel
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." &> /dev/null && pwd)"
cd "$SCRIPT_DIR"

# Intentar detectar el entorno virtual
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    echo "No se encontró entorno virtual (venv o .venv)."
    exit 1
fi

echo "Recopilando archivos estáticos..."
"$PYTHON" manage.py collectstatic --noinput

if [ $? -eq 0 ]; then
    echo ""
    echo "¡Archivos estáticos recopilados exitosamente!"
else
    echo ""
    echo "Hubo un error al recopilar los archivos estáticos."
fi
