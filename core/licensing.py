import hashlib
import uuid
import hmac
from datetime import datetime, timedelta
from django.utils import timezone
from .models import SchoolSettings

# المفتاح السري الخاص بك لتشفير التراخيص (لا تعطه لأحد)
SECRET_SALT = "IRAQ_EDU_SAAS_SECRET_2026_BY_ABDUL"

def get_machine_fingerprint():
    """توليد معرف رقمي ثابت لحاسبة المدرسة (Hardware ID)"""
    node = uuid.getnode()
    raw = f"NODE_{node}_{SECRET_SALT}"
    hashed = hashlib.sha256(raw.encode()).hexdigest().upper()
    return f"{hashed[:4]}-{hashed[4:8]}-{hashed[8:12]}"

def generate_license_key(machine_id, plan="YEAR"):
    """
    توليد مفتاح التفعيل بحسب الباقة المطلوبة:
    - MONTH: شهر واحد (30 يوماً)
    - YEAR: سنة كاملة (365 يوماً)
    - LIFETIME: دائمي مدى الحياة
    """
    mid = machine_id.strip().upper()
    
    if plan == "MONTH":
        token = f"{mid}_PLAN_MONTH_30DAYS"
        prefix = "MTH"
    elif plan == "YEAR":
        token = f"{mid}_PLAN_YEAR_365DAYS"
        prefix = "YR"
    elif plan == "LIFETIME":
        token = f"{mid}_PLAN_LIFETIME_FOREVER"
        prefix = "LIFE"
    else:
        return None

    # توليد بصمة توقيع مشفرة للكود
    signature = hmac.new(SECRET_SALT.encode(), token.encode(), hashlib.sha256).hexdigest().upper()[:8]
    clean_mid_chunk = mid.replace("-", "")[:4]
    return f"{prefix}-{clean_mid_chunk}-{signature}"

def compute_license_seal(end_date_str, license_key):
    """توليد توقيع مشفر (Cryptographic Seal) لمنع التلاعب المباشر بقاعدة البيانات"""
    mid = get_machine_fingerprint()
    raw = f"MADRASATI_SEAL_{mid}_{str(end_date_str)}_{str(license_key)}_{SECRET_SALT}"
    return hashlib.sha256(raw.encode()).hexdigest()

def generate_license_file_data(machine_id, plan="YEAR", school_name=""):
    """توليد محتوى ملف ترخيص رقمي (.lic) معتمد"""
    import json
    key = generate_license_key(machine_id, plan)
    if not key:
        return None
    days = 36500 if plan == "LIFETIME" else (365 if plan == "YEAR" else 30)
    end_date_str = (timezone.now().date() + timedelta(days=days)).isoformat()
    seal = compute_license_seal(end_date_str, key)
    data = {
        "version": "1.0",
        "app": "Madrasati",
        "school_name": school_name,
        "machine_id": machine_id.strip().upper(),
        "plan": plan,
        "license_key": key,
        "valid_until": end_date_str,
        "seal": seal
    }
    return json.dumps(data, indent=2, ensure_ascii=False)

def verify_and_apply_license_file(school, file_content_str):
    """التحقق التام وتفعيل النظام عبر ملف الترخيص الرقمي (.lic)"""
    import json
    try:
        data = json.loads(file_content_str)
        mid = get_machine_fingerprint()
        if data.get("machine_id", "").strip().upper() != mid:
            return False, "ملف الترخيص مخصص لحاسوب آخر ولا يتطابق مع هذا الجهاز."
        key = data.get("license_key", "").strip().upper()
        plan = data.get("plan", "YEAR")
        valid_until_str = data.get("valid_until", "")
        seal = data.get("seal", "")
        expected_seal = compute_license_seal(valid_until_str, key)
        if seal != expected_seal:
            return False, "ملف الترخيص غير سليم أو تم التعديل عليه بشكل غير قانوني."

        end_date = datetime.strptime(valid_until_str, "%Y-%m-%d").date()
        school.license_key = key
        school.is_subscription_active = True
        school.subscription_end_date = end_date
        school.license_hash = seal
        school.save()
        return True, f"تم بنجاح تفعيل المنظومة بنظام ({plan}) حتى تاريخ {valid_until_str}."
    except Exception as e:
        return False, f"تعذر قراءة ملف الترخيص: {str(e)}"

def verify_and_apply_license(school, license_key):
    """التحقق من الكود المكتوب وتطبيقه على النظام وحفظ تاريخ الانتهاء وختم التشفير"""
    key = license_key.strip().upper()
    machine_id = get_machine_fingerprint()

    # 1. فحص كود التفعيل الدائمي (Lifetime)
    expected_life = generate_license_key(machine_id, plan="LIFETIME")
    if key == expected_life:
        school.license_key = key
        school.is_subscription_active = True
        end_date = timezone.now().date() + timedelta(days=36500) # 100 سنة
        school.subscription_end_date = end_date
        school.license_hash = compute_license_seal(str(end_date), key)
        school.save()
        return True, "تم تفعيل المنظومة مدى الحياة بنجاح! شكراً لثقتكم."

    # 2. فحص كود التفعيل السنوي (Year)
    expected_year = generate_license_key(machine_id, plan="YEAR")
    if key == expected_year:
        school.license_key = key
        school.is_subscription_active = True
        end_date = timezone.now().date() + timedelta(days=365)
        school.subscription_end_date = end_date
        school.license_hash = compute_license_seal(str(end_date), key)
        school.save()
        return True, "تم تفعيل الاشتراك السنوي بنجاح لمدة سنة كاملة."

    # 3. فحص كود التفعيل الشهري (Month)
    expected_month = generate_license_key(machine_id, plan="MONTH")
    if key == expected_month:
        school.license_key = key
        school.is_subscription_active = True
        end_date = timezone.now().date() + timedelta(days=30)
        school.subscription_end_date = end_date
        school.license_hash = compute_license_seal(str(end_date), key)
        school.save()
        return True, "تم تفعيل الاشتراك الشهري بنجاح لمدة 30 يوماً."

    return False, "مفتاح الترخيص غير صالح لهذه الحاسبة أو غير صحيح."