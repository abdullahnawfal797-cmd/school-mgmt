#!/bin/bash
set -e

# تنفيذ ترحيلات قاعدة البيانات أولاً
python manage.py migrate --noinput

# تنزيل وحقن البيانات بطريقة متسامحة تتجاهل السجلات غير المتطابقة
if [ ! -f "data_loaded.flag" ]; then
    echo "Downloading full school data using Python..."
    python -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/abdullahnawfal797-cmd/school-mgmt/data-sync/full_school_data.json', 'full_school_data.json')"
    
    echo "Loading school core data into PostgreSQL..."
    python manage.py loaddata --ignorenonexistent full_school_data.json || true
    
    touch data_loaded.flag
fi

# تشغيل خادم المنظومة
exec "$@"
