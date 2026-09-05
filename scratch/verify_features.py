import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')

import django
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from core.models import SchoolSettings, SchoolClass, Section, Student, OfficialDocument
from core.views import (
    portal_export_students_excel,
    portal_document_pdf_download,
    portal_letter_export_pdf,
    portal_students_manage,
    general_registry_view,
    letter_builder_view,
    portal_official_archive
)

factory = RequestFactory()
User = get_user_model()
admin_user = User.objects.filter(is_superuser=True).first()
if not admin_user:
    admin_user = User.objects.filter(is_staff=True).first()
if not admin_user:
    admin_user = User.objects.first()

print("1. Testing Classes & Stages in Database...")
classes = SchoolClass.objects.all().order_by('level_order')
assert classes.count() >= 15, f"Expected at least 15 classes, got {classes.count()}"
print(f"   [OK] Total Iraqi Classes: {classes.count()}")

print("2. Testing Excel Export for All Students...")
req = factory.get('/portal/students/export-excel/?export_all=1')
req.user = admin_user
resp = portal_export_students_excel(req)
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
assert 'spreadsheetml' in resp['Content-Type']
assert len(resp.content) > 1000, f"Excel file too small: {len(resp.content)} bytes"
print(f"   [OK] All Students Excel exported successfully ({len(resp.content)} bytes).")

print("3. Testing Excel Export for Specific Class & Section...")
first_class = classes.first()
first_sec = first_class.sections.first()
req2 = factory.get(f'/portal/students/export-excel/?class_id={first_class.id}&section_id={first_sec.id if first_sec else ""}')
req2.user = admin_user
resp2 = portal_export_students_excel(req2)
assert resp2.status_code == 200
assert len(resp2.content) > 1000
print(f"   [OK] Specific Class/Section Excel exported successfully ({len(resp2.content)} bytes).")

print("4. Testing PDF Direct Download from Official Archive...")
school = SchoolSettings.get_settings()
doc = OfficialDocument.objects.first()
if not doc:
    doc = OfficialDocument.objects.create(
        doc_number='TEST/001',
        doc_date='2026-09-04',
        doc_type='issued',
        sender_receiver='الجهة المعنية',
        subject='كتاب اختبار تجريبي',
        body_content='هذا كتاب اختبار تجريبي للتأكد من جودة طباعة وتوليد وثائق PDF.'
    )
req_pdf = factory.get(f'/portal/archive/{doc.id}/pdf/')
req_pdf.user = admin_user
resp_pdf = portal_document_pdf_download(req_pdf, doc.id)
assert resp_pdf.status_code == 200, f"Expected 200, got {resp_pdf.status_code}"
assert resp_pdf['Content-Type'] == 'application/pdf'
assert len(resp_pdf.content) > 10000, f"PDF file too small: {len(resp_pdf.content)} bytes"
print(f"   [OK] Official Archive PDF generated successfully ({len(resp_pdf.content)} bytes).")

print("5. Testing Letter Builder PDF Instant Export...")
req_builder_pdf = factory.post('/portal/letter-builder/export-pdf/', {
    'doc_number': 'م.ت/99',
    'doc_date': '2026/09/04',
    'destination': 'إلى من يهمه الأمر',
    'subject': 'تأييد استمرار بالدوام',
    'body_content': 'نؤيد استمرار الطالب بالدوام الرسمي في الصف الأول المتوسط.'
})
req_builder_pdf.user = admin_user
resp_bpdf = portal_letter_export_pdf(req_builder_pdf)
assert resp_bpdf.status_code == 200
assert resp_bpdf['Content-Type'] == 'application/pdf'
assert len(resp_bpdf.content) > 10000
print(f"   [OK] Letter Builder Instant PDF exported successfully ({len(resp_bpdf.content)} bytes).")

print("6. Testing Portal Views Rendering...")
for view_fn, path in [
    (portal_students_manage, '/portal/students-manage/'),
    (general_registry_view, '/portal/registry/'),
    (letter_builder_view, '/portal/letter-builder/'),
    (portal_official_archive, '/portal/archive/')
]:
    r = factory.get(path)
    r.user = admin_user
    # Some views might use messages framework
    from django.contrib.messages.storage.fallback import FallbackStorage
    setattr(r, 'session', {})
    setattr(r, '_messages', FallbackStorage(r))
    res = view_fn(r)
    assert res.status_code == 200, f"View {view_fn.__name__} returned {res.status_code}"
    print(f"   [OK] View {view_fn.__name__} rendered cleanly.")

print("\n=======================================================")
print("ALL 5 PILLARS SYSTEM INTEGRATION VERIFIED SUCCESSFULLY!")
print("=======================================================")
