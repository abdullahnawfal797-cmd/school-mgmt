FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# تحديث الحزم وسد الثغرات الأمنية مع تنظيف الكاش لتقليل الحجم
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# إنشاء مستخدم غير جذري (Non-root user) لتشغيل التطبيق بأمان وفق معايير Snyk
RUN groupadd -r appuser && useradd -r -g appuser -d /code -s /sbin/nologin appuser

WORKDIR /code

COPY requirements.txt /code/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /code/
RUN chown -R appuser:appuser /code

# تشغيل التطبيق بمستخدم غير جذري
USER appuser
