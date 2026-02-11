#!/usr/bin/env bash
cd "$(dirname "$0")/.."
PORT=8000

echo "Deteniendo procesos en el puerto $PORT..."
fuser -k ${PORT}/tcp 2>/dev/null && \
  echo "Servidor Django detenido (puerto $PORT)." || \
  echo "No había servidor en el puerto $PORT."
