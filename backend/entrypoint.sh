#!/bin/sh
# Entrypoint del backend (Smart Retail Platform).
# 1. Espera a que PostgreSQL esté disponible.
# 2. Verifica diferencias entre modelos y BD: si existen, genera una
#    migración automática y la aplica (verify_db_schema.py).
# 3. Arranca la API con Uvicorn.
set -e

echo "Esperando a que PostgreSQL esté disponible en ${DB_HOST:-db}:${DB_PORT:-5432}..."
python - <<'PYEOF'
import os
import socket
import sys
import time

host = os.getenv("DB_HOST", "db")
port = int(os.getenv("DB_PORT", "5432"))

for attempt in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"PostgreSQL disponible en {host}:{port} (intento {attempt + 1}).")
            break
    except OSError:
        if attempt % 10 == 9:
            print(f"Intento {attempt + 1}: PostgreSQL aún no responde...")
        time.sleep(1)
else:
    print(f"No se pudo conectar a PostgreSQL en {host}:{port} tras 60 intentos.", file=sys.stderr)
    sys.exit(1)
PYEOF

echo "Verificando esquema de la base de datos y aplicando migraciones..."
python verify_db_schema.py

echo "Iniciando servidor API (uvicorn)..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
