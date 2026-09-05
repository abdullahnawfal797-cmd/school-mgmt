import re

path = 'core/templates/portal/exam_halls.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove target="_blank"
content = re.sub(r'<a\s+href="([^"]+)"\s+target="_blank"', r'<a href="\1"', content)
print("1. target='_blank' removed from exam_halls.html.")

# 2. Update cards preview: remove registration number
content = content.replace(
    '<span>القيد: {{ seat.student.registration_number|default:seat.student.id }}</span>',
    '<span class="fw-bold text-primary">مقعد رقم: {{ seat.seat_number }}</span>'
)
print("2. Card preview registration number replaced.")

# 3. Update table preview: remove registration number column
old_table_head = '''                        <tr>
                            <th style="width: 8%;">رقم المقعد</th>
                            <th style="width: 15%;">القاعة</th>
                            <th style="width: 32%;">اسم الطالب الرباعي</th>
                            <th style="width: 20%;">المرحلة والشعبة</th>
                            <th style="width: 12%;">رقم القيد</th>
                            <th style="width: 13%;">موقع الرحلة</th>
                        </tr>'''

new_table_head = '''                        <tr>
                            <th style="width: 10%;">رقم المقعد</th>
                            <th style="width: 15%;">القاعة</th>
                            <th style="width: 38%;">اسم الطالب الرباعي واللقب</th>
                            <th style="width: 22%;">المرحلة والشعبة</th>
                            <th style="width: 15%;">موقع الرحلة</th>
                        </tr>'''

old_table_body = '''                        <tr>
                            <td class="fw-bold fs-6 text-warning">{{ seat.seat_number }}</td>
                            <td><span class="badge" style="background: rgba(255, 255, 255, 0.12); color: #ffffff; border: 1px solid rgba(255, 255, 255, 0.18);">{{ seat.exam_hall.name }}</span></td>
                            <td class="text-start fw-bold pe-3">{{ seat.student.full_name }}</td>
                            <td>{{ seat.student.current_class.name }} - شعبة {{ seat.student.section.name|default:"أ" }}</td>
                            <td class="font-monospace text-muted">{{ seat.student.registration_number|default:seat.student.id }}</td>
                            <td class="small text-muted">صف {{ seat.desk_row|default:"1" }} / عمود {{ seat.desk_col|default:"1" }}</td>
                        </tr>'''

new_table_body = '''                        <tr>
                            <td class="fw-bold fs-6 text-warning">{{ seat.seat_number }}</td>
                            <td><span class="badge" style="background: rgba(255, 255, 255, 0.12); color: #ffffff; border: 1px solid rgba(255, 255, 255, 0.18);">{{ seat.exam_hall.name }}</span></td>
                            <td class="text-start fw-bold pe-3">{{ seat.student.full_name }}</td>
                            <td>{{ seat.student.current_class.name }} - شعبة {{ seat.student.section.name|default:"أ" }}</td>
                            <td class="small text-muted">خط {{ seat.desk_col|default:"1" }} / رحلة {{ seat.desk_row|default:"1" }}</td>
                        </tr>'''

content = content.replace(old_table_head, new_table_head)
content = content.replace(old_table_body, new_table_body)
content = content.replace('<td colspan="6" class="text-muted py-4">لا توجد مقاعد مسجلة حالياً.</td>', '<td colspan="5" class="text-muted py-4">لا توجد مقاعد مسجلة حالياً.</td>')
print("3. Table preview registration number column removed.")

# 4. Update the Halls Table and action buttons
old_halls_section = '''            <div class="table-responsive">
                <table class="table table-bordered table-hover align-middle mb-0 text-center" style="font-size: 13px;">
                    <thead>
                        <tr>
                            <th>اسم / رقم القاعة</th>
                            <th>الموقع / الجناح</th>
                            <th>السعة الكلية للمقاعد</th>
                            <th>مصفوفة المقاعد (صفوف × أعمدة)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for hall in halls %}
                        <tr>
                            <td class="fw-bold text-warning">{{ hall.name }}</td>
                            <td>{{ hall.location|default:"المبنى الرئيسي" }}</td>
                            <td><span class="badge bg-success fs-6 rounded-pill px-3 py-1">{{ hall.capacity }} طالب</span></td>
                            <td>{{ hall.rows_count }} صفوف × {{ hall.cols_count }} أعمدة</td>
                        </tr>
                        {% empty %}
                        <tr>
                            <td colspan="4" class="text-muted py-4">لم يتم تسجيل أي قاعات امتحانية حتى الآن.</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>'''

new_halls_section = '''            <div class="table-responsive">
                <table class="table table-bordered table-hover align-middle mb-0 text-center" style="font-size: 13px;">
                    <thead>
                        <tr>
                            <th>اسم / رقم القاعة</th>
                            <th>الموقع / الجناح</th>
                            <th>عدد الخطوط</th>
                            <th>طبيعة المقعد / الرحلة</th>
                            <th>عدد الرحلات بكل خط</th>
                            <th>السعة الاستيعابية</th>
                            <th style="width: 180px;">إجراءات التحكم</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for hall in halls %}
                        <tr>
                            <td class="fw-bold text-warning fs-6">{{ hall.name }}</td>
                            <td>{{ hall.location|default:"المبنى الرئيسي" }}</td>
                            <td><span class="badge bg-info text-dark rounded-pill px-3 py-1 fw-bold">{{ hall.lines_count|default:hall.cols_count }} خطوط</span></td>
                            <td>
                                {% if hall.desk_type == 'double' %}
                                <span class="badge bg-warning text-dark rounded-pill px-3 py-1 fw-bold"><i class="bi bi-people-fill me-1"></i>مقعد ثنائي (طالبان)</span>
                                {% else %}
                                <span class="badge bg-primary rounded-pill px-3 py-1 fw-bold"><i class="bi bi-person-fill me-1"></i>مقعد فردي (طالب واحد)</span>
                                {% endif %}
                            </td>
                            <td>{{ hall.desks_per_line|default:hall.rows_count }} رحلة</td>
                            <td><span class="badge bg-success fs-6 rounded-pill px-3 py-1">{{ hall.capacity }} طالب</span></td>
                            <td>
                                <div class="d-flex justify-content-center gap-2">
                                    <button type="button" class="btn btn-sm btn-outline-warning rounded-pill px-3 fw-bold" data-bs-toggle="modal" data-bs-target="#editHallModal_{{ hall.id }}">
                                        <i class="bi bi-pencil-square me-1"></i> تعديل
                                    </button>
                                    <button type="button" class="btn btn-sm btn-outline-danger rounded-pill px-3 fw-bold" data-bs-toggle="modal" data-bs-target="#deleteHallModal_{{ hall.id }}">
                                        <i class="bi bi-trash3-fill me-1"></i> حذف
                                    </button>
                                </div>
                            </td>
                        </tr>
                        {% empty %}
                        <tr>
                            <td colspan="7" class="text-muted py-4">لم يتم تسجيل أي قاعات امتحانية حتى الآن.</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>'''

content = content.replace(old_halls_section, new_halls_section)
print("4. Halls table updated with edit/delete buttons.")

# 5. Update #newHallModal with lines_count, desks_per_line, desk_type and dynamic capacity
old_new_hall_modal = '''<!-- نافذة إضافة قاعة امتحانية جديدة (Modal) -->
<div class="modal fade" id="newHallModal" tabindex="-1" aria-hidden="true" dir="rtl">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content rounded-4 border-0 shadow">
            <div class="modal-header bg-primary text-white">
                <h6 class="modal-title fw-bold"><i class="bi bi-door-open me-2"></i>إضافة قاعة امتحانية</h6>
                <button type="button" class="btn-close btn-close-white ms-0 me-auto" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST" action="{% url 'portal_exam_halls' %}">
                {% csrf_token %}
                <input type="hidden" name="action_type" value="create_hall">
                <div class="modal-body p-4 text-start" dir="rtl">
                    <div class="mb-3">
                        <label class="form-label small fw-bold">اسم أو رقم القاعة:</label>
                        <input type="text" name="name" class="form-control fw-bold" placeholder="مثال: القاعة رقم 1" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">الموقع / الجناح (اختياري):</label>
                        <input type="text" name="location" class="form-control" placeholder="مثال: الطابق الثاني - الجناح الأيمن">
                    </div>
                    <div class="row g-2 mb-2">
                        <div class="col-6">
                            <label class="form-label small fw-bold">عدد الصفوف (الصفوف):</label>
                            <input type="number" name="rows_count" class="form-control" value="6" min="1" required>
                        </div>
                        <div class="col-6">
                            <label class="form-label small fw-bold">عدد الأعمدة (الأعمدة):</label>
                            <input type="number" name="cols_count" class="form-control" value="4" min="1" required>
                        </div>
                    </div>
                    <small class="text-muted d-block mt-1">يتم احتساب السعة الكلية تلقائياً (الصفوف × الأعمدة).</small>
                </div>
                <div class="modal-footer border-top border-0 justify-content-center" style="border-color: rgba(255, 255, 255, 0.1) !important;">
                    <button type="button" class="btn btn-secondary rounded-pill px-3" data-bs-dismiss="modal">إلغاء</button>
                    <button type="submit" class="btn btn-primary rounded-pill px-4 fw-bold shadow-sm">حفظ القاعة</button>
                </div>
            </form>
        </div>
    </div>
</div>'''

new_new_hall_modal = '''<!-- نافذة إضافة قاعة امتحانية جديدة (Modal) -->
<div class="modal fade" id="newHallModal" tabindex="-1" aria-hidden="true" dir="rtl">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content rounded-4 border-0 shadow">
            <div class="modal-header bg-primary text-white">
                <h6 class="modal-title fw-bold"><i class="bi bi-door-open me-2"></i>إضافة قاعة امتحانية جديدة</h6>
                <button type="button" class="btn-close btn-close-white ms-0 me-auto" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST" action="{% url 'portal_exam_halls' %}">
                {% csrf_token %}
                <input type="hidden" name="action_type" value="create_hall">
                <div class="modal-body p-4 text-start" dir="rtl">
                    <div class="mb-3">
                        <label class="form-label small fw-bold">اسم أو رقم القاعة:</label>
                        <input type="text" name="name" class="form-control fw-bold" placeholder="مثال: القاعة رقم 1 (أو قاعة الخوارزمي)" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">الموقع / الجناح (اختياري):</label>
                        <input type="text" name="location" class="form-control" placeholder="مثال: الطابق الثاني - الجناح الأيمن">
                    </div>
                    <div class="row g-3 mb-3">
                        <div class="col-6">
                            <label class="form-label small fw-bold">عدد الخطوط في القاعة:</label>
                            <input type="number" name="lines_count" id="new_lines_count" class="form-control fw-bold" value="3" min="1" max="10" oninput="recalcNewCapacity()" required>
                            <small class="text-muted">خطان، 3 خطوط، 4 أو أكثر</small>
                        </div>
                        <div class="col-6">
                            <label class="form-label small fw-bold">طبيعة المقعد / الرحلة:</label>
                            <select name="desk_type" id="new_desk_type" class="form-select fw-bold" onchange="recalcNewCapacity()" required>
                                <option value="single" selected>مقعد فردي (طالب واحد)</option>
                                <option value="double">مقعد ثنائي (طالبان)</option>
                            </select>
                            <small class="text-muted">فردي أو رحلة مزدوجة</small>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">عدد الرحلات في كل خط:</label>
                        <input type="number" name="desks_per_line" id="new_desks_per_line" class="form-control fw-bold" value="6" min="1" max="30" oninput="recalcNewCapacity()" required>
                        <small class="text-muted">عدد المقاعد المتتالية طولياً في كل خط</small>
                    </div>
                    <div class="p-3 rounded-3 text-center border" style="background: rgba(255, 255, 255, 0.05); border-color: rgba(255, 255, 255, 0.15) !important;">
                        <span class="text-muted small d-block mb-1">السعة الاستيعابية المحتسبة تلقائياً:</span>
                        <span class="badge bg-success fs-5 px-4 py-2 rounded-pill" id="new_hall_capacity_badge">18 طالب</span>
                    </div>
                </div>
                <div class="modal-footer border-top border-0 justify-content-center" style="border-color: rgba(255, 255, 255, 0.1) !important;">
                    <button type="button" class="btn btn-secondary rounded-pill px-3" data-bs-dismiss="modal">إلغاء</button>
                    <button type="submit" class="btn btn-primary rounded-pill px-4 fw-bold shadow-sm">حفظ القاعة</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- نوافذ تعديل وحذف القاعات الامتحانية (Modals لكل قاعة) -->
{% for hall in halls %}
<!-- نافذة تعديل القاعة -->
<div class="modal fade" id="editHallModal_{{ hall.id }}" tabindex="-1" aria-hidden="true" dir="rtl">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content rounded-4 border-0 shadow">
            <div class="modal-header bg-warning text-dark">
                <h6 class="modal-title fw-bold"><i class="bi bi-pencil-square me-2"></i>تعديل بيانات القاعة ({{ hall.name }})</h6>
                <button type="button" class="btn-close ms-0 me-auto" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST" action="{% url 'portal_exam_halls' %}">
                {% csrf_token %}
                <input type="hidden" name="action_type" value="edit_hall">
                <input type="hidden" name="hall_id" value="{{ hall.id }}">
                <div class="modal-body p-4 text-start" dir="rtl">
                    <div class="mb-3">
                        <label class="form-label small fw-bold">اسم أو رقم القاعة:</label>
                        <input type="text" name="name" class="form-control fw-bold" value="{{ hall.name }}" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">الموقع / الجناح:</label>
                        <input type="text" name="location" class="form-control" value="{{ hall.location|default:'' }}">
                    </div>
                    <div class="row g-3 mb-3">
                        <div class="col-6">
                            <label class="form-label small fw-bold">عدد الخطوط:</label>
                            <input type="number" name="lines_count" id="edit_lines_{{ hall.id }}" class="form-control fw-bold" value="{{ hall.lines_count|default:hall.cols_count }}" min="1" max="10" oninput="recalcEditCapacity('{{ hall.id }}')" required>
                        </div>
                        <div class="col-6">
                            <label class="form-label small fw-bold">طبيعة المقعد / الرحلة:</label>
                            <select name="desk_type" id="edit_desk_type_{{ hall.id }}" class="form-select fw-bold" onchange="recalcEditCapacity('{{ hall.id }}')" required>
                                <option value="single" {% if hall.desk_type == 'single' %}selected{% endif %}>مقعد فردي (طالب واحد)</option>
                                <option value="double" {% if hall.desk_type == 'double' %}selected{% endif %}>مقعد ثنائي (طالبان)</option>
                            </select>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-bold">عدد الرحلات في كل خط:</label>
                        <input type="number" name="desks_per_line" id="edit_desks_{{ hall.id }}" class="form-control fw-bold" value="{{ hall.desks_per_line|default:hall.rows_count }}" min="1" max="30" oninput="recalcEditCapacity('{{ hall.id }}')" required>
                    </div>
                    <div class="p-3 rounded-3 text-center border" style="background: rgba(255, 255, 255, 0.05); border-color: rgba(255, 255, 255, 0.15) !important;">
                        <span class="text-muted small d-block mb-1">السعة الاستيعابية المحدثة:</span>
                        <span class="badge bg-success fs-5 px-4 py-2 rounded-pill" id="edit_capacity_badge_{{ hall.id }}">{{ hall.capacity }} طالب</span>
                    </div>
                </div>
                <div class="modal-footer border-top border-0 justify-content-center" style="border-color: rgba(255, 255, 255, 0.1) !important;">
                    <button type="button" class="btn btn-secondary rounded-pill px-3" data-bs-dismiss="modal">إلغاء</button>
                    <button type="submit" class="btn btn-warning rounded-pill px-4 fw-bold shadow-sm text-dark">حفظ التعديلات</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- نافذة تأكيد حذف القاعة -->
<div class="modal fade" id="deleteHallModal_{{ hall.id }}" tabindex="-1" aria-hidden="true" dir="rtl">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content rounded-4 border-0 shadow">
            <div class="modal-header bg-danger text-white">
                <h6 class="modal-title fw-bold"><i class="bi bi-exclamation-triangle-fill me-2"></i>تأكيد حذف القاعة الامتحانية</h6>
                <button type="button" class="btn-close btn-close-white ms-0 me-auto" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST" action="{% url 'portal_exam_halls' %}">
                {% csrf_token %}
                <input type="hidden" name="action_type" value="delete_hall">
                <input type="hidden" name="hall_id" value="{{ hall.id }}">
                <div class="modal-body p-4 text-center" dir="rtl">
                    <i class="bi bi-trash3-fill text-danger display-4 d-block mb-3"></i>
                    <h6 class="fw-bold mb-2">هل أنت متأكد تماماً من حذف القاعة ({{ hall.name }})؟</h6>
                    <p class="text-muted small mb-0">
                        سيؤدي هذا الإجراء إلى حذف القاعة نهائياً وإلغاء توزيع أي مقاعد كانت مخصصة لطلابها في الدورات الامتحانية الحالية.
                    </p>
                </div>
                <div class="modal-footer border-top border-0 justify-content-center" style="border-color: rgba(255, 255, 255, 0.1) !important;">
                    <button type="button" class="btn btn-secondary rounded-pill px-3" data-bs-dismiss="modal">تراجع</button>
                    <button type="submit" class="btn btn-danger rounded-pill px-4 fw-bold shadow-sm">نعم، احذف القاعة</button>
                </div>
            </form>
        </div>
    </div>
</div>
{% endfor %}

<script>
function recalcNewCapacity() {
    var lines = parseInt(document.getElementById('new_lines_count').value) || 1;
    var desks = parseInt(document.getElementById('new_desks_per_line').value) || 1;
    var type = document.getElementById('new_desk_type').value;
    var mult = (type === 'double') ? 2 : 1;
    var cap = lines * desks * mult;
    var badge = document.getElementById('new_hall_capacity_badge');
    if (badge) badge.innerText = cap + ' طالب';
}

function recalcEditCapacity(hallId) {
    var lines = parseInt(document.getElementById('edit_lines_' + hallId).value) || 1;
    var desks = parseInt(document.getElementById('edit_desks_' + hallId).value) || 1;
    var type = document.getElementById('edit_desk_type_' + hallId).value;
    var mult = (type === 'double') ? 2 : 1;
    var cap = lines * desks * mult;
    var badge = document.getElementById('edit_capacity_badge_' + hallId);
    if (badge) badge.innerText = cap + ' طالب';
}
</script>'''

content = content.replace(old_new_hall_modal, new_new_hall_modal)
print("5. Modals and JavaScript updated.")

# 6. Update the distribute button text
content = content.replace(
    'بدء التوزيع الذكي للمقاعد وتوليد القوائم',
    'توليد وتوزيع الطلاب آلياً (مكافحة الغش)'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("exam_halls.html successfully updated!")
