from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Parent, Teacher, Student, SchoolClass,
    Section, Subject, Attendance, Grade,
    TimetableSlot, Enrollment, OfficialDocument, Invoice,
    AcademicYear, StudentAcademicHistory, ExamHall,
    ExamSession, ExamSeatAssignment, OfficialLetterTemplate
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_student', 'is_teacher', 'is_parent', 'is_staff')
    list_filter = ('is_student', 'is_teacher', 'is_parent', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role Flags', {'fields': ('is_student', 'is_teacher', 'is_parent')}),
    )


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'phone', 'address')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'job_title', 'statistical_code', 'hire_date')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'job_title', 'statistical_code')
    filter_horizontal = ('subjects',)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current', 'is_archived')
    list_filter = ('is_current', 'is_archived')
    search_fields = ('name',)
    actions = ['generate_50_years']

    @admin.action(description='توليد السنوات الدراسية لـ 50 سنة قادمة تلقائياً (ابتداءً من 2026)')
    def generate_50_years(self, request, queryset):
        count = AcademicYear.generate_next_50_years(start_year=2026)
        self.message_user(request, f"تم بنجاح توليد {count} سنة دراسية جديدة تبدأ من عام 2026-2027.")


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'level_order', 'next_class', 'is_final_stage')
    list_filter = ('is_final_stage',)
    search_fields = ('name',)
    ordering = ('level_order', 'name')


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'school_class')
    list_filter = ('school_class',)
    search_fields = ('name', 'school_class__name')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('registration_number', 'user', 'current_class', 'section', 'student_status', 'admission_date', 'is_deleted')
    list_filter = ('student_status', 'current_class', 'section', 'is_deleted')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'registration_number', 'national_id')
    fieldsets = (
        ('بيانات الحساب والهوية', {
            'fields': ('user', 'registration_number', 'national_id', 'dob', 'parent')
        }),
        ('القيد والدوام المدرسي', {
            'fields': ('current_class', 'section', 'student_status', 'admission_date')
        }),
        ('حالة الحذف الآمن (Soft Delete)', {
            'fields': ('is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StudentAcademicHistory)
class StudentAcademicHistoryAdmin(admin.ModelAdmin):
    list_display = ('student', 'academic_year', 'school_class', 'section', 'result_status', 'general_average', 'recorded_at')
    list_filter = ('academic_year', 'result_status', 'school_class')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'student__registration_number')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'school_class', 'academic_year', 'status')
    list_filter = ('academic_year', 'status', 'school_class')
    search_fields = ('student__user__username', 'student__user__first_name', 'student__user__last_name')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code')
    search_fields = ('name', 'code')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'date', 'status', 'recorded_by')
    list_filter = ('status', 'date')
    search_fields = ('student__user__first_name', 'student__user__last_name')


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'student', 'subject', 'academic_year',
        'first_term_effort', 'midyear_exam', 'second_term_effort',
        'annual_effort', 'final_grade', 'decision_marks',
        'final_grade_after_decision', 'status'
    )
    list_filter = ('academic_year', 'status', 'subject', 'student__current_class')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'subject__name')
    fieldsets = (
        ('معلومات الطالب والمادة', {
            'fields': ('student', 'subject', 'academic_year')
        }),
        ('الفصل الأول', {
            'fields': ('first_term_month1', 'first_term_month2', 'first_term_effort')
        }),
        ('امتحان نصف السنة', {
            'fields': ('midyear_exam',)
        }),
        ('الفصل الثاني', {
            'fields': ('second_term_month1', 'second_term_month2', 'second_term_effort')
        }),
        ('السعي السنوي والامتحان النهائي', {
            'fields': ('annual_effort', 'final_exam_round1', 'final_exam_round2')
        }),
        ('الدرجة النهائية والقرار', {
            'fields': ('final_grade', 'decision_marks', 'final_grade_after_decision', 'status')
        }),
    )


@admin.register(TimetableSlot)
class TimetableSlotAdmin(admin.ModelAdmin):
    list_display = ('id', 'school_class', 'section', 'subject', 'teacher', 'day', 'start_time', 'end_time')
    list_filter = ('day', 'school_class', 'section', 'subject')


@admin.register(ExamHall)
class ExamHallAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'capacity', 'rows_count', 'cols_count')
    search_fields = ('name', 'location')


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'session_type', 'academic_year', 'start_date', 'end_date')
    list_filter = ('session_type', 'academic_year')
    search_fields = ('title',)
    filter_horizontal = ('halls',)


@admin.register(ExamSeatAssignment)
class ExamSeatAssignmentAdmin(admin.ModelAdmin):
    list_display = ('exam_session', 'exam_hall', 'seat_number', 'student', 'desk_row', 'desk_col')
    list_filter = ('exam_session', 'exam_hall')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'student__registration_number', 'seat_number')
    ordering = ('exam_hall', 'seat_number')


@admin.register(OfficialLetterTemplate)
class OfficialLetterTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'created_at')
    list_filter = ('template_type',)
    search_fields = ('name', 'content')


@admin.register(OfficialDocument)
class OfficialDocumentAdmin(admin.ModelAdmin):
    list_display = ('doc_number', 'doc_date', 'doc_type', 'sender_receiver', 'subject', 'status', 'created_by')
    list_filter = ('doc_type', 'status', 'doc_date')
    search_fields = ('doc_number', 'subject', 'sender_receiver', 'notes', 'incoming_doc_number', 'outgoing_reply_number')
    date_hierarchy = 'doc_date'
    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('doc_type', 'doc_number', 'doc_date', 'sender_receiver', 'subject', 'status')
        }),
        ('ربط الوارد بالصادر', {
            'fields': ('incoming_doc_number', 'incoming_doc_date', 'outgoing_reply_number')
        }),
        ('نص الكتاب والمرفقات', {
            'fields': ('body_content', 'file', 'notes', 'created_by')
        }),
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'amount', 'due_date', 'status', 'created_at')
    list_filter = ('status', 'due_date')
    search_fields = ('student__user__first_name', 'student__user__last_name')