import re
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('core/templates/portal/records_manage.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all blocks between {% if record_type == ... %} and {% elif ... %}
sections = re.split(r'{%\s*(?:elif|if)\s+record_type\s*==\s*[\'"]([^\'"]+)[\'"](?:\s+or\s+record_type\s*==\s*[\'"]([^\'"]+)[\'"])?\s*%}', content)

# sections structure: [preamble, rt1, rt1_alt, body1, rt2, rt2_alt, body2, ...]
# Let's parse systematically
table_blocks = re.findall(r'(<table\b.*?</table>)', content, re.DOTALL)
print(f"Total <table> elements in records_manage.html: {len(table_blocks)}")

mismatches = []

for idx, tbl in enumerate(table_blocks):
    # Check if this table has page.students or page.empty_rows
    if 'page.students' in tbl or 'page.empty_rows' in tbl or 'empty_rows' in tbl:
        # Count thead ths
        thead_match = re.search(r'<thead\b.*?</thead>', tbl, re.DOTALL)
        thead_cols = 0
        if thead_match:
            th_tags = re.findall(r'<th\b([^>]*)>(.*?)</th>', thead_match.group(0), re.DOTALL)
            for attrs, _ in th_tags:
                colspan_m = re.search(r'colspan=[\'"]?(\d+)[\'"]?', attrs)
                if colspan_m:
                    thead_cols += int(colspan_m.group(1))
                else:
                    thead_cols += 1
        
        # Count student row tds
        st_row_cols = 0
        st_match = re.search(r'{%\s*for\s+st\s+in\s+page\.students\s*%}(.*?){%\s*endfor\s*%}', tbl, re.DOTALL)
        if st_match:
            td_tags = re.findall(r'<td\b([^>]*)>', st_match.group(1))
            for attrs in td_tags:
                colspan_m = re.search(r'colspan=[\'"]?(\d+)[\'"]?', attrs)
                if colspan_m:
                    st_row_cols += int(colspan_m.group(1))
                else:
                    st_row_cols += 1

        # Count empty row tds
        empty_row_cols = 0
        empty_match = re.search(r'{%\s*for\s+[^%]+in\s+page\.empty_rows\s*%}(.*?){%\s*endfor\s*%}', tbl, re.DOTALL)
        if empty_match:
            td_tags = re.findall(r'<td\b([^>]*)>', empty_match.group(1))
            for attrs in td_tags:
                colspan_m = re.search(r'colspan=[\'"]?(\d+)[\'"]?', attrs)
                if colspan_m:
                    empty_row_cols += int(colspan_m.group(1))
                else:
                    empty_row_cols += 1

        print(f"Table {idx+1:2d}: thead={thead_cols:2d}, student_tds={st_row_cols:2d}, empty_tds={empty_row_cols:2d}")
        if st_row_cols != empty_row_cols:
            mismatches.append((idx+1, st_row_cols, empty_row_cols, "student != empty"))
        if thead_cols > 0 and st_row_cols > 0 and thead_cols != st_row_cols:
            # Note: thead could have multi-row headers so sum of ths could be different if multi-tier
            pass

if mismatches:
    print(f"\nMISMATCHES FOUND ({len(mismatches)}):")
    for m in mismatches:
        print("  Table", m)
else:
    print("\nALL PRINT TABLES HAVE 100% MATCHING COLUMN COUNTS BETWEEN STUDENT ROWS AND EMPTY ROWS!")
