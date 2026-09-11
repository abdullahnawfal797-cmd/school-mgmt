#!/bin/bash
set -e

# تنفيذ الترحيلات
python manage.py migrate --noinput

# تنزيل بيانات المنظومة الكاملة واستيرادها باستخدام بايثون مباشرة
if [ ! -f "full_school_data.json" ]; then
    echo "Downloading full school data using Python..."
    python -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/abdullahnawfal797-cmd/school-mgmt/data-sync/full_school_data.json', 'full_school_data.json')"
    echo "Loading data into PostgreSQL..."
    python manage.py loaddata full_school_data.json || true
fi

# تشغيل الخادم
exec "$@"
