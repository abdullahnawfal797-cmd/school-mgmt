import re
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('core/templates/portal/base_portal.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if '{% url' in line or 'href="/portal/' in line:
        print(f"Line {idx+1}: {line.strip()}")
