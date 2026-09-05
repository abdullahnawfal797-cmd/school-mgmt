import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('core/templates/portal/records_manage.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

for idx, line in enumerate(lines):
    if '{% if record_type' in line or '{% elif record_type' in line:
        print(f"Line {idx+1}: {line.strip()}")
