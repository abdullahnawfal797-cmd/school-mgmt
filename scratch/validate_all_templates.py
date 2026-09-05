import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')

import django
django.setup()

from django.template.loader import get_template
from django.conf import settings

templates_dir = os.path.join(settings.BASE_DIR, 'core', 'templates')
print(f"Scanning templates directory: {templates_dir}")

errors = []
success_count = 0

for root, dirs, files in os.walk(templates_dir):
    for f in files:
        if f.endswith('.html') or f.endswith('.htm'):
            rel_path = os.path.relpath(os.path.join(root, f), templates_dir)
            template_name = rel_path.replace('\\', '/')
            try:
                t = get_template(template_name)
                success_count += 1
            except Exception as e:
                errors.append((template_name, str(e)))

print(f"Successfully compiled: {success_count} templates.")
if errors:
    print(f"ERRORS FOUND IN {len(errors)} TEMPLATES:")
    for t_name, err in errors:
        print(f"  [ERROR] {t_name}: {err}")
else:
    print("ALL TEMPLATES COMPILED WITH ZERO SYNTAX ERRORS!")
