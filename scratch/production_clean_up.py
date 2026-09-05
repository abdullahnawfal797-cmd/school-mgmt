import os
import sys
import shutil

sys.stdout.reconfigure(encoding='utf-8')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')
sys.path.insert(0, r'c:\Users\abdul\OneDrive\سطح المكتب\school momo\school-mgmt-main')

import django
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from core.models import (
    SchoolSettings, SchoolClass, Section, Subject, AcademicYear,
    Student, Parent, Teacher, Grade, Attendance, TimetableSlot,
    ExamSession, ExamHall, ExamSeatAssignment, OfficialDocument, Invoice
)

User = get_user_model()

print("=" * 60)
print("Starting Production Clean-up & Factory Reset for Madrasati...")
print("=" * 60)

with transaction.atomic():
    # 1. Clear grades, attendance, exam seating, documents, timetable
    g_count = Grade.objects.count()
    Grade.objects.all().delete()
    print(f"✓ Deleted {g_count} test Grade records.")

    att_count = Attendance.objects.count()
    Attendance.objects.all().delete()
    print(f"✓ Deleted {att_count} Attendance records.")

    seat_count = ExamSeatAssignment.objects.count()
    ExamSeatAssignment.objects.all().delete()
    print(f"✓ Deleted {seat_count} ExamSeatAssignment records.")

    hall_count = ExamHall.objects.count()
    ExamHall.objects.all().delete()
    print(f"✓ Deleted {hall_count} ExamHall records.")

    sess_count = ExamSession.objects.count()
    ExamSession.objects.all().delete()
    print(f"✓ Deleted {sess_count} ExamSession records.")

    slot_count = TimetableSlot.objects.count()
    TimetableSlot.objects.all().delete()
    print(f"✓ Deleted {slot_count} TimetableSlot records.")

    doc_count = OfficialDocument.objects.count()
    OfficialDocument.objects.all().delete()
    print(f"✓ Deleted {doc_count} OfficialDocument records.")

    inv_count = Invoice.objects.count()
    Invoice.objects.all().delete()
    print(f"✓ Deleted {inv_count} Invoice records.")

    # 2. Clear dummy students and parents
    st_count = Student.objects.count()
    Student.objects.all().delete()
    print(f"✓ Deleted {st_count} dummy Student records.")

    p_count = Parent.objects.count()
    Parent.objects.all().delete()
    print(f"✓ Deleted {p_count} Parent records.")

    # 3. Clear non-admin users (students, parents, test users)
    users_to_delete = User.objects.filter(is_superuser=False, is_staff=False)
    del_users_count = users_to_delete.count()
    users_to_delete.delete()
    print(f"✓ Deleted {del_users_count} dummy User accounts (preserved admin/staff).")

    # 4. Reset SchoolSettings to Factory Clean State
    school = SchoolSettings.get_settings()
    school.school_name = "مدرسة العراق النموذجية"
    school.director_name = ""
    school.directorate = "المديرية العامة لتربية بغداد / الكرخ الأولى"
    school.sub_directorate = "قسم الإدارة المدرسية وشؤون الامتحانات"
    school.ministry_school_code = ""  # Empty and ready for new school entry!
    school.is_first_run_completed = False  # Wizard will show immediately on first run!
    school.save()
    print("✓ SchoolSettings reset to clean factory state (is_first_run_completed=False, ministry_school_code='').")

# 5. Reset sync log file
sync_status_path = r"c:\Users\abdul\OneDrive\سطح المكتب\school momo\school-mgmt-main\last_sync_status.json"
if os.path.exists(sync_status_path):
    os.remove(sync_status_path)
    print("✓ Removed old sync status log file.")

# 6. Synchronize clean database to AppData runtime
appdata_db = r"C:\Users\abdul\AppData\Local\Madrasati\data\db.sqlite3"
workspace_db = r"c:\Users\abdul\OneDrive\سطح المكتب\school momo\school-mgmt-main\db.sqlite3"

if os.path.exists(appdata_db):
    try:
        shutil.copy2(appdata_db, workspace_db)
        print(f"✓ Clean database mirrored to workspace: {workspace_db}")
    except Exception as e:
        print(f"⚠️ Note copying to AppData: {e}")

print("=" * 60)
print("PRODUCTION CLEAN-UP COMPLETED SUCCESSFULLY!")
print("=" * 60)
