from .licensing import get_machine_fingerprint
from .models import SchoolSettings, AcademicYear

def school_portal_context(request):
    try:
        school = SchoolSettings.get_settings()
    except Exception:
        school = None

    try:
        machine_id = get_machine_fingerprint()
    except Exception:
        machine_id = "IQ-SYSTEM-NODE"

    try:
        current_year = AcademicYear.objects.filter(is_current=True).first()
        all_academic_years = list(AcademicYear.objects.all().order_by('-start_date')[:6])
    except Exception:
        current_year = None
        all_academic_years = []

    show_wizard = bool(school and not getattr(school, 'is_first_run_completed', False))

    days_remaining = school.days_remaining if school else 0
    is_trial = school.is_trial if school else False
    is_official_license = school.is_official_license if school else False
    subscription_status_label = school.subscription_status_label if school else ""

    return {
        'school': school,
        'machine_id': machine_id,
        'global_machine_id': machine_id,
        'current_year': current_year,
        'all_academic_years': all_academic_years,
        'show_first_run_wizard': show_wizard,
        'days_remaining': days_remaining,
        'is_trial': is_trial,
        'is_official_license': is_official_license,
        'subscription_status_label': subscription_status_label,
    }
