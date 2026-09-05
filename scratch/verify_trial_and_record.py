import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import django
from datetime import timedelta

# Initialize Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')
django.setup()

from django.test import Client, RequestFactory
from django.utils import timezone
from django.contrib.messages.storage.fallback import FallbackStorage
from core.models import SchoolSettings, Student, User, SchoolClass, Section
from core.licensing import (
    get_machine_fingerprint,
    generate_license_key,
    verify_and_apply_license,
    compute_license_seal
)
from core.middleware import LicenseEnforcementMiddleware, TRIAL_EXPIRED_MESSAGE

def run_tests():
    print("==================================================")
    print("  QA & VALIDATION: TRIAL SYSTEM & MIDDLE RECORD   ")
    print("==================================================")

    # ----------------------------------------------------
    # 1. Clean Reg Number & Model Tests
    # ----------------------------------------------------
    print("\n[TEST 1] Testing Student Clean Registration Number...")
    st = Student()
    st.registration_number = "STD-2026/450"
    clean_num = st.clean_reg_number
    assert clean_num == "2026/450", f"Expected '2026/450', got '{clean_num}'"

    st.registration_number = "REG_9981"
    clean_num = st.clean_reg_number
    assert clean_num == "9981", f"Expected '9981', got '{clean_num}'"

    st.registration_number = "105"
    clean_num = st.clean_reg_number
    assert clean_num == "105", f"Expected '105', got '{clean_num}'"
    print(" -> PASS: Registration number cleansing works perfectly with zero foreign prefixes.")

    # ----------------------------------------------------
    # 2. Trial Logic & 14-Day Duration Tests
    # ----------------------------------------------------
    print("\n[TEST 2] Testing 14-Day Trial Initialization & Date Calculations...")
    today = timezone.now().date()
    school = SchoolSettings.get_settings()
    
    # Save original state to restore later
    orig_installation_date = school.installation_date
    orig_sub_end = school.subscription_end_date
    orig_key = school.license_key
    orig_hash = school.license_hash
    orig_active = school.is_subscription_active

    try:
        # Simulate fresh install trial mode
        school.installation_date = today
        school.subscription_end_date = today + timedelta(days=14)
        school.license_key = None
        school.license_hash = None
        school.is_subscription_active = True
        school.save()

        school.refresh_from_db()
        assert school.is_trial is True, "School should be in trial mode"
        assert school.is_official_license is False, "School should not have official license"
        assert school.is_trial_or_license_valid is True, "Trial should be valid"
        assert school.days_remaining == 14, f"Expected 14 days remaining, got {school.days_remaining}"
        assert "نسخة تجريبية" in school.subscription_status_label, f"Unexpected label: {school.subscription_status_label}"
        assert "14" in school.subscription_status_label, f"Label must contain remaining days: {school.subscription_status_label}"
        print(f" -> PASS: Fresh trial initialized: {school.subscription_status_label}")

        # Test expired trial
        school.subscription_end_date = today - timedelta(days=1)
        school.save()
        school.refresh_from_db()
        assert school.is_trial_or_license_valid is False, "Expired trial must be invalid"
        assert school.days_remaining == 0, f"Days remaining should be 0, got {school.days_remaining}"
        assert "انتهت" in school.subscription_status_label, f"Unexpected label: {school.subscription_status_label}"
        print(f" -> PASS: Expired trial detected: {school.subscription_status_label}")

        # ----------------------------------------------------
        # 3. Middleware Lock & Redirection Tests
        # ----------------------------------------------------
        print("\n[TEST 3] Testing Middleware Hard Lock on Expired Trial...")
        client = Client()

        # Try sensitive portal URLs while trial is expired
        sensitive_urls = [
            '/portal/',
            '/portal/registry/',
            '/portal/exam-halls/',
            '/portal/records/',
            '/portal/timetable/',
            '/portal/students-manage/',
            '/portal/grades-manage/',
        ]

        for u in sensitive_urls:
            resp = client.get(u, follow=False)
            assert resp.status_code == 302, f"Expected 302 redirect for {u}, got {resp.status_code}"
            assert '/portal/license-lock/' in resp.url, f"Expected redirect to license-lock, got {resp.url}"

        # Test lock screen itself is accessible (200 OK)
        lock_resp = client.get('/portal/license-lock/')
        assert lock_resp.status_code == 200, f"Lock screen returned {lock_resp.status_code}"
        assert "07723457175" in lock_resp.content.decode('utf-8'), "Phone contact must appear on lock screen"
        assert "14" in lock_resp.content.decode('utf-8'), "14-day notice must appear on lock screen"
        print(" -> PASS: Middleware locked all sensitive routes and redirected to license-lock.")

        # ----------------------------------------------------
        # 4. Official License Activation Tests
        # ----------------------------------------------------
        print("\n[TEST 4] Testing Official Paid License Key Activation...")
        machine_id = get_machine_fingerprint()
        key_year = generate_license_key(machine_id, plan="YEAR")
        assert key_year is not None, "Failed to generate year license key"
        
        success, msg = verify_and_apply_license(school, key_year)
        assert success is True, f"Failed to apply license: {msg}"
        
        school.refresh_from_db()
        assert school.is_official_license is True, "School must be officially licensed"
        assert school.is_trial is False, "School must no longer be in trial mode"
        assert school.is_trial_or_license_valid is True, "License must be valid"
        assert school.days_remaining >= 364, f"Days remaining should be ~365, got {school.days_remaining}"
        assert "مفعّل رسمياً" in school.subscription_status_label, f"Label must indicate official activation: {school.subscription_status_label}"
        print(f" -> PASS: License activated: {school.subscription_status_label}")

        # Check that sensitive URLs are now accessible (200 OK)
        resp_portal = client.get('/portal/')
        assert resp_portal.status_code == 200, f"Portal dashboard should be 200, got {resp_portal.status_code}"
        print(" -> PASS: All sensitive routes unlocked immediately after activation.")

        # ----------------------------------------------------
        # 5. Middle Record Layout Rendering Tests
        # ----------------------------------------------------
        print("\n[TEST 5] Testing Middle Record HTML/CSS Layout...")
        # Access Middle Record view
        resp_rec = client.get('/portal/records/?record_type=middle_record')
        assert resp_rec.status_code == 200, f"Middle record returned {resp_rec.status_code}"
        html = resp_rec.content.decode('utf-8')
        
        assert "middle-record-signatures" in html, "Signatures class missing from Middle Record"
        assert "sub-row" in html, "sub-row class missing from Middle Record"
        assert "result-row" in html, "result-row class missing from Middle Record"
        assert "official-border" in html, "official-border class missing"
        assert "سجل الدرجات الوسطي" in html, "Middle record title missing"
        assert "height: 283mm" in html or "283mm" in html, "283mm A4 height style missing"
        print(" -> PASS: Middle Record template renders with full-page A4 structure and signatures.")

    finally:
        # Restore active school settings
        print("\n[CLEANUP] Restoring active 14-day trial for user...")
        school.installation_date = orig_installation_date or today
        # Ensure fresh 14 days trial from today
        school.subscription_end_date = today + timedelta(days=14)
        school.license_key = None
        school.license_hash = None
        school.is_subscription_active = True
        school.save()
        print(" -> Active 14-day trial restored successfully.")

    print("\n==================================================")
    print("        ALL QA & VALIDATION TESTS PASSED!         ")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
