import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.utils import timezone

def get_app_root_dir():
    """
    تحديد المسار الجذري الفعلي للبرنامج على أي حاسبة:
    سواء كان التطبيق مجمعاً كملف تنفيذي (.exe) أو يعمل ككود مصدري.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return str(settings.BASE_DIR)

def get_backup_dir():
    """
    الحصول على مجلد النسخ الاحتياطي الديناميكي التابع لموقع البرنامج على أي حاسبة:
    <مجلد البرنامج>/Backups/
    مع قابلية العمل على أي جهاز محمول أو مجلد يتم نسخ البرنامج إليه تلقائياً دون تثبيت مسار مستخدم معين.
    """
    app_dir = get_app_root_dir()
    backup_dir = os.path.join(app_dir, 'Backups')
    try:
        os.makedirs(backup_dir, exist_ok=True)
        test_file = os.path.join(backup_dir, '.perm_test')
        with open(test_file, 'w') as f:
            f.write('1')
        if os.path.exists(test_file):
            os.remove(test_file)
        return backup_dir
    except Exception:
        appdata = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or str(Path.home())
        backup_dir = os.path.join(appdata, 'Madrasati', 'Backups')
        os.makedirs(backup_dir, exist_ok=True)
        return backup_dir

def rotate_backups(backup_dir, max_keep=7):
    """
    تطبيق سياسة تدوير النسخ الاحتياطية التلقائية:
    الاحتفاظ بآخر 7 نسخ يومية فقط وحذف الأقدم لمنع تراكم الملفات.
    """
    try:
        if not os.path.exists(backup_dir):
            return

        files = []
        for fname in os.listdir(backup_dir):
            if fname.startswith("backup_") and (fname.endswith(".db") or fname.endswith(".sqlite3")):
                fpath = os.path.join(backup_dir, fname)
                try:
                    files.append((os.path.getmtime(fpath), fpath))
                except Exception:
                    pass

        # ترتيب من الأقدم إلى الأحدث
        files.sort(key=lambda x: x[0])

        # حذف النسخ الأقدم الزائدة عن 7
        while len(files) > max_keep:
            oldest = files.pop(0)
            try:
                os.remove(oldest[1])
            except Exception:
                pass
    except Exception:
        pass

def create_daily_backup_snapshot():
    """
    حفظ لقطة يومية باسم backup_YYYY_MM_DD.db تلقائياً
    باستخدام واجهة SQLite Online Backup API لضمان سلامة البيانات ومنع أي تلف
    مع الاحتفاظ بآخر 7 نسخ فقط.
    """
    try:
        backup_dir = get_backup_dir()
        today_str = timezone.now().strftime("%Y_%m_%d")
        dest_filename = f"backup_{today_str}.db"
        dest_path = os.path.join(backup_dir, dest_filename)

        db_path = str(settings.DATABASES['default']['NAME'])
        if not os.path.exists(db_path):
            return False, "ملف قاعدة البيانات الأساسي غير موجود."

        # إجراء النسخ الاحتياطي عبر محرك SQLite الحي بأمان تام
        src_conn = sqlite3.connect(db_path)
        dst_conn = sqlite3.connect(dest_path)
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

        # تدوير النسخ وحذف ما زاد عن آخر 7 نسخ
        rotate_backups(backup_dir, max_keep=7)

        file_size_kb = round(os.path.getsize(dest_path) / 1024, 2)
        return True, f"تم بنجاح حفظ اللقطة اليومية في ({dest_path}) بحجم {file_size_kb} KB."
    except Exception as e:
        return False, f"تعذر إنشاء اللقطة اليومية: {str(e)}"

def list_local_backups():
    """
    استعراض النسخ الاحتياطية المحفوظة محلياً في الخزنة
    """
    backup_dir = get_backup_dir()
    backups = []
    try:
        if os.path.exists(backup_dir):
            for fname in sorted(os.listdir(backup_dir), reverse=True):
                if fname.startswith("backup_") and (fname.endswith(".db") or fname.endswith(".sqlite3")):
                    fpath = os.path.join(backup_dir, fname)
                    try:
                        size_kb = round(os.path.getsize(fpath) / 1024, 2)
                        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                        backups.append({
                            'filename': fname,
                            'path': fpath,
                            'size_kb': size_kb,
                            'date': mtime.strftime('%Y/%m/%d - %I:%M %p')
                        })
                    except Exception:
                        pass
    except Exception:
        pass
    return backups

def get_removable_drives():
    """
    كشف محركات الأقراص المحمولة والفلاش ميموري (USB) المتصلة بالحاسوب على نظام Windows
    """
    drives = []
    if sys.platform == 'win32':
        try:
            import ctypes
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            DRIVE_REMOVABLE = 2
            DRIVE_FIXED = 3
            for letter in range(65, 91):  # A - Z
                if bitmask & (1 << (letter - 65)):
                    drive_str = f"{chr(letter)}:\\"
                    dtype = ctypes.windll.kernel32.GetDriveTypeW(drive_str)
                    if dtype == DRIVE_REMOVABLE:
                        drives.append({
                            'path': drive_str,
                            'label': f"فلاش ميموري USB ({chr(letter)}:)",
                            'is_usb': True
                        })
        except Exception:
            pass
    return drives

def safe_join(base_dir, user_input_path):
    """التحقق الصارم من مسار الملف ومنع ثغرات Path Traversal والوصول غير المصرح"""
    base = os.path.abspath(str(base_dir))
    target = os.path.abspath(os.path.join(base, str(user_input_path)))
    if not (target == base or target.startswith(base + os.sep)):
        raise ValueError("Access denied: Invalid file path")
    return target

def save_backup_to_usb(target_directory):
    """
    حفظ نسخة احتياطية مباشرة على فلاش ميموري USB أو مسار مخصص
    """
    try:
        if not target_directory:
            return False, "لم يتم تحديد مسار الفلاش ميموري أو القرص الخارجي."

        base_dir = os.path.abspath(target_directory.strip())
        target_path = safe_join(base_dir, "Madrasati_Backups")
        os.makedirs(target_path, exist_ok=True)

        timestamp = timezone.now().strftime("%Y_%m_%d_%H%M%S")
        dest_filename = f"backup_madrasati_{timestamp}.db"
        dest_file_path = safe_join(target_path, dest_filename)

        db_path = str(settings.DATABASES['default']['NAME'])
        if not os.path.exists(db_path):
            return False, "ملف قاعدة البيانات الأساسي غير موجود."

        src_conn = sqlite3.connect(db_path)
        dst_conn = sqlite3.connect(dest_file_path)
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

        size_kb = round(os.path.getsize(dest_file_path) / 1024, 2)
        return True, f"تم بنجاح حفظ النسخة الاحتياطية على الفلاش ميموري: ({dest_file_path}) بحجم {size_kb} KB."
    except Exception as e:
        return False, f"فشل الحفظ على الفلاش ميموري: {str(e)}"
