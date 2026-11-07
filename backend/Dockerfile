# Usa una imagen base de Python
FROM python:3.11-slim

# Evita buffering de logs y archivos .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Establece el directorio de trabajo en /app
WORKDIR /app

# Copia los archivos requirements.txt al contenedor
COPY ./requirements.txt /app/requirements.txt

# Instala las dependencias
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copia todo el código de la aplicación a /app
COPY . /app

# Expone el puerto 8000 para la API
EXPOSE 8000

# Entrypoint: espera a la BD, aplica migraciones (alembic upgrade head)
# y arranca Uvicorn.
COPY entrypoint.sh /app/entrypoint.sh
# Normaliza saltos de línea CRLF (por si se edita en Windows) y da permisos.
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh
CMD ["/app/entrypoint.sh"]

# Healthcheck sin curl (imagen slim)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3)"
