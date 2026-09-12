from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

User = settings.AUTH_USER_MODEL

class UserRole(models.TextChoices):
    OWNER = 'OWNER', 'المالك والمشرف العام'
    MANAGER = 'MANAGER', 'مدير المدرسة'
    TEACHER = 'TEACHER', 'معلم'
    PARENT = 'PARENT', 'ولي أمر'

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mobile_profile', verbose_name='المستخدم')
    school = models.ForeignKey('core.SchoolSettings', on_delete=models.SET_NULL, null=True, blank=True, related_name='mobile_profiles', verbose_name='المدرسة')
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.PARENT, verbose_name='الدور')
    full_name = models.CharField(max_length=150, blank=True, default='', verbose_name='الاسم الكامل')
    phone = models.CharField(max_length=20, blank=True, default='', verbose_name='رقم الهاتف')
    is_approved = models.BooleanField(default=False, verbose_name='معتمد رسمياً')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        verbose_name = 'ملف مستخدم المنظومة'
        verbose_name_plural = 'ملفات مستخدمي المنظومة'

    def __str__(self):
        return f"{self.full_name or self.user.username} ({self.get_role_display()})"


class ParentStudentRelation(models.Model):
    parent = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='children_relations', verbose_name='ولي الأمر')
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE, related_name='parents_relations', verbose_name='الطالب')
    is_confirmed = models.BooleanField(default=False, verbose_name='تم تأكيد الربط')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('parent', 'student')
        verbose_name = 'علاقة ولي الأمر بالطالب'
        verbose_name_plural = 'علاقات أولياء الأمور بالطلبة'


class SubscriptionStatus(models.TextChoices):
    PENDING = 'PENDING', 'قيد المراجعة'
    ACTIVE = 'ACTIVE', 'نشط وسارٍ'
    EXPIRED = 'EXPIRED', 'منتهي الصلاحية'
    REJECTED = 'REJECTED', 'مرفوض'
    SUSPENDED = 'SUSPENDED', 'معلق'

class StudentActivation(models.Model):
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE, related_name='activations', verbose_name='الطالب')
    parent = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='activations', null=True, blank=True, verbose_name='ولي الأمر')
    school = models.ForeignKey('core.SchoolSettings', on_delete=models.CASCADE, null=True, blank=True, related_name='activations', verbose_name='المدرسة')
    academic_year = models.ForeignKey('core.AcademicYear', on_delete=models.SET_NULL, null=True, blank=True, related_name='student_activations', verbose_name='السنة الدراسية')
    activation_code = models.CharField(max_length=64, unique=True, default='', verbose_name='كود التفعيل')
    status = models.CharField(max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.PENDING, verbose_name='حالة الاشتراك')
    is_used = models.BooleanField(default=False, verbose_name='تم استخدام الكود')
    starts_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ البداية')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الانتهاء')
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الطلب')
    activated_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ التفعيل الفعلي')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_student_activations', verbose_name='من أنشأ الكود')
    decision_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ القرار')
    decision_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='decided_subscriptions', verbose_name='صاحب القرار')
    rejection_reason = models.TextField(blank=True, default='', verbose_name='سبب الرفض')

    class Meta:
        verbose_name = 'تفعيل واشتراك الطالب'
        verbose_name_plural = 'تفعيلات واشتراكات الطلبة'
        indexes = [
            models.Index(fields=['student', 'academic_year']),
            models.Index(fields=['status', 'academic_year']),
        ]

    def __str__(self):
        yr = f" - {self.academic_year.name}" if self.academic_year else ""
        return f"{self.student} [{self.activation_code}]{yr}"

    @property
    def is_currently_valid(self):
        """التحقق التام من سريان صلاحية كود التفعيل لهذا الطالب"""
        if self.status != SubscriptionStatus.ACTIVE:
            return False
        if self.expires_at:
            from datetime import datetime, date
            now_val = timezone.now()
            exp = self.expires_at
            if isinstance(exp, date) and not isinstance(exp, datetime):
                if now_val.date() > exp:
                    return False
            else:
                if timezone.is_naive(exp):
                    exp = timezone.make_aware(exp)
                if now_val > exp:
                    return False

        if self.academic_year and not self.academic_year.is_current:
            return False
        return True

    def expire(self):
        """إنهاء صلاحية الكود القديم دون حذفه نهائياً"""
        self.status = SubscriptionStatus.EXPIRED
        self.save(update_fields=['status'])

ParentSubscription = StudentActivation


class GradeStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'مسودة لدى المعلم'
    SUBMITTED = 'SUBMITTED', 'مرسلة للمراجعة'
    APPROVED = 'APPROVED', 'معتمدة ومصادقة من الإدارة'
    REJECTED = 'REJECTED', 'معادة للتدقيق'

class GradeEntry(models.Model):
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE, related_name='mobile_grades')
    subject = models.ForeignKey('core.Subject', on_delete=models.CASCADE, related_name='mobile_grades')
    teacher = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='entered_grades')
    exam_type = models.CharField(max_length=50, default='شهري', verbose_name='نوع الامتحان')
    month1 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    month2 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    daily = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    final_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=GradeStatus.choices, default=GradeStatus.DRAFT)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_grades')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'سجل رصد واعتماد الدرجات'
        verbose_name_plural = 'سجلات رصد واعتماد الدرجات'


class DocumentRequestStatus(models.TextChoices):
    SUBMITTED = 'SUBMITTED', 'تم الإرسال'
    UNDER_REVIEW = 'UNDER_REVIEW', 'قيد التدقيق'
    APPROVED = 'APPROVED', 'تمت الموافقة وجاهز للاستلام'
    REJECTED = 'REJECTED', 'مرفوض'
    COMPLETED = 'COMPLETED', 'تم التسليم'

class DocumentRequest(models.Model):
    request_number = models.CharField(max_length=32, unique=True, null=True, blank=True, editable=False, verbose_name='رقم المعاملة')
    parent = models.ForeignKey(UserProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='document_requests')
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE, null=True, blank=True, related_name='document_requests')
    doc_type = models.CharField(max_length=100, default='تأييد استمرار بالدوام', verbose_name='نوع المعاملة')
    destination = models.CharField(max_length=200, default='إدارة المدرسة', blank=True, verbose_name='الجهة الموجه إليها')
    details = models.TextField(blank=True, default='', verbose_name='تفاصيل إضافية')
    status = models.CharField(max_length=20, choices=DocumentRequestStatus.choices, default=DocumentRequestStatus.SUBMITTED)
    admin_response = models.TextField(blank=True, default='', verbose_name='رد الإدارة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.request_number:
            year = timezone.now().year
            unique_part = uuid.uuid4().hex[:6].upper()
            self.request_number = f"REQ-{year}-{unique_part}"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'طلب وثيقة أو معاملة رسمية'
        verbose_name_plural = 'طلبات الوثائق والمعاملات الرسمية'

OfficialDocumentRequest = DocumentRequest


class HomeworkAssignment(models.Model):
    school = models.ForeignKey('core.SchoolSettings', on_delete=models.SET_NULL, null=True, blank=True, related_name='homework_assignments', verbose_name='المدرسة')
    classroom = models.CharField(max_length=100, default='الصف الأول', verbose_name='الشعبة / الصف')
    subject = models.CharField(max_length=100, default='الرياضيات', verbose_name='المادة')
    title = models.CharField(max_length=200, default='', verbose_name='عنوان الواجب')
    description = models.TextField(default='', verbose_name='تفاصيل الواجب')
    due_date = models.CharField(max_length=50, blank=True, default='', verbose_name='موعد التسليم')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'واجب منزلي'
        verbose_name_plural = 'الواجبات المنزلية'


class SchoolNews(models.Model):
    school = models.ForeignKey('core.SchoolSettings', on_delete=models.SET_NULL, null=True, blank=True, related_name='school_news', verbose_name='المدرسة')
    title = models.CharField(max_length=200, default='', verbose_name='العنوان')
    content = models.TextField(default='', verbose_name='المحتوى')
    category = models.CharField(max_length=50, default='تعميم إداري', verbose_name='التصنيف')
    is_urgent = models.BooleanField(default=False, verbose_name='عاجل')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'تعميم أو خبر مدرسي'
        verbose_name_plural = 'التعاميم والأخبار المدرسية'


class MobileNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mobile_notifications')
    title = models.CharField(max_length=200, default='')
    body = models.TextField(default='')
    notification_type = models.CharField(max_length=50, default='GENERAL')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'إشعار فوري'
        verbose_name_plural = 'الإشعارات الفورية'


class AuditTrailLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=150, default='', verbose_name='الإجراء')
    entity_name = models.CharField(max_length=100, default='', verbose_name='الكيان')
    entity_id = models.CharField(max_length=50, blank=True, default='')
    details = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'سجل تدقيق العمليات'
        verbose_name_plural = 'سجل تدقيق العمليات'


class RevokedToken(models.Model):
    token_jti = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='معرف التوكن الفريد')
    revoked_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإبطال')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الانتهاء الأصلي')

    class Meta:
        db_table = 'mobile_api_revokedtoken'
        verbose_name = 'توكن مبطل'
        verbose_name_plural = 'قائمة التوكنات المبطلة'

    def __str__(self):
        return f"RevokedToken: {self.token_jti[:12]}... at {self.revoked_at}"

