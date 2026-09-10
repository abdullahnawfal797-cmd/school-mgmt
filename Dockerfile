FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk update && apk add --no-cache \
    gcc \
    musl-dev \
    postgresql-dev \
    python3-dev \
    libffi-dev

RUN adduser -D appuser && chown -R appuser /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

CMD ["sh", "entrypoint.sh"]
