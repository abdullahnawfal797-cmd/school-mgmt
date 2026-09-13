from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_schoolsubscriptionpayment_academic_year_and_more'),
        ('mobile_api', '0005_create_revoked_token_table'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportTicket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(db_index=True, default='GENERAL', max_length=50, verbose_name='التصنيف')),
                ('priority', models.CharField(choices=[('LOW', 'منخفضة'), ('MEDIUM', 'متوسطة'), ('HIGH', 'عالية'), ('URGENT', 'عاجلة')], db_index=True, default='MEDIUM', max_length=20, verbose_name='الأولوية')),
                ('status', models.CharField(choices=[('OPEN', 'مفتوحة'), ('IN_PROGRESS', 'قيد المعالجة'), ('RESOLVED', 'تم الحل'), ('CLOSED', 'مغلقة')], db_index=True, default='OPEN', max_length=20, verbose_name='الحالة')),
                ('subject', models.CharField(max_length=200, verbose_name='الموضوع')),
                ('description', models.TextField(verbose_name='وصف المشكلة')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_support_tickets', to=settings.AUTH_USER_MODEL, verbose_name='منشئ التذكرة')),
                ('school', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='support_tickets', to='core.schoolsettings', verbose_name='المدرسة')),
            ],
            options={'verbose_name': 'تذكرة دعم مركزية', 'verbose_name_plural': 'تذاكر الدعم المركزية', 'ordering': ['-updated_at', '-id']},
        ),
        migrations.CreateModel(
            name='SupportTicketMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField(verbose_name='الرسالة')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('is_internal_note', models.BooleanField(default=False, verbose_name='ملاحظة داخلية')),
                ('sender', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='support_ticket_messages', to=settings.AUTH_USER_MODEL, verbose_name='المرسل')),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='mobile_api.supportticket', verbose_name='التذكرة')),
            ],
            options={'verbose_name': 'رسالة تذكرة دعم', 'verbose_name_plural': 'رسائل تذاكر الدعم', 'ordering': ['created_at', 'id']},
        ),
    ]
