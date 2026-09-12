import json
import base64
import uuid
import hashlib
from datetime import timedelta
from functools import wraps
from django.conf import settings
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.http import JsonResponse
from django.utils import timezone
from .models import UserProfile, ParentStudentRelation, UserRole, RevokedToken

signer = TimestampSigner(salt='madrasati_mobile_jwt_salt')

def generate_tokens_for_user(user, profile):
    """توليد Access Token و Refresh Token موقعين رقمياً مع معرف فريد jti"""
    jti = uuid.uuid4().hex
    payload = {
        'jti': jti,
        'user_id': user.id,
        'username': user.username,
        'role': profile.role,
        'profile_id': profile.id,
        'school_id': profile.school_id if profile.school else None,
        'type': 'access'
    }
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    access_token = signer.sign(encoded_payload)

    refresh_payload = {
        'jti': uuid.uuid4().hex,
        'user_id': user.id,
        'type': 'refresh'
    }
    encoded_refresh = base64.urlsafe_b64encode(json.dumps(refresh_payload).encode()).decode()
    refresh_token = signer.sign(encoded_refresh)

    return access_token, refresh_token

def revoke_token(token, payload=None):
    """إبطال التوكن على مستوى الخادم وحفظه في قائمة التوكنات الملغاة"""
    try:
        if not payload:
            raw_payload = signer.unsign(token, max_age=86400 * 30)
            payload = json.loads(base64.urlsafe_b64decode(raw_payload.encode()).decode())
    except Exception:
        payload = None

    jti = payload.get('jti') if isinstance(payload, dict) else None
    if jti:
        RevokedToken.objects.get_or_create(token_jti=jti)

    # حفظ بصمة التوكن أيضاً للتوثيق التام
    tok_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    RevokedToken.objects.get_or_create(token_jti=tok_hash)

def verify_token(token, max_age_seconds=86400 * 30):  # صالح لـ 30 يوماً للوصول المتواصل
    """فك التشفير والتحقق من صحة وصلاحية الـ Token مع التحقق من عدم إبطاله"""
    try:
        raw_payload = signer.unsign(token, max_age=max_age_seconds)
        data = json.loads(base64.urlsafe_b64decode(raw_payload.encode()).decode())
        
        # فحص معرف jti في البلاك ليست
        jti = data.get('jti')
        if jti and RevokedToken.objects.filter(token_jti=jti).exists():
            return None

        # فحص بصمة التوكن في البلاك ليست
        tok_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        if RevokedToken.objects.filter(token_jti=tok_hash).exists():
            return None

        return data
    except (BadSignature, SignatureExpired, Exception):
        return None


def require_mobile_auth(allowed_roles=None):
    """Decorator لحماية Endpoints وفحص الـ Role والتوثيق وعزل المدارس"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            auth_header = request.headers.get('Authorization', '') or request.META.get('HTTP_AUTHORIZATION', '')
            if not auth_header.startswith('Bearer '):
                return JsonResponse({'error': 'غير مصرح بالدخول، يرجى تقديم رمز التوثيق'}, status=401)

            token = auth_header.split('Bearer ')[1].strip()
            payload = verify_token(token)
            if not payload or payload.get('type') != 'access':
                return JsonResponse({'error': 'جلسة الدخول منتهية أو الرمز غير صالح'}, status=401)

            from django.contrib.auth import get_user_model
            User = get_user_model()

            user = User.objects.filter(id=payload.get('user_id'), is_active=True).first()
            if not user:
                return JsonResponse({'error': 'المستخدم غير موجود أو تم تعطيل حسابه'}, status=401)

            request.user = user
            request.user_id = user.id
            request.profile_id = payload.get('profile_id')

            profile = UserProfile.objects.filter(id=request.profile_id).first()
            if not profile:
                profile = getattr(user, 'mobile_profile', None)

            if not profile:
                return JsonResponse({'error': 'ملف المستخدم غير مهيأ'}, status=401)

            request.user_profile = profile
            request.user_role = profile.role
            request.school_id = profile.school_id
            request.auth_token = token
            request.token_payload = payload

            if allowed_roles and request.user_role not in allowed_roles:
                return JsonResponse({'error': 'ليس لديك صلاحية لتنفيذ هذا الإجراء (صلاحية غير كافية)'}, status=403)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def verify_school_access(request, target_school_id):
    """التحقق الصارم من العزل المدرسي: المالك يرى الكل، والمدير والمعلم يريان مدرستهما فقط"""
    if request.user_role == UserRole.OWNER:
        return True
    return request.school_id is not None and str(request.school_id) == str(target_school_id)

def verify_parent_student_access(parent_profile_id, student_id):
    """حماية صارمة ضد ثغرة IDOR: منع ولي الأمر من رؤية بيانات أي طالب خارج أبنائه المعتمدين"""
    return ParentStudentRelation.objects.filter(
        parent_id=parent_profile_id,
        student_id=student_id,
        is_confirmed=True
    ).exists()
