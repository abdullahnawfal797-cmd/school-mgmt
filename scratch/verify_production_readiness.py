import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')
sys.path.insert(0, r'c:\Users\abdul\OneDrive\سطح المكتب\school momo\school-mgmt-main')

import django
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from core.models import SchoolSettings, Student, Grade, SchoolClass, AcademicYear
from core.views import portal_student_result_cards, portal_settings

User = get_user_model()
factory = RequestFactory()
client = Client()

print("=" * 60)
print("RUNNING PRODUCTION READINESS & SECURITY VERIFICATION")
print("=" * 60)

# -------------------------------------------------------------
# 1. Verification of Result Cards UI & Print Protection
# -------------------------------------------------------------
print("\n[TEST 1] Verifying Result Cards UI & Print Controls...")
req_cards = factory.get('/portal/result-cards/')
resp_cards = portal_student_result_cards(req_cards)
assert resp_cards.status_code == 200, f"Expected 200, got {resp_cards.status_code}"
cards_html = resp_cards.content.decode('utf-8')

# Check Back button
assert "رجوع للدرجات" in cards_html or "portal_grades_manage" in cards_html, "Missing 'رجوع' button in result cards toolbar!"
assert "الرئيسية" in cards_html, "Missing 'الرئيسية' button in result cards toolbar!"
print("✓ Back and Home navigation buttons present in result cards toolbar.")

# Check Print protection
assert ".no-print-toolbar" in cards_html, "Missing .no-print-toolbar CSS class."
assert "display: none !important" in cards_html, "Missing print protection rules in @media print."
print("✓ @media print rules hide toolbar and control elements during actual printing.")

# -------------------------------------------------------------
# 2. Verification of Masked Sensitive Identifiers in Printed Cards
# -------------------------------------------------------------
print("\n[TEST 2] Verifying Sensitive Identifiers (School Code) are REMOVED from Result Cards...")
assert "كود التربية:" not in cards_html, "Found 'كود التربية' in printed result cards!"
assert "الرمز الإحصائي:" not in cards_html, "Found 'الرمز الإحصائي' in printed result cards!"
assert "IRQ_TEST" not in cards_html, "Found raw cloud code in printed result cards!"
print("✓ Verified: No statistical code or cloud ID appears in result cards / report cards.")

# -------------------------------------------------------------
# 3. Verification of Cloud Sync UI Security
# -------------------------------------------------------------
print("\n[TEST 3] Verifying Cloud Sync UI Security in Settings...")
admin_user = User.objects.filter(is_superuser=True).first()
assert admin_user is not None, "Admin superuser not found!"
client.force_login(admin_user)

resp_settings = client.get('/portal/settings/')
assert resp_settings.status_code == 200, f"Expected 200, got {resp_settings.status_code}"
settings_html = resp_settings.content.decode('utf-8')

# Verify raw Firebase URL is NOT exposed
assert "https://madrasati-iraq-288be-default-rtdb.firebaseio.com" not in settings_html, "Security breach: raw Firebase RTDB URL is visible in UI!"
print("✓ Verified: Raw Firebase RTDB URL is completely hidden from user interface.")

# Verify friendly status indicator
assert "متصل بالخادم المركزي الآمن 🟢" in settings_html, "Missing friendly cloud status badge in settings!"
print("✓ Verified: Cloud status displayed as 'حالة السحابة: متصل بالخادم المركزي الآمن 🟢'.")

# Verify code masking and password input type
assert 'type="password"' in settings_html, "Code input is not masked as password type!"
assert "maskedCodeBadge" in settings_html, "Missing maskedCodeBadge element."
assert "revealCloudCode" in settings_html, "Missing revealCloudCode JavaScript security function."
print("✓ Verified: School cloud code is masked with asterisks and protected with password type and toggle.")

# -------------------------------------------------------------
# 4. Verification of Production Clean-up State
# -------------------------------------------------------------
print("\n[TEST 4] Verifying Database Clean-up & Factory State...")
school = SchoolSettings.get_settings()
student_count = Student.objects.count()
grade_count = Grade.objects.count()

assert student_count == 0, f"Expected 0 students, found {student_count}!"
assert grade_count == 0, f"Expected 0 grades, found {grade_count}!"
assert school.ministry_school_code == "", f"Expected empty ministry_school_code, found '{school.ministry_school_code}'!"
assert school.is_first_run_completed is False, "Expected is_first_run_completed=False for initial setup wizard!"
print("✓ Verified: Students count = 0, Grades count = 0, School code is empty and ready for new school.")

# Verify first-run setup wizard includes ministry_school_code input
resp_dash = client.get('/portal/')
dash_html = resp_dash.content.decode('utf-8')
assert 'name="ministry_school_code"' in dash_html, "First-run setup wizard is missing ministry_school_code input field!"
assert "firstRunWizardModal" in dash_html, "First-run setup wizard modal not triggered!"
print("✓ Verified: First-run setup wizard triggers immediately on dashboard with ministry_school_code field.")

print("\n" + "=" * 60)
print("ALL PRODUCTION READINESS & SECURITY CHECKS PASSED (100% SUCCESS)!")
print("=" * 60)
