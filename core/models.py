import math
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP


def round_integer(val):
    """دالة مساعدة لتقريب أي قيمة عشرية لأقرب عدد صحيح جبرياً"""
    if val is None:
        return None
    try:
        d = Decimal(str(val))
        return int(d.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except Exception:
        return int(round(float(val)))


class SchoolSettings(models.Model):
    """
    نموذج هوية المدرسة، التخصيص، وإدارة التراخيص والاشتراكات التجارية
    """
    GENDER_CHOICES = (
        ('boys', 'بنين (ذكور)'),
        ('girls', 'بنات (إناث)'),
        ('mixed', 'مختلط'),
    )
    LEVEL_CHOICES = (
        ('primary', 'ابتدائية (الصفوف 1 - 6)'),
        ('intermediate', 'متوسطة (الأول - الثالث متوسط)'),
        ('preparatory', 'إعدادية (الرابع - السادس إعدادي)'),
        ('secondary', 'ثانوية (متوسطة + إعدادية)'),
        ('all_stages', 'شاملة / ثانوية متكاملة (ابتدائية + متوسطة + إعدادية)'),
    )

    school_name = models.CharField(max_length=255, default='اسم المؤسسة التعليمية', verbose_name='اسم المدرسة')
    ministry_school_code = models.CharField(max_length=50, default='', blank=False, verbose_name='الرمز الإحصائي الوزاري للمدرسة (كود التربية)')
    director_name = models.CharField(max_length=255, default='', blank=True, verbose_name='اسم مدير المدرسة')
    directorate = models.CharField(max_length=255, default='المديرية العامة للتربية', verbose_name='المديرية العامة للتربية')
    sub_directorate = models.CharField(max_length=255, default='قسم التربية', verbose_name='القسم / الممثلية')
    school_gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='boys', verbose_name='جنس المدرسة')
    school_level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='secondary', verbose_name='المرحلة الدراسية')
    logo = models.ImageField(upload_to='school_logos/', null=True, blank=True, verbose_name='لوغو المدرسة')

    # تخصيص عدد حصص اليوم الدراسي (افتراضياً 6 حصص كما هو معتمد في العراق)
    daily_periods_count = models.PositiveIntegerField(default=6, verbose_name='عدد الحصص اليومية المعتمدة')

    # حماية الاشتراكات والترخيص التجاري
    installation_date = models.DateField(default=timezone.now, verbose_name='تاريخ تثبيت المنظومة')
    is_subscription_active = models.BooleanField(default=True, verbose_name='حالة الاشتراك (مفعل/معطل)')
    subscription_end_date = models.DateField(null=True, blank=True, verbose_name='تاريخ نهاية الاشتراك')
    license_key = models.CharField(max_length=100, blank=True, null=True, verbose_name='مفتاح الترخيص البرمجي')
    license_hash = models.CharField(max_length=64, blank=True, null=True, verbose_name='توقيع التشفير لحماية الترخيص')

    # حالة معالج الإعداد الأول
    is_first_run_completed = models.BooleanField(default=False, verbose_name='اكتمل معالج الإعداد الأول')

    class Meta:
        verbose_name = 'إعدادات وهوية المدرسة والترخيص'
        verbose_name_plural = 'إعدادات وهوية المدرسة والترخيص'

    def __str__(self):
        return self.school_name

    @property
    def is_official_license(self):
        """فحص ما إذا كان النظام مفعلاً بكود ترخيص رسمي مدفوع ومختوم بالتشفير"""
        if not self.license_key or not self.license_hash or not self.subscription_end_date:
            return False
        from .licensing import compute_license_seal
        expected_seal = compute_license_seal(str(self.subscription_end_date), self.license_key)
        return self.license_hash == expected_seal

    @property
    def is_trial(self):
        """هل النظام حالياً في الفترة التجريبية (غير مفعل برمز رسمي مدفوع)"""
        return not self.is_official_license

    @property
    def is_trial_or_license_valid(self):
        """التحقق التام من سريان الصلاحية سواء كانت تجريبية (خلال 14 يوماً) أو ترخيصاً رسمياً"""
        if not self.is_subscription_active or not self.subscription_end_date:
            return False
        today = timezone.now().date()
        if today > self.subscription_end_date:
            return False
        if self.license_hash:
            from .licensing import compute_license_seal
            expected_seal = compute_license_seal(str(self.subscription_end_date), self.license_key or '')
            if self.license_hash != expected_seal:
                return False
        return True

    @property
    def days_remaining(self):
        """حساب الأيام المتبقية بدقة مع منع أي أخطاء نوعية في التواريخ"""
        if not self.subscription_end_date:
            return 0
        today = timezone.now().date()
        delta = (self.subscription_end_date - today).days
        return max(0, delta)

    @property
    def subscription_status_label(self):
        """نص حالة الاشتراك للعرض في الواجهة الرئيسية"""
        if not self.is_trial_or_license_valid:
            return "انتهت الفترة التجريبية (14 يوماً)"
        days = self.days_remaining
        if self.is_trial:
            return f"نسخة تجريبية (متبقي {days} يوم)"
        else:
            return f"اشتراك مفعّل رسمياً (متبقي {days} يوم)"

    def is_active(self):
        return self.is_trial_or_license_valid

    @classmethod
    def get_settings(cls):
        """جلب الإعدادات أو إنشائها مع منح فترة تجريبية مجانية لمدة 14 يوماً فقط عند أول تشغيل"""
        obj, created = cls.objects.get_or_create(id=1)
        today = timezone.now().date()
        save_needed = False
        if not obj.installation_date:
            obj.installation_date = today
            save_needed = True
        if created or not obj.subscription_end_date:
            obj.installation_date = today
            obj.is_subscription_active = True
            obj.subscription_end_date = today + timezone.timedelta(days=14)
            obj.school_name = obj.school_name or 'اسم المؤسسة التعليمية'
            obj.director_name = obj.director_name or ''
            obj.directorate = obj.directorate or 'المديرية العامة للتربية'
            obj.sub_directorate = obj.sub_directorate or 'قسم التربية'
            save_needed = True
        if save_needed:
            obj.save()
        return obj


class User(AbstractUser):
    is_student = models.BooleanField(default=False, verbose_name='طالب')
    is_teacher = models.BooleanField(default=False, verbose_name='معلم / مدرس')
    is_parent = models.BooleanField(default=False, verbose_name='ولي أمر')

    class Meta:
        verbose_name = 'مستخدم'
        verbose_name_plural = 'المستخدمون'

    def __str__(self):
        full_name = self.get_full_name()
        return full_name if full_name else self.username


class Parent(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='حساب المستخدم')
    phone = models.CharField(max_length=30, blank=True, null=True, verbose_name='رقم الهاتف')
    address = models.TextField(blank=True, null=True, verbose_name='عنوان السكن')

    class Meta:
        verbose_name = 'ولي أمر'
        verbose_name_plural = 'أولياء الأمور'

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Subject(models.Model):
    name = models.CharField(max_length=100, verbose_name='اسم المادة')
    code = models.CharField(max_length=20, blank=True, null=True, verbose_name='رمز المادة')

    class Meta:
        verbose_name = 'مادة دراسية'
        verbose_name_plural = 'المواد الدراسية'

    def __str__(self):
        return self.name


class Teacher(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='حساب المعلم')
    job_title = models.CharField(max_length=100, default='مدرس', verbose_name='العنوان الوظيفي')
    statistical_code = models.CharField(max_length=50, blank=True, null=True, verbose_name='الرقم الإحصائي / الوظيفي')
    hire_date = models.DateField(blank=True, null=True, verbose_name='تاريخ المباشرة')
    subjects = models.ManyToManyField(Subject, blank=True, verbose_name='المواد التي يدرسها')
    school_classes = models.ManyToManyField('SchoolClass', blank=True, verbose_name='الصفوف والمراحل التي يدرسها')

    class Meta:
        verbose_name = 'معلم / مدرس'
        verbose_name_plural = 'الكادر التدريسي'

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class AcademicYear(models.Model):
    name = models.CharField(max_length=20, unique=True, verbose_name="السنة الدراسية")
    start_date = models.DateField(verbose_name="تاريخ البدء")
    end_date = models.DateField(verbose_name="تاريخ الانتهاء")
    is_current = models.BooleanField(default=False, verbose_name="السنة الحالية")
    is_archived = models.BooleanField(default=False, verbose_name="مؤرشفة ومغلقة")

    class Meta:
        verbose_name = "سنة دراسية"
        verbose_name_plural = "السنوات الدراسية"
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicYear.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    @classmethod
    def generate_next_50_years(cls, start_year=2026):
        """توليد سلسلة السنوات الدراسية ابتداءً من العام الدراسي الفعال 2026-2027"""
        created_count = 0
        for y in range(start_year, start_year + 50):
            year_name = f"{y}-{y+1}"
            obj, created = cls.objects.get_or_create(
                name=year_name,
                defaults={
                    'start_date': f"{y}-09-15",
                    'end_date': f"{y+1}-06-30",
                    'is_current': (y == start_year),
                    'is_archived': False
                }
            )
            if created:
                created_count += 1
        return created_count


class SchoolClass(models.Model):
    name = models.CharField(max_length=100, verbose_name='الصف الدراسي')
    level_order = models.PositiveIntegerField(default=1, db_index=True, verbose_name="ترتيب المرحلة")
    next_class = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='previous_classes',
        verbose_name="الصف اللاحق للترحيل"
    )
    is_final_stage = models.BooleanField(default=False, verbose_name="مرحلة منتهية (تخرج)")

    class Meta:
        verbose_name = 'صف دراسي'
        verbose_name_plural = 'الصفوف الدراسية'
        ordering = ['level_order', 'name']
        indexes = [
            models.Index(fields=['level_order', 'name']),
        ]

    def __str__(self):
        return f"{self.name}"


class Section(models.Model):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='sections', verbose_name='الصف')
    name = models.CharField(max_length=50, verbose_name='اسم الشعبة')
    capacity = models.PositiveIntegerField(default=40, verbose_name='الطاقة الاستيعابية')

    class Meta:
        verbose_name = 'شعبة دراسية'
        verbose_name_plural = 'الشعب الدراسية'

    def __str__(self):
        return f"{self.school_class.name} - الشعبة {self.name}"


class Student(models.Model):
    STATUS_CHOICES = (
        ('active', 'مستمر بالدوام'),
        ('graduated', 'خريج'),
        ('transferred', 'منقول'),
        ('dismissed', 'مفصول / تارك'),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='حساب الطالب')
    registration_number = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name='رقم القيد العام')
    admission_date = models.DateField(default=timezone.now, verbose_name='تاريخ المباشرة')
    student_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True, verbose_name='حالة الطالب')
    national_id = models.CharField(max_length=50, blank=True, null=True, db_index=True, verbose_name='الرقم الوطني / الهوية')
    dob = models.DateField(blank=True, null=True, verbose_name='تاريخ التولد')
    current_class = models.ForeignKey(SchoolClass, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الصف الحالي')
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الشعبة')
    parent = models.ForeignKey(Parent, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='ولي الأمر')

    is_deleted = models.BooleanField(default=False, db_index=True, verbose_name='محذوف')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الحذف')

    class Meta:
        verbose_name = 'طالب'
        verbose_name_plural = 'الطلاب'
        indexes = [
            models.Index(fields=['current_class', 'is_deleted']),
            models.Index(fields=['current_class', 'section', 'is_deleted']),
            models.Index(fields=['student_status', 'is_deleted']),
        ]

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def save(self, *args, **kwargs):
        if self.registration_number:
            import re
            cleaned = re.sub(r'[a-zA-Z_-]+', '', str(self.registration_number)).strip()
            self.registration_number = cleaned if cleaned else None
        super().save(*args, **kwargs)

    @property
    def clean_reg_number(self):
        """إرجاع رقم القيد كنص نقي وأرقام مجردة دون أي بادئات أجنبية أو حروف لاتينية"""
        if not self.registration_number:
            return ""
        import re
        return re.sub(r'[a-zA-Z_-]+', '', str(self.registration_number)).strip()

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def name(self):
        return self.full_name

    def __str__(self):
        reg = f"[{self.clean_reg_number or self.registration_number}] " if self.registration_number else ""
        return f"{reg}{self.full_name}"


class StudentAcademicHistory(models.Model):
    RESULT_CHOICES = (
        ('passed', 'ناجح'),
        ('failed', 'راسب'),
        ('graduated', 'تخرج'),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='academic_history', verbose_name='الطالب')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, verbose_name='السنة الدراسية')
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, verbose_name='الصف الدراسي')
    section = models.CharField(max_length=50, blank=True, null=True, verbose_name='الشعبة')
    result_status = models.CharField(max_length=20, choices=RESULT_CHOICES, default='passed', verbose_name='النتيجة النهائية')
    general_average = models.DecimalField(max_digits=5, decimal_places=0, default=Decimal('0'), verbose_name='المعدل العام (صحيح)')
    recorded_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التسجيل')

    class Meta:
        verbose_name = 'أرشيف أكاديمي لطالب'
        verbose_name_plural = 'أرشيف المسيرة الدراسية للطلاب'
        unique_together = ('student', 'academic_year')

    def __str__(self):
        return f"{self.student} - {self.academic_year.name} ({self.get_result_status_display()})"


class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name='الطالب')
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, verbose_name='الصف')
    academic_year = models.CharField(max_length=20, default='2026-2027', verbose_name='العام الدراسي')
    status = models.CharField(max_length=20, default='active', verbose_name='حالة القيد')

    class Meta:
        verbose_name = 'قيد وتسجيل'
        verbose_name_plural = 'سجل القيود'

    def __str__(self):
        return f"{self.student} - {self.school_class} ({self.academic_year})"


class Attendance(models.Model):
    STATUS_CHOICES = (
        ('present', 'حاضر'),
        ('absent', 'غائب'),
        ('late', 'متأخر'),
        ('excused', 'مجاز'),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name='الطالب')
    date = models.DateField(db_index=True, verbose_name='التاريخ')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, db_index=True, verbose_name='حالة الحضور')
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المسجل')

    class Meta:
        verbose_name = 'حضور وغياب'
        verbose_name_plural = 'سجل الحضور والغياب'
        unique_together = ('student', 'date')
        indexes = [
            models.Index(fields=['student', 'date']),
            models.Index(fields=['date', 'status']),
        ]

    def __str__(self):
        return f"{self.student} - {self.date} ({self.get_status_display()})"


class Grade(models.Model):
    STATUS_CHOICES = (
        ('pending', 'قيد الإنجاز'),
        ('passed', 'ناجح'),
        ('passed_by_decision', 'ناجح بالقرار'),
        ('supplementary', 'مكمل'),
        ('failed', 'راسب'),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grades', verbose_name='الطالب')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='grades', verbose_name='المادة')
    academic_year = models.CharField(max_length=20, default='2026-2027', db_index=True, verbose_name='العام الدراسي')

    first_term_month1 = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True, verbose_name='الفصل الأول - شهر 1')
    first_term_month2 = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True, verbose_name='الفصل الأول - شهر 2')
    first_term_effort = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True, verbose_name='سعي الفصل الأول')

    midyear_exam = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True, verbose_name='امتحان نصف السنة')

    second_term_month1 = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True, verbose_name='الفصل الثاني - شهر 1')
    second_term_month2 = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True, verbose_name='الفصل الثاني - شهر 2')
    second_term_effort = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True, verbose_name='سعي الفصل الثاني')

    annual_effort = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True, verbose_name='السعي السنوي')

    final_exam_round1 = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True, verbose_name='الامتحان النهائي - الدور الأول')
    final_exam_round2 = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True, verbose_name='الامتحان النهائي - الدور الثاني')

    final_grade = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True, verbose_name='الدرجة النهائية قبل القرار')
    decision_marks = models.DecimalField(max_digits=4, decimal_places=0, default=0, verbose_name='درجات القرار الممنوحة')
    final_grade_after_decision = models.DecimalField(max_digits=5, decimal_places=0, null=True, blank=True, verbose_name='الدرجة النهائية بعد القرار')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True, verbose_name='النتيجة النهائية')

    class Meta:
        verbose_name = 'سجل درجات'
        verbose_name_plural = 'سجل الدرجات (النظام العراقي)'
        unique_together = ('student', 'subject', 'academic_year')
        indexes = [
            models.Index(fields=['student', 'academic_year']),
            models.Index(fields=['academic_year', 'subject']),
            models.Index(fields=['academic_year', 'status']),
        ]

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.academic_year})"

    def calculate_first_term_effort(self):
        if self.first_term_month1 is not None and self.first_term_month2 is not None:
            return Decimal(str(round_integer((self.first_term_month1 + self.first_term_month2) / Decimal('2.0'))))
        elif self.first_term_month1 is not None:
            return Decimal(str(round_integer(self.first_term_month1)))
        return self.first_term_effort

    def calculate_second_term_effort(self):
        if self.second_term_month1 is not None and self.second_term_month2 is not None:
            return Decimal(str(round_integer((self.second_term_month1 + self.second_term_month2) / Decimal('2.0'))))
        elif self.second_term_month1 is not None:
            return Decimal(str(round_integer(self.second_term_month1)))
        return self.second_term_effort

    def calculate_annual_effort(self):
        t1 = self.first_term_effort
        mid = self.midyear_exam
        t2 = self.second_term_effort

        components = [val for val in [t1, mid, t2] if val is not None]
        if len(components) == 3:
            return Decimal(str(round_integer(sum(components) / Decimal('3.0'))))
        elif len(components) > 0:
            return Decimal(str(round_integer(sum(components) / Decimal(str(len(components))))))
        return None

    def calculate_final_grade(self):
        exam_score = self.final_exam_round2 if self.final_exam_round2 is not None else self.final_exam_round1
        if exam_score is not None:
            if self.annual_effort is not None:
                return Decimal(str(round_integer((self.annual_effort + exam_score) / Decimal('2.0'))))
            return Decimal(str(round_integer(exam_score)))
        return None

    def apply_decision_marks(self, max_allowed=5):
        base_grade = self.final_grade
        if base_grade is not None and Decimal('45') <= base_grade < Decimal('50'):
            needed = Decimal('50') - base_grade
            if needed <= Decimal(str(max_allowed)):
                self.decision_marks = needed
                self.final_grade_after_decision = Decimal('50')
                self.status = 'passed_by_decision'
                return needed
        return Decimal('0')

    def update_all_calculations(self, auto_apply_decision=False, max_decision=5):
        self.first_term_effort = self.calculate_first_term_effort()
        self.second_term_effort = self.calculate_second_term_effort()
        self.annual_effort = self.calculate_annual_effort()
        calculated_final = self.calculate_final_grade()

        if calculated_final is not None:
            self.final_grade = calculated_final
            if auto_apply_decision:
                self.apply_decision_marks(max_allowed=max_decision)
            else:
                if self.decision_marks > 0:
                    self.final_grade_after_decision = min(Decimal('100'), self.final_grade + self.decision_marks)
                else:
                    self.final_grade_after_decision = self.final_grade

            effective_grade = self.final_grade_after_decision if self.final_grade_after_decision is not None else self.final_grade
            if effective_grade is not None:
                if effective_grade >= Decimal('50'):
                    self.status = 'passed_by_decision' if self.decision_marks > 0 else 'passed'
                elif self.final_exam_round1 is not None and self.final_exam_round2 is None:
                    self.status = 'supplementary'
                elif self.final_exam_round2 is not None and effective_grade < Decimal('50'):
                    self.status = 'failed'
                else:
                    self.status = 'pending'

    def save(self, *args, **kwargs):
        self.update_all_calculations()
        super().save(*args, **kwargs)


class TimetableSlot(models.Model):
    DAYS_CHOICES = (
        (0, 'الأحد'),
        (1, 'الإثنين'),
        (2, 'الثلاثاء'),
        (3, 'الأربعاء'),
        (4, 'الخميس'),
    )

    PERIOD_CHOICES = (
        (1, 'الحصة الأولى'),
        (2, 'الحصة الثانية'),
        (3, 'الحصة الثالثة'),
        (4, 'الحصة الرابعة'),
        (5, 'الحصة الخامسة'),
        (6, 'الحصة السادسة'),
        (7, 'الحصة السابعة'),
        (8, 'الحصة الثامنة'),
    )

    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='timetable_slots', verbose_name='الصف الدراسي')
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name='timetable_slots', verbose_name='الشعبة')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='timetable_slots', verbose_name='المادة')
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='timetable_slots', verbose_name='المدرس')
    day = models.IntegerField(choices=DAYS_CHOICES, db_index=True, verbose_name='اليوم')
    period = models.IntegerField(choices=PERIOD_CHOICES, default=1, db_index=True, verbose_name='رقم الحصة')
    start_time = models.TimeField(null=True, blank=True, verbose_name='وقت البدء')
    end_time = models.TimeField(null=True, blank=True, verbose_name='وقت الانتهاء')
    room = models.CharField(max_length=50, blank=True, default='', verbose_name='القاعة / المختبر')
    notes = models.TextField(blank=True, default='', verbose_name='ملاحظات')
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='حصة فعالة')

    class Meta:
        verbose_name = 'حصة دراسية'
        verbose_name_plural = 'جدول الحصص الأسبوعي'
        ordering = ['day', 'period']
        indexes = [
            models.Index(fields=['school_class', 'day', 'period']),
            models.Index(fields=['teacher', 'day', 'period']),
            models.Index(fields=['day', 'period', 'is_active']),
        ]

    def __str__(self):
        return f"{self.get_day_display()} - {self.get_period_display()} | {self.school_class.name} ({self.subject.name})"

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("وقت بدء الحصة يجب أن يكون قبل وقت الانتهاء.")

        if self.teacher and self.day is not None and self.period is not None:
            t_conflicts = TimetableSlot.objects.filter(
                teacher=self.teacher,
                day=self.day,
                period=self.period,
                is_active=True
            ).exclude(pk=self.pk)
            if t_conflicts.exists():
                c = t_conflicts.first()
                raise ValidationError(
                    f"تعارض في جدول المعلم ({self.teacher}): لديه حصة بالفعل في {c.school_class.name} "
                    f"({c.get_period_display()})."
                )

        if self.school_class and self.day is not None and self.period is not None:
            c_conflicts = TimetableSlot.objects.filter(
                school_class=self.school_class,
                section=self.section,
                day=self.day,
                period=self.period,
                is_active=True
            ).exclude(pk=self.pk)
            if c_conflicts.exists():
                c = c_conflicts.first()
                raise ValidationError(
                    f"تعارض في جدول الصف ({self.school_class.name}): توجد مادة ({c.subject.name}) مسجلة في هذا التوقيت."
                )

        if self.room and self.room.strip() and self.day is not None and self.period is not None:
            r_conflicts = TimetableSlot.objects.filter(
                room=self.room.strip(),
                day=self.day,
                period=self.period,
                is_active=True
            ).exclude(pk=self.pk)
            if r_conflicts.exists():
                c = r_conflicts.first()
                raise ValidationError(
                    f"القاعة ({self.room}) مشغولة في {c.get_period_display()} بواسطة صف ({c.school_class.name})."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class TeacherQuota(models.Model):
    teacher = models.OneToOneField(Teacher, on_delete=models.CASCADE, related_name='quota', verbose_name='المعلم')
    required_periods = models.PositiveIntegerField(default=24, verbose_name='الحصص المطلوبة أسبوعياً')

    class Meta:
        verbose_name = 'نصاب معلم'
        verbose_name_plural = 'نصاب المعلمين الأسبوعي'

    def scheduled_count(self):
        return self.teacher.timetable_slots.filter(is_active=True).count()

    def remaining_count(self):
        return max(0, self.required_periods - self.scheduled_count())

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} (المطلوب: {self.required_periods})"


class TimetableSubstitution(models.Model):
    date = models.DateField(default=timezone.now, verbose_name='تاريخ الاستبدال')
    slot = models.ForeignKey(TimetableSlot, on_delete=models.CASCADE, related_name='substitutions', verbose_name='الحصة المستبدلة')
    original_teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='absent_substitutions', verbose_name='المعلم الغائب')
    substitute_teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='covered_substitutions', verbose_name='المعلم البديل (الاحتياط)')
    reason = models.CharField(max_length=200, blank=True, default='إجازة رسمية / طارئة', verbose_name='سبب الاستبدال')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'استبدال حصة / احتياط'
        verbose_name_plural = 'سجل الاستبدالات والاحتياط اليومي'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} | {self.original_teacher} ⬅ {self.substitute_teacher}"


class TimetableVersion(models.Model):
    name = models.CharField(max_length=100, verbose_name='اسم الإصدار')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='العام الدراسي')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الاعتماد')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المسؤول')
    notes = models.TextField(blank=True, default='', verbose_name='ملاحظات الإصدار')
    snapshot_data = models.JSONField(default=dict, verbose_name='بيانات النسخة')

    class Meta:
        verbose_name = 'إصدار جدول معتمد'
        verbose_name_plural = 'أرشيف إصدارات الجداول المعتمدة'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.created_at.strftime('%Y/%m/%d')})"


class ExamHall(models.Model):
    DESK_TYPES = (
        ('single', 'مقعد فردي (طالب واحد)'),
        ('double', 'مقعد ثنائي (طالبان)'),
    )
    name = models.CharField(max_length=100, verbose_name="اسم / رقم القاعة")
    location = models.CharField(max_length=100, blank=True, null=True, verbose_name="الموقع / الجناح")
    lines_count = models.PositiveIntegerField(default=3, verbose_name="عدد الخطوط في القاعة")
    desks_per_line = models.PositiveIntegerField(default=6, verbose_name="عدد الرحلات في كل خط")
    desk_type = models.CharField(max_length=20, choices=DESK_TYPES, default='single', verbose_name="طبيعة المقعد / الرحلة")
    capacity = models.PositiveIntegerField(default=18, verbose_name="السعة الكلية للمقاعد")
    rows_count = models.PositiveIntegerField(default=6, verbose_name="عدد الصفوف")
    cols_count = models.PositiveIntegerField(default=3, verbose_name="عدد الأعمدة")

    class Meta:
        verbose_name = "قاعة امتحانية"
        verbose_name_plural = "القاعات الامتحانية"

    def save(self, *args, **kwargs):
        multiplier = 2 if self.desk_type == 'double' else 1
        self.capacity = (self.lines_count or 1) * (self.desks_per_line or 1) * multiplier
        self.rows_count = self.desks_per_line or 1
        self.cols_count = self.lines_count or 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (سعة: {self.capacity})"


class ExamSession(models.Model):
    SESSION_TYPES = (
        ('mid_year', 'امتحانات نصف السنة'),
        ('final_round1', 'الامتحانات النهائية - الدور الأول'),
        ('final_round2', 'الامتحانات النهائية - الدور الثاني'),
    )
    title = models.CharField(max_length=150, verbose_name="عنوان الدورة الامتحانية")
    session_type = models.CharField(max_length=30, choices=SESSION_TYPES, verbose_name="نوع الامتحان")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, verbose_name="السنة الدراسية")
    start_date = models.DateField(verbose_name="تاريخ البدء")
    end_date = models.DateField(verbose_name="تاريخ الانتهاء")
    halls = models.ManyToManyField(ExamHall, blank=True, verbose_name="القاعات المعتمدة")

    class Meta:
        verbose_name = "دورة امتحانية"
        verbose_name_plural = "الدورات الامتحانية"

    def __str__(self):
        return f"{self.title} - {self.academic_year.name}"


class ExamSeatAssignment(models.Model):
    exam_session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='seats', verbose_name="الدورة الامتحانية")
    exam_hall = models.ForeignKey(ExamHall, on_delete=models.CASCADE, related_name='seats', verbose_name="القاعة")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exam_seats', verbose_name="الطالب")
    seat_number = models.PositiveIntegerField(verbose_name="رقم الجلوس / المقعد")
    desk_row = models.PositiveIntegerField(verbose_name="الصف الأفقي")
    desk_col = models.PositiveIntegerField(verbose_name="العمود")

    class Meta:
        verbose_name = "توزيع مقعد امتحاني"
        verbose_name_plural = "توزيع مقاعد الامتحانات"
        unique_together = [('exam_session', 'student'), ('exam_session', 'exam_hall', 'seat_number')]
        ordering = ['exam_hall', 'seat_number']

    def __str__(self):
        return f"{self.exam_hall.name} - مقعد {self.seat_number} ({self.student})"


class OfficialLetterTemplate(models.Model):
    TEMPLATE_TYPES = (
        ('service_confirmation', 'تأييد استمرار بالخدمة'),
        ('grades_confirmation', 'تأييد درجات طالب'),
        ('dept_reply', 'إجابة كتاب رسمي'),
        ('general', 'كتاب رسمي عام'),
    )
    name = models.CharField(max_length=150, verbose_name="عنوان القالب")
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES, verbose_name="نوع القالب")
    content = models.TextField(
        verbose_name="نص القالب",
        help_text="المتغيرات: {{student_name}}, {{class_name}}, {{reg_number}}, {{teacher_name}}, {{date}}, {{school_name}}"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    class Meta:
        verbose_name = "قالب كتاب رسمي"
        verbose_name_plural = "قوالب الكتب والتأييدات الرسمية"

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class OfficialDocument(models.Model):
    DOC_TYPE_CHOICES = (
        ('issued', 'كتاب صادر'),
        ('received', 'كتاب وارد'),
        ('student_cert', 'وثائق وتأييدات الطلبة'),
        ('circular', 'أمر إداري / تعميم'),
        ('dept_reply', 'إجابات ومخاطبات القسم'),
        ('directorate', 'المديرية العامة للتربية'),
        ('ministry', 'وزارة التربية'),
        ('other', 'أخرى'),
    )
    STATUS_CHOICES = (
        ('pending', 'قيد المتابعة / الإجراء'),
        ('completed', 'تم الإنجاز والرد'),
        ('archived', 'مؤرشف للحفظ'),
    )

    doc_number = models.CharField(max_length=100, db_index=True, verbose_name='رقم الكتاب الرسمي')
    doc_date = models.DateField(db_index=True, verbose_name='تاريخ الكتاب')
    doc_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES, default='received', db_index=True, verbose_name='نوع الكتاب')
    sender_receiver = models.CharField(max_length=200, verbose_name='الجهة الصادرة / المستلمة')
    subject = models.CharField(max_length=255, verbose_name='الموضوع / خلاصة الكتاب')
    file = models.FileField(upload_to='official_documents/%Y/%m/', null=True, blank=True, verbose_name='الملف المرفق')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='archived', verbose_name='حالة المتابعة')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات / نص الإجراء')

    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_documents', verbose_name='الطالب المعني')
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_documents', verbose_name='المعلم المعني')

    incoming_doc_number = models.CharField(max_length=100, blank=True, null=True, verbose_name='رقم الكتاب الوارد المربوط')
    incoming_doc_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الوارد المربوط')
    outgoing_reply_number = models.CharField(max_length=100, blank=True, null=True, verbose_name='رقم كتاب الإجابة الصادر')
    body_content = models.TextField(blank=True, null=True, verbose_name='نص الكتاب / الرد الكامل')

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المسجل')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التسجيل')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')

    class Meta:
        verbose_name = 'كتاب رسمي / أرشيف'
        verbose_name_plural = 'سجل الكتب والمخاطبات الرسمية'
        ordering = ['-doc_date', '-created_at']
        indexes = [
            models.Index(fields=['doc_type', 'doc_date']),
            models.Index(fields=['doc_number', 'doc_date']),
        ]

    def __str__(self):
        return f"[{self.get_doc_type_display()}] رقم {self.doc_number} - {self.subject}"


class Invoice(models.Model):
    STATUS = (
        ('draft', 'مسودة'),
        ('due', 'مستحق الدفع'),
        ('paid', 'مدفوع'),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name='الطالب')
    amount = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='المبلغ (صحيح)')
    due_date = models.DateField(verbose_name='تاريخ الاستحقاق')
    status = models.CharField(max_length=10, choices=STATUS, default='due', verbose_name='الحالة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        verbose_name = 'فاتورة رسوم'
        verbose_name_plural = 'سجل الفواتير والرسوم'

    def __str__(self):
        return f"فاتورة #{self.id} - {self.student} ({self.amount})"