import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task
def send_absence_notification(student_id, date_str):
    """
    Sends an absence notification to the student's parent.
    """
    from .models import Student
    try:
        student = Student.objects.select_related('user', 'parent__user').get(pk=student_id)
        parent_name = student.parent.user.get_full_name() if student.parent else "Parent/Guardian"
        student_name = student.user.get_full_name() or student.user.username
        parent_phone = student.parent.phone if student.parent else None

        logger.info(
            f"[Notification] Dear {parent_name}, your child {student_name} was marked ABSENT on {date_str}. "
            f"Contact: {parent_phone}"
        )
        return {
            'status': 'sent',
            'student_id': student_id,
            'student_name': student_name,
            'date': date_str,
            'recipient': parent_phone
        }
    except Student.DoesNotExist:
        logger.error(f"[Notification Error] Student with ID {student_id} not found.")
        return {'status': 'failed', 'reason': 'Student not found'}


@shared_task
def send_invoice_reminder(invoice_id):
    """
    Sends a payment reminder for an unpaid or due invoice.
    """
    from .models import Invoice
    try:
        invoice = Invoice.objects.select_related('student__user', 'student__parent__user').get(pk=invoice_id)
        student_name = invoice.student.user.get_full_name() or invoice.student.user.username
        parent_phone = invoice.student.parent.phone if invoice.student.parent else None

        logger.info(
            f"[Invoice Reminder] Invoice #{invoice.id} for {student_name} with amount ${invoice.amount} "
            f"is {invoice.status.upper()}. Due date: {invoice.due_date}."
        )
        return {
            'status': 'sent',
            'invoice_id': invoice_id,
            'amount': str(invoice.amount),
            'due_date': str(invoice.due_date),
            'recipient': parent_phone
        }
    except Invoice.DoesNotExist:
        logger.error(f"[Invoice Error] Invoice with ID {invoice_id} not found.")
        return {'status': 'failed', 'reason': 'Invoice not found'}


@shared_task
def generate_monthly_attendance_summary(month=None, year=None):
    """
    Generates summary statistics for school attendance in a given month/year.
    """
    from .models import Attendance
    from django.db.models import Count

    now = timezone.now()
    target_month = month or now.month
    target_year = year or now.year

    stats = Attendance.objects.filter(
        date__year=target_year,
        date__month=target_month
    ).values('status').annotate(total=Count('id'))

    summary = {item['status']: item['total'] for item in stats}
    logger.info(f"[Attendance Report] {target_year}-{target_month:02d} Summary: {summary}")
    return {
        'year': target_year,
        'month': target_month,
        'summary': summary
    }
