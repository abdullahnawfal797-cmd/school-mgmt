import sys, os, django
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')
django.setup()

from core.cloud_sync import prepare_backup_package, get_school_sync_folder, run_isolated_sync

folder = get_school_sync_folder()
print(f"Isolated school folder: {folder}")

pkg, fn, meta = prepare_backup_package()
print(f"Package size: {len(pkg)} bytes, filename: {fn}, sha256: {meta['sha256'][:16]}...")

success, msg = run_isolated_sync(is_manual=True)
print(f"Run isolated sync test: success={success}, msg={msg}")
