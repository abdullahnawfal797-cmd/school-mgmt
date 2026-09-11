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

# تفعيل صلاحيات تنزيل وحفظ ملفات الـ PDF والتقارير المدرسية والإكسل محلياً
try:
    webview.settings['ALLOW_DOWNLOADS'] = True
    webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = False
except Exception:
    pass

# الإصدار الحالي للتطبيق
CURRENT_VERSION = "2.2.0"
SINGLE_INSTANCE_MUTEX_NAME = "Madrasati_SingleInstance_Mutex_2026"
_mutex_handle = None

def acquire_single_instance_mutex():
    global _mutex_handle
    if sys.platform == 'win32':
        ERROR_ALREADY_EXISTS = 183
        _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX_NAME)
        last_err = ctypes.windll.kernel32.GetLastError()
        if last_err == ERROR_ALREADY_EXISTS:
            ctypes.windll.user32.MessageBoxW(
                0,
                "نظام مدرستي قيد التشغيل بالفعل على هذا الجهاز.\nلا يمكن تشغيل نسختين في نفس الوقت لحماية قاعدة البيانات.",
                "المنظومة قيد التشغيل",
                0x30 | 0x00100000 | 0x00080000
            )
            sys.exit(0)

def release_single_instance_mutex():
    global _mutex_handle
    if sys.platform == 'win32' and _mutex_handle:
        ctypes.windll.kernel32.CloseHandle(_mutex_handle)
        _mutex_handle = None

# ضبط المسار الحقيقي للتنفيذ سواء ككود عادي أو ملف مجمع PyInstaller
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    internal_dir = os.path.join(BASE_DIR, '_internal')
    if internal_dir not in sys.path:
        sys.path.insert(0, internal_dir)
    # ترتيب sys.meta_path لتقديم مستورد الملفات على المستورد المجمد في PyInstaller
    # هذا يضمن تحميل الملفات والمسارات البرمجية المحدثة والمرقعة من القرص فوراً
    for imp in list(sys.meta_path):
        if 'FrozenImporter' in imp.__class__.__name__ or 'pyimod02' in getattr(imp, '__module__', ''):
            sys.meta_path.remove(imp)
            sys.meta_path.append(imp)
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

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(('127.0.0.1', port)) == 0

def find_available_port(start_port=8000):
    for p in [start_port, 8001, 8002, 8080, 8888, 9000]:
        if not is_port_in_use(p):
            return p
    return start_port

PORT = find_available_port(8000)
URL = f"http://127.0.0.1:{PORT}/portal/"

server_error_message = None

def get_cloud_configuration():
    """
    قراءة رابط السحابة من عدة مصادر بالترتيب:
    1. وسيط سطر الأوامر (--cloud-url <url> أو --url <url>)
    2. متغير البيئة (MADRASATI_CLOUD_URL أو CLOUD_URL)
    3. ملف cloud_config.json في مجلد البرنامج أو مجلد البيانات
    4. ملف platform_link.json إذا كانت المدرسة مربوطة بالمنصة المركزية
    """
    # 1. وسيط سطر الأوامر
    for i, arg in enumerate(sys.argv):
        if arg in ('--cloud-url', '--url') and i + 1 < len(sys.argv):
            return sys.argv[i + 1].strip(), "cli"
        if arg.startswith('--cloud-url='):
            return arg.split('=', 1)[1].strip(), "cli"
        if arg.startswith('--url='):
            return arg.split('=', 1)[1].strip(), "cli"

    # 2. متغيرات البيئة
    env_url = os.getenv('MADRASATI_CLOUD_URL') or os.getenv('CLOUD_URL')
    if env_url and env_url.strip():
        return env_url.strip(), "env"

    # 3. ملف cloud_config.json
    data_dir = os.environ.get('LOCALAPPDATA')
    potential_paths = [
        os.path.join(BASE_DIR, 'cloud_config.json'),
        os.path.join(data_dir, 'Madrasati', 'cloud_config.json') if data_dir else None,
        os.path.join(data_dir, 'Madrasati', 'data', 'cloud_config.json') if data_dir else None,
    ]
    for cfg_path in potential_paths:
        if cfg_path and os.path.exists(cfg_path):
            try:
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    url = cfg.get('cloud_url') or cfg.get('url') or cfg.get('server_url')
                    enabled = cfg.get('enabled', True)
                    if enabled and url and isinstance(url, str) and url.strip():
                        return url.strip(), f"config:{os.path.basename(cfg_path)}"
            except Exception:
                pass

    # 4. ملف ربط المنصة platform_link.json
    link_paths = [
        os.path.join(BASE_DIR, 'platform_link.json'),
        os.path.join(data_dir, 'Madrasati', 'data', 'platform_link.json') if data_dir else None,
        os.path.join(data_dir, 'Madrasati', 'platform_link.json') if data_dir else None,
    ]
    for lp in link_paths:
        if lp and os.path.exists(lp):
            try:
                with open(lp, 'r', encoding='utf-8') as f:
                    link_data = json.load(f)
                    base = link_data.get('base_url')
                    if base and isinstance(base, str) and base.strip():
                        return base.strip(), "platform_link"
            except Exception:
                pass

    return None, None


def format_portal_url(raw_url):
    """صياغة وتنسيق الرابط لضمان توجيه المستخدم مباشرة إلى البوابة المدرسية /portal/"""
    url = raw_url.strip()
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    url = url.rstrip('/')
    
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if not parsed.path or parsed.path == '/':
        return f"{url}/portal/"
    if not url.endswith('/'):
        return f"{url}/"
    return url


def check_cloud_health(cloud_url, timeout=3.5):
    """التحقق السريع من إمكانية الوصول لرابط السحابة مع مهلة سريعة"""
    try:
        req = urllib.request.Request(
            cloud_url,
            headers={'User-Agent': 'Madrasati-Desktop-Client/3.1'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 301, 302, 307, 308, 401, 403)
    except Exception:
        return False

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
        time.sleep(5)
        from core.updates import (
            check_for_remote_updates,
            download_and_verify_update_package,
            create_pre_update_safety_backup,
            create_program_files_snapshot,
            launch_windows_external_installer
        )
        info = check_for_remote_updates()
        if info.get("has_update") and info.get("verified_manifest"):
            manifest = info["verified_manifest"]
            latest_version = manifest.get("version", CURRENT_VERSION)
            size_mb = manifest.get("file_size", 0) / (1024 * 1024)

            MB_YESNO = 0x00000004
            MB_ICONINFORMATION = 0x00000040
            MB_RTLREADING = 0x00100000
            MB_RIGHT = 0x00080000
            IDYES = 6

            msg = (
                f"يتوفر تحديث رسمي معتمد للمنظومة برقم ({latest_version}).\n"
                f"الإصدار المثبت حالياً: ({CURRENT_VERSION})\n"
                f"حجم التحديث: {size_mb:.2f} MB\n"
                f"التوقيع الرقمي: Ed25519 Verified 🛡️\n\n"
                f"ملاحظات: {manifest.get('release_notes', '')}\n\n"
                f"هل تريد تنزيل التحديث والتحقق التشفيري وتثبيته الآن؟"
            )
            title = "تحديث رسمي متوفر - منظومة مدرستي"

            user_response = ctypes.windll.user32.MessageBoxW(
                0, msg, title, MB_YESNO | MB_ICONINFORMATION | MB_RTLREADING | MB_RIGHT
            )

            if user_response == IDYES:
                # 1. Mandatory Pre-update safety backup
                bak_ok, bak_msg, _ = create_pre_update_safety_backup()
                if not bak_ok:
                    ctypes.windll.user32.MessageBoxW(0, f"تعذر إتمام التحديث: {bak_msg}", "إلغاء التحديث", 0x10)
                    return
                create_program_files_snapshot()

                # 2. Download and Cryptographic Verify
                dl_ok, dl_msg, verified_path = download_and_verify_update_package(manifest)
                if not dl_ok:
                    ctypes.windll.user32.MessageBoxW(0, f"فشل التحقق الأمني من حزمة التحديث:\n{dl_msg}", "تنبيه أمني", 0x10)
                    return

                # 3. Release single-instance mutex and launch installer
                release_single_instance_mutex()
                launch_windows_external_installer(verified_path, silent=True)
                time.sleep(0.6)
                os._exit(0)
    except Exception:
        pass

def on_closing():
    MB_YESNO = 0x00000004
    MB_ICONQUESTION = 0x00000020
    MB_RTLREADING = 0x00100000
    MB_RIGHT = 0x00080000
    IDYES = 6

    prompt_text = "هل تريد بالتأكيد إغلاق المنظومة المدرسية وحفظ السجلات والنسخ الاحتياطي؟"
    title_text = "تأكيد الخروج الآمن"

    res = ctypes.windll.user32.MessageBoxW(
        0, prompt_text, title_text,
        MB_YESNO | MB_ICONQUESTION | MB_RTLREADING | MB_RIGHT
    )
    if res == IDYES:
        try:
            from core.backup_vault import create_daily_backup_snapshot, get_removable_drives, save_backup_to_usb
            create_daily_backup_snapshot()
            drives = get_removable_drives()
            if drives:
                save_backup_to_usb(drives[0])
        except Exception:
            pass
        release_single_instance_mutex()
        return True
    return False

if __name__ == '__main__':
    # 0. فحص قفل التشغيل الأحادي لمنع تشغيل نسختين في وقت واحد
    acquire_single_instance_mutex()

    # 1. فحص إمكانية التشغيل السحابي المباشر
    cloud_url_raw, cloud_source = get_cloud_configuration()
    force_local = '--local-only' in sys.argv or '--force-local' in sys.argv
    force_cloud = '--cloud-only' in sys.argv or '--force-cloud' in sys.argv

    target_url = None
    is_cloud_active = False

    if cloud_url_raw and not force_local:
        candidate_url = format_portal_url(cloud_url_raw)
        print(f"[DesktopRunner] تم اكتشاف رابط السحابة ({cloud_source}): {candidate_url}")
        cloud_ok = check_cloud_health(candidate_url, timeout=4.0)
        if cloud_ok:
            target_url = candidate_url
            is_cloud_active = True
            print(f"[DesktopRunner] الاتصال بالسحابة ممتاز ☁️ -> تم تفعيل وضع الاتصال السحابي المباشر.")
        elif force_cloud:
            ctypes.windll.user32.MessageBoxW(
                0,
                f"تعذر الاتصال بالسيرفر السحابي المباشر:\n{candidate_url}\n\nيرجى التأكد من اتصال الإنترنت أو جاهزية الخادم السحابي.",
                "فشل الاتصال بالسحابة",
                0x10 | 0x00100000 | 0x00080000
            )
            release_single_instance_mutex()
            sys.exit(1)
        else:
            print(f"[DesktopRunner] تعذر الوصول للرابط السحابي ({candidate_url}). سيتم التبديل التلقائي للوضع المحلي (Offline Fallback)...")

    # 2. في حال عدم تفعيل السحابة، يتم إطلاق خادم الويب المحلي
    if not is_cloud_active:
        server_thread = threading.Thread(target=start_django_server, daemon=True)
        server_thread.start()

        # انتظار تحقق الاتصال
        ready = wait_for_server()
        if not ready:
            err_msg = server_error_message if server_error_message else "تعذر بدء السيرفر الداخلي على المنفذ 8000."
            ctypes.windll.user32.MessageBoxW(0, f"تنبيه تشغيل النظام:\n{err_msg}", "خطأ في السيرفر", 0x10)
            release_single_instance_mutex()
            sys.exit(1)

        target_url = f"http://127.0.0.1:{PORT}/portal/"
        print(f"[DesktopRunner] تم تشغيل السيرفر المحلي بنجاح: {target_url}")

    # 3. إطلاق خيط فحص التحديثات
    update_thread = threading.Thread(target=check_for_updates, daemon=True)
    update_thread.start()

    if '--server-only' in sys.argv:
        print(f"SERVER_READY_PORT:{PORT}", flush=True)
        try:
            while True:
                time.sleep(0.5)
        except (KeyboardInterrupt, SystemExit):
            pass
        release_single_instance_mutex()
        sys.exit(0)

    # 4. فتح واجهة التطبيق
    app_title = 'نظام الإدارة المدرسية الحديث (متصل بالسحابة ☁️)' if is_cloud_active else 'نظام الإدارة المدرسية الحديث'
    window = webview.create_window(
        title=app_title,
        url=target_url,
        width=1280,
        height=850,
        min_size=(1024, 700),
        resizable=True,
        confirm_close=False
    )

    window.events.closing += on_closing
    webview.start()
    release_single_instance_mutex()
    sys.exit(0)