from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from .models import SchoolSettings

EXEMPT_EXACT_NAMES = {
    'portal_license_lock',
    'portal_license_activate',
    'portal_owner_generator',
    'portal_backup_download',
    'portal_backup_restore',
}

EXEMPT_PATH_PREFIXES = (
    '/portal/license-lock/',
    '/portal/license-activate/',
    '/portal/owner-generator/',
    '/portal/settings/backup/',
    '/static/',
    '/media/',
    '/admin/',
    '/favicon.ico',
)

TRIAL_EXPIRED_MESSAGE = "انتهت الفترة التجريبية (14 يوماً) لمنظومة مدرستي. يرجى إدخال كود التفعيل السنوي أو التواصل مع الدعم الفني: 07723457175 لتجديد الترخيص"

class LicenseEnforcementMiddleware:
    """
    ميدلوير أمني صارم لحماية تراخيص النظام والنسخة التجريبية:
    - يمنح المستخدم 14 يوماً تجربة مجانية كاملة.
    - بعد انقضاء الـ 14 يوماً دون تفعيل رسمي مدفوع، يغلق فورياً كافة بوابات النظام الحساسة
      (القيد العام، القاعات، السجلات، الطباعة، الجدول، وغيرها).
    - يحول المستخدم تلقائياً إلى شاشة حالة الاشتراك والتفعيل مع إشعار رسمي واضح.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # السماح بالمسارات المعفاة (شاشات التفعيل والنسخ الاحتياطي والملفات الثابتة)
        if any(path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES):
            return self.get_response(request)

        # فحص حالة الترخيص وإعدادات المدرسة
        try:
            school = SchoolSettings.get_settings()
            is_valid = school.is_trial_or_license_valid
        except Exception:
            is_valid = True

        if not is_valid:
            # التحقق من أن الطلب يستهدف بوابات النظام أو الصفحة الرئيسية
            if path == '/' or path.startswith('/portal/') or path.startswith('/certificates/'):
                # إضافة رسالة التنبيه لمرة واحدة في الجلسة لمنع التكرار
                existing_msgs = [m.message for m in messages.get_messages(request)]
                if TRIAL_EXPIRED_MESSAGE not in existing_msgs:
                    messages.error(request, TRIAL_EXPIRED_MESSAGE)
                return redirect('portal_license_lock')

        return self.get_response(request)
