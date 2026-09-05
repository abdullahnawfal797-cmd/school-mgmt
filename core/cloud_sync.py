import os
import sys
import gzip
import json
import base64
import sqlite3
import tempfile
import threading
import urllib.request
import urllib.error
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from .models import SchoolSettings
from .licensing import get_machine_fingerprint
from .backup_vault import create_daily_backup_snapshot, get_backup_dir

FIREBASE_RTDB_URL = "https://madrasati-iraq-288be-default-rtdb.firebaseio.com"
SYNC_STATUS_FILE = os.path.join(settings.BASE_DIR, "last_sync_status.json")


def get_last_cloud_sync_info():
    """قراءة تفاصيل آخر مزامنة سحابية محفوظة محلياً"""
    if os.path.exists(SYNC_STATUS_FILE):
        try:
            with open(SYNC_STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def upload_cloud_backup():
    """
    رفع النسخة الاحتياطية سحابياً إلى Firebase Realtime Database
    - الاعتماد على ministry_school_code كمعرف أساسي
    - ضغط قاعدة البيانات بـ gzip وتشفيرها بـ Base64
    - إرسال طلب HTTP PATCH إلى /backups/{ministry_school_code}.json
    """
    school = SchoolSettings.get_settings()
    ministry_code = (school.ministry_school_code or '').strip()

    if not ministry_code:
        msg = "لم يتم تحديد الرمز الإحصائي الوزاري للمدرسة (كود التربية). يرجى تعيينه في الإعدادات."
        _record_sync_status(False, msg, school.school_name, "")
        return False, msg

    db_path = str(settings.DATABASES['default']['NAME'])
    if not os.path.exists(db_path):
        msg = f"ملف قاعدة البيانات غير موجود في المسار: {db_path}"
        _record_sync_status(False, msg, school.school_name, ministry_code)
        return False, msg

    try:
        # 1. أخذ لقطة آمنة ومتناسقة بدون قفل الملف
        temp_snap = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_snap_path = temp_snap.name
        temp_snap.close()

        src_conn = sqlite3.connect(db_path)
        dst_conn = sqlite3.connect(temp_snap_path)
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

        with open(temp_snap_path, 'rb') as f:
            raw_db_bytes = f.read()

        try:
            os.remove(temp_snap_path)
        except Exception:
            pass

        # 2. ضغط قاعدة البيانات بـ gzip وتشفيرها بـ Base64
        compressed_bytes = gzip.compress(raw_db_bytes, compresslevel=6)
        encoded_db_string = base64.b64encode(compressed_bytes).decode('ascii')

        # 3. استخراج البيانات والبيانات الوصفية
        machine_id = get_machine_fingerprint()
        now_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S")

        payload = {
            "school_name": school.school_name,
            "ministry_school_code": ministry_code,
            "machine_id": machine_id,
            "last_sync": now_str,
            "backup_data": encoded_db_string
        }

        # 4. إرسال طلب HTTP PATCH إلى Firebase RTDB
        url = f"{FIREBASE_RTDB_URL}/backups/{ministry_code}.json"
        data_json = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data_json,
            headers={
                'Content-Type': 'application/json; charset=utf-8',
                'User-Agent': 'Madrasati-CloudSync/2.0'
            },
            method='PATCH'
        )

        with urllib.request.urlopen(req, timeout=45) as resp:
            resp_code = resp.status

        # 5. تسجيل نجاح المزامنة
        success_msg = f"تمت المزامنة والرفع السحابي بنجاح ({now_str})"
        _record_sync_status(
            True,
            success_msg,
            school.school_name,
            ministry_code,
            orig_size=len(raw_db_bytes),
            comp_size=len(compressed_bytes)
        )

        # أخذ نسخة محلية يومية أيضاً لضمان الأمان المزدوج
        create_daily_backup_snapshot()

        return True, success_msg

    except urllib.error.URLError as ue:
        err_msg = f"تعذر الاتصال بالسحابة (تحقق من الإنترنت): {ue.reason}"
        _record_sync_status(False, err_msg, school.school_name, ministry_code)
        return False, err_msg
    except Exception as e:
        err_msg = f"حدث خطأ أثناء المزامنة السحابية: {str(e)}"
        _record_sync_status(False, err_msg, school.school_name, ministry_code)
        return False, err_msg


def upload_cloud_backup_async():
    """تشغيل المزامنة السحابية في خيط خلفي (Daemon Thread) بدون تعطيل المستخدم"""
    t = threading.Thread(target=upload_cloud_backup, daemon=True, name="MadrasatiCloudSync")
    t.start()
    return t


def restore_cloud_backup(entered_code):
    """
    استعادة النسخة السحابية للطوارئ عبر الرمز الإحصائي الوزاري للمدرسة
    - جلب /backups/{entered_code}.json
    - فك تشفير Base64 وفك ضغط gzip
    - التحقق من سلامة قاعدة بيانات SQLite في ملف مؤقت
    - أخذ نسخة أمان قبل الاستبدال db.sqlite3.pre_restore_safety
    - استبدال ملف قاعدة البيانات الحالي
    """
    code_clean = str(entered_code or '').strip()
    if not code_clean:
        return False, "يرجى إدخال الرمز الإحصائي الوزاري للمدرسة."

    url = f"{FIREBASE_RTDB_URL}/backups/{code_clean}.json"

    try:
        req = urllib.request.Request(
            url,
            headers={
                'Accept': 'application/json',
                'User-Agent': 'Madrasati-CloudSync/2.0'
            }
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            content = resp.read().decode('utf-8')
            if not content or content == 'null':
                return False, f"لم يتم العثور على أي نسخة سحابية مطابقة للرمز الإحصائي ({code_clean}). تأكد من صحة الرمز."
            data = json.loads(content)

        if not isinstance(data, dict) or "backup_data" not in data:
            return False, f"البيانات السحابية للرمز ({code_clean}) غير صالحة أو لا تحتوي على نسخة قاعدة بيانات."

        encoded_data = data.get("backup_data", "")
        if not encoded_data:
            return False, "حزمة النسخة السحابية المسترجعة فارغة."

        # فك التشفير وفك الضغط
        raw_decoded = base64.b64decode(encoded_data)
        try:
            db_bytes = gzip.decompress(raw_decoded)
        except Exception:
            db_bytes = raw_decoded

        # التحقق من سلامة قاعدة البيانات
        temp_verify = tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite3')
        temp_verify_path = temp_verify.name
        temp_verify.write(db_bytes)
        temp_verify.close()

        try:
            chk_conn = sqlite3.connect(temp_verify_path)
            c = chk_conn.cursor()
            c.execute("PRAGMA integrity_check;")
            row = c.fetchone()
            if not row or row[0] != 'ok':
                chk_conn.close()
                os.remove(temp_verify_path)
                return False, "النسخة المسترجعة من السحابة تالفة وفشلت في فحص السلامة (Integrity Check)."

            c.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
            tbl_count = c.fetchone()[0]
            chk_conn.close()

            if tbl_count < 5:
                os.remove(temp_verify_path)
                return False, "قاعدة البيانات المسترجعة لا تحتوي على جداول المنظومة الأساسية."
        except Exception as e:
            try:
                os.remove(temp_verify_path)
            except Exception:
                pass
            return False, f"فشل فحص سلامة النسخة المسترجعة: {str(e)}"

        # استبدال قاعدة البيانات بأمان
        target_db_path = str(settings.DATABASES['default']['NAME'])
        os.makedirs(os.path.dirname(target_db_path), exist_ok=True)

        if os.path.exists(target_db_path):
            safety_backup = f"{target_db_path}.pre_restore_safety"
            try:
                import shutil
                shutil.copy2(target_db_path, safety_backup)
            except Exception:
                pass

        # إغلاق اتصالات دجانغو القديمة
        try:
            from django.db import connection
            connection.close()
        except Exception:
            pass

        # استبدال ملف قاعدة البيانات
        with open(target_db_path, 'wb') as out_f:
            out_f.write(db_bytes)

        try:
            os.remove(temp_verify_path)
        except Exception:
            pass

        school_name = data.get("school_name", "المدرسة")
        last_sync = data.get("last_sync", "غير محدد")

        # تحديث ملف الحالة محلياً
        _record_sync_status(True, f"تمت الاستعادة السحابية بنجاح لمدرسة ({school_name})", school_name, code_clean)

        return True, {
            "school_name": school_name,
            "ministry_school_code": code_clean,
            "last_sync": last_sync,
            "message": f"تمت استعادة كافة سجلات وبيانات مدرسة ({school_name}) بنجاح تام! تاريخ النسخة المسترجعة: {last_sync}."
        }

    except urllib.error.URLError as ue:
        return False, f"تعذر الاتصال بالسحابة (تأكد من اتصال الجهاز بالإنترنت): {ue.reason}"
    except Exception as e:
        return False, f"حدث خطأ أثناء عملية الاستعادة: {str(e)}"


def _record_sync_status(success, msg, school_name, ministry_code, orig_size=0, comp_size=0):
    """حفظ سجل الحالة محلياً"""
    record = {
        "last_attempt": timezone.now().strftime("%Y-%m-%d %I:%M %p"),
        "success": success,
        "message": msg,
        "school_name": school_name,
        "ministry_school_code": ministry_code,
        "original_size_kb": round(orig_size / 1024, 2) if orig_size else 0,
        "compressed_size_kb": round(comp_size / 1024, 2) if comp_size else 0
    }
    try:
        with open(SYNC_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def run_isolated_sync(is_manual=False):
    """تنفيذ النسخ المحلي والرفع السحابي الخلفي"""
    success, msg = create_daily_backup_snapshot()
    upload_cloud_backup_async()
    return success, msg
