from django.urls import path
from . import views

urlpatterns = [
    # 1. المصادقة والجلسات المستمرة
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/verify-session/', views.verify_session_view, name='verify_session'),
    path('auth/me/', views.verify_session_view, name='auth_me'),
    path('auth/refresh/', views.refresh_token_view, name='refresh_token'),
    path('auth/activate-code/', views.submit_activation_code_view, name='submit_activation_code'),
    path('auth/activate/', views.submit_activation_code_view, name='auth_activate'),

    # 2. بوابة المالك المركزي والاشتراكات المالية
    path('owner/dashboard/', views.owner_dashboard_summary_view, name='owner_dashboard_summary'),
    path('owner/schools-summary/', views.owner_dashboard_summary_view, name='owner_schools_summary'),
    path('owner/financial-analytics/', views.owner_dashboard_summary_view, name='owner_financial_analytics'),
    path('owner/schools/create/', views.owner_create_school_view, name='owner_create_school'),
    path('owner/schools/<int:school_id>/details/', views.owner_school_details_view, name='owner_school_details'),
    path('owner/schools/<int:school_id>/statement/', views.owner_school_yearly_statement_view, name='owner_school_yearly_statement'),
    path('owner/schools/<int:school_id>/update-subscription/', views.owner_update_school_subscription_view, name='owner_update_subscription'),
    path('owner/schools/<int:school_id>/payments/add/', views.owner_add_payment_view, name='owner_add_payment'),
    path('owner/schools/<int:school_id>/adjustments/add/', views.owner_add_adjustment_view, name='owner_add_adjustment'),
    path('owner/schools/<int:school_id>/managers/create/', views.owner_create_manager_view, name='owner_create_manager'),

    # إدارة تفعيل أولياء الأمور من المالك
    path('owner/activations/pending/', views.owner_pending_activations_view, name='owner_pending_activations'),
    path('owner/activations/<int:activation_id>/decide/', views.owner_decide_activation_view, name='owner_decide_activation'),

    # 3. توليد كود التفعيل من سطح المكتب
    path('activations/generate/', views.generate_activation_code_view, name='generate_activation_code'),

    # 4. بوابة مدير المدرسة والعزل المدرسي
    path('manager/dashboard/', views.manager_dashboard_view, name='manager_dashboard'),
    path('manager/grades-approval/', views.manager_grades_approval_view, name='manager_grades_approval'),
    path('manager/pending-grades/', views.manager_pending_grades_view, name='manager_pending_grades'),
    path('manager/approve-grade/', views.manager_approve_grade_view, name='manager_approve_grade'),
    path('manager/pending-activations/', views.manager_pending_activations_view, name='manager_pending_activations'),
    path('manager/pending-requests/', views.manager_pending_requests_view, name='manager_pending_requests'),

    # 5. بوابة المعلم ورصد الدرجات وسجل الحضور
    path('teacher/dashboard/', views.teacher_dashboard_view, name='teacher_dashboard'),
    path('teacher/classroom/', views.teacher_classroom_view, name='teacher_classroom'),
    path('teacher/class-students/', views.teacher_class_students_view, name='teacher_class_students'),
    path('teacher/grading-sheet/', views.teacher_grading_sheet_view, name='teacher_grading_sheet'),
    path('teacher/submit-grades/', views.teacher_submit_grades_view, name='teacher_submit_grades'),
    path('teacher/submit-attendance/', views.teacher_submit_attendance_view, name='teacher_submit_attendance'),

    # 6. بوابة ولي الأمر
    path('parent/dashboard/', views.parent_dashboard_view, name='parent_dashboard'),
    path('parent/portal/', views.parent_dashboard_view, name='parent_portal'),
    path('parent/student/<int:student_id>/', views.parent_student_detail_view, name='parent_student_detail'),
    path('parent/student/<int:student_id>/timeline/', views.parent_student_timeline_view, name='parent_student_timeline'),
    path('parent/student-profile/', views.parent_student_detail_view, name='parent_student_profile_alias'),
    path('parent/grades/', views.parent_dashboard_view, name='parent_grades_alias'),
    path('parent/activate-code/', views.submit_activation_code_view, name='parent_activate_code'),
    path('parent/requests/', views.parent_requests_view, name='parent_requests'),
    path('documents/', views.parent_requests_view, name='documents_alias'),

    # 7. الإشعارات والتعاميم والواجبات المدرسية
    path('notifications/', views.list_notifications_view, name='list_notifications'),
    path('notifications/mark-read/', views.mark_notifications_read_view, name='mark_notifications_read'),
    path('news/', views.school_news_view, name='school_news'),
    path('homework/', views.homework_view, name='homework'),
    path('homework/broadcast/', views.homework_view, name='homework_broadcast'),
    path('teacher/homework/', views.homework_view, name='teacher_homework_alias'),
]
