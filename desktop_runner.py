import os
import sys
import time
import json
import threading
import socket
import ctypes
import subprocess
import urllib.request
import tempfile
import webview

# الإصدار الحالي للتطبيق
CURRENT_VERSION = "1.0.0"
VERSION_CHECK_URL = "https://raw.githubusercontent.com/abdullahnawfal797-cmd/school-mgmt/main/version.json"

# ضبط المسار الحقيقي للتنفيذ سواء ككود عادي أو ملف مجمع PyInstaller
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('iraq.school.mgmt.system.2026')
except Exception:
    pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')

PORT = 8000
URL = f"http://127.0.0.1:{PORT}/portal/"

server_error_message = None

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_django_server():
    global server_error_message
    try:
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')
        django.setup()

        # التأكد من هجرة البيانات بهدوء
        try:
            from django.core.management import call_command
            call_command('migrate', interactive=False)
        except Exception:
            pass

        from django.core.wsgi import get_wsgi_application
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from waitress import serve

        app = StaticFilesHandler(get_wsgi_application())
        serve(app, host='127.0.0.1', port=PORT, threads=6, _quiet=True)
    except Exception:
        import traceback
        server_error_message = traceback.format_exc()

def wait_for_server():
    """الانتظار الصارم حتى يصبح المنفذ جاهزاً 100%"""
    for _ in range(80):  # مهلة كافية
        if server_error_message:
            return False
        if is_port_in_use(PORT):
            time.sleep(0.4)
            return True
        time.sleep(0.2)
    return False

def check_for_updates():
    try:
        time.sleep(4)
        req = urllib.request.Request(VERSION_CHECK_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            latest_version = data.get("version", CURRENT_VERSION)
            download_url = data.get("download_url", "")

            if latest_version > CURRENT_VERSION and download_url:
                MB_YESNO = 0x00000004
                MB_ICONINFORMATION = 0x00000040
                MB_RTLREADING = 0x00100000
                MB_RIGHT = 0x00080000
                IDYES = 6

                msg = f"يتوفر تحديث جديد للمنظومة برقم ({latest_version}).\nالإصدار الحالي: ({CURRENT_VERSION})\n\nهل تريد تنزيل التحديث وتثبيته الآن؟"
                title = "تحديث جديد متوفر"

                user_response = ctypes.windll.user32.MessageBoxW(
                    0, msg, title, MB_YESNO | MB_ICONINFORMATION | MB_RTLREADING | MB_RIGHT
                )

                if user_response == IDYES:
                    installer_path = os.path.join(tempfile.gettempdir(), "Madrasati_Update.exe")
                    urllib.request.urlretrieve(download_url, installer_path)
                    subprocess.Popen([installer_path, "/SILENT"])
                    time.sleep(0.5)
                    os._exit(0)
    except Exception:
        pass

def on_closing():
    MB_YESNO = 0x00000004
    MB_ICONQUESTION = 0x00000020
    MB_RTLREADING = 0x00100000
    MB_RIGHT = 0x00080000
    IDYES = 6

    prompt_text = "هل تريد بالتأكيد إغلاق المنظومة المدرسية وحفظ السجلات؟"
    title_text = "تأكيد الخروج"

    res = ctypes.windll.user32.MessageBoxW(
        0, prompt_text, title_text,
        MB_YESNO | MB_ICONQUESTION | MB_RTLREADING | MB_RIGHT
    )
    if res == IDYES:
        try:
            from core.backup_vault import create_daily_backup_snapshot
            create_daily_backup_snapshot()
        except Exception:
            pass
        return True
    return False

if __name__ == '__main__':
    # 1. إطلاق خادم الويب في الخلفية
    server_thread = threading.Thread(target=start_django_server, daemon=True)
    server_thread.start()

    # 2. انتظار تحقق الاتصال
    ready = wait_for_server()

    # إذا حدث انهيار للسيرفر يتم إيقاف العملية وإظهار تفاصيل الخطأ بدقة
    if not ready:
        err_msg = server_error_message if server_error_message else "تعذر بدء السيرفر الداخلي على المنفذ 8000."
        ctypes.windll.user32.MessageBoxW(0, f"تنبيه تشغيل النظام:\n{err_msg}", "خطأ في السيرفر", 0x10)
        sys.exit(1)

    # 3. إطلاق خيط فحص التحديثات
    update_thread = threading.Thread(target=check_for_updates, daemon=True)
    update_thread.start()

    # 4. فتح واجهة التطبيق
    window = webview.create_window(
        title='نظام الإدارة المدرسية الحديث',
        url=URL,
        width=1280,
        height=850,
        min_size=(1024, 700),
        resizable=True,
        confirm_close=False
    )

    window.events.closing += on_closing
    webview.start()
    sys.exit(0)