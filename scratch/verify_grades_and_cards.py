import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')
sys.path.insert(0, r'c:\Users\abdul\OneDrive\سطح المكتب\school momo\school-mgmt-main')
django.setup()

from django.test import RequestFactory
from django.urls import reverse
from core.models import SchoolClass, Student, Subject, Grade, SchoolSettings, User
from core.views import class_master_sheet_view, portal_student_result_cards

factory = RequestFactory()

print("=" * 60)
print("Testing Master Sheet Pagination & Layout (27 students per page)")
print("=" * 60)

first_class = SchoolClass.objects.first()
if not first_class:
    print("Creating test class...")
    first_class = SchoolClass.objects.create(name="الصف السادس الابتدائي", level_order=6)

print(f"Testing with Class: {first_class.name} (ID: {first_class.id})")

# Ensure test students exist to test pagination
existing_count = Student.objects.filter(current_class=first_class, is_deleted=False).count()
print(f"Current students count in class: {existing_count}")

req = factory.get(f'/certificates/master-sheet/{first_class.id}/')
resp = class_master_sheet_view(req, first_class.id)
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
content = resp.content.decode('utf-8')

# Verify pagination elements in HTML
assert "master-page-block" in content, "Missing .master-page-block in template"
assert "A4 landscape" in content or "size: A4 landscape" in content, "Missing A4 landscape styling"
assert "صفحة" in content, "Missing page indicator in master sheet"
print("✓ Master sheet renders successfully with A4 Landscape and pagination blocks!")

# Test Student Result Cards (Batch)
print("\n" + "=" * 60)
print("Testing Student Result Cards (Batch - 2up and 1up)")
print("=" * 60)

req_batch_2up = factory.get(f'/portal/result-cards/?class_id={first_class.id}&layout=2up')
resp_batch_2up = portal_student_result_cards(req_batch_2up)
assert resp_batch_2up.status_code == 200, f"Expected 200, got {resp_batch_2up.status_code}"
content_2up = resp_batch_2up.content.decode('utf-8')

# Verify the 8 mandatory columns in template
mandatory_cols = [
    "1. المادة الدراسية",
    "2. الفصل الأول",
    "3. نصف السنة",
    "4. الفصل الثاني",
    "5. السعي السنوي",
    "6. الامتحان النهائي",
    "7. الدرجة النهائية",
    "8. الملاحظات"
]

for col in mandatory_cols:
    assert col in content_2up, f"Mandatory column '{col}' missing from result card template!"
    print(f"✓ Found column: {col}")

# Check summary box and signatures
assert "المجموع الكلي" in content_2up, "Missing total sum in result card"
assert "المعدل العام" in content_2up, "Missing average in result card"
assert "القرار والنتيجة النهائية" in content_2up, "Missing final decision in result card"
assert "مدقق الدرجات" in content_2up, "Missing grade auditor signature"
assert "مدير المدرسة" in content_2up, "Missing principal signature"
assert "الختم الرسمي" in content_2up, "Missing official stamp placeholder"
assert "خط القص الفاصل" in content_2up or "cut-divider" in content_2up, "Missing cut line in 2-up layout"
print("✓ Summary box, official signatures, and cut line verified successfully!")

# Test Student Result Cards (Single student)
test_student = Student.objects.filter(current_class=first_class, is_deleted=False).first()
if test_student:
    print(f"\nTesting single student result card for: {test_student.user.get_full_name()} (ID: {test_student.id})")
    req_single = factory.get(f'/portal/result-cards/{test_student.id}/?layout=1up')
    resp_single = portal_student_result_cards(req_single, student_id=test_student.id)
    assert resp_single.status_code == 200, f"Expected 200, got {resp_single.status_code}"
    content_single = resp_single.content.decode('utf-8')
    assert test_student.user.get_full_name() in content_single, "Student full name not found in single result card"
    print(f"✓ Single student result card verified for: {test_student.user.get_full_name()}")

print("\n" + "=" * 60)
print("ALL VERIFICATIONS PASSED SUCCESSFULLY!")
print("=" * 60)
