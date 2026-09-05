FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# تثبيت الحزم الأساسية لبناء psycopg2 والمكتبات دون حزم دبيان المصابة
RUN apk update && apk add --no-cache \
    gcc \
    musl-dev \
    postgresql-dev \
    python3-dev \
    libffi-dev

# إنشاء مستخدم آمن غير جذري مسبقاً
RUN adduser -D appuser && chown -R appuser /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# نسخ الملفات بملكية المستخدم غير الجذري مباشرة لتفادي الطبقات الزائدة
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
