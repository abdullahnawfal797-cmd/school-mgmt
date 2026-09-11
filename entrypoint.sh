#!/bin/bash
set -e

# تطبيق ترحيلات الجداول
python manage.py migrate --noinput

# حقن البيانات مرة واحدة فقط
if [ ! -f "data_loaded.flag" ]; then
    echo "Downloading full school data using Python..."
    python -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/abdullahnawfal797-cmd/school-mgmt/data-sync/full_school_data.json', 'full_school_data.json')"
    
    echo "Loading school core data into PostgreSQL..."
    python manage.py loaddata --ignorenonexistent full_school_data.json || true
    
    touch data_loaded.flag
fi

# تشغيل خادم المنظومة وتثبيته على المنفذ 8000
echo "Starting School Management System..."
exec python manage.py runserver 0.0.0.0:8000
