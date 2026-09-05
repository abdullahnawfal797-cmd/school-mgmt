from django.urls import path, include
from django.views.generic.base import RedirectView
from rest_framework import routers
from .views import (
    UserViewSet, ParentViewSet, TeacherViewSet,
    SchoolClassViewSet, SectionViewSet, StudentViewSet,
    EnrollmentViewSet, SubjectViewSet, AttendanceViewSet,
    GradeViewSet, TimetableSlotViewSet, OfficialDocumentViewSet,
    InvoiceViewSet,
    # واجهات الـ API التجارية المضافة
    SyncEngineViewSet,
    BackupRestoreAPI,
    LicenseValidationAPI,
    SystemUpdateAPI,
    # دوال النسخ الاحتياطي والتحديثات المحلية
    download_backup_view,
    restore_backup_view,
    upload_patch_view,
    # دوال النسخ والاسترجاع السحابي والتحديث التلقائي
    cloud_backup_upload_view,
    cloud_backup_restore_view,
    cloud_check_update_view,
    apply_system_update_view,
    # دوال الشهادات والتأييدات
    teacher_service_certificate_view,
    student_transcript_view,
    class_master_sheet_view,
    portal_student_result_cards,
    # دوال البوابة المدرسية
    portal_dashboard,
    portal_set_current_year,
    portal_settings,
    portal_students_manage,
    portal_classes_manage,
    portal_subjects_manage,
    portal_attendance_manage,
    portal_parents_manage,
    portal_teachers_manage,
    portal_teacher_delete,
    portal_timetable,
    portal_grades_manage,
    portal_records_manage,
    portal_records_export_pdf,
    portal_usb_backup_save,
    portal_create_snapshot_now,
    portal_cloud_backup_now,
    portal_cloud_restore,
    promotion_view,
    generate_years_view,
    exam_halls_view,
    print_exam_labels,
    print_exam_attendance,
    general_registry_view,
    letter_builder_view,
    # دوال معالج التهيئة والأرشيف الرسمي
    portal_first_run_setup,
    portal_official_archive,
    portal_archive_add,
    portal_archive_save_letter,
    portal_archive_delete,
    portal_document_pdf_download,
    portal_letter_export_pdf,
    portal_export_students_excel,
    # دوال الترخيص والمالك
    portal_license_lock,
    portal_license_activate,
    owner_key_generator,
    # دوال التعديل السريع
    portal_student_edit,
    portal_teacher_edit,
    portal_subject_edit,
    portal_parent_edit,
    portal_class_edit
)

router = routers.DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'parents', ParentViewSet, basename='parent')
router.register(r'teachers', TeacherViewSet, basename='teacher')
router.register(r'classes', SchoolClassViewSet, basename='schoolclass')
router.register(r'sections', SectionViewSet, basename='section')
router.register(r'students', StudentViewSet, basename='student')
router.register(r'enrollments', EnrollmentViewSet, basename='enrollment')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'attendance', AttendanceViewSet, basename='attendance')
router.register(r'grades', GradeViewSet, basename='grade')
router.register(r'timetable', TimetableSlotViewSet, basename='timetableslot')
router.register(r'official-docs', OfficialDocumentViewSet, basename='officialdocument')
router.register(r'invoices', InvoiceViewSet, basename='invoice')

# تسجيل محرك المزامنة التلقائي في الـ API
router.register(r'sync', SyncEngineViewSet, basename='sync_engine')

urlpatterns = [
    # REST API Endpoints
    path('api/', include(router.urls)),
    path('api/backup-status/', BackupRestoreAPI.as_view(), name='api_backup_status'),
    path('api/license-validate/', LicenseValidationAPI.as_view(), name='api_license_validate'),
    path('api/check-updates/', SystemUpdateAPI.as_view(), name='api_check_updates'),

    # Official Certificate & Document Print Endpoints
    path('certificates/teacher-service/<int:teacher_id>/', teacher_service_certificate_view, name='cert_teacher_service'),
    path('certificates/student-transcript/<int:student_id>/', student_transcript_view, name='student_transcript'),
    path('certificates/student-transcript-alt/<int:student_id>/', student_transcript_view, name='cert_student_transcript'),
    path('certificates/master-sheet/<int:class_id>/', class_master_sheet_view, name='cert_master_sheet'),

    # Interactive Portal & Management System Endpoints
    path('', portal_dashboard, name='home'),
    path('portal/', portal_dashboard, name='portal_dashboard'),
    path('portal/set-year/', portal_set_current_year, name='portal_set_current_year'),
    path('portal/settings/', portal_settings, name='portal_settings'),
    path('portal/students-manage/', portal_students_manage, name='portal_students_manage'),
    path('portal/classes-manage/', portal_classes_manage, name='portal_classes_manage'),
    path('portal/subjects-manage/', portal_subjects_manage, name='portal_subjects_manage'),
    path('portal/attendance-manage/', portal_attendance_manage, name='portal_attendance_manage'),
    path('portal/parents-manage/', portal_parents_manage, name='portal_parents_manage'),
    path('portal/teachers-manage/', portal_teachers_manage, name='portal_teachers_manage'),
    path('portal/timetable/', portal_timetable, name='portal_timetable'),
    path('portal/grades-manage/', portal_grades_manage, name='portal_grades_manage'),
    path('portal/result-cards/', portal_student_result_cards, name='portal_student_result_cards'),
    path('portal/result-cards/<int:student_id>/', portal_student_result_cards, name='portal_student_result_card_single'),
    path('portal/records/', portal_records_manage, name='portal_records_manage'),
    path('portal/records/export-pdf/', portal_records_export_pdf, name='portal_records_export_pdf'),
    path('portal/promotion/', promotion_view, name='portal_promotion'),
    path('portal/generate-years/', generate_years_view, name='portal_generate_years'),
    path('portal/exam-halls/', exam_halls_view, name='portal_exam_halls'),
    path('portal/exam-halls/<int:session_id>/labels/', print_exam_labels, name='print_exam_labels'),
    path('portal/exam-halls/<int:session_id>/attendance/', print_exam_attendance, name='print_exam_attendance'),
    path('portal/registry/', general_registry_view, name='portal_general_registry'),
    path('portal/students/export-excel/', portal_export_students_excel, name='portal_students_export_excel'),
    path('portal/letter-builder/', letter_builder_view, name='portal_letter_builder'),
    path('portal/letter-builder/export-pdf/', portal_letter_export_pdf, name='portal_letter_export_pdf'),

    # First-Run Setup Wizard
    path('portal/first-run/', portal_first_run_setup, name='portal_first_run_setup'),

    # Official Documents Archive Module
    path('portal/archive/', portal_official_archive, name='portal_official_archive'),
    path('portal/archive/add/', portal_archive_add, name='portal_archive_add'),
    path('portal/archive/save-letter/', portal_archive_save_letter, name='portal_archive_save_letter'),
    path('portal/archive/<int:doc_id>/delete/', portal_archive_delete, name='portal_archive_delete'),
    path('portal/archive/<int:doc_id>/pdf/', portal_document_pdf_download, name='portal_document_pdf'),

    # Management Backup & Updates Endpoints (Local & USB Vault)
    path('portal/settings/backup/download/', download_backup_view, name='portal_backup_download'),
    path('portal/settings/backup/restore/', restore_backup_view, name='portal_backup_restore'),
    path('portal/settings/backup/usb/', portal_usb_backup_save, name='portal_usb_backup_save'),
    path('portal/settings/backup/snapshot-now/', portal_create_snapshot_now, name='portal_create_snapshot_now'),
    path('portal/settings/patch/upload/', upload_patch_view, name='portal_patch_upload'),

    # Management Backup & Updates Endpoints (Cloud)
    path('portal/settings/cloud-sync/', portal_cloud_backup_now, name='portal_cloud_backup_now'),
    path('portal/settings/cloud-restore/', portal_cloud_restore, name='portal_cloud_restore'),
    path('portal/settings/cloud/upload/', cloud_backup_upload_view, name='portal_cloud_backup_upload'),
    path('portal/settings/cloud/restore/', cloud_backup_restore_view, name='portal_cloud_backup_restore'),
    path('portal/settings/cloud/check-update/', cloud_check_update_view, name='portal_cloud_check_update'),
    path('portal/settings/cloud/apply-update/', apply_system_update_view, name='portal_cloud_apply_update'),

    # SaaS Licensing & Activation Engine
    path('portal/license-lock/', portal_license_lock, name='portal_license_lock'),
    path('portal/license-activate/', portal_license_activate, name='portal_license_activate'),
    path('portal/owner-generator/', owner_key_generator, name='portal_owner_generator'),

    # Entity Edit & Delete Endpoints
    path('portal/students/<int:student_id>/edit/', portal_student_edit, name='portal_student_edit'),
    path('portal/teachers/<int:teacher_id>/edit/', portal_teacher_edit, name='portal_teacher_edit'),
    path('portal/teachers/delete/<int:teacher_id>/', portal_teacher_delete, name='portal_teacher_delete'),
    path('portal/subjects/<int:subject_id>/edit/', portal_subject_edit, name='portal_subject_edit'),
    path('portal/parents/<int:parent_id>/edit/', portal_parent_edit, name='portal_parent_edit'),
    path('portal/classes/<int:class_id>/edit/', portal_class_edit, name='portal_class_edit'),

    # Favicon route (prevents 404 console errors)
    path('favicon.ico', RedirectView.as_view(url='/static/img/favicon.ico', permanent=True)),

    # Friendly Navigation Aliases (prevents 404 on direct manual URLs)
    path('portal/teachers/', portal_teachers_manage),
    path('portal/classes/', portal_classes_manage),
    path('portal/grades/', portal_grades_manage),
    path('portal/students/', portal_students_manage),
    path('portal/subjects/', portal_subjects_manage),
    path('portal/parents/', portal_parents_manage),
    path('portal/attendance/', portal_attendance_manage),
    path('portal/official-archive/', portal_official_archive),
    path('portal/general-registry/', general_registry_view),
    path('portal/letters/', letter_builder_view),
]