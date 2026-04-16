FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENV=cloud \
    PORT=8080

WORKDIR /app

# Runtime libraries for PDF rendering (WeasyPrint) and HEIF/AVIF support.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libffi8 \
    libgdk-pixbuf-2.0-0 \
    libheif1 \
    libpango-1.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY --chown=appuser:appgroup . .

# Ensure runtime-generated folders (e.g. media/) can be created by non-root user.
RUN mkdir -p /app/media /app/transactions && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
