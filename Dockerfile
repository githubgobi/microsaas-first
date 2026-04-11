FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps required by asyncpg (libpq) and bcrypt (build-essential)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps before copying source so this layer is cache-stable
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Never run as root in production
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --no-create-home appuser
USER appuser

EXPOSE 8000

# --timeout must exceed AI_TIMEOUT_SECONDS (60 s) + network overhead.
# --log-level warning silences gunicorn's own HTTP access lines;
# structured JSON logs from the app cover request logging instead.
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "90", \
     "--log-level", "warning", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
