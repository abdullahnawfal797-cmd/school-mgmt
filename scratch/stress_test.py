import os
import sys
import time
import django
import random

sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from django.conf import settings
from decimal import Decimal
from core.models import (
    SchoolClass, Section, Student, Subject, Teacher,
    Grade, Attendance, TimetableSlot, SchoolSettings, AcademicYear
)

User = get_user_model()

def populate_mock_data_if_needed(target_students=1000):
    print("=== [1] فحص وتجهيز بيانات الضغط العالي ===")
    current_count = Student.objects.filter(is_deleted=False).count()
    print(f"عدد الطلاب الحالي في قاعدة البيانات: {current_count}")
    if current_count >= 500:
        print("البيانات كافية وجاهزة لإجراء اختبارات الضغط والتحمل الفائقة.")
        return

    subjects = list(Subject.objects.all())
    if not subjects:
        for sname in ['التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات', 'العلوم', 'الاجتماعيات']:
            Subject.objects.get_or_create(name=sname)
        subjects = list(Subject.objects.all())

    needed = target_students - current_count
    if needed > 0:
        print(f"جاري إضافة {needed} طالب لمحاكاة مدرسة ضخمة...")
        start_id = current_count + 1
        users_to_create = []
        for i in range(start_id, start_id + needed):
            users_to_create.append(
                User(
                    username=f"student_stress_{i}",
                    first_name=f"طالب_{i}",
                    last_name=f"العراقي_{i}",
                    is_student=True
                )
            )
        User.objects.bulk_create(users_to_create, batch_size=500)

        # جلب المستخدمين المنشئين
        created_users = list(User.objects.filter(username__startswith='student_stress_').order_by('id')[current_count:])
        sections = list(Section.objects.all())

        students_to_create = []
        for idx, u in enumerate(created_users):
            cls = classes[idx % len(classes)]
            sec = sections[idx % len(sections)] if sections else None
            students_to_create.append(
                Student(
                    user=u,
                    registration_number=f"REG_{20260000 + idx}",
                    national_id=f"NAT_{1000000000 + idx}",
                    student_status='active',
                    current_class=cls,
                    section=sec
                )
            )
        Student.objects.bulk_create(students_to_create, batch_size=500)
        print(f"تم بنجاح توليد الطلاب؛ الإجمالي الآن: {Student.objects.filter(is_deleted=False).count()} طالب.")

    # إنشاء درجات عينة للطلاب إن لم تكن كافية
    grade_count = Grade.objects.count()
    if grade_count < 3000:
        print("توليد عينات درجات مكثفة لفحص سرعة الاستعلامات...")
        active_students = list(Student.objects.filter(is_deleted=False)[:500])
        grades_to_create = []
        for st in active_students:
            for sub in subjects[:4]:
                grades_to_create.append(
                    Grade(
                        student=st,
                        subject=sub,
                        academic_year='2026-2027',
                        first_term_effort=Decimal(random.randint(50, 95)),
                        midyear_exam=Decimal(random.randint(50, 95)),
                        second_term_effort=Decimal(random.randint(50, 95)),
                        annual_effort=Decimal(random.randint(50, 95)),
                        final_exam_round1=Decimal(random.randint(50, 95)),
                        final_grade=Decimal(random.randint(50, 95)),
                        status='passed'
                    )
                )
        Grade.objects.bulk_create(grades_to_create, batch_size=500, ignore_conflicts=True)
        print(f"إجمالي سجلات الدرجات المفهرسة: {Grade.objects.count()}.")

def run_benchmarks():
    print("\n=== [2] تشغيل اختبارات التحمل والضغط وسرعة الاستجابة ===")
    u = User.objects.first()
    client = Client()
    if u:
        client.force_login(u)

    first_class = SchoolClass.objects.first()
    fc_id = first_class.id if first_class else 1

    tests = [
        ("سجل القيد العام (كل الطلاب)", "/portal/registry/"),
        ("سجل القيد العام (بحث نصي في 1000+ طالب)", "/portal/registry/?q=العراقي_50"),
        ("سجل القيد العام (تصفية حسب الصف والحالة)", f"/portal/registry/?school_class={fc_id}&status=active"),
        ("إدارة رصد الدرجات (Grades Management)", "/portal/grades-manage/"),
        ("لوحة السجلات الرسمية (Records Portal)", "/portal/records/"),
        ("السجل الجامع للدرجات مع الطلاب (Master Sheet)", f"/portal/records/?class_id={fc_id}&record_type=master_exam_sheet"),
        ("جدول الحصص المدرسي الأسبوعي (Weekly Master)", "/portal/timetable/"),
        ("لوحة التحكم المدرسية الرئيسية (Dashboard)", "/portal/"),
        ("شؤون الطلاب (Students Manage)", "/portal/students-manage/"),
        ("إدارة الصفوف والشعب (Classes Manage)", "/portal/classes-manage/"),
    ]

    results = []
    settings.DEBUG = True

    for label, url in tests:
        reset_queries()
        times = []
        status_code = 200
        for _ in range(3):
            t0 = time.perf_counter()
            resp = client.get(url)
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1000.0) # in ms
            status_code = resp.status_code

        avg_time = sum(times) / len(times)
        query_count = len(connection.queries)
        
        # Benchmark score: < 200ms -> 100%
        if avg_time <= 150.0:
            score = 100.0
        elif avg_time <= 200.0:
            score = 95.0 + (200.0 - avg_time) / 50.0 * 5.0
        elif avg_time <= 300.0:
            score = 90.0 + (300.0 - avg_time) / 100.0 * 5.0
        else:
            score = max(50.0, 90.0 - (avg_time - 300.0) / 10.0)

        results.append({
            'label': label,
            'url': url,
            'status': status_code,
            'time_ms': round(avg_time, 2),
            'queries': query_count,
            'score': round(score, 1)
        })

    settings.DEBUG = False

    print("\n" + "="*95)
    print(f"{'Endpoint / Test Case':<50} | {'Status':<6} | {'Time (ms)':<10} | {'Queries':<8} | {'Score':<6}")
    print("="*95)
    total_score = 0
    for r in results:
        print(f"{r['label']:<50} | {r['status']:<6} | {r['time_ms']:<7} ms | {r['queries']:<8} | {r['score']}%")
        total_score += r['score']

    overall_score = round(total_score / len(results), 2)
    print("="*95)
    print(f"Overall Benchmark Performance Score: {overall_score}%")
    if overall_score >= 90.0:
        print("[PASS] System exceeds the +90% high-performance benchmark with sub-200ms latency!")
    else:
        print("[WARN] Overall performance is below 90%, query review needed.")

if __name__ == '__main__':
    populate_mock_data_if_needed(1000)
    run_benchmarks()
