import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')

import django
django.setup()

from django.test import RequestFactory
from core.views import portal_records_manage
from core.models import SchoolClass, Student, Section

record_types = [
    'master_exam_sheet',
    'dual_science_sheet',
    'dual_art_sheet',
    'single_islamic',
    'single_arabic',
    'single_sports',
    'single_math',
    'single_science_oral',
    'english_p1_p2',
    'english_p3',
    'english_p4',
    'english_p5_p6',
    'english_arabic_labels',
    'oral_exam_builder',
    'middle_record',
    'admin_grade_sheet'
]

factory = RequestFactory()
first_class = SchoolClass.objects.first()
print(f"Testing with Class: {first_class} (ID: {first_class.id if first_class else 'None'})")

errors = []

# 1. Test without class_id
for rt in record_types:
    req = factory.get(f'/portal/records/?record_type={rt}')
    try:
        resp = portal_records_manage(req)
        if resp.status_code != 200:
            errors.append(f"[FAIL status {resp.status_code}] {rt} (no class)")
        else:
            content = resp.content.decode('utf-8')
            print(f"[OK 200] {rt:22} (no class) - length: {len(content)}")
    except Exception as e:
        errors.append(f"[EXCEPTION] {rt} (no class): {e}")

# 2. Test with class_id
if first_class:
    for rt in record_types:
        req = factory.get(f'/portal/records/?class_id={first_class.id}&record_type={rt}')
        try:
            resp = portal_records_manage(req)
            if resp.status_code != 200:
                errors.append(f"[FAIL status {resp.status_code}] {rt} (with class)")
            else:
                content = resp.content.decode('utf-8')
                print(f"[OK 200] {rt:22} (with class) - length: {len(content)}")
        except Exception as e:
            errors.append(f"[EXCEPTION] {rt} (with class): {e}")

print("\n" + "="*50)
if errors:
    print(f"FOUND {len(errors)} ERRORS:")
    for err in errors:
        print(" ", err)
else:
    print("ALL 32 RECORD RENDER TESTS PASSED PERFECTLY!")
