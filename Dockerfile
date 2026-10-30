FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    WALLET_DB_PATH=/srv/data/db.json PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY frontend ./frontend
RUN mkdir -p data && useradd --create-home appuser && chown -R appuser /srv
USER appuser

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT}"]
