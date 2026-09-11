FROM python:3.12.3-slim AS builder
WORKDIR /build
COPY requirements.txt .
# TODO 1: instalar dependencias en /install sin conservar caché de pip.

FROM python:3.12.3-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# TODO 2: crear el grupo y usuario appuser con UID/GID 10001.
WORKDIR /app
COPY --from=builder /install /usr/local
# TODO 3: copiar app/ con propietario appuser.
# TODO 4: cambiar al usuario appuser.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
