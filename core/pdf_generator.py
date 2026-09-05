import io
import os
import re
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

# تهيئة الخطوط العربية من نظام التشغيل Windows مع بدائل احتياطية
FONTS_INITIALIZED = False
FONT_REGULAR = 'ArabicRegular'
FONT_BOLD = 'ArabicBold'

def init_fonts():
    global FONTS_INITIALIZED, FONT_REGULAR, FONT_BOLD
    if FONTS_INITIALIZED:
        return

    regular_candidates = [
        r'C:\Windows\Fonts\arial.ttf',
        r'C:\Windows\Fonts\tahoma.ttf',
        r'C:\Windows\Fonts\segoeui.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    bold_candidates = [
        r'C:\Windows\Fonts\arialbd.ttf',
        r'C:\Windows\Fonts\tahomabd.ttf',
        r'C:\Windows\Fonts\segoeuib.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ]

    reg_found = None
    for p in regular_candidates:
        if os.path.exists(p):
            reg_found = p
            break

    bold_found = None
    for p in bold_candidates:
        if os.path.exists(p):
            bold_found = p
            break

    if reg_found:
        try:
            pdfmetrics.registerFont(TTFont(FONT_REGULAR, reg_found))
        except Exception:
            FONT_REGULAR = 'Helvetica'
    else:
        FONT_REGULAR = 'Helvetica'

    if bold_found:
        try:
            pdfmetrics.registerFont(TTFont(FONT_BOLD, bold_found))
        except Exception:
            FONT_BOLD = FONT_REGULAR
    else:
        FONT_BOLD = FONT_REGULAR

    FONTS_INITIALIZED = True


def ar(text):
    """إعادة تشكيل وعكس النص العربي ليتوافق بدقة 100% مع محرك الرسم في ReportLab"""
    if text is None:
        return ''
    cleaned = str(text).strip()
    if not cleaned:
        return ''
    try:
        reshaped = arabic_reshaper.reshape(cleaned)
        return get_display(reshaped)
    except Exception:
        return cleaned


def clean_html_tags(text):
    """إزالة وسوم HTML من النصوص مع الحفاظ على الأسطر الجديدة وتجنب التكرار الكارثي (ReDoS)"""
    if not text:
        return ''
    t = str(text)
    t = t.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
    t = t.replace('<BR>', '\n').replace('<BR/>', '\n').replace('<BR />', '\n')
    t = t.replace('</p>', '\n').replace('</P>', '\n')
    chars = []
    inside_tag = False
    for ch in t:
        if ch == '<':
            inside_tag = True
        elif ch == '>':
            inside_tag = False
        elif not inside_tag:
            chars.append(ch)
    return ''.join(chars).strip()


def wrap_arabic_lines(text, font_name, font_size, max_width):
    """تقسيم النص العربي إلى أسطر تناسب عرض الصفحة A4 المتاح دون انكسار الكلمات"""
    init_fonts()
    raw_lines = text.split('\n')
    wrapped_lines = []

    for paragraph in raw_lines:
        paragraph = paragraph.strip()
        if not paragraph:
            wrapped_lines.append('')
            continue

        words = paragraph.split()
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            display_text = ar(test_line)
            width = pdfmetrics.stringWidth(display_text, font_name, font_size)
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    wrapped_lines.append(' '.join(current_line))
                current_line = [word]
        if current_line:
            wrapped_lines.append(' '.join(current_line))

    return wrapped_lines


def generate_official_document_pdf(school, doc_number, doc_date, doc_type_display, destination, subject, body_content, notes=None):
    """
    توليد كتاب رسمي أصولي بصيغة PDF مطابق لمعايير وزارة التربية العراقية وقياس A4 القياسي
    """
    init_fonts()
    buffer = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)

    # إطار أصولي للصفحة
    margin_x = 40
    margin_y = 40
    content_width = width - (margin_x * 2)

    # رسم إطار الصفحة الأنيق
    c.setLineWidth(1.2)
    c.setStrokeColorRGB(0.15, 0.15, 0.15)
    c.rect(margin_x - 10, margin_y - 10, content_width + 20, height - (margin_y * 2) + 20)

    # الإطار الداخلي الرفيع
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.rect(margin_x - 7, margin_y - 7, content_width + 14, height - (margin_y * 2) + 14)

    # ==========================
    # ترويسة الوزارة (أعلى اليمين)
    # ==========================
    right_x = width - margin_x
    cur_y = height - margin_y - 20

    c.setFillColorRGB(0, 0, 0)
    c.setFont(FONT_BOLD, 12)
    c.drawRightString(right_x, cur_y, ar("جمهورية العراق"))
    cur_y -= 18

    c.setFont(FONT_BOLD, 12)
    c.drawRightString(right_x, cur_y, ar("وزارة التربية"))
    cur_y -= 16

    directorate = getattr(school, 'directorate', None) or "المديرية العامة للتربية"
    c.setFont(FONT_REGULAR, 10.5)
    c.drawRightString(right_x, cur_y, ar(directorate))
    cur_y -= 15

    sub_dir = getattr(school, 'sub_directorate', None) or "قسم الإدارة المدرسية"
    c.setFont(FONT_REGULAR, 10)
    c.drawRightString(right_x, cur_y, ar(sub_dir))
    cur_y -= 16

    school_name = getattr(school, 'school_name', None) or "إدارة المدرسة"
    c.setFont(FONT_BOLD, 11)
    c.drawRightString(right_x, cur_y, ar(school_name))

    # ==========================
    # وسط الترويسة: الشعار الرسمي
    # ==========================
    logo_drawn = False
    if school and getattr(school, 'logo', None):
        try:
            logo_path = school.logo.path
            if os.path.exists(logo_path):
                logo_size = 65
                center_x = (width / 2) - (logo_size / 2)
                center_y = height - margin_y - 80
                c.drawImage(logo_path, center_x, center_y, width=logo_size, height=logo_size, preserveAspectRatio=True, mask='auto')
                logo_drawn = True
        except Exception:
            logo_drawn = False

    if not logo_drawn:
        # رسم رمز تربوي أنيق في حال عدم توفر صورة الشعار
        cx = width / 2
        cy = height - margin_y - 45
        c.setLineWidth(1)
        c.setStrokeColorRGB(0.2, 0.2, 0.2)
        c.circle(cx, cy, 26, stroke=1, fill=0)
        c.setFont(FONT_BOLD, 8)
        c.drawCentredString(cx, cy + 6, ar("جمهورية العراق"))
        c.drawCentredString(cx, cy - 6, ar("وزارة التربية"))

    # ==========================
    # يسار الترويسة: العدد والتاريخ والنوع
    # ==========================
    left_x = margin_x + 10
    left_y = height - margin_y - 25

    c.setFont(FONT_BOLD, 10.5)
    doc_num_str = f"العدد : {doc_number or '---'}"
    c.drawString(left_x, left_y, ar(doc_num_str))
    left_y -= 18

    c.setFont(FONT_REGULAR, 10.5)
    doc_date_str = f"التاريخ : {doc_date or '---'}"
    c.drawString(left_x, left_y, ar(doc_date_str))
    left_y -= 18

    if doc_type_display:
        c.setFont(FONT_REGULAR, 10)
        type_str = f"النوع : {doc_type_display}"
        c.drawString(left_x, left_y, ar(type_str))

    # خط فاصل مزدوج أصولي تحت الترويسة
    separator_y = height - margin_y - 110
    c.setLineWidth(1.5)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(margin_x, separator_y, width - margin_x, separator_y)
    c.setLineWidth(0.5)
    c.line(margin_x, separator_y - 3, width - margin_x, separator_y - 3)

    # ==========================
    # المخاطبة والموضوع
    # ==========================
    cur_y = separator_y - 35
    c.setFont(FONT_BOLD, 12.5)
    dest_str = f"إلى / {destination or 'الجهة المعنية المحترمة'}"
    c.drawRightString(right_x, cur_y, ar(dest_str))

    cur_y -= 26
    subj_str = f"م / {subject or 'كتاب رسمي أصولي'}"
    c.setFont(FONT_BOLD, 12.5)
    c.drawRightString(right_x, cur_y, ar(subj_str))

    # خط رفيع تحت الموضوع
    subj_width = pdfmetrics.stringWidth(ar(subj_str), FONT_BOLD, 12.5)
    c.setLineWidth(0.8)
    c.line(right_x - subj_width - 5, cur_y - 4, right_x, cur_y - 4)

    # ==========================
    # متن الوثيقة ومحتواها
    # ==========================
    cur_y -= 38
    clean_body = clean_html_tags(body_content)
    lines = wrap_arabic_lines(clean_body, FONT_REGULAR, 11.5, content_width - 15)

    c.setFont(FONT_REGULAR, 11.5)
    line_height = 22

    for line in lines:
        if cur_y < margin_y + 180:
            # إذا امتد النص يتم الانتقال لصفحة جديدة مع تكرار الإطار
            c.showPage()
            c.setLineWidth(1.2)
            c.setStrokeColorRGB(0.15, 0.15, 0.15)
            c.rect(margin_x - 10, margin_y - 10, content_width + 20, height - (margin_y * 2) + 20)
            cur_y = height - margin_y - 40
            c.setFont(FONT_REGULAR, 11.5)

        if line:
            c.drawRightString(right_x - 5, cur_y, ar(line))
        cur_y -= line_height

    # ==========================
    # تذييل التواقيع والختم الإداري
    # ==========================
    sig_y = margin_y + 95

    # اليمين: التوجيهات والأرشيف
    c.setFont(FONT_BOLD, 9.5)
    c.drawRightString(right_x - 5, sig_y + 20, ar("نسخة منه إلى:"))
    c.setFont(FONT_REGULAR, 8.5)
    c.drawRightString(right_x - 5, sig_y + 5, ar("- الأرشيف وسجلات الصادر والوارد"))
    c.drawRightString(right_x - 5, sig_y - 10, ar("- الإضبارة العامة للمؤسسة"))

    # اليسار: إدارة المدرسة والمدير والختم
    center_sig_x = margin_x + 100
    c.setFont(FONT_BOLD, 11)
    c.drawCentredString(center_sig_x, sig_y + 20, ar("إدارة مدرسة"))
    c.drawCentredString(center_sig_x, sig_y + 4, ar(school_name))

    director_name = getattr(school, 'director_name', '')
    if director_name:
        c.setFont(FONT_REGULAR, 10)
        c.drawCentredString(center_sig_x, sig_y - 12, ar(f"المدير: {director_name}"))

    c.setFont(FONT_REGULAR, 8.5)
    c.drawCentredString(center_sig_x, sig_y - 28, ar("الختم والتوقيع الرسمي"))

    # خط توقيع منقط
    c.setDash(2, 2)
    c.setLineWidth(0.8)
    c.line(center_sig_x - 55, sig_y - 38, center_sig_x + 55, sig_y - 38)
    c.setDash()

    # تذييل سفلي صغير
    c.setFont(FONT_REGULAR, 7.5)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(width / 2, margin_y - 2, ar("صادر رسمياً وموثق ضمن منظومة الإدارة المدرسية الحديثة - جمهورية العراق"))

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def generate_middle_record_pdf(school, selected_class, current_year, sections_data, subjects_list, empty_pages_count=0):
    """
    توليد سجل الدرجات الوسطي بصيغة PDF أصولية معتمدة وفق المعايير الوزارية العراقية
    يدعم معالجة مئات الصفحات بسرعة فائقة وبدون أي ضغط على واجهة العرض أو المتصفح.
    """
    init_fonts()
    buffer = io.BytesIO()
    width, height = A4 # 595.27 x 841.89
    c = canvas.Canvas(buffer, pagesize=A4)

    pages_to_render = []
    for sec_item in sections_data:
        sec = sec_item['section']
        for st in sec_item['students']:
            pages_to_render.append({
                'is_empty': False,
                'student': st,
                'section': sec,
            })

    for i in range(empty_pages_count):
        pages_to_render.append({
            'is_empty': True,
            'spare_index': i + 1,
            'section': sections_data[0]['section'] if sections_data else None,
        })

    total_pages = len(pages_to_render)
    if total_pages == 0:
        pages_to_render.append({'is_empty': True, 'spare_index': 1, 'section': None})

    school_name = getattr(school, 'school_name', '') or 'المدرسة'
    director_name = getattr(school, 'director_name', '') or '........................'
    year_name = getattr(current_year, 'name', '') or '2026-2027'
    class_name = getattr(selected_class, 'name', '') or ''

    for idx, page_info in enumerate(pages_to_render):
        # 1. الإطار الخارجي المزدوج للصفحة A4
        c.setLineWidth(1.8)
        c.setStrokeColorRGB(0, 0, 0)
        c.rect(20, 20, width - 40, height - 40)
        c.setLineWidth(0.8)
        c.rect(23, 23, width - 46, height - 46)

        # 2. الترويسة العليا
        c.setFont(FONT_BOLD, 10.5)
        c.setFillColorRGB(0, 0, 0)
        c.drawRightString(width - 35, height - 42, ar(f"إدارة {school_name}"))

        c.setFont(FONT_BOLD, 14)
        c.drawCentredString(width / 2, height - 42, ar("سجل الدرجات الوسطي"))
        c.setFont(FONT_REGULAR, 10)
        c.drawCentredString(width / 2, height - 56, ar(f"للعام الدراسي ( {year_name} )"))

        c.setFont(FONT_BOLD, 10)
        if page_info['is_empty']:
            seq_text = f"صفحة احتياطية ({page_info.get('spare_index', 1)})"
        else:
            seq_text = f"التسلسل: {idx + 1}"
        c.drawString(35, height - 42, ar(seq_text))

        # خط فاصل تحت الترويسة
        c.setLineWidth(1)
        c.line(23, height - 66, width - 23, height - 66)

        # 3. بيانات الطالب
        cur_y = height - 82
        c.setFont(FONT_BOLD, 10)
        if not page_info['is_empty']:
            st = page_info['student']
            sec = page_info['section']
            st_name = getattr(st, 'full_name', '') or getattr(st.user, 'username', '')
            sec_name = sec.name if sec else 'أ'
            reg_num = getattr(st, 'clean_reg_number', '') or getattr(st, 'registration_number', '') or '---'

            c.drawRightString(width - 35, cur_y, ar(f"اسم الطالب: {st_name}"))
            c.drawCentredString(width / 2, cur_y, ar(f"الصف: {class_name}    الشعبة: {sec_name}"))
            c.drawString(35, cur_y, ar(f"رقمه في القيد العام: {reg_num}"))
        else:
            sec = page_info['section']
            sec_name = sec.name if sec else 'أ'
            c.drawRightString(width - 35, cur_y, ar("اسم الطالب: ................................................"))
            c.drawCentredString(width / 2, cur_y, ar(f"الصف: {class_name}    الشعبة: {sec_name}"))
            c.drawString(35, cur_y, ar("رقمه في القيد العام: ...................."))

        # 4. رسم جدول المواد والدرجات
        table_x = 28
        table_width = width - 56
        col0_w = 125
        other_col_w = (table_width - col0_w) / 9
        
        table_top_y = height - 98
        col_x = [table_x, table_x + col0_w]
        for c_idx in range(9):
            col_x.append(col_x[-1] + other_col_w)

        headers = [
            "المواد", "سعي ف1", "نصف السنة", "سعي ف2", "السعي السنوي",
            "امتحان نهائي", "الدرجة النهائية", "درجة الإكمال", "بعد الإكمال", "الملاحظات"
        ]

        header_h = 42
        c.setFillColorRGB(0.94, 0.94, 0.94)
        c.rect(table_x, table_top_y - header_h, table_width, header_h, stroke=1, fill=1)
        c.setFillColorRGB(0, 0, 0)
        c.setFont(FONT_BOLD, 8.5)
        for h_idx in range(10):
            cx = (col_x[h_idx] + col_x[h_idx + 1]) / 2
            c.drawCentredString(cx, table_top_y - (header_h / 2) - 3, ar(headers[h_idx]))

        row_y = table_top_y - header_h
        sub_list = subjects_list or ["التربية الإسلامية", "اللغة العربية", "اللغة الإنكليزية", "الرياضيات", "العلوم", "الاجتماعيات"]
        available_height_for_rows = row_y - 100
        row_h = available_height_for_rows / (len(sub_list) + 2)
        row_h = max(24, min(38, row_h))

        c.setFont(FONT_REGULAR, 9)
        for s_idx, sub_name in enumerate(sub_list):
            r_top = row_y - (s_idx * row_h)
            r_bot = r_top - row_h

            if s_idx % 2 == 1:
                c.setFillColorRGB(0.98, 0.98, 0.98)
                c.rect(table_x, r_bot, table_width, row_h, stroke=0, fill=1)
                c.setFillColorRGB(0, 0, 0)

            c.rect(table_x, r_bot, table_width, row_h, stroke=1, fill=0)
            for x_line in col_x[1:-1]:
                c.line(x_line, r_bot, x_line, r_top)

            c.setFont(FONT_BOLD, 9)
            c.drawRightString(col_x[1] - 8, r_bot + (row_h / 2) - 3, ar(sub_name))

        # نتيجتي الدورين
        results_start_y = row_y - (len(sub_list) * row_h)
        for r_num, r_title in enumerate(["نتيجة الدور الأول", "نتيجة الدور الثاني"]):
            r_top = results_start_y - (r_num * row_h)
            r_bot = r_top - row_h
            c.setFillColorRGB(0.93, 0.93, 0.93)
            c.rect(table_x, r_bot, col0_w, row_h, stroke=1, fill=1)
            c.setFillColorRGB(0, 0, 0)
            c.setFont(FONT_BOLD, 9)
            c.drawCentredString(table_x + (col0_w / 2), r_bot + (row_h / 2) - 3, ar(r_title))
            c.rect(table_x + col0_w, r_bot, table_width - col0_w, row_h, stroke=1, fill=0)

        # 5. التذييل
        sig_y = 42
        c.setLineWidth(1)
        c.line(28, sig_y + 25, width - 28, sig_y + 25)

        c.setFont(FONT_BOLD, 9)
        c.drawRightString(width - 35, sig_y + 8, ar("عضو اللجنة الامتحانية: ................................"))
        c.drawCentredString(width / 2, sig_y + 8, ar("مدقق السجل: ................................"))
        c.drawString(35, sig_y + 8, ar(f"مدير المدرسة والختم: {director_name}"))

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.getvalue()

