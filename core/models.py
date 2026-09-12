import math
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from simple_history.models import HistoricalRecords


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
    license_status = models.CharField(max_length=30, default='ACTIVE', verbose_name='حالة الترخيص المؤسسي')
    last_known_valid_time = models.DateTimeField(null=True, blank=True, verbose_name='آخر وقت نظام صالح وموثق')
    time_tamper_detected = models.BooleanField(default=False, verbose_name='هل تم اكتشاف تلاعب زمني')
    activation_date = models.DateField(null=True, blank=True, verbose_name='تاريخ التفعيل الفعلي')
    subscription_plan = models.CharField(max_length=50, default='MONTHLY_30_DAYS', verbose_name='باقة الاشتراك')
    license_code_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='معرف كود الترخيص الفريد')

    # حالة معالج الإعداد الأول
    is_first_run_completed = models.BooleanField(default=False, verbose_name='اكتمل معالج الإعداد الأول')

    # الاشتراك المالي للمنظومة المركزية
    subscription_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='قيمة الاشتراك المالي')

    class Meta:
        verbose_name = 'إعدادات وهوية المدرسة والترخيص'
        verbose_name_plural = 'إعدادات وهوية المدرسة والترخيص'

    def __str__(self):
        return self.school_name

    @property
    def total_paid_amount(self):
        val = self.subscription_payments.aggregate(total=models.Sum('amount'))['total']
        return val if val is not None else Decimal('0.00')

    @property
    def remaining_subscription_balance(self):
        fee = self.subscription_fee or Decimal('0.00')
        paid = self.total_paid_amount
        rem = fee - paid
        return max(Decimal('0.00'), rem)

    @property
    def enrolled_students_count(self):
        return self.students.filter(is_deleted=False).count()

    def get_year_subscription(self, academic_year):
        """الحصول على أو إنشاء سجل اشتراك المدرسة للسنة الدراسية المحددة"""
        if not academic_year:
            return None
        sub, _ = self.yearly_subscriptions.get_or_create(
            academic_year=academic_year,
            defaults={
                'fee_amount': self.subscription_fee or Decimal('0.00'),
                'is_active': self.is_subscription_active
            }
        )
        return sub

    def is_year_subscription_active(self, academic_year=None):
        """التحقق من سريان اشتراك المدرسة لسنة دراسية محددة"""
        if not academic_year:
            from core.models import AcademicYear
            academic_year = AcademicYear.objects.filter(is_current=True).first()
        if not academic_year:
            return self.is_active()
        sub = self.yearly_subscriptions.filter(academic_year=academic_year).first()
        if not sub:
            return self.is_active()
        return sub.is_active

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
        """التحقق التام من سريان الصلاحية سواء كانت تجريبية أو ترخيصاً رسمياً مع كشف التلاعب بالساعة"""
        from core.utils.licensing import check_clock_integrity, compute_license_seal
        clock_ok, _ = check_clock_integrity()
        if not clock_ok:
            return False

        if not self.is_subscription_active or not self.subscription_end_date:
            return False
        today = timezone.now().date()
        if today > self.subscription_end_date:
            return False
        if self.license_hash:
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

    def get_allowed_stage_names(self):
        """إرجاع المراحل الدراسية والصفوف المسموح بها حسب نوع المدرسة المحدد"""
        if self.school_level == 'primary':
            return ['الأول الابتدائي', 'الثاني الابتدائي', 'الثالث الابتدائي', 'الرابع الابتدائي', 'الخامس الابتدائي', 'السادس الابتدائي']
        elif self.school_level == 'intermediate':
            return ['الأول المتوسط', 'الاول المتوسط', 'الثاني المتوسط', 'الثالث المتوسط']
        elif self.school_level == 'preparatory':
            return ['الرابع العلمي', 'الرابع الأدبي', 'الرابع الادبي', 'الخامس العلمي', 'الخامس الأدبي', 'الخامس الادبي', 'السادس العلمي', 'السادس الأدبي', 'السادس الادبي']
        elif self.school_level == 'secondary':
            return [
                'الأول المتوسط', 'الاول المتوسط', 'الثاني المتوسط', 'الثالث المتوسط',
                'الرابع العلمي', 'الرابع الأدبي', 'الرابع الادبي', 'الخامس العلمي', 'الخامس الأدبي', 'الخامس الادبي', 'السادس العلمي', 'السادس الأدبي', 'السادس الادبي'
            ]
        return None

    def filter_classes(self, queryset):
        """تصفية الصفوف الدراسية لتقتصر حصراً على نوع مرحلة المدرسة"""
        allowed = self.get_allowed_stage_names()
        if allowed is not None:
            return queryset.filter(name__in=allowed)
        return queryset

    def is_gender_allowed(self, gender_value):
        """التحقق الصارم من توافق جنس الطالب مع هوية وجنس المدرسة"""
        if not gender_value:
            return True, ""
        g = str(gender_value).strip().lower()
        is_male = g in ['male', 'ذكر', 'ولد', 'بنين', 'm']
        is_female = g in ['female', 'أنثى', 'انثى', 'بنت', 'بنات', 'f']

        if self.school_gender == 'boys' and is_female:
            return False, "المدرسة مخصصة للبنين فقط، ولا يُسمح بتسجيل أو قبول الطالبات الإناث."
        elif self.school_gender == 'girls' and is_male:
            return False, "المدرسة مخصصة للبنات فقط، ولا يُسمح بتسجيل أو قبول الطلاب الذكور."
        return True, ""

    def get_allowed_record_categories(self):
        """تحديد سجلات وزارة التربية المصرح بتوليدها وعرضها بحسب المرحلة"""
        if self.school_level == 'primary':
            return ['primary_records', 'primary_scores_30_70', 'primary_dossier']
        elif self.school_level == 'intermediate':
            return ['intermediate_annual_effort', 'intermediate_roster']
        elif self.school_level in ['preparatory', 'secondary']:
            return ['secondary_annual_effort', 'branch_records', 'secondary_dossier']
        return ['all']

    def __str__(self):
        return f"{self.school_name} ({self.get_school_level_display()} - {self.get_school_gender_display()})"

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
    ROLE_CHOICES = (
        ('super_admin', 'مدير النظام العام (Super Administrator)'),
        ('school_admin', 'مدير النظام المدرسي (School Administrator)'),
        ('principal', 'مدير المدرسة (Principal)'),
        ('assistant_principal', 'معاون المدير (Assistant Principal)'),
        ('teacher', 'معلم / مدرس (Teacher)'),
        ('grades_officer', 'مسؤول الدرجات والامتحانات (Grades Officer)'),
        ('accountant', 'المحاسب المالي (Accountant)'),
        ('registrar', 'مسؤول التسجيل وشؤون الطلبة (Registrar)'),
        ('viewer', 'مستعرض / قارئ فقط (Viewer)'),
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='school_admin', db_index=True, verbose_name='الدور المؤسسي')
    is_student = models.BooleanField(default=False, verbose_name='طالب')
    is_teacher = models.BooleanField(default=False, verbose_name='معلم / مدرس')
    is_parent = models.BooleanField(default=False, verbose_name='ولي أمر')

    class Meta:
        verbose_name = 'مستخدم'
        verbose_name_plural = 'المستخدمون'

    def __str__(self):
        full_name = self.get_full_name()
        return full_name if full_name else self.username

    @property
    def can_manage_users(self):
        return self.is_superuser or self.role in ('super_admin', 'school_admin', 'principal')

    @property
    def can_edit_grades(self):
        if self.role == 'viewer':
            return False
        return self.is_superuser or self.role in ('super_admin', 'school_admin', 'principal', 'assistant_principal', 'grades_officer', 'teacher')

    @property
    def can_approve_grades(self):
        return self.is_superuser or self.role in ('super_admin', 'school_admin', 'principal')

    @property
    def can_lock_grades(self):
        return self.is_superuser or self.role in ('super_admin', 'school_admin', 'principal')

    @property
    def can_amend_locked_grades(self):
        return self.is_superuser or self.role in ('super_admin', 'principal')

    @property
    def can_manage_backups(self):
        return self.is_superuser or self.role in ('super_admin', 'school_admin', 'principal')

    @property
    def can_manage_license(self):
        return self.is_superuser or self.role in ('super_admin', 'school_admin', 'principal')

    @property
    def can_manage_accounting(self):
        return self.is_superuser or self.role in ('super_admin', 'school_admin', 'accountant', 'principal')

    @property
    def can_manage_registration(self):
        return self.is_superuser or self.role in ('super_admin', 'school_admin', 'registrar', 'principal')

    @property
    def is_readonly_viewer(self):
        return self.role == 'viewer'



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
    grade_level = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name='المرحلة / الصف الدراسي')
    order = models.PositiveIntegerField(default=1, verbose_name='الترتيب')
    weekly_periods = models.PositiveIntegerField(default=2, verbose_name='عدد الحصص الأسبوعية (النصاب الوزاري)')
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'مادة دراسية'
        verbose_name_plural = 'المواد الدراسية'
        ordering = ['order', 'id']

    def __str__(self):
        if self.grade_level:
            return f"{self.name} ({self.grade_level})"
        return self.name

    @classmethod
    def ensure_official_subjects(cls):
        """ضمان تسجيل كافة المواد الرسمية المقررة وزارياً لكافة المراحل الـ 15 في قاعدة البيانات بالترتيب المعتمد"""
        from django.db import transaction
        STAGE_SUBJECTS = {
            # 1. المرحلة الابتدائية (الصفوف 1 - 3: 8 مواد)
            'الأول الابتدائي': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'العلوم', 'التربية الفنية والنشيد', 'التربية الرياضية', 'الأخلاقية'
            ],
            'الثاني الابتدائي': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'العلوم', 'التربية الفنية والنشيد', 'التربية الرياضية', 'الأخلاقية'
            ],
            'الثالث الابتدائي': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'العلوم', 'التربية الفنية والنشيد', 'التربية الرياضية', 'الأخلاقية'
            ],
            # المرحلة الابتدائية (الصفوف 4 - 6: 9 مواد تشمل الاجتماعيات)
            'الرابع الابتدائي': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'العلوم', 'الاجتماعيات', 'التربية الفنية والنشيد', 'التربية الرياضية', 'الأخلاقية'
            ],
            'الخامس الابتدائي': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'العلوم', 'الاجتماعيات', 'التربية الفنية والنشيد', 'التربية الرياضية', 'الأخلاقية'
            ],
            'السادس الابتدائي': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'العلوم', 'الاجتماعيات', 'التربية الفنية والنشيد', 'التربية الرياضية', 'الأخلاقية'
            ],
            # 2. المرحلة المتوسطة (الأول والثاني المتوسط: 12 مادة بدون علوم وبدون أقواس للاجتماعيات)
            'الأول المتوسط': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'الاجتماعيات', 'الكيمياء', 'الفيزياء', 'الأحياء',
                'التربية الأخلاقية', 'الحاسوب', 'التربية الرياضية', 'التربية الفنية'
            ],
            'الثاني المتوسط': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'الاجتماعيات', 'الكيمياء', 'الفيزياء', 'الأحياء',
                'التربية الأخلاقية', 'الحاسوب', 'التربية الرياضية', 'التربية الفنية'
            ],
            # الثالث المتوسط (10 مواد وزارية محددة حصراً بالترتيب المعتمد)
            'الثالث المتوسط': [
                'التربية الإسلامية',
                'اللغة العربية',
                'اللغة الإنكليزية',
                'الرياضيات',
                'الاجتماعيات',
                'الكيمياء',
                'الفيزياء',
                'الأحياء',
                'التربية الرياضية',
                'التربية الفنية',
            ],
            # 3. المرحلة الإعدادية - الفرع العلمي (8 مواد)
            'الرابع العلمي': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'الكيمياء', 'الفيزياء', 'علم الأحياء', 'الحاسوب'
            ],
            'الخامس العلمي': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'الكيمياء', 'الفيزياء', 'علم الأحياء', 'الحاسوب'
            ],
            'السادس العلمي': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'الكيمياء', 'الفيزياء', 'علم الأحياء', 'الحاسوب'
            ],
            # المرحلة الإعدادية - الفرع الأدبي (8 مواد)
            'الرابع الأدبي': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'التاريخ', 'الجغرافية', 'الاقتصاد', 'الحاسوب'
            ],
            'الخامس الأدبي': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'التاريخ', 'الجغرافية', 'الاقتصاد', 'الحاسوب'
            ],
            'السادس الأدبي': [
                'التربية الإسلامية', 'اللغة العربية', 'اللغة الإنكليزية', 'الرياضيات',
                'التاريخ', 'الجغرافية', 'الاقتصاد', 'الحاسوب'
            ],
        }

        with transaction.atomic():
            for stage_name, subs in STAGE_SUBJECTS.items():
                for idx, sub_name in enumerate(subs, start=1):
                    # مطابقة بأكثر من صورة للاسم لضمان التوافق التام
                    obj = cls.objects.filter(name=sub_name, grade_level=stage_name).first()
                    if not obj:
                        clean_stage = stage_name.replace('أ', 'ا').replace('إ', 'ا')
                        obj = cls.objects.filter(name=sub_name, grade_level=clean_stage).first()

                    if not obj:
                        cls.objects.create(
                            name=sub_name,
                            grade_level=stage_name,
                            order=idx
                        )
                    else:
                        if obj.order != idx or obj.grade_level != stage_name:
                            obj.order = idx
                            obj.grade_level = stage_name
                            obj.save(update_fields=['order', 'grade_level'])



class Teacher(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='حساب المعلم')
    school = models.ForeignKey(SchoolSettings, on_delete=models.SET_NULL, null=True, blank=True, default=1, related_name='teachers', verbose_name='المدرسة')
    is_active = models.BooleanField(default=True, verbose_name='نشط في المدرسة')
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
    CLASS_CHOICES = (
        ('المراحل الابتدائية', (
            ('الأول الابتدائي', 'الأول الابتدائي'),
            ('الثاني الابتدائي', 'الثاني الابتدائي'),
            ('الثالث الابتدائي', 'الثالث الابتدائي'),
            ('الرابع الابتدائي', 'الرابع الابتدائي'),
            ('الخامس الابتدائي', 'الخامس الابتدائي'),
            ('السادس الابتدائي', 'السادس الابتدائي'),
        )),
        ('المراحل المتوسطة', (
            ('الأول المتوسط', 'الأول المتوسط'),
            ('الثاني المتوسط', 'الثاني المتوسط'),
            ('الثالث المتوسط', 'الثالث المتوسط'),
        )),
        ('المراحل الإعدادية', (
            ('الرابع العلمي', 'الرابع العلمي'),
            ('الرابع الأدبي', 'الرابع الأدبي'),
            ('الخامس العلمي', 'الخامس العلمي'),
            ('الخامس الأدبي', 'الخامس الأدبي'),
            ('السادس العلمي', 'السادس العلمي'),
            ('السادس الأدبي', 'السادس الأدبي'),
        )),
    )

    IRAQI_OFFICIAL_STAGES = [
        # المراحل الابتدائية
        (1, 'الأول الابتدائي', 'primary', False),
        (2, 'الثاني الابتدائي', 'primary', False),
        (3, 'الثالث الابتدائي', 'primary', False),
        (4, 'الرابع الابتدائي', 'primary', False),
        (5, 'الخامس الابتدائي', 'primary', False),
        (6, 'السادس الابتدائي', 'primary', True),
        # المراحل المتوسطة
        (7, 'الأول المتوسط', 'intermediate', False),
        (8, 'الثاني المتوسط', 'intermediate', False),
        (9, 'الثالث المتوسط', 'intermediate', True),
        # المراحل الإعدادية
        (10, 'الرابع العلمي', 'preparatory', False),
        (11, 'الرابع الأدبي', 'preparatory', False),
        (12, 'الخامس العلمي', 'preparatory', False),
        (13, 'الخامس الأدبي', 'preparatory', False),
        (14, 'السادس العلمي', 'preparatory', True),
        (15, 'السادس الأدبي', 'preparatory', True),
    ]

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
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'صف دراسي'
        verbose_name_plural = 'الصفوف الدراسية'
        ordering = ['level_order', 'name']
        indexes = [
            models.Index(fields=['level_order', 'name']),
        ]

    def __str__(self):
        return f"{self.name}"

    @classmethod
    def ensure_all_stages(cls):
        """ضمان وجود كافة المراحل الدراسية العراقية الـ 15 في قاعدة البيانات دون أي حظر"""
        from django.db import transaction
        created_count = 0
        with transaction.atomic():
            for order, name, stage, is_final in cls.IRAQI_OFFICIAL_STAGES:
                name_clean = name.replace('أ', 'ا').replace('إ', 'ا')
                obj = cls.objects.filter(
                    models.Q(name=name) |
                    models.Q(name=name_clean) |
                    models.Q(level_order=order)
                ).first()
                if not obj:
                    obj = cls.objects.create(name=name, level_order=order, is_final_stage=is_final)
                    created_count += 1
                else:
                    updated = False
                    if obj.level_order != order:
                        obj.level_order = order
                        updated = True
                    if obj.is_final_stage != is_final:
                        obj.is_final_stage = is_final
                        updated = True
                    if updated:
                        obj.save()
                if not obj.sections.exists():
                    Section = cls.sections.rel.related_model
                    Section.objects.create(school_class=obj, name="أ", capacity=40)
        return created_count



class Section(models.Model):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='sections', verbose_name='الصف')
    name = models.CharField(max_length=50, verbose_name='اسم الشعبة')
    capacity = models.PositiveIntegerField(default=40, verbose_name='الطاقة الاستيعابية')
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'شعبة دراسية'
        verbose_name_plural = 'الشعب الدراسية'

    def __str__(self):
        return self.name



class Student(models.Model):
    STATUS_CHOICES = (
        ('active', 'مستمر بالدوام'),
        ('graduated', 'خريج'),
        ('transferred', 'منقول'),
        ('dismissed', 'مفصول / تارك'),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='حساب الطالب')
    school = models.ForeignKey(SchoolSettings, on_delete=models.SET_NULL, null=True, blank=True, default=1, related_name='students', verbose_name='المدرسة')
    registration_number = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name='رقم القيد العام')
    GENDER_TYPES = (
        ('male', 'ذكر'),
        ('female', 'أنثى'),
    )
    gender = models.CharField(max_length=10, choices=GENDER_TYPES, default='male', verbose_name='جنس الطالب')
    admission_date = models.DateField(default=timezone.now, verbose_name='تاريخ المباشرة')
    student_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True, verbose_name='حالة الطالب')
    national_id = models.CharField(max_length=50, blank=True, null=True, db_index=True, verbose_name='الرقم الوطني / الهوية')
    dob = models.DateField(blank=True, null=True, verbose_name='تاريخ التولد')
    current_class = models.ForeignKey(SchoolClass, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الصف الحالي')
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الشعبة')
    parent = models.ForeignKey(Parent, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='ولي الأمر')

    is_deleted = models.BooleanField(default=False, db_index=True, verbose_name='محذوف')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الحذف')
    history = HistoricalRecords()

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

    def get_full_name(self):
        """اسم الطالب الرباعي واللقب من حسابه أو قيده"""
        if self.user:
            name = self.user.get_full_name()
            if name and name.strip():
                return name.strip()
            if self.user.username:
                return self.user.username
        return "طالب غير محدد"

    @property
    def full_name(self):
        return self.get_full_name()

    @property
    def name(self):
        return self.get_full_name()

    @property
    def student_id(self):
        """الرقم الإحصائي / كود الطالب / رقم القيد"""
        return self.clean_reg_number or self.registration_number or str(self.id)

    @property
    def grade_level(self):
        """الصف الدراسي للطالب"""
        return self.current_class.name if self.current_class else ""

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

    APPROVAL_STATE_CHOICES = (
        ('DRAFT', 'مسودة'),
        ('SUBMITTED', 'مرفوعة للاعتماد'),
        ('APPROVED', 'معتمدة رسمياً'),
        ('LOCKED', 'مقفلة نهائياً'),
        ('AMENDED', 'معدلة استثنائياً'),
    )
    approval_state = models.CharField(max_length=20, choices=APPROVAL_STATE_CHOICES, default='APPROVED', db_index=True, verbose_name='حالة الاعتماد المؤسسي')
    is_locked = models.BooleanField(default=False, db_index=True, verbose_name='هل الدرجة مقفلة')
    locked_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإقفال')
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='locked_grades', verbose_name='من قام بالإقفال')
    last_amended_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ التعديل الاستثنائي')
    last_amended_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='amended_grades', verbose_name='من قام بالتعديل الاستثنائي')
    amendment_reason = models.TextField(blank=True, null=True, verbose_name='سبب التعديل الاستثنائي')

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'سجل درجات'
        verbose_name_plural = 'سجل الدرجات (النظام العراقي)'
        unique_together = ('student', 'subject', 'academic_year')
        indexes = [
            models.Index(fields=['student', 'academic_year']),
            models.Index(fields=['academic_year', 'subject']),
            models.Index(fields=['academic_year', 'status']),
            models.Index(fields=['academic_year', 'approval_state']),
            models.Index(fields=['academic_year', 'is_locked']),
        ]

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.academic_year})"

    def submit_for_approval(self, user=None):
        if self.is_locked:
            raise ValidationError("لا يمكن تغيير حالة درجة مقفلة نهائياً.")
        self.approval_state = 'SUBMITTED'
        self.save()
        AuditChainRecord.create_entry(
            user=user,
            action='SUBMIT_GRADE',
            model_name='Grade',
            object_id=self.pk,
            object_repr=str(self),
            new_value={'approval_state': 'SUBMITTED', 'final_grade': str(self.final_grade)}
        )

    def approve_grade(self, user):
        if not (user.is_superuser or getattr(user, 'can_approve_grades', False)):
            raise ValidationError("ليس لديك صلاحية اعتماد الدرجات.")
        self.approval_state = 'APPROVED'
        self.save()
        AuditChainRecord.create_entry(
            user=user,
            action='APPROVE_GRADE',
            model_name='Grade',
            object_id=self.pk,
            object_repr=str(self),
            new_value={'approval_state': 'APPROVED', 'final_grade': str(self.final_grade)}
        )

    def lock_grade(self, user):
        if not (user.is_superuser or getattr(user, 'can_lock_grades', False)):
            raise ValidationError("ليس لديك صلاحية إقفال الدرجات.")
        self.is_locked = True
        self.approval_state = 'LOCKED'
        self.locked_at = timezone.now()
        self.locked_by = user
        self.save()
        AuditChainRecord.create_entry(
            user=user,
            action='LOCK_GRADE',
            model_name='Grade',
            object_id=self.pk,
            object_repr=str(self),
            new_value={'approval_state': 'LOCKED', 'is_locked': True, 'final_grade': str(self.final_grade)}
        )

    def amend_locked_grade(self, user, reason, new_values):
        if not (user.is_superuser or getattr(user, 'can_amend_locked_grades', False)):
            raise ValidationError("تعديل الدرجات المقفلة صلاحية حصرية لمدير المدرسة (Principal) فقط.")
        if not reason or len(reason.strip()) < 5:
            raise ValidationError("يجب ذكر سبب رسمي مبرر ومفصل لتعديل الدرجة المقفلة (لا يقل عن 5 أحرف).")

        old_state = {
            'first_term_effort': str(self.first_term_effort),
            'midyear_exam': str(self.midyear_exam),
            'second_term_effort': str(self.second_term_effort),
            'annual_effort': str(self.annual_effort),
            'final_exam_round1': str(self.final_exam_round1),
            'final_exam_round2': str(self.final_exam_round2),
            'final_grade': str(self.final_grade),
            'status': self.status,
            'approval_state': self.approval_state
        }

        for k, v in new_values.items():
            if hasattr(self, k):
                setattr(self, k, v)

        self.update_all_calculations()
        self.approval_state = 'AMENDED'
        self.last_amended_at = timezone.now()
        self.last_amended_by = user
        self.amendment_reason = reason.strip()
        self.save()

        new_state = {
            'first_term_effort': str(self.first_term_effort),
            'midyear_exam': str(self.midyear_exam),
            'second_term_effort': str(self.second_term_effort),
            'annual_effort': str(self.annual_effort),
            'final_exam_round1': str(self.final_exam_round1),
            'final_exam_round2': str(self.final_exam_round2),
            'final_grade': str(self.final_grade),
            'status': self.status,
            'approval_state': 'AMENDED'
        }

        AuditChainRecord.create_entry(
            user=user,
            action='AMEND_LOCKED_GRADE',
            model_name='Grade',
            object_id=self.pk,
            object_repr=str(self),
            old_value=old_state,
            new_value=new_state,
            edit_reason=reason.strip()
        )

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
class SchoolSubscriptionPayment(models.Model):
    school = models.ForeignKey(SchoolSettings, on_delete=models.CASCADE, related_name='subscription_payments', verbose_name='المدرسة')
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.SET_NULL, null=True, blank=True, related_name='subscription_payments', verbose_name='السنة الدراسية')
    subscription = models.ForeignKey('SchoolYearSubscription', on_delete=models.SET_NULL, null=True, blank=True, related_name='payments', verbose_name='الاشتراك السنوي المستهدف')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='المبلغ المدفوع')
    payment_date = models.DateTimeField(default=timezone.now, verbose_name='تاريخ ووقت الدفعة')
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المستخدم الذي سجل الدفعة')
    notes = models.TextField(blank=True, default='', verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التسجيل')

    class Meta:
        verbose_name = 'دفعة اشتراك مدرسة'
        verbose_name_plural = 'سجل دفعات اشتراكات المدارس'
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        yr = f" ({self.academic_year.name})" if self.academic_year else ""
        return f"{self.school.school_name} - {self.amount}{yr}"

class SchoolYearSubscription(models.Model):
    """
    اشتراك المدرسة السنوي لكل سنة دراسية مستقلة
    المدرسة هي العميل المالي للمالك، ولكل سنة اشتراك مستقل لا يلغي السنوات السابقة
    """
    STATUS_CHOICES = (
        ('PAID', 'مسدد بالكامل'),
        ('PARTIAL', 'مسدد جزئياً'),
        ('UNPAID', 'غير مسدد'),
        ('OVERDUE', 'متأخر'),
    )

    school = models.ForeignKey(SchoolSettings, on_delete=models.CASCADE, related_name='yearly_subscriptions', verbose_name='المدرسة')
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, related_name='school_subscriptions', verbose_name='السنة الدراسية')
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='قيمة الاشتراك المستحق')
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='الخصومات والتسويات المعتمدة')
    is_active = models.BooleanField(default=True, verbose_name='حالة الاشتراك السنوي (مفعل/معطل)')
    due_date = models.DateField(null=True, blank=True, verbose_name='تاريخ استحقاق السداد')
    notes = models.TextField(blank=True, default='', verbose_name='ملاحظات العقد أو الاشتراك')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')

    class Meta:
        verbose_name = 'اشتراك المدرسة السنوي'
        verbose_name_plural = 'اشتراكات المدارس السنوية'
        unique_together = ('school', 'academic_year')
        ordering = ['-academic_year__start_date', '-created_at']

    def __str__(self):
        return f"{self.school.school_name} - {self.academic_year.name}"

    @property
    def final_due_amount(self):
        """المبلغ الصافي المستحق بعد الخصم"""
        fee = self.fee_amount or Decimal('0.00')
        disc = self.discount_amount or Decimal('0.00')
        return max(Decimal('0.00'), fee - disc)

    @property
    def total_paid(self):
        """إجمالي المبالغ المدفوعة لهذه السنة الدراسية حصراً"""
        val = self.payments.aggregate(total=models.Sum('amount'))['total']
        return val if val is not None else Decimal('0.00')

    @property
    def remaining_balance(self):
        """المبلغ المتبقي بذمة المدرسة للسنة الدراسية"""
        due = self.final_due_amount
        paid = self.total_paid
        return max(Decimal('0.00'), due - paid)

    @property
    def credit_balance(self):
        """رصيد دائن للمدرسة إذا دفعت أكثر من المستحق"""
        due = self.final_due_amount
        paid = self.total_paid
        if paid > due:
            return paid - due
        return Decimal('0.00')

    @property
    def payment_status(self):
        """حالة السداد الدقيقة"""
        due = self.final_due_amount
        paid = self.total_paid
        if due == Decimal('0.00'):
            return 'PAID'
        if paid >= due:
            return 'PAID'
        if paid > Decimal('0.00'):
            return 'PARTIAL'
        if self.due_date and timezone.now().date() > self.due_date:
            return 'OVERDUE'
        return 'UNPAID'

    @property
    def payment_status_display(self):
        mapping = {
            'PAID': 'مسدد بالكامل',
            'PARTIAL': 'مسدد جزئياً',
            'UNPAID': 'غير مسدد',
            'OVERDUE': 'متأخر',
        }
        return mapping.get(self.payment_status, 'غير مسدد')

class SchoolPaymentAdjustment(models.Model):
    """
    سجل الخصومات والتسويات المالية الخاصة بالمدرسة لسنة دراسية محددة
    """
    ADJUSTMENT_TYPES = (
        ('discount', 'خصم مالي ممنوح'),
        ('waiver', 'إعفاء أو تسوية خاصة'),
        ('scholarship', 'منحة / تسوية شرفية'),
        ('other', 'أخرى'),
    )

    school = models.ForeignKey(SchoolSettings, on_delete=models.CASCADE, related_name='financial_adjustments', verbose_name='المدرسة')
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, related_name='financial_adjustments', verbose_name='السنة الدراسية')
    subscription = models.ForeignKey(SchoolYearSubscription, on_delete=models.CASCADE, null=True, blank=True, related_name='adjustments', verbose_name='الاشتراك السنوي')
    adjustment_type = models.CharField(max_length=30, choices=ADJUSTMENT_TYPES, default='discount', verbose_name='نوع التسوية/الخصم')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='قيمة الخصم/التسوية')
    reason = models.TextField(blank=True, default='', verbose_name='سبب وتفاصيل الخصم أو التسوية')
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المسؤول المعتمد')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التسجيل')

    class Meta:
        verbose_name = 'خصم / تسوية مالية للمدرسة'
        verbose_name_plural = 'سجل الخصومات والتسويات المالية للمدارس'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.school.school_name} - {self.academic_year.name} ({self.amount})"

class AuditChainRecord(models.Model):
    """
    سلسلة تدقيق تشفيرية موثقة غير قابلة للتلاعب (Immutable Cryptographic Audit Chain):
    كل سجل يرتبط تشفيرياً بالسجل السابق عبر SHA-256 لمنع التعديل أو الحذف المباشر في قاعدة البيانات.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المستخدم')
    username = models.CharField(max_length=150, blank=True, verbose_name='اسم المستخدم')
    action = models.CharField(max_length=50, db_index=True, verbose_name='العملية')
    model_name = models.CharField(max_length=100, db_index=True, verbose_name='النموذج')
    object_id = models.CharField(max_length=100, db_index=True, verbose_name='معرف الكائن')
    object_repr = models.CharField(max_length=255, blank=True, verbose_name='وصف الكائن')
    old_value = models.TextField(blank=True, null=True, verbose_name='القيمة السابقة')
    new_value = models.TextField(blank=True, null=True, verbose_name='القيمة الجديدة')
    edit_reason = models.TextField(blank=True, null=True, verbose_name='سبب التعديل')
    device_id = models.CharField(max_length=100, blank=True, verbose_name='بصمة الجهاز')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='التاريخ والوقت')
    previous_hash = models.CharField(max_length=64, default="0" * 64, verbose_name='بصمة السجل السابق')
    current_hash = models.CharField(max_length=64, db_index=True, verbose_name='بصمة التشفير الحالية')

    class Meta:
        verbose_name = 'سجل تدقيق تشفيري'
        verbose_name_plural = 'سلسلة التدقيق التشفيرية الموثقة'
        ordering = ['id']

    def __str__(self):
        return f"[{self.id}] {self.action} on {self.model_name}#{self.object_id} by {self.username}"

    def calculate_current_hash(self):
        import hashlib
        ts = self.timestamp.isoformat() if hasattr(self.timestamp, 'isoformat') else str(self.timestamp)
        payload = (
            f"{self.user_id or ''}|{self.username}|{self.action}|{self.model_name}|"
            f"{self.object_id}|{self.old_value or ''}|{self.new_value or ''}|"
            f"{self.edit_reason or ''}|{self.device_id}|{ts}|{self.previous_hash}"
        )
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk is not None:
            existing = AuditChainRecord.objects.filter(pk=self.pk).first()
            if existing:
                raise ValidationError("غير مسموح بتعديل سجل تدقيق مسجل مسبقاً (Immutable Record).")
        if not self.current_hash:
            self.current_hash = self.calculate_current_hash()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("غير مسموح بحذف سجلات سلسلة التدقيق (Immutable Audit Chain).")

    @classmethod
    def create_entry(cls, user, action, model_name, object_id, old_value=None, new_value=None, edit_reason=None, device_id="", object_repr=""):
        import json
        from django.db import transaction
        with transaction.atomic():
            last_record = cls.objects.select_for_update().order_by('-id').first()
            prev_hash = last_record.current_hash if last_record else ("0" * 64)

            uname = user.username if user and hasattr(user, 'username') else "System"
            u_obj = user if user and getattr(user, 'is_authenticated', False) else None

            old_str = json.dumps(old_value, ensure_ascii=False) if isinstance(old_value, (dict, list)) else (str(old_value) if old_value is not None else "")
            new_str = json.dumps(new_value, ensure_ascii=False) if isinstance(new_value, (dict, list)) else (str(new_value) if new_value is not None else "")

            rec = cls(
                user=u_obj,
                username=uname,
                action=action,
                model_name=model_name,
                object_id=str(object_id),
                object_repr=str(object_repr)[:255],
                old_value=old_str,
                new_value=new_str,
                edit_reason=edit_reason,
                device_id=device_id,
                timestamp=timezone.now(),
                previous_hash=prev_hash
            )
            rec.current_hash = rec.calculate_current_hash()
            super(AuditChainRecord, rec).save()
            return rec

    @classmethod
    def verify_audit_chain(cls):
        records = cls.objects.all().order_by('id')
        if not records.exists():
            return True, "INTEGRITY: PASS (سلسلة التدقيق فارغة)", None

        expected_prev_hash = "0" * 64
        for rec in records:
            if rec.previous_hash != expected_prev_hash:
                return False, f"INTEGRITY: FAILED (انقطاع السلسلة عند السجل #{rec.id}: التوقيع السابق غير متطابق)", rec.id
            recalculated = rec.calculate_current_hash()
            if rec.current_hash != recalculated:
                return False, f"INTEGRITY: FAILED (تم اكتشاف تلاعب في محتوى السجل #{rec.id} ({rec.model_name}:{rec.object_id}))", rec.id
            expected_prev_hash = rec.current_hash

        return True, "INTEGRITY: PASS", None

class SecurityEventLog(models.Model):
    """سجل أحداث وتنبيهات الأمان المؤسساتي (Security Events)"""
    SEVERITY_CHOICES = (
        ('INFO', 'معلوماتي'),
        ('WARNING', 'تحذيري'),
        ('HIGH', 'عالي الخطورة'),
        ('CRITICAL', 'حرج للغاية'),
    )
    event_type = models.CharField(max_length=60, db_index=True, verbose_name='نوع الحدث')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='INFO', db_index=True, verbose_name='درجة الخطورة')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المستخدم')
    username = models.CharField(max_length=150, blank=True, verbose_name='اسم المستخدم')
    ip_address = models.CharField(max_length=50, blank=True, verbose_name='عنوان IP')
    device_id = models.CharField(max_length=100, blank=True, verbose_name='بصمة الجهاز')
    details = models.TextField(blank=True, verbose_name='تفاصيل الحدث')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='وقت الحدث')

    class Meta:
        verbose_name = 'سجل حدث أمني'
        verbose_name_plural = 'سجل أحداث الأمان'
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.severity}] {self.event_type} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    @classmethod
    def log_event(cls, event_type, severity='INFO', user=None, ip_address="", device_id="", details=""):
        uname = user.username if user and hasattr(user, 'username') else ""
        u_obj = user if user and getattr(user, 'is_authenticated', False) else None
        return cls.objects.create(
            event_type=event_type,
            severity=severity,
            user=u_obj,
            username=uname,
            ip_address=ip_address,
            device_id=device_id,
            details=details,
            timestamp=timezone.now()
        )

class StudentBehaviorRecord(models.Model):
    """السجل السلوكي للطالب — يراه ولي الأمر مع الوضع الدراسي الكامل."""
    BEHAVIOR_TYPES = (
        ('PRAISE', 'سلوك إيجابي / تشجيع'),
        ('CONCERN', 'ملاحظة سلوكية'),
        ('WARNING', 'تنبيه / إنذار'),
        ('CALL_IN', 'استدعاء ولي الأمر'),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='behavior_records', verbose_name='الطالب')
    behavior_type = models.CharField(max_length=20, choices=BEHAVIOR_TYPES, default='CONCERN', verbose_name='نوع الملاحظة')
    description = models.TextField(verbose_name='التفاصيل')
    recorded_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='behavior_records', verbose_name='مُسجّل بواسطة')
    recorded_at = models.DateTimeField(auto_now_add=True, verbose_name='وقت التسجيل')

    class Meta:
        verbose_name = 'سجل سلوكي'
        verbose_name_plural = 'السجل السلوكي للطلاب'
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.student} — {self.get_behavior_type_display()}"

class SchoolNotice(models.Model):
    """إشعارات الإدارة لأولياء الأمور (استدعاء / اجتماع / إعلان / امتحان)."""
    NOTICE_KINDS = (
        ('GENERAL', 'إعلان عام'),
        ('CALL_IN', 'استدعاء ولي أمر'),
        ('MEETING', 'اجتماع أولياء الأمور'),
        ('EXAM', 'امتحان'),
        ('OTHER', 'إشعار آخر'),
    )
    kind = models.CharField(max_length=20, choices=NOTICE_KINDS, default='GENERAL', verbose_name='النوع')
    title = models.CharField(max_length=200, verbose_name='العنوان')
    body = models.TextField(verbose_name='النص')
    school_class = models.ForeignKey(SchoolClass, on_delete=models.SET_NULL, null=True, blank=True, related_name='notices', verbose_name='الصف (إن كان خاصاً بصف)')
    created_by = models.CharField(max_length=150, blank=True, default='', verbose_name='أُنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='وقت الإرسال')
    is_active = models.BooleanField(default=True, verbose_name='نشط')

    class Meta:
        verbose_name = 'إشعار للإدارة'
        verbose_name_plural = 'إشعارات الإدارة لأولياء الأمور'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_kind_display()}] {self.title}"

class ExamAnnouncement(models.Model):
    """إعلان امتحان لصف معين — يصل بضغطة زر واحدة لجميع أولياء الأمور."""
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='exam_announcements', verbose_name='الصف')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='exam_announcements', verbose_name='المادة')
    exam_title = models.CharField(max_length=150, verbose_name='عنوان الامتحان', blank=True, default='')
    exam_date = models.DateField(verbose_name='تاريخ الامتحان')
    exam_time = models.CharField(max_length=40, blank=True, default='', verbose_name='الوقت')
    topics = models.TextField(verbose_name='المواضيع المطلوبة (من صفحة إلى صفحة)', blank=True, default='')
    notes = models.TextField(verbose_name='ملاحظات', blank=True, default='')
    created_by = models.CharField(max_length=150, blank=True, default='', verbose_name='أُعلن بواسطة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='وقت النشر')

    class Meta:
        verbose_name = 'إعلان امتحان'
        verbose_name_plural = 'إعلانات الامتحانات الشهرية'
        ordering = ['-exam_date', '-created_at']

    def __str__(self):
        return f"{self.school_class.name} — {self.subject.name} ({self.exam_date})"

class ParentServiceRequest(models.Model):
    """طلبات ولي الأمر (نقل / تأييد درجات / تأييد استمرارية خدمة) تصله إلى حاسبة الإدارة لإصدار الكتاب."""
    REQUEST_KINDS = (
        ('TRANSFER', 'طلب نقل الطالب'),
        ('GRADE_ATTESTATION', 'تأييد درجات'),
        ('SERVICE_ATTESTATION', 'تأييد استمرارية خدمة'),
        ('TRANSCRIPT', 'كشف درجات / شهادة'),
        ('OTHER', 'طلب آخر'),
    )
    STATUS = (
        ('SUBMITTED', 'وصل الطلب'),
        ('IN_PROGRESS', 'جاري تحضير الكتاب'),
        ('READY', 'الكتاب جاهز للتسليم'),
        ('DENIED', 'مرفوض'),
    )
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name='service_requests', verbose_name='ولي الأمر')
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name='service_requests', verbose_name='الطالب المعني')
    kind = models.CharField(max_length=30, choices=REQUEST_KINDS, verbose_name='نوع الطلب')
    details = models.TextField(blank=True, default='', verbose_name='التفاصيل')
    status = models.CharField(max_length=20, choices=STATUS, default='SUBMITTED', verbose_name='الحالة')
    letter_document = models.ForeignKey(OfficialDocument, on_delete=models.SET_NULL, null=True, blank=True, related_name='parent_requests', verbose_name='الكتاب الصادر')
    admin_note = models.TextField(blank=True, default='', verbose_name='ملاحظة الإدارة')
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='وقت الإرسال')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')

    class Meta:
        verbose_name = 'طلب ولي أمر'
        verbose_name_plural = 'طلبات أولياء الأمور والكتب'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.get_kind_display()} — {self.student or ''} ({self.get_status_display()})"

class ParentChatMessage(models.Model):
    """محادثة مباشرة بين ولي الأمر والإدارة (حاسبة المدرسة المركزية)."""
    DIRECTION = (
        ('TO_SCHOOL', 'إلى المدرسة'),
        ('FROM_SCHOOL', 'من المدرسة'),
    )
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name='chat_messages', verbose_name='ولي الأمر')
    direction = models.CharField(max_length=20, choices=DIRECTION, default='TO_SCHOOL', verbose_name='الاتجاه')
    body = models.TextField(verbose_name='النص')
    is_read = models.BooleanField(default=False, verbose_name='مقروء')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='الوقت')

    class Meta:
        verbose_name = 'رسالة محادثة'
        verbose_name_plural = 'محادثات أولياء الأمور مع الإدارة'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.parent} → {self.get_direction_display()}"
