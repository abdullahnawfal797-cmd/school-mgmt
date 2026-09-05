import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('core/templates/portal/records_manage.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Check for javascript blocks
import re
scripts = re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
print(f"Found {len(scripts)} script tags in records_manage.html")

# Check for missing closing tags or common Django template syntax issues
tag_stack = []
tokens = re.findall(r'{%\s*(if|elif|else|endif|for|empty|endfor|block|endblock)\b([^%]*)%}', content)
print(f"Total template tags found: {len(tokens)}")

if_count = 0
for_count = 0
block_count = 0
for tag, arg in tokens:
    if tag == 'if':
        if_count += 1
    elif tag == 'endif':
        if_count -= 1
    elif tag == 'for':
        for_count += 1
    elif tag == 'endfor':
        for_count -= 1
    elif tag == 'block':
        block_count += 1
    elif tag == 'endblock':
        block_count -= 1

print(f"Unclosed if tags: {if_count}")
print(f"Unclosed for tags: {for_count}")
print(f"Unclosed block tags: {block_count}")
