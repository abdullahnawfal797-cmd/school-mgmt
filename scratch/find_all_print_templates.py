import os
import re
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

templates_dir = 'core/templates'
print_templates = []

for root, dirs, files in os.walk(templates_dir):
    for f in files:
        if f.endswith('.html') or f.endswith('.htm'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as tf:
                c = tf.read()
            if '@media print' in c or 'window.print' in c or '@page' in c:
                print_templates.append((path.replace('\\', '/'), '@media print' in c, '@page' in c, 'window.print' in c))

for p, mp, page, wp in print_templates:
    print(f"{p:55} | print_css: {str(mp):5} | @page: {str(page):5} | print_btn: {str(wp):5}")
