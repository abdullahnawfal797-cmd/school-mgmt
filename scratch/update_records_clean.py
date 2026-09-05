import re

path = 'core/templates/portal/records_manage.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Top bar: add PDF download button
old_top_btn = '''<div class="d-flex gap-2">
        <button type="button" onclick="window.print()" class="btn btn-success rounded-pill px-4 fw-bold shadow-sm">
            <i class="bi bi-printer-fill me-1"></i> طباعة القائمة
        </button>'''

new_top_btn = '''<div class="d-flex gap-2">
        <button type="button" onclick="window.print()" class="btn btn-danger rounded-pill px-4 fw-bold shadow-sm">
            <i class="bi bi-file-earmark-pdf-fill me-1"></i> تحميل نسخة PDF
        </button>
        <button type="button" onclick="window.print()" class="btn btn-success rounded-pill px-4 fw-bold shadow-sm">
            <i class="bi bi-printer-fill me-1"></i> طباعة القائمة
        </button>'''

if old_top_btn in content:
    content = content.replace(old_top_btn, new_top_btn, 1)
    print("1. Top button updated.")
else:
    print("1. Top button already updated or not found.")

# 2. CSS: Enforce white headers
old_css_th = '''.table-oral th,
    .table-oral td,
    .table-official th,
    .table-official td,
    .table-admin-grades th,
    .table-admin-grades td {
        border: 1.5px solid #000000;
        padding: 2px 1px;
        vertical-align: middle;
    }'''

new_css_th = '''.table-oral th,
    .table-oral td,
    .table-official th,
    .table-official td,
    .table-admin-grades th,
    .table-admin-grades td {
        border: 1.5px solid #000000;
        padding: 2px 1px;
        vertical-align: middle;
        background-color: #FFFFFF !important;
        color: #000000 !important;
    }

    .table-oral thead th,
    .table-official thead th,
    .table-admin-grades thead th {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        font-weight: bold !important;
        border: 1.5px solid #000000 !important;
    }'''

if old_css_th in content:
    content = content.replace(old_css_th, new_css_th, 1)
    print("2. CSS updated.")

# 3. master_exam_sheet
old_master_th = '''                        <th style="width: 4%;">ت</th>
                        <th style="width: 8%;">القيد</th>
                        <th style="width: 22%;">اسم التلميذ</th>'''

new_master_th = '''                        <th style="width: 4%;">ت</th>
                        <th style="width: 30%;">اسم التلميذ</th>'''

old_master_td = '''                        <td class="font-monospace">{{ forloop.counter }}</td>
                        <td class="font-monospace">{{ st.registration_number|default:"" }}</td>
                        <td class="text-start ps-2">{{ st.full_name|default:st.user.username }}</td>'''

new_master_td = '''                        <td class="font-monospace">{{ forloop.counter }}</td>
                        <td class="text-start ps-2">{{ st.full_name|default:st.user.username }}</td>'''

old_master_empty_td = '''                        <td class="font-monospace">{{ r }}</td>
                        <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'''

new_master_empty_td = '''                        <td class="font-monospace">{{ r }}</td>
                        <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'''

if old_master_th in content:
    content = content.replace(old_master_th, new_master_th, 1)
    content = content.replace(old_master_td, new_master_td, 1)
    content = content.replace(old_master_empty_td, new_master_empty_td, 1)
    print("3. master_exam_sheet updated.")

# 4. dual_science_sheet
old_dual_sci_th = '''                        <th style="width: 4%;">ت</th>
                        <th style="width: 7%;">القيد</th>
                        <th style="width: 25%;">اسم التلميذ</th>
                        <th style="width: 14%;">
                            <div>الدرجة</div>
                            <div class="d-flex border-top border-dark mt-1">
                                <div style="width: 45%;" class="border-start border-dark">رقماً</div>
                                <div style="width: 55%;">كتابة</div>
                            </div>
                        </th>
                        <th style="width: 4%;">ت</th>
                        <th style="width: 7%;">القيد</th>
                        <th style="width: 25%;">اسم التلميذ</th>
                        <th style="width: 14%;">'''

new_dual_sci_th = '''                        <th style="width: 5%;">ت</th>
                        <th style="width: 31%;">اسم التلميذ</th>
                        <th style="width: 14%;">
                            <div>الدرجة</div>
                            <div class="d-flex border-top border-dark mt-1">
                                <div style="width: 45%;" class="border-start border-dark">رقماً</div>
                                <div style="width: 55%;">كتابة</div>
                            </div>
                        </th>
                        <th style="width: 5%;">ت</th>
                        <th style="width: 31%;">اسم التلميذ</th>
                        <th style="width: 14%;">'''

old_dual_sci_td = '''                        <td class="font-monospace">{{ left_idx }}</td>
                        <td style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 55px; font-size: 11px;" class="font-monospace">
                            {% for st in sec_item.students %}
                                {% if forloop.counter == left_idx %}{{ st.registration_number|default:"" }}{% endif %}
                            {% endfor %}
                        </td>
                        <td class="text-start ps-1" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            {% for st in sec_item.students %}
                                {% if forloop.counter == left_idx %}{{ st.full_name|default:st.user.username }}{% endif %}
                            {% endfor %}
                        </td>
                        <td class="p-0">
                            <div class="d-flex h-100">
                                <div style="width: 45%; height: 25px;" class="border-start border-dark"></div>
                                <div style="width: 55%; height: 25px;"></div>
                            </div>
                        </td>
                        <td class="font-monospace">{% if right_idx <= 33 %}{{ right_idx }}{% endif %}</td>
                        <td style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 55px; font-size: 11px;" class="font-monospace">
                            {% if right_idx <= 33 %}
                            {% for st in sec_item.students %}
                                {% if forloop.counter == right_idx %}{{ st.registration_number|default:"" }}{% endif %}
                            {% endfor %}
                            {% endif %}
                        </td>
                        <td class="text-start ps-1" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">'''

new_dual_sci_td = '''                        <td class="font-monospace">{{ left_idx }}</td>
                        <td class="text-start ps-1" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            {% for st in sec_item.students %}
                                {% if forloop.counter == left_idx %}{{ st.full_name|default:st.user.username }}{% endif %}
                            {% endfor %}
                        </td>
                        <td class="p-0">
                            <div class="d-flex h-100">
                                <div style="width: 45%; height: 25px;" class="border-start border-dark"></div>
                                <div style="width: 55%; height: 25px;"></div>
                            </div>
                        </td>
                        <td class="font-monospace">{% if right_idx <= 33 %}{{ right_idx }}{% endif %}</td>
                        <td class="text-start ps-1" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">'''

if old_dual_sci_th in content:
    content = content.replace(old_dual_sci_th, new_dual_sci_th, 1)
    content = content.replace(old_dual_sci_td, new_dual_sci_td, 1)
    print("4. dual_science_sheet updated.")

# 5. dual_art_sheet
old_dual_art_th = '''                        <th style="width: 4%;">ت</th>
                        <th style="width: 7%;">القيد</th>
                        <th style="width: 23%;">اسم التلميذ</th>
                        <th style="width: 8%;">فنية (7)</th>
                        <th style="width: 8%;">نشيد (3)</th>
                        <th style="width: 8%;">المجموع</th>
                        <th style="width: 4%;">ت</th>
                        <th style="width: 7%;">القيد</th>
                        <th style="width: 23%;">اسم التلميذ</th>'''

new_dual_art_th = '''                        <th style="width: 5%;">ت</th>
                        <th style="width: 29%;">اسم التلميذ</th>
                        <th style="width: 8%;">فنية (7)</th>
                        <th style="width: 8%;">نشيد (3)</th>
                        <th style="width: 8%;">المجموع</th>
                        <th style="width: 5%;">ت</th>
                        <th style="width: 29%;">اسم التلميذ</th>'''

old_dual_art_td = '''                        <td class="font-monospace">{{ left_idx }}</td>
                        <td style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 55px; font-size: 11px;" class="font-monospace">
                            {% for st in sec_item.students %}{% if forloop.counter == left_idx %}{{ st.registration_number|default:"" }}{% endif %}{% endfor %}
                        </td>
                        <td class="text-start ps-1" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            {% for st in sec_item.students %}{% if forloop.counter == left_idx %}{{ st.full_name|default:st.user.username }}{% endif %}{% endfor %}
                        </td>
                        <td></td><td></td><td></td>
                        <td class="font-monospace">{% if right_idx <= 33 %}{{ right_idx }}{% endif %}</td>
                        <td style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 55px; font-size: 11px;" class="font-monospace">
                            {% if right_idx <= 33 %}
                            {% for st in sec_item.students %}{% if forloop.counter == right_idx %}{{ st.registration_number|default:"" }}{% endif %}{% endfor %}
                            {% endif %}
                        </td>
                        <td class="text-start ps-1" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">'''

new_dual_art_td = '''                        <td class="font-monospace">{{ left_idx }}</td>
                        <td class="text-start ps-1" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            {% for st in sec_item.students %}{% if forloop.counter == left_idx %}{{ st.full_name|default:st.user.username }}{% endif %}{% endfor %}
                        </td>
                        <td></td><td></td><td></td>
                        <td class="font-monospace">{% if right_idx <= 33 %}{{ right_idx }}{% endif %}</td>
                        <td class="text-start ps-1" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">'''

if old_dual_art_th in content:
    content = content.replace(old_dual_art_th, new_dual_art_th, 1)
    content = content.replace(old_dual_art_td, new_dual_art_td, 1)
    print("5. dual_art_sheet updated.")

# 6. single_islamic
old_islamic_th = '''                        <th rowspan="2" style="width: 4%;">ت</th>
                        <th rowspan="2" style="width: 8%;">رقم القيد</th>
                        <th rowspan="2" style="width: 25%;">اسم التلميذ</th>'''

new_islamic_th = '''                        <th rowspan="2" style="width: 4%;">ت</th>
                        <th rowspan="2" style="width: 33%;">اسم التلميذ</th>'''

old_islamic_td = '''                        <td class="font-monospace">{{ forloop.counter }}</td>
                        <td class="font-monospace">{{ st.registration_number|default:"" }}</td>
                        <td class="text-start ps-2">{{ st.full_name|default:st.user.username }}</td>'''

new_islamic_td = '''                        <td class="font-monospace">{{ forloop.counter }}</td>
                        <td class="text-start ps-2">{{ st.full_name|default:st.user.username }}</td>'''

old_islamic_empty_td = '''                        <td class="font-monospace">{{ r }}</td>
                        <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'''

new_islamic_empty_td = '''                        <td class="font-monospace">{{ r }}</td>
                        <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'''

if old_islamic_th in content:
    content = content.replace(old_islamic_th, new_islamic_th, 1)
    content = content.replace(old_islamic_td, new_islamic_td, 1)
    content = content.replace(old_islamic_empty_td, new_islamic_empty_td, 1)
    print("6. single_islamic updated.")

# 7. single_sports
old_sports_th = '''                        <th rowspan="2" style="width: 4%;">ت</th>
                        <th rowspan="2" style="width: 7%;">رقم القيد</th>
                        <th rowspan="2" style="width: 24%;">اسم التلميذ</th>'''

new_sports_th = '''                        <th rowspan="2" style="width: 4%;">ت</th>
                        <th rowspan="2" style="width: 31%;">اسم التلميذ</th>'''

old_sports_td = '''                        <td class="font-monospace">{{ forloop.counter }}</td>
                        <td class="font-monospace">{{ st.registration_number|default:"" }}</td>
                        <td class="text-start ps-2">{{ st.full_name|default:st.user.username }}</td>
                        <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'''

new_sports_td = '''                        <td class="font-monospace">{{ forloop.counter }}</td>
                        <td class="text-start ps-2">{{ st.full_name|default:st.user.username }}</td>
                        <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'''

old_sports_empty_td = '''                        <td class="font-monospace">{{ r }}</td>
                        <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'''

new_sports_empty_td = '''                        <td class="font-monospace">{{ r }}</td>
                        <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'''

if old_sports_th in content:
    content = content.replace(old_sports_th, new_sports_th, 1)
    content = content.replace(old_sports_td, new_sports_td, 1)
    content = content.replace(old_sports_empty_td, new_sports_empty_td, 1)
    print("7. single_sports updated.")

# 8. single_math
old_math_th = '''                        <th rowspan="2" style="width: 4%;">ت</th>
                        <th rowspan="2" style="width: 8%;">رقم القيد</th>
                        <th rowspan="2" style="width: 28%;">اسم التلميذ</th>'''

new_math_th = '''                        <th rowspan="2" style="width: 4%;">ت</th>
                        <th rowspan="2" style="width: 36%;">اسم التلميذ</th>'''

old_math_td = '''                        <td class="font-monospace">{{ forloop.counter }}</td>
                        <td class="font-monospace">{{ st.registration_number|default:"" }}</td>
                        <td class="text-start ps-2">{{ st.full_name|default:st.user.username }}</td>'''

new_math_td = '''                        <td class="font-monospace">{{ forloop.counter }}</td>
                        <td class="text-start ps-2">{{ st.full_name|default:st.user.username }}</td>'''

old_math_empty_td = '''                        <td class="font-monospace">{{ r }}</td>
                        <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'''

new_math_empty_td = '''                        <td class="font-monospace">{{ r }}</td>
                        <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'''

if old_math_th in content:
    content = content.replace(old_math_th, new_math_th, 1)
    content = content.replace(old_math_td, new_math_td, 1)
    content = content.replace(old_math_empty_td, new_math_empty_td, 1)
    print("8. single_math updated.")

# 9. single_science_oral
old_sci_oral_th = '''                        <th rowspan="2" style="width: 4%;">ت</th>
                        <th rowspan="2" style="width: 8%;">رقم القيد</th>
                        <th rowspan="2" style="width: 28%;">اسم التلميذ</th>'''

new_sci_oral_th = '''                        <th rowspan="2" style="width: 4%;">ت</th>
                        <th rowspan="2" style="width: 36%;">اسم التلميذ</th>'''

if old_sci_oral_th in content:
    content = content.replace(old_sci_oral_th, new_sci_oral_th, 1)
    content = content.replace(old_math_td, new_math_td, 1)
    content = content.replace(old_math_empty_td, new_math_empty_td, 1)
    print("9. single_science_oral updated.")

# 10. english_arabic_labels
old_eng_th = '''                        <th rowspan="2" style="width: 4%;">ت</th>
                        <th rowspan="2" style="width: 8%;">رقم القيد</th>
                        <th rowspan="2" style="width: 28%;">اسم التلميذ</th>'''

new_eng_th = '''                        <th rowspan="2" style="width: 4%;">ت</th>
                        <th rowspan="2" style="width: 36%;">اسم التلميذ</th>'''

if old_eng_th in content:
    content = content.replace(old_eng_th, new_eng_th, 1)
    content = content.replace(old_math_td, new_math_td, 1)
    content = content.replace(old_math_empty_td, new_math_empty_td, 1)
    print("10. english_arabic_labels updated.")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("All updates to records_manage.html completed!")
