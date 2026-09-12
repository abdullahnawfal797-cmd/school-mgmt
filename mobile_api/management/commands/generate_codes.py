import secrets
import csv
from django.core.management.base import BaseCommand
from mobile_api.models import StudentActivation

class Command(BaseCommand):
    help = 'توليد أكواد التفعيل السنوية لجميع الطلبة وتصديرها إلى ملف CSV'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=str, default='2026-2027', help='العام الدراسي')
        parser.add_argument('--count', type=int, default=50, help='عدد الأكواد الافتراضية المراد توليدها للتجربة أو التوزيع')

    def handle(self, *args, **options):
        year = options['year']
        count = options['count']

        generated = []
        for i in range(1, count + 1):
            raw_code = f'MDR-{secrets.token_hex(3).upper()}'
            student_name = f'طالب تجريبي {i}'
            classroom = f'الصف {((i-1)%6)+1}'

            act, created = StudentActivation.objects.get_or_create(
                student_name=student_name,
                academic_year=year,
                defaults={'code': raw_code, 'classroom': classroom, 'status': 'GENERATED'}
            )
            generated.append([act.student_name, act.classroom, act.code, act.academic_year])

        # تصدير إلى CSV للطباعة
        csv_file = 'activation_cards.csv'
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['اسم الطالب', 'الصف والشعبة', 'كود التفعيل السنوي', 'العام الدراسي'])
            writer.writerows(generated)

        self.stdout.write(self.style.SUCCESS(f'✅ تم إنشاء وتحديث {len(generated)} كود تفعيل بنجاح!'))
        self.stdout.write(self.style.SUCCESS(f'📄 تم حفظ كروت التفعيل للطباعة في الملف: {csv_file}'))
