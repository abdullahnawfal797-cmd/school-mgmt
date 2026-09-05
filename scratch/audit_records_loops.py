import re

with open('core/templates/portal/records_manage.html', 'r', encoding='utf-8') as f:
    content = f.read()

matches = re.findall(r'{%\s*(?:elif|if)\s+record_type\s*==\s*[\'"]([^\'"]+)[\'"]\s*%}', content)
print('Found records count:', len(matches))
print('Records:', matches)

for r in matches:
    start = content.find(f"'{r}'")
    if start == -1:
        start = content.find(f'"{r}"')
    # Find next elif or endif
    next_pos = len(content)
    for next_r in matches:
        if next_r != r:
            p = content.find(f"'{next_r}'", start + 10)
            if p != -1 and p < next_pos:
                next_pos = p
    block = content[start:next_pos]
    loops = re.findall(r'{%\s*for\s+([^%]+)%}', block)
    print(f"\n--- Record: {r} ---")
    for l in loops:
        print("  loop:", l.strip())
