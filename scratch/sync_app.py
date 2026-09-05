import os
import shutil

src_root = r"c:\Users\abdul\OneDrive\سطح المكتب\school momo\school-mgmt-main"
dest_roots = [
    r"C:\Users\abdul\AppData\Local\Madrasati\_internal",
    r"c:\Users\abdul\OneDrive\سطح المكتب\school momo\school-mgmt-main\dist\Madrasati\_internal"
]

files_to_sync = [
    ('core/views.py', 'core/views.py'),
    ('core/urls.py', 'core/urls.py'),
    ('core/pdf_generator.py', 'core/pdf_generator.py'),
    ('core/licensing.py', 'core/licensing.py'),
    ('core/cloud_sync.py', 'core/cloud_sync.py'),
    ('core/backup_vault.py', 'core/backup_vault.py'),
    ('core/apps.py', 'core/apps.py'),
    ('core/context_processors.py', 'core/context_processors.py'),
    ('core/middleware.py', 'core/middleware.py'),
    ('core/models.py', 'core/models.py'),
    ('school_mgmt/settings.py', 'school_mgmt/settings.py'),
    ('desktop_runner.py', 'desktop_runner.py'),
]

dirs_to_sync = [
    ('core/templates', 'core/templates'),
    ('core/migrations', 'core/migrations'),
    ('core/static', 'core/static'),
    ('static', 'static'),
    ('staticfiles', 'staticfiles'),
]

for dest_root in dest_roots:
    if not os.path.exists(dest_root):
        print(f"Skipping non-existent dest: {dest_root}")
        continue
    print(f"\n--- Syncing to: {dest_root} ---")
    
    for rel_src, rel_dest in files_to_sync:
        s_path = os.path.join(src_root, rel_src)
        d_path = os.path.join(dest_root, rel_dest)
        if os.path.exists(s_path):
            os.makedirs(os.path.dirname(d_path), exist_ok=True)
            shutil.copy2(s_path, d_path)
            print(f"Copied file: {rel_src} -> {d_path}")
            
    for rel_src, rel_dest in dirs_to_sync:
        s_path = os.path.join(src_root, rel_src)
        d_path = os.path.join(dest_root, rel_dest)
        if os.path.exists(s_path):
            shutil.copytree(s_path, d_path, dirs_exist_ok=True)
            print(f"Synced dir: {rel_src} -> {d_path}")

print("\nSync completed successfully!")
