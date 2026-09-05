import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import re

with open('core/templates/portal/records_manage.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if 'sec_item.students' in line:
        print(f"Line {idx+1}: {line.strip()}")
