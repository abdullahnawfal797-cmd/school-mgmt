import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')
import django
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from core.models import (
    Student, SchoolClass, Section, ExamHall, ExamSession,
    ExamSeatAssignment, AcademicYear, SchoolSettings
)
from core.views import (
    exam_halls_view, portal_records_manage, general_registry_view,
    print_exam_attendance, print_exam_labels
)

print("=" * 60)
print("BEGINNING COMPREHENSIVE VERIFICATION FOR ALL 5 PILLARS")
print("=" * 60)

# ----------------------------------------------------------------------
# PILLAR 1: Registration Numbers Cleansing & Visibility Restriction
# ----------------------------------------------------------------------
print("\n[PILLAR 1] Verifying Registration Numbers Cleansing:")
total_students = Student.objects.count()
prefixed_students = Student.objects.filter(registration_number__regex=r'^[a-zA-Z_]').count()
print(f"  Total Students in DB: {total_students}")
print(f"  Students with English prefixes (REG_ / EXAM_): {prefixed_students}")
assert prefixed_students == 0, f"Expected 0 prefixed students, found {prefixed_students}"

sample_regs = list(Student.objects.values_list('registration_number', flat=True)[:5])
print(f"  Sample registration numbers: {sample_regs}")
for r in sample_regs:
    if r:
        assert r.isdigit(), f"Registration number {r} is not pure digits!"

# Check records_manage.html
with open('core/templates/portal/records_manage.html', 'r', encoding='utf-8') as f:
    records_html = f.read()

# Separate middle_record from other sheets
parts = records_html.split("record_type == 'middle_record'")
non_middle_part = parts[0]
if len(parts) > 1:
    # also anything after middle_record block
    sub_parts = parts[1].split("record_type == 'admin_grade_sheet'")
    if len(sub_parts) > 1:
        non_middle_part += sub_parts[1]

# Ensure no 'القيد' or 'registration_number' in non-middle sheets
non_middle_reg_matches = re.findall(r'القيد|registration_number', non_middle_part)
print(f"  'القيد' / 'registration_number' in Oral, Final, and Monthly sheets: {len(non_middle_reg_matches)}")
assert len(non_middle_reg_matches) == 0, f"Found {len(non_middle_reg_matches)} occurrences of registration number in prohibited sheets!"

# Check exam_attendance_print.html
with open('core/templates/portal/exam_attendance_print.html', 'r', encoding='utf-8') as f:
    att_html = f.read()
att_reg_matches = re.findall(r'القيد|registration_number', att_html)
print(f"  'القيد' / 'registration_number' in Exam Attendance Sheet: {len(att_reg_matches)}")
assert len(att_reg_matches) == 0, "Registration number found in Exam Attendance Sheet!"

print("  ==> PILLAR 1 PASSED: 100% compliant!")

# ----------------------------------------------------------------------
# PILLAR 2: Black Header Elimination
# ----------------------------------------------------------------------
print("\n[PILLAR 2] Verifying Black Table Header Removal:")
with open('core/templates/portal/base_portal.html', 'r', encoding='utf-8') as f:
    base_html = f.read()

assert 'background-color: #000000 !important;\n            color: #FFFFFF !important;' not in base_html, "Found black header rule in base_portal.html!"
assert '.table-oral thead th' in base_html, "Missing white table-oral header rule in base_portal.html"
assert 'table-layout: fixed' in records_html, "Missing table-layout: fixed in records_manage.html"
print("  ==> PILLAR 2 PASSED: Black table headers completely eliminated!")

# ----------------------------------------------------------------------
# PILLAR 3: Keep Windows/Previews inside pywebview
# ----------------------------------------------------------------------
print("\n[PILLAR 3] Verifying Containment Inside Desktop App Window:")
with open('core/templates/portal/exam_halls.html', 'r', encoding='utf-8') as f:
    halls_html = f.read()

# Check that print labels and print attendance don't have target="_blank"
assert 'target="_blank"' not in halls_html, "Found target='_blank' in exam_halls.html!"
assert 'document.querySelectorAll(\'a[target="_blank"]\')' in base_html, "Missing global link sanitizer in base_portal.html"
print("  ==> PILLAR 3 PASSED: All internal navigation contained in pywebview!")

# ----------------------------------------------------------------------
# PILLAR 4: Exam Halls Engine Upgrade (CRUD + Geometry + Anti-Cheat)
# ----------------------------------------------------------------------
print("\n[PILLAR 4] Verifying Exam Halls Engine & Anti-Cheat Distribution:")
# 1. Create Hall with double desks
test_hall = ExamHall.objects.create(
    name="قاعة التحقق والاختبار",
    location="الجناح الشمالي",
    lines_count=3,
    desks_per_line=5,
    desk_type='double'
)
print(f"  Created test hall: {test_hall.name}, lines={test_hall.lines_count}, desks={test_hall.desks_per_line}, type={test_hall.desk_type}")
print(f"  Calculated capacity: {test_hall.capacity}")
assert test_hall.capacity == 3 * 5 * 2, f"Expected 30, got {test_hall.capacity}"

# 2. Edit Hall
test_hall.lines_count = 4
test_hall.desks_per_line = 6
test_hall.desk_type = 'single'
test_hall.save()
print(f"  Updated test hall: lines={test_hall.lines_count}, desks={test_hall.desks_per_line}, type={test_hall.desk_type}")
print(f"  Updated capacity: {test_hall.capacity}")
assert test_hall.capacity == 4 * 6 * 1, f"Expected 24, got {test_hall.capacity}"

# 3. Test Anti-Cheat Distribution
current_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
test_session = ExamSession.objects.create(
    title="دورة اختبار مكافحة الغش",
    session_type="final_round1",
    academic_year=current_year,
    start_date="2026-06-01",
    end_date="2026-06-15"
)
test_hall.desk_type = 'double'
test_hall.lines_count = 2
test_hall.desks_per_line = 3 # capacity = 2 * 3 * 2 = 12
test_hall.save()
test_session.halls.add(test_hall)

# Get classes
c1 = SchoolClass.objects.filter(level_order=1).first()
c2 = SchoolClass.objects.filter(level_order=2).first()
assert c1 and c2, "Need at least two classes in DB"

factory = RequestFactory()
req = factory.post('/portal/exam-halls/', {
    'action_type': 'distribute_seats',
    'session_id': str(test_session.id),
    'classes': [str(c1.id), str(c2.id)]
})
# Setup session & messages
req.session = {}
setattr(req, '_messages', FallbackStorage(req))
User = get_user_model()
req.user = User.objects.filter(is_superuser=True).first() or User.objects.first()

response = exam_halls_view(req)
assert response.status_code == 302, f"Expected 302 redirect, got {response.status_code}"

# Verify seat assignments in the double desk hall
seats = list(ExamSeatAssignment.objects.filter(exam_session=test_session, exam_hall=test_hall).order_by('seat_number').select_related('student__current_class'))
print(f"  Distributed seats count: {len(seats)}")
assert len(seats) > 0, "No seats were assigned!"

# Group by desk (row, col)
from collections import defaultdict
desks_map = defaultdict(list)
for s in seats:
    desks_map[(s.desk_row, s.desk_col)].append(s)

violations = 0
for (r, c), desk_seats in desks_map.items():
    if len(desk_seats) == 2:
        c_a = desk_seats[0].student.current_class_id
        c_b = desk_seats[1].student.current_class_id
        if c_a == c_b:
            violations += 1

print(f"  Double desks checked: {len(desks_map)}")
print(f"  Same-class violations on same desk: {violations}")
assert violations == 0, f"Found {violations} violations where same class students sat on the same desk!"

# Clean up test session & hall
test_session.delete()
test_hall.delete()
print("  ==> PILLAR 4 PASSED: Exam Halls Engine & Anti-Cheat are working flawlessly!")

# ----------------------------------------------------------------------
# PILLAR 5: Export Buttons & UI Rendering
# ----------------------------------------------------------------------
print("\n[PILLAR 5] Verifying Views HTTP 200 & PDF/Excel Buttons:")
# Records Manage view
req_rec = factory.get('/portal/records/?record_type=oral_exam_builder')
req_rec.session = {}
setattr(req_rec, '_messages', FallbackStorage(req_rec))
req_rec.user = req.user
resp_rec = portal_records_manage(req_rec)
assert resp_rec.status_code == 200, f"records view returned {resp_rec.status_code}"
assert 'تحميل نسخة PDF' in resp_rec.content.decode('utf-8'), "Missing PDF button in records_manage.html"
print("  Records Manage rendered HTTP 200 with PDF button.")

# General Registry view
req_reg = factory.get('/portal/registry/')
req_reg.session = {}
setattr(req_reg, '_messages', FallbackStorage(req_reg))
req_reg.user = req.user
resp_reg = general_registry_view(req_reg)
assert resp_reg.status_code == 200, f"registry view returned {resp_reg.status_code}"
assert 'تصدير القوائم (Excel)' in resp_reg.content.decode('utf-8'), "Missing Excel button in general_registry.html"
print("  General Registry rendered HTTP 200 with Excel button.")

print("  ==> PILLAR 5 PASSED: All exports and buttons verified!")

print("\n" + "=" * 60)
print("ALL 5 PILLARS FULLY VERIFIED AND VALIDATED!")
print("=" * 60)
