# Servicio del formulario de presupuesto (Cloud Run, europe-west1). Sin credenciales en la imagen:
# BREVO_API_KEY llega de Secret Manager como variable de entorno.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --require-hashes -r requirements.txt
COPY app.py .
# Smoke test: si la app no importa, el build muere aquí y no en Cloud Run.
RUN python -c "import app; assert any(r.path == '/quote' for r in app.app.routes)"
USER nobody
CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log
