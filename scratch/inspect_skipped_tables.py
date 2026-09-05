import re
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('core/templates/portal/records_manage.html', 'r', encoding='utf-8') as f:
    content = f.read()

table_blocks = re.findall(r'(<table\b.*?</table>)', content, re.DOTALL)
for idx, tbl in enumerate(table_blocks):
    if not ('page.students' in tbl or 'page.empty_rows' in tbl):
        print(f"Table {idx+1} is NOT using page.students/page.empty_rows:")
        print(tbl[:300])
        print("="*40)
