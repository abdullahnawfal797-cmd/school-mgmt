import os
import sys
from pathlib import Path
import tempfile
import time

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')
django.setup()

from django.test import Client
from django.utils import timezone
from core.models import SchoolSettings, SchoolClass, Section, Student, Subject, AcademicYear
from core.backup_vault import (
    get_backup_dir,
    create_daily_backup_snapshot,
    rotate_backups,
    list_local_backups,
    get_removable_drives,
    save_backup_to_usb
)
from core.pdf_generator import generate_middle_record_pdf

def test_all():
    print("==================================================")
    print("   QA & VALIDATION: BACKUP VAULT & PRINT FIX      ")
    print("==================================================")

    # ----------------------------------------------------
    # 1. Test Backup Vault Snapshot Creation
    # ----------------------------------------------------
    print("\n[TEST 1] Testing Local Backup Snapshot Creation...")
    success, msg = create_daily_backup_snapshot()
    assert success is True, f"Failed to create daily backup snapshot: {msg}"
    backup_dir = get_backup_dir()
    today_str = timezone.now().strftime("%Y_%m_%d")
    expected_file = os.path.join(backup_dir, f"backup_{today_str}.db")
    assert os.path.exists(expected_file), f"Expected snapshot file does not exist: {expected_file}"
    assert os.path.getsize(expected_file) > 0, "Snapshot file is empty!"
    print(f" -> PASS: Snapshot successfully created: {expected_file} ({round(os.path.getsize(expected_file)/1024, 2)} KB)")

    # ----------------------------------------------------
    # 2. Test 7-Day Backup Retention Policy
    # ----------------------------------------------------
    print("\n[TEST 2] Testing 7-Day Retention Policy (Purging older than 7)...")
    with tempfile.TemporaryDirectory() as temp_vault:
        # Create 10 dummy backup files with staggered timestamps
        for i in range(10):
            dummy_path = os.path.join(temp_vault, f"backup_2026_01_{i+1:02d}.db")
            with open(dummy_path, "w") as f:
                f.write(f"dummy data {i}")
            # Set mtime
            mtime = time.time() - (10 - i) * 86400
            os.utime(dummy_path, (mtime, mtime))

        assert len(os.listdir(temp_vault)) == 10, "Failed to create 10 dummy files"
        rotate_backups(temp_vault, max_keep=7)
        remaining = os.listdir(temp_vault)
        assert len(remaining) == 7, f"Expected 7 files to remain, got {len(remaining)}"
        assert "backup_2026_01_01.db" not in remaining, "Oldest file was not purged!"
        assert "backup_2026_01_02.db" not in remaining, "Second oldest file was not purged!"
        assert "backup_2026_01_03.db" not in remaining, "Third oldest file was not purged!"
        assert "backup_2026_01_10.db" in remaining, "Newest file was deleted unexpectedly!"
        print(" -> PASS: Retention policy strictly kept the 7 newest files and removed the 3 oldest.")

    # ----------------------------------------------------
    # 3. Test USB Backup Export
    # ----------------------------------------------------
    print("\n[TEST 3] Testing USB Backup Export to Target Directory...")
    with tempfile.TemporaryDirectory() as mock_usb:
        success, msg = save_backup_to_usb(mock_usb)
        assert success is True, f"Failed to save USB backup: {msg}"
        usb_dest = os.path.join(mock_usb, "Madrasati_Backups")
        assert os.path.exists(usb_dest), "Madrasati_Backups folder not created on USB!"
        files = os.listdir(usb_dest)
        assert len(files) == 1, f"Expected 1 backup file in USB folder, got {files}"
        assert files[0].startswith("backup_madrasati_") and files[0].endswith(".db")
        print(f" -> PASS: USB Backup successfully created: {os.path.join(usb_dest, files[0])}")

    # ----------------------------------------------------
    # 4. Test Middle Record PDF Generator Engine
    # ----------------------------------------------------
    print("\n[TEST 4] Testing Server-side Middle Record PDF Generation (ReportLab)...")
    school = SchoolSettings.get_settings()
    current_year = AcademicYear.objects.filter(is_current=True).first()
    selected_class = SchoolClass.objects.first()
    if not selected_class:
        selected_class = SchoolClass.objects.create(name="الصف الأول المتوسط", level_order=1)

    sections_data = []
    class_sections = list(selected_class.sections.all())
    if not class_sections:
        sec = Section.objects.create(school_class=selected_class, name='أ')
        class_sections = [sec]

    for sec in class_sections:
        st_list = list(Student.objects.filter(current_class=selected_class, section=sec, is_deleted=False)[:5])
        sections_data.append({
            'section': sec,
            'students': st_list,
            'students_count': len(st_list)
        })

    subjects_list = ["التربية الإسلامية", "اللغة العربية", "اللغة الإنكليزية", "الرياضيات", "العلوم", "الاجتماعيات"]

    pdf_bytes = generate_middle_record_pdf(
        school=school,
        selected_class=selected_class,
        current_year=current_year,
        sections_data=sections_data,
        subjects_list=subjects_list,
        empty_pages_count=2
    )

    assert pdf_bytes is not None and len(pdf_bytes) > 0, "PDF generator returned empty output"
    assert pdf_bytes.startswith(b'%PDF-'), "Generated data does not start with PDF magic header %PDF-"
    print(f" -> PASS: Middle Record PDF generated cleanly ({round(len(pdf_bytes)/1024, 2)} KB) with ministerial layout.")

    # ----------------------------------------------------
    # 5. Test Endpoints & View Responses
    # ----------------------------------------------------
    print("\n[TEST 5] Testing Endpoints & Middle Record Web Controls...")
    client = Client()

    # Test PDF Export Endpoint
    export_url = f"/portal/records/export-pdf/?class_id={selected_class.id}"
    resp_pdf = client.get(export_url)
    assert resp_pdf.status_code == 200, f"Export PDF returned {resp_pdf.status_code}"
    assert resp_pdf['Content-Type'] == 'application/pdf', f"Unexpected Content-Type: {resp_pdf['Content-Type']}"
    assert resp_pdf.content.startswith(b'%PDF-'), "Response is not valid PDF"
    print(" -> PASS: /portal/records/export-pdf/ endpoint streams valid PDF directly.")

    # Test Snapshot Now Endpoint
    resp_snap = client.post('/portal/settings/backup/snapshot-now/')
    assert resp_snap.status_code == 302, f"Expected 302 redirect, got {resp_snap.status_code}"

    # Test Records Manage HTML elements
    resp_html = client.get(f'/portal/records/?record_type=middle_record&class_id={selected_class.id}')
    assert resp_html.status_code == 200
    html = resp_html.content.decode('utf-8')
    assert "filterSectionSelect" in html, "filterSectionSelect missing from template"
    assert "filterStudentSelect" in html, "filterStudentSelect missing from template"
    assert "filterPageFrom" in html, "filterPageFrom missing from template"
    assert "btnExportPdfDirect" in html, "btnExportPdfDirect missing from template"
    assert "middle-record-page" in html, "middle-record-page class missing from template"
    assert "printFilteredMiddleRecord" in html, "printFilteredMiddleRecord function missing"
    assert "print-page-hidden" in html, "print-page-hidden CSS missing"
    print(" -> PASS: All smart print controls, filter elements, and performance CSS verified in template.")

    print("\n==================================================")
    print("        ALL QA & VALIDATION TESTS PASSED!         ")
    print("==================================================")

if __name__ == '__main__':
    test_all()
