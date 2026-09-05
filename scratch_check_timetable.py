with open('core/templates/portal/timetable.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if any(k in line for k in ['portal_dashboard', 'total_classes }}', 'current_year', '01empty', 'openAddSlotModalDirect', 'deleteSlot', 'btn-outline-dark', 'text-dark']):
        print(f"{i+1}: {line.strip()[:100]}")
