import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import re

files_to_check = [
    'core/templates/portal/records_manage.html',
    'core/templates/portal/exam_attendance_print.html',
    'core/templates/portal/general_registry.html',
    'core/templates/portal/letter_builder.html',
    'core/templates/certificates/base_doc.html',
    'core/templates/portal/exam_labels_print.html',
    'core/templates/portal/official_archive.html',
    'core/templates/portal/timetable.html'
]

for fp in files_to_check:
    with open(fp, 'r', encoding='utf-8') as f:
        c = f.read()
    page_m = re.search(r'@page\s*{([^}]+)}', c)
    page_style = page_m.group(1).replace('\n', ' ').strip() if page_m else "NONE"
    
    # Check font family
    font_m = re.findall(r'font-family:[^;]+;', c)
    print(f"File: {fp}")
    print(f"  @page: {page_style}")
    print(f"  Fonts sample: {list(set(font_m))[:3]}")
    print("-" * 50)
