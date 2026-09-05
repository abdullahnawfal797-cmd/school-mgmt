from rest_framework import serializers
from .models import (
    User, Parent, Teacher, SchoolClass, Section,
    Student, Enrollment, Subject, Attendance, Grade,
    TimetableSlot, OfficialDocument, Invoice
)

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_student', 'is_teacher', 'is_parent', 'is_staff', 'password'
        ]

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user


class UserMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'code']


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ['id', 'school_class', 'name']


class SchoolClassSerializer(serializers.ModelSerializer):
    sections = SectionSerializer(many=True, read_only=True)

    class Meta:
        model = SchoolClass
        fields = ['id', 'name', 'year', 'sections']


class ParentSerializer(serializers.ModelSerializer):
    user_details = UserMiniSerializer(source='user', read_only=True)

    class Meta:
        model = Parent
        fields = ['id', 'user', 'user_details', 'phone', 'address']


class TeacherSerializer(serializers.ModelSerializer):
    user_details = UserMiniSerializer(source='user', read_only=True)
    subjects_details = SubjectSerializer(source='subjects', many=True, read_only=True)

    class Meta:
        model = Teacher
        fields = [
            'id', 'user', 'user_details', 'job_title', 'statistical_code',
            'hire_date', 'subjects', 'subjects_details'
        ]


class StudentSerializer(serializers.ModelSerializer):
    user_details = UserMiniSerializer(source='user', read_only=True)
    parent_details = ParentSerializer(source='parent', read_only=True)
    class_name = serializers.CharField(source='current_class.name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'user', 'user_details', 'national_id', 'dob',
            'current_class', 'class_name', 'section', 'section_name',
            'parent', 'parent_details'
        ]


class EnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    class_name = serializers.CharField(source='school_class.name', read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'student', 'student_name', 'school_class', 'class_name', 'academic_year', 'status']


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Attendance
        fields = [
            'id', 'student', 'student_name', 'date', 'status',
            'status_display', 'recorded_by', 'recorded_by_name'
        ]


class GradeSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Grade
        fields = [
            'id', 'student', 'student_name', 'subject', 'subject_name', 'academic_year',
            # الفصل الأول
            'first_term_month1', 'first_term_month2', 'first_term_effort',
            # نصف السنة
            'midyear_exam',
            # الفصل الثاني
            'second_term_month1', 'second_term_month2', 'second_term_effort',
            # السعي السنوي
            'annual_effort',
            # الامتحان النهائي
            'final_exam_round1', 'final_exam_round2',
            # الدرجات النهائية والقرار
            'final_grade', 'decision_marks', 'final_grade_after_decision',
            # النتيجة
            'status', 'status_display'
        ]


class TimetableSlotSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source='school_class.name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    day_display = serializers.CharField(source='get_day_display', read_only=True)

    class Meta:
        model = TimetableSlot
        fields = [
            'id', 'school_class', 'class_name', 'section', 'section_name',
            'subject', 'subject_name', 'teacher', 'teacher_name',
            'day', 'day_display', 'start_time', 'end_time'
        ]


class OfficialDocumentSerializer(serializers.ModelSerializer):
    doc_type_display = serializers.CharField(source='get_doc_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = OfficialDocument
        fields = [
            'id', 'doc_number', 'doc_date', 'doc_type', 'doc_type_display',
            'sender_receiver', 'subject', 'file', 'status', 'status_display',
            'notes', 'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Invoice
        fields = ['id', 'student', 'student_name', 'amount', 'due_date', 'status', 'status_display', 'created_at']
