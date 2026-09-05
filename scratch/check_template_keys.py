import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import re

with open('core/templates/portal/records_manage.html', 'r', encoding='utf-8') as f:
    content = f.read()

page_vars = re.findall(r'page\.([a-zA-Z0-9_]+)', content)
print("Keys used on 'page' in records_manage.html:", set(page_vars))

sec_vars = re.findall(r'sec_item\.([a-zA-Z0-9_]+)', content)
print("Keys used on 'sec_item' in records_manage.html:", set(sec_vars))
