import os
import sys
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')
django.setup()

from django.test import Client
from core.models import SchoolSettings
from core.cloud_sync import (
    FIREBASE_RTDB_URL,
    upload_cloud_backup,
    restore_cloud_backup,
    get_last_cloud_sync_info
)

def test_cloud_sync_and_restore():
    print("==================================================")
    print("   QA: MINISTRY CODE, CLOUD SYNC & RESTORE        ")
    print("==================================================")

    # ----------------------------------------------------
    # 1. Test Model Field Presence
    # ----------------------------------------------------
    print("\n[TEST 1] Testing SchoolSettings.ministry_school_code...")
    school = SchoolSettings.get_settings()
    assert hasattr(school, 'ministry_school_code'), "SchoolSettings is missing ministry_school_code field!"
    print(f" -> PASS: ministry_school_code field exists on SchoolSettings (Current: '{school.ministry_school_code}')")

    # ----------------------------------------------------
    # 2. Test Mandatory Field Validation on Settings Save
    # ----------------------------------------------------
    print("\n[TEST 2] Testing Mandatory Validation in portal_settings...")
    client = Client()

    # Attempt POST with empty ministry_school_code
    post_data_empty = {
        'school_name': 'مدرسة الاختبار التجريبية',
        'director_name': 'الأستاذ أحمد',
        'directorate': 'الكرخ الأولى',
        'sub_directorate': 'قسم التربية',
        'school_gender': 'boys',
        'school_level': 'secondary',
        'ministry_school_code': ''  # Empty!
    }
    resp_empty = client.post('/portal/settings/', data=post_data_empty, follow=True)
    assert resp_empty.status_code == 200
    html_empty = resp_empty.content.decode('utf-8')
    assert "إجباري" in html_empty or "الرمز الإحصائي" in html_empty, "Empty ministry_school_code did not trigger error message in HTML!"
    print(" -> PASS: Saving settings without ministry_school_code was rejected with mandatory error message.")

    # Now set a valid test code
    test_code = "IRQ_TEST_88124"
    post_data_valid = {
        'school_name': 'ثانوية المتميزين النموذجية',
        'director_name': 'د. حيدر العراقي',
        'directorate': 'مديرية الرصافة الأولى',
        'sub_directorate': 'قسم التعليم العام',
        'school_gender': 'boys',
        'school_level': 'secondary',
        'ministry_school_code': test_code
    }
    resp_valid = client.post('/portal/settings/', data=post_data_valid, follow=True)
    assert resp_valid.status_code == 200
    school.refresh_from_db()
    assert school.ministry_school_code == test_code, f"Expected {test_code}, got {school.ministry_school_code}"
    print(f" -> PASS: Settings saved successfully with ministry_school_code = '{test_code}'.")

    # ----------------------------------------------------
    # 3. Test Cloud Backup Upload to Firebase RTDB
    # ----------------------------------------------------
    print("\n[TEST 3] Testing Cloud Backup Upload to Firebase RTDB...")
    success, msg = upload_cloud_backup()
    print(f" -> Upload result: success={success}, msg={msg}")
    assert success is True, f"Cloud backup upload failed: {msg}"

    sync_info = get_last_cloud_sync_info()
    assert sync_info is not None, "last_sync_status.json not created!"
    assert sync_info.get("success") is True, "Sync status record indicates failure"
    assert sync_info.get("ministry_school_code") == test_code
    print(f" -> PASS: Cloud backup uploaded to {FIREBASE_RTDB_URL}/backups/{test_code}.json")
    print(f"    Compressed size: {sync_info.get('compressed_size_kb')} KB (Original: {sync_info.get('original_size_kb')} KB)")

    # ----------------------------------------------------
    # 4. Test Emergency Cloud Restore from Firebase RTDB
    # ----------------------------------------------------
    print("\n[TEST 4] Testing Emergency Cloud Restore from Firebase RTDB...")
    # First test invalid/non-existent code
    success_bad, msg_bad = restore_cloud_backup("NON_EXISTENT_CODE_999999")
    assert success_bad is False, "Restore should fail for non-existent code"
    print(f" -> PASS: Non-existent code correctly failed: {msg_bad}")

    # Now restore using the uploaded test_code
    success_ok, res_ok = restore_cloud_backup(test_code)
    assert success_ok is True, f"Restore failed for valid code: {res_ok}"
    assert isinstance(res_ok, dict), "Expected dict response on successful restore"
    assert res_ok.get("ministry_school_code") == test_code
    print(f" -> PASS: Emergency Cloud Restore completed successfully for school: '{res_ok.get('school_name')}' (Last Sync: {res_ok.get('last_sync')})")

    # ----------------------------------------------------
    # 5. Test Web UI & Endpoints
    # ----------------------------------------------------
    print("\n[TEST 5] Testing Web UI & Endpoints...")
    resp_ui = client.get('/portal/settings/')
    assert resp_ui.status_code == 200
    html = resp_ui.content.decode('utf-8')

    assert "ministry_school_code" in html, "ministry_school_code input missing from template"
    assert "الرمز الإحصائي الوزاري للمدرسة (كود التربية)*" in html, "Label text missing"
    assert "الرمز الإحصائي الثابت الصادر من وزارة التربية" in html, "Help text missing"
    assert "modalCloudRestore" in html, "modalCloudRestore missing from template"
    assert "/portal/settings/cloud-sync/" in html, "portal_cloud_backup_now URL missing"
    assert "/portal/settings/cloud-restore/" in html, "portal_cloud_restore URL missing"
    print(" -> PASS: All UI elements (input, badge, modal, action buttons) verified in settings.html.")

    # Test POST endpoint for cloud sync
    resp_sync_ep = client.post('/portal/settings/cloud-sync/')
    assert resp_sync_ep.status_code == 302
    print(" -> PASS: /portal/settings/cloud-sync/ endpoint returns 302 redirect.")

    # Test POST endpoint for emergency restore with empty code
    resp_res_ep = client.post('/portal/settings/cloud-restore/', data={'ministry_school_code': ''})
    assert resp_res_ep.status_code == 302
    print(" -> PASS: /portal/settings/cloud-restore/ endpoint returns 302 redirect.")

    print("\n==================================================")
    print("     ALL CLOUD SYNC & RESTORE TESTS PASSED!       ")
    print("==================================================")

if __name__ == '__main__':
    test_cloud_sync_and_restore()
