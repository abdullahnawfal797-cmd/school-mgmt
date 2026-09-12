import json
import uuid
from decimal import Decimal
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count, Q

from core.models import (
    SchoolSettings, SchoolSubscriptionPayment, SchoolYearSubscription,
    SchoolPaymentAdjustment, AcademicYear, Student, StudentAcademicHistory,
    Enrollment, Teacher, SchoolClass, Section, Subject, Attendance, Grade
)
from .models import (
    UserProfile, UserRole, ParentStudentRelation, StudentActivation,
    SubscriptionStatus, GradeEntry, GradeStatus, DocumentRequest,
    DocumentRequestStatus, HomeworkAssignment, SchoolNews,
    MobileNotification, AuditTrailLog
)
from .auth_utils import (
    generate_tokens_for_user, verify_token, revoke_token,
    require_mobile_auth, verify_school_access,
    verify_parent_student_access
)

User = get_user_model()


# =============================================================================
# 1. المصادقة والجلسات المستمرة (Authentication & Session Persistence)
# =============================================================================

@csrf_exempt
def login_view(request):
    """
    تسجيل الدخول المركزي لجميع الأدوار:
    - Owner (المالك والمشرف العام)
    - Manager (مدير المدرسة)
    - Teacher (المعلم)
    - Parent (ولي الأمر)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'طريقة الطلب غير مدعومة (POST مطلوب)'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return JsonResponse({'error': 'يرجى إدخال اسم المستخدم وكلمة المرور'}, status=400)

        user = authenticate(username=username, password=password)
        if not user:
            # التحقق الإضافي في حال كان الحساب موجوداً
            try:
                u_obj = User.objects.get(username=username)
                if u_obj.check_password(password):
                    user = u_obj
            except Exception:
                pass

        if not user:
            return JsonResponse({'error': 'اسم المستخدم أو كلمة المرور غير صحيحة'}, status=401)

        if not user.is_active:
            return JsonResponse({'error': 'هذا الحساب معطل، يرجى مراجعة إدارة المنظومة'}, status=403)

        profile, created = UserProfile.objects.get_or_create(user=user)

        # التحقق من حساب المالك المركزي استناداً للصلاحية المؤسساتية الحقيقية (is_superuser أو الدور المحفوظ في قاعدة البيانات)
        if user.is_superuser or profile.role == UserRole.OWNER:
            if profile.role != UserRole.OWNER:
                profile.role = UserRole.OWNER
                profile.school = None
                profile.is_approved = True
                profile.save()

        # فحص حساب ولي الأمر: يجب أن يكون معتمداً واشتراكه نشطاً
        if profile.role == UserRole.PARENT:
            has_active_activation = StudentActivation.objects.filter(
                parent=profile,
                status=SubscriptionStatus.ACTIVE
            ).exists()

            if not profile.is_approved and not has_active_activation:
                has_pending = StudentActivation.objects.filter(
                    parent=profile,
                    status=SubscriptionStatus.PENDING
                ).exists()
                if has_pending:
                    return JsonResponse({
                        'error': 'حساب ولي الأمر قيد المراجعة وبانتظار موافقة واعتماد المالك.',
                        'pending_approval': True
                    }, status=403)

        access_token, refresh_token = generate_tokens_for_user(user, profile)

        # تسجيل الدخول في سجل التدقيق
        AuditTrailLog.objects.create(
            user=user,
            action='تسجيل دخول ناجح',
            entity_name='Auth',
            entity_id=str(user.id),
            details=f'تسجيل دخول بواسطة [{user.username}] بدور: {profile.get_role_display()}'
        )

        school_info = None
        if profile.school:
            school_info = {
                'id': profile.school.id,
                'name': profile.school.school_name,
                'code': profile.school.ministry_school_code,
            }

        return JsonResponse({
            'status': 'success',
            'token': access_token,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'role': profile.role,
            'full_name': profile.full_name or user.get_full_name() or user.username,
            'user_id': user.id,
            'school': school_info,
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': profile.full_name or user.get_full_name() or user.username,
                'name': profile.full_name or user.get_full_name() or user.username,
                'role': profile.role,
                'role_display': profile.get_role_display(),
                'school_id': profile.school_id,
            }
        })
    except Exception as e:
        return JsonResponse({'error': f'فشل في معالجة طلب تسجيل الدخول: {str(e)}'}, status=500)


@csrf_exempt
@require_mobile_auth()
def verify_session_view(request):
    """
    التحقق من صلاحية الجلسة عند فتح التطبيق:
    تتيح تسجيل الدخول التلقائي والدخول المباشر للشاشة دون طلب كلمة المرور مرة أخرى.
    """
    profile = request.user_profile
    school_info = None
    if profile.school:
        school_info = {
            'id': profile.school.id,
            'name': profile.school.school_name,
            'code': profile.school.ministry_school_code,
        }

    return JsonResponse({
        'status': 'success',
        'valid': True,
        'user_id': request.user.id,
        'username': request.user.username,
        'role': profile.role,
        'role_display': profile.get_role_display(),
        'full_name': profile.full_name or request.user.get_full_name() or request.user.username,
        'school': school_info,
        'user': {
            'id': request.user.id,
            'username': request.user.username,
            'full_name': profile.full_name or request.user.get_full_name() or request.user.username,
            'role': profile.role,
            'school_id': profile.school_id,
        }
    })


@csrf_exempt
def refresh_token_view(request):
    """تجديد رمز الوصول باستخدام Refresh Token دون مقاطعة الجلسة"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        refresh_tok = data.get('refresh_token', '').strip()
        payload = verify_token(refresh_tok, max_age_seconds=86400 * 90)

        if not payload or payload.get('type') != 'refresh':
            return JsonResponse({'error': 'رمز التجديد منتهي أو غير صالح'}, status=401)

        user = User.objects.filter(id=payload.get('user_id'), is_active=True).first()
        if not user:
            return JsonResponse({'error': 'الحساب غير متاح'}, status=401)

        profile = getattr(user, 'mobile_profile', None)
        if not profile:
            profile, _ = UserProfile.objects.get_or_create(user=user)

        new_access, new_refresh = generate_tokens_for_user(user, profile)
        return JsonResponse({
            'status': 'success',
            'access_token': new_access,
            'refresh_token': new_refresh,
            'token': new_access
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_mobile_auth()
def logout_view(request):
    """
    تسجيل الخروج وإبطال الجلسة على الخادم فورياً:
    - يبطل التوكن الحالي ويضيفه لقائمة التوكنات الملغاة (Blacklist)
    - يسجل عملية تسجيل الخروج في سجل التدقيق AuditTrailLog
    """
    token = getattr(request, 'auth_token', None)
    if not token:
        auth_header = request.headers.get('Authorization', '') or request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1].strip()

    if token:
        revoke_token(token, getattr(request, 'token_payload', None))

    AuditTrailLog.objects.create(
        user=request.user,
        action='تسجيل خروج وإبطال جلسة',
        entity_name='Auth',
        entity_id=str(request.user.id),
        details=f'تم إبطال جلسة التوكن للمستخدم [{request.user.username}]'
    )

    return JsonResponse({
        'status': 'success',
        'message': 'تم تسجيل الخروج وإبطال الجلسة بنجاح.'
    })



# =============================================================================
# 2. بوابة المالك المركزي (Owner Portal & Multi-School Finance)
# =============================================================================

@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_dashboard_summary_view(request):
    """
    إحصائيات لوحة تحكم المالك الإجمالية + قائمة المدارس والاشتراكات
    تدعم التصفية بالسنة الدراسية الحالية أو المحددة
    وتحسب المؤشرات المالية الثمانية المعتمدة للمالك بدقة
    """
    year_id = request.GET.get('year_id') or request.GET.get('year')
    current_year = AcademicYear.objects.filter(is_current=True).first()
    target_year = None
    if year_id and year_id != 'all':
        if str(year_id).isdigit():
            target_year = AcademicYear.objects.filter(id=int(year_id)).first()
        else:
            target_year = AcademicYear.objects.filter(name=str(year_id)).first()
    if not target_year and year_id != 'all':
        target_year = current_year

    schools = SchoolSettings.objects.all().order_by('id')
    total_schools = schools.count()
    total_students = Student.objects.filter(is_deleted=False).count()

    paid_in_full_count = 0
    partially_paid_count = 0
    unpaid_count = 0
    overdue_count = 0

    total_due = Decimal('0.00')
    total_received = Decimal('0.00')
    total_debt = Decimal('0.00')
    total_credit = Decimal('0.00')

    schools_data = []
    for s in schools:
        if target_year:
            sub = s.get_year_subscription(target_year)
            sub_fee = sub.final_due_amount
            paid = sub.total_paid
            rem = sub.remaining_balance
            credit = sub.credit_balance
            status = sub.payment_status
            status_display = sub.payment_status_display
            is_active = sub.is_active
        else:
            sub_fee = s.subscription_fee or Decimal('0.00')
            paid = s.total_paid_amount
            rem = s.remaining_subscription_balance
            credit = max(Decimal('0.00'), paid - sub_fee) if paid > sub_fee else Decimal('0.00')
            if rem == Decimal('0.00') and sub_fee > Decimal('0.00'):
                status = 'PAID'
                status_display = 'مسدد بالكامل'
            elif paid > Decimal('0.00'):
                status = 'PARTIAL'
                status_display = 'مسدد جزئياً'
            else:
                status = 'UNPAID'
                status_display = 'غير مسدد'
            is_active = s.is_subscription_active

        total_due += sub_fee
        total_received += paid
        total_debt += rem
        total_credit += credit

        if status == 'PAID':
            paid_in_full_count += 1
        elif status == 'PARTIAL':
            partially_paid_count += 1
        elif status == 'OVERDUE':
            overdue_count += 1
        else:
            unpaid_count += 1

        st_count = s.enrolled_students_count

        schools_data.append({
            'id': s.id,
            'school_name': s.school_name,
            'ministry_code': s.ministry_school_code,
            'director_name': s.director_name or 'غير محدد',
            'students_count': st_count,
            'subscription_fee': float(sub_fee),
            'total_paid': float(paid),
            'remaining_balance': float(rem),
            'credit_balance': float(credit),
            'payment_status': status,
            'payment_status_display': status_display,
            'is_subscription_active': is_active,
            'year_name': target_year.name if target_year else 'جميع السنوات',
            'year_id': target_year.id if target_year else None,
        })

    pending_activations_count = StudentActivation.objects.filter(status=SubscriptionStatus.PENDING).count()

    all_years = AcademicYear.objects.all().order_by('-start_date')[:15]
    years_data = [{
        'id': y.id,
        'name': y.name,
        'is_current': y.is_current,
    } for y in all_years]

    return JsonResponse({
        'status': 'success',
        'metrics': {
            'total_schools': total_schools,
            'paid_in_full_count': paid_in_full_count,
            'partially_paid_count': partially_paid_count,
            'unpaid_count': unpaid_count,
            'overdue_count': overdue_count,
            'total_students': total_students,
            'total_subscriptions': float(total_due),
            'total_due': float(total_due),
            'total_received': float(total_received),
            'total_paid': float(total_received),
            'total_remaining': float(total_debt),
            'total_debt': float(total_debt),
            'total_credit': float(total_credit),
            'pending_activations_count': pending_activations_count,
            'active_year': target_year.name if target_year else (current_year.name if current_year else '2026-2027'),
            'active_year_id': target_year.id if target_year else (current_year.id if current_year else None),
        },
        'years': years_data,
        'schools': schools_data
    })


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_school_details_view(request, school_id):
    """تفاصيل المدرسة وسجل دفعاتها المالية ومديريها واشتراكها السنوي"""
    school = get_object_or_404(SchoolSettings, pk=school_id)
    year_id = request.GET.get('year_id') or request.GET.get('year')
    current_year = AcademicYear.objects.filter(is_current=True).first()
    
    if year_id:
        if str(year_id).isdigit():
            target_year = AcademicYear.objects.filter(id=int(year_id)).first()
        else:
            target_year = AcademicYear.objects.filter(name=str(year_id)).first()
    else:
        target_year = current_year

    if not target_year:
        target_year = AcademicYear.objects.order_by('-start_date').first()

    sub = school.get_year_subscription(target_year)

    payments = school.subscription_payments.all().order_by('-payment_date', '-created_at')
    payments_data = []
    for p in payments:
        payments_data.append({
            'id': p.id,
            'amount': float(p.amount),
            'year': p.academic_year.name if p.academic_year else (target_year.name if target_year else ''),
            'payment_date': p.payment_date.strftime('%Y-%m-%d %H:%M'),
            'recorded_by': p.recorded_by.get_full_name() or p.recorded_by.username if p.recorded_by else 'المالك',
            'notes': p.notes,
        })

    managers = UserProfile.objects.filter(school=school, role=UserRole.MANAGER).select_related('user')
    managers_data = [{
        'id': m.user.id,
        'username': m.user.username,
        'full_name': m.full_name or m.user.get_full_name() or m.user.username,
        'phone': m.phone,
        'is_active': m.user.is_active
    } for m in managers]

    return JsonResponse({
        'status': 'success',
        'school': {
            'id': school.id,
            'school_name': school.school_name,
            'ministry_code': school.ministry_school_code,
            'director_name': school.director_name,
            'subscription_fee': float(sub.final_due_amount),
            'total_paid': float(sub.total_paid),
            'remaining_balance': float(sub.remaining_balance),
            'credit_balance': float(sub.credit_balance),
            'payment_status': sub.payment_status_display,
            'students_count': school.enrolled_students_count,
            'active_year': target_year.name,
        },
        'payments': payments_data,
        'managers': managers_data
    })


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_school_yearly_statement_view(request, school_id):
    """
    كشف حساب مستقل ومفصل لكل مدرسة ولكل سنة دراسية:
    المستحق، الخصومات والتسويات، المدفوع، المتبقي، سجل الحركات المالية
    """
    school = get_object_or_404(SchoolSettings, pk=school_id)
    year_id = request.GET.get('year_id') or request.GET.get('year')
    current_year = AcademicYear.objects.filter(is_current=True).first()
    
    if year_id:
        if str(year_id).isdigit():
            target_year = AcademicYear.objects.filter(id=int(year_id)).first()
        else:
            target_year = AcademicYear.objects.filter(name=str(year_id)).first()
    else:
        target_year = current_year

    if not target_year:
        target_year = AcademicYear.objects.order_by('-start_date').first()

    sub = school.get_year_subscription(target_year)

    payments = SchoolSubscriptionPayment.objects.filter(
        school=school,
        academic_year=target_year
    ).order_by('-payment_date', '-created_at')

    if not payments.exists():
        payments = school.subscription_payments.all().order_by('-payment_date', '-created_at')

    payments_data = []
    for p in payments:
        payments_data.append({
            'id': p.id,
            'amount': float(p.amount),
            'payment_date': p.payment_date.strftime('%Y-%m-%d %H:%M'),
            'recorded_by': p.recorded_by.get_full_name() or p.recorded_by.username if p.recorded_by else 'المالك',
            'notes': p.notes,
        })

    adjustments = SchoolPaymentAdjustment.objects.filter(
        school=school,
        academic_year=target_year
    ).order_by('-created_at')

    adjustments_data = []
    for a in adjustments:
        adjustments_data.append({
            'id': a.id,
            'type': a.get_adjustment_type_display(),
            'amount': float(a.amount),
            'reason': a.reason,
            'created_at': a.created_at.strftime('%Y-%m-%d %H:%M'),
            'recorded_by': a.recorded_by.username if a.recorded_by else 'المالك'
        })

    all_subs = school.yearly_subscriptions.all().select_related('academic_year').order_by('-academic_year__start_date')
    history_subs = [{
        'year_id': s.academic_year.id,
        'year_name': s.academic_year.name,
        'fee': float(s.fee_amount),
        'discount': float(s.discount_amount),
        'final_due': float(s.final_due_amount),
        'paid': float(s.total_paid),
        'remaining': float(s.remaining_balance),
        'status': s.payment_status,
        'status_display': s.payment_status_display,
    } for s in all_subs]

    return JsonResponse({
        'status': 'success',
        'statement': {
            'school_id': school.id,
            'school_name': school.school_name,
            'ministry_code': school.ministry_school_code,
            'director_name': school.director_name or 'غير محدد',
            'academic_year': target_year.name,
            'academic_year_id': target_year.id,
            'original_fee': float(sub.fee_amount),
            'discount_amount': float(sub.discount_amount),
            'final_due_amount': float(sub.final_due_amount),
            'total_paid': float(sub.total_paid),
            'remaining_balance': float(sub.remaining_balance),
            'credit_balance': float(sub.credit_balance),
            'payment_status': sub.payment_status,
            'payment_status_display': sub.payment_status_display,
            'is_subscription_active': sub.is_active,
            'payments': payments_data,
            'adjustments': adjustments_data,
            'historical_years': history_subs,
        }
    })


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_update_school_subscription_view(request, school_id):
    """تحديد أو تعديل قيمة الاشتراك المالي للمدرسة عن سنة دراسية محددة حصراً من المالك"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        school = get_object_or_404(SchoolSettings, pk=school_id)
        data = json.loads(request.body.decode('utf-8'))
        fee_raw = data.get('subscription_fee')
        year_id = data.get('academic_year_id') or data.get('year_id')

        if fee_raw is None:
            return JsonResponse({'error': 'قيمة الاشتراك مطلوبة'}, status=400)

        fee = Decimal(str(fee_raw))
        if fee < Decimal('0.00'):
            return JsonResponse({'error': 'لا يمكن أن تكون قيمة الاشتراك بالسالب'}, status=400)

        if year_id:
            target_year = AcademicYear.objects.filter(id=year_id).first()
        else:
            target_year = AcademicYear.objects.filter(is_current=True).first()

        if not target_year:
            target_year = AcademicYear.objects.order_by('-start_date').first()

        sub = school.get_year_subscription(target_year)
        old_fee = sub.fee_amount
        sub.fee_amount = fee
        sub.save()

        school.subscription_fee = fee
        school.save(update_fields=['subscription_fee'])

        AuditTrailLog.objects.create(
            user=request.user,
            action='تعديل قيمة الاشتراك السنوي',
            entity_name='SchoolYearSubscription',
            entity_id=str(sub.id),
            details=f'المالك عدل اشتراك مدرسة [{school.school_name}] للعام [{target_year.name}] من {old_fee} إلى {fee}'
        )

        return JsonResponse({
            'status': 'success',
            'message': f'تم تحديث قيمة اشتراك مدرسة [{school.school_name}] للعام ({target_year.name}) إلى {fee:,.0f} بنجاح.',
            'year_name': target_year.name,
            'subscription_fee': float(sub.fee_amount),
            'final_due_amount': float(sub.final_due_amount),
            'total_paid': float(sub.total_paid),
            'remaining_balance': float(sub.remaining_balance),
            'payment_status': sub.payment_status_display,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_add_payment_view(request, school_id):
    """
    تسجيل دفعة مالية جديدة لمدرسة عن سنة دراسية محددة:
    المبلغ، السنة، التاريخ والوقت، المدرسة، المسجل (المالك)، ملاحظة اختيارية
    مع تحديث المتبقي فوراً ومنع المبالغ السالبة.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        school = get_object_or_404(SchoolSettings, pk=school_id)
        data = json.loads(request.body.decode('utf-8'))
        amount_raw = data.get('amount')
        notes = data.get('notes', '').strip()
        custom_date = data.get('payment_date')
        year_id = data.get('academic_year_id') or data.get('year_id')

        if not amount_raw:
            return JsonResponse({'error': 'المبلغ مطلوب'}, status=400)

        amount = Decimal(str(amount_raw))
        if amount <= Decimal('0.00'):
            return JsonResponse({'error': 'يجب أن يكون مبلغ الدفعة أكبر من صفر'}, status=400)

        if year_id:
            target_year = AcademicYear.objects.filter(id=year_id).first()
        else:
            target_year = AcademicYear.objects.filter(is_current=True).first()

        if not target_year:
            target_year = AcademicYear.objects.order_by('-start_date').first()

        sub = school.get_year_subscription(target_year)

        payment_dt = timezone.now()
        if custom_date:
            try:
                payment_dt = timezone.datetime.fromisoformat(custom_date)
            except Exception:
                pass

        payment = SchoolSubscriptionPayment.objects.create(
            school=school,
            academic_year=target_year,
            subscription=sub,
            amount=amount,
            payment_date=payment_dt,
            recorded_by=request.user,
            notes=notes
        )

        AuditTrailLog.objects.create(
            user=request.user,
            action='تسجيل دفعة اشتراك سنوي',
            entity_name='SchoolSubscriptionPayment',
            entity_id=str(payment.id),
            details=f'المالك [{request.user.username}] سجل دفعة بقيمة {amount:,.0f} لمدرسة [{school.school_name}] عن عام [{target_year.name}]. ملاحظة: {notes}'
        )

        return JsonResponse({
            'status': 'success',
            'message': f'تم تسجيل دفعة بقيمة {amount:,.0f} لمدرسة [{school.school_name}] عن عام ({target_year.name}) بنجاح.',
            'payment': {
                'id': payment.id,
                'amount': float(payment.amount),
                'academic_year': target_year.name,
                'payment_date': payment.payment_date.strftime('%Y-%m-%d %H:%M'),
                'recorded_by': request.user.username,
                'notes': payment.notes,
            },
            'subscription_fee': float(sub.final_due_amount),
            'total_paid': float(sub.total_paid),
            'remaining_balance': float(sub.remaining_balance),
            'payment_status': sub.payment_status_display,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_add_adjustment_view(request, school_id):
    """إضافة خصم أو تسوية مالية لمدرسة عن سنة دراسية محددة"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        school = get_object_or_404(SchoolSettings, pk=school_id)
        data = json.loads(request.body.decode('utf-8'))
        amount_raw = data.get('amount')
        adj_type = data.get('adjustment_type', 'discount')
        reason = data.get('reason', '').strip()
        year_id = data.get('academic_year_id') or data.get('year_id')

        if not amount_raw:
            return JsonResponse({'error': 'مبلغ الخصم أو التسوية مطلوب'}, status=400)

        amount = Decimal(str(amount_raw))
        if amount <= Decimal('0.00'):
            return JsonResponse({'error': 'يجب أن يكون مبلغ الخصم أكبر من صفر'}, status=400)

        if year_id:
            target_year = AcademicYear.objects.filter(id=year_id).first()
        else:
            target_year = AcademicYear.objects.filter(is_current=True).first()

        if not target_year:
            target_year = AcademicYear.objects.order_by('-start_date').first()

        sub = school.get_year_subscription(target_year)
        sub.discount_amount = (sub.discount_amount or Decimal('0.00')) + amount
        sub.save()

        adj = SchoolPaymentAdjustment.objects.create(
            school=school,
            academic_year=target_year,
            subscription=sub,
            adjustment_type=adj_type,
            amount=amount,
            reason=reason,
            recorded_by=request.user
        )

        AuditTrailLog.objects.create(
            user=request.user,
            action='منح خصم أو تسوية مالية',
            entity_name='SchoolPaymentAdjustment',
            entity_id=str(adj.id),
            details=f'المالك سجل خصماً بقيمة {amount:,.0f} لمدرسة [{school.school_name}] للعام [{target_year.name}]. السبب: {reason}'
        )

        return JsonResponse({
            'status': 'success',
            'message': f'تم تسجيل الخصم بقيمة {amount:,.0f} لمدرسة [{school.school_name}] بنجاح.',
            'adjustment': {
                'id': adj.id,
                'amount': float(adj.amount),
                'type': adj.get_adjustment_type_display(),
                'reason': adj.reason,
            },
            'final_due_amount': float(sub.final_due_amount),
            'remaining_balance': float(sub.remaining_balance),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_create_school_view(request):
    """إنشاء مدرسة جديدة في المنظومة وتحديد اشتراكها المالي"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        school_name = data.get('school_name', '').strip()
        code = data.get('ministry_school_code', '').strip()
        director_name = data.get('director_name', '').strip()
        fee_raw = data.get('subscription_fee', 0)

        if not school_name:
            return JsonResponse({'error': 'اسم المدرسة مطلوب'}, status=400)

        fee = Decimal(str(fee_raw or 0))
        if fee < Decimal('0.00'):
            fee = Decimal('0.00')

        school = SchoolSettings.objects.create(
            school_name=school_name,
            ministry_school_code=code,
            director_name=director_name,
            subscription_fee=fee,
            is_subscription_active=True,
            installation_date=timezone.now().date()
        )

        AuditTrailLog.objects.create(
            user=request.user,
            action='إنشاء مدرسة جديدة',
            entity_name='SchoolSettings',
            entity_id=str(school.id),
            details=f'المالك أنشأ مدرسة [{school_name}] بكود [{code}] واشتراك [{fee}]'
        )

        return JsonResponse({
            'status': 'success',
            'message': f'تم إنشاء مدرسة [{school_name}] بنجاح.',
            'school': {
                'id': school.id,
                'school_name': school.school_name,
                'ministry_code': school.ministry_school_code,
                'subscription_fee': float(school.subscription_fee),
                'total_paid': float(school.total_paid_amount),
                'remaining_balance': float(school.remaining_subscription_balance),
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_create_manager_view(request, school_id):
    """إنشاء حساب مدير مدرسة مستقل وربطه بمدرسته حصراً"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        school = get_object_or_404(SchoolSettings, pk=school_id)
        data = json.loads(request.body.decode('utf-8'))
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        full_name = data.get('full_name', '').strip()
        phone = data.get('phone', '').strip()

        if not username or not password:
            return JsonResponse({'error': 'اسم المستخدم وكلمة المرور مطلوبان'}, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': 'اسم المستخدم هذا مستخدم مسبقاً'}, status=400)

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=full_name.split()[0] if full_name else 'المدير',
            is_active=True
        )

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserRole.MANAGER
        profile.school = school
        profile.full_name = full_name
        profile.phone = phone
        profile.is_approved = True
        profile.save()

        AuditTrailLog.objects.create(
            user=request.user,
            action='إنشاء حساب مدير',
            entity_name='User',
            entity_id=str(user.id),
            details=f'المالك أنشأ حساب المدير [{username}] لمدرسة [{school.school_name}]'
        )

        return JsonResponse({
            'status': 'success',
            'message': f'تم إنشاء حساب المدير [{username}] لمدرسة [{school.school_name}] بنجاح.',
            'manager': {
                'id': user.id,
                'username': user.username,
                'full_name': profile.full_name,
                'school_id': school.id,
                'school_name': school.school_name,
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
# 3. دورة تفعيل أولياء الأمور والأكواد الفريدة (Parent Activation & Codes)
# =============================================================================

@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_pending_activations_view(request):
    """
    قائمة طلبات تفعيل أولياء الأمور المعلقة بانتظار موافقة المالك
    مع تفاصيل المدرسة والطالب والكود
    """
    pending = StudentActivation.objects.filter(
        status=SubscriptionStatus.PENDING
    ).select_related('student', 'parent', 'school', 'student__school').order_by('-requested_at')

    data = []
    for a in pending:
        sch_name = a.school.school_name if a.school else (a.student.school.school_name if a.student and a.student.school else 'المدرسة العامة')
        data.append({
            'id': a.id,
            'activation_code': a.activation_code,
            'student_id': a.student.id,
            'student_name': str(a.student),
            'school_id': a.school_id or (a.student.school_id if a.student else None),
            'school_name': sch_name,
            'parent_name': a.parent.full_name if a.parent else (a.parent.user.username if a.parent else 'ولي الأمر'),
            'parent_phone': a.parent.phone if a.parent else '',
            'requested_at': a.requested_at.strftime('%Y-%m-%d %H:%M') if a.requested_at else '',
            'status': 'بانتظار موافقة المالك'
        })

    return JsonResponse({
        'status': 'success',
        'count': len(data),
        'pending_activations': data,
        'requests': data
    })


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_decide_activation_view(request, activation_id):
    """
    موافقة المالك واعتماد كود التفعيل أو رفضه:
    - عند الموافقة: الحالة ACTIVE، الكود يصبح مستخدماً وغير قابل لإعادة الاستخدام.
    - تسجيل الحدث في Audit Log: من أنشأه، المدرسة، الطالب، أوقات الطلب والموافقة، المالك.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        activation = get_object_or_404(StudentActivation.objects.select_related('student', 'parent', 'school', 'academic_year'), pk=activation_id)
        data = json.loads(request.body.decode('utf-8'))
        action = data.get('action', 'APPROVE').strip().upper()
        reason = data.get('reason', '').strip()

        now = timezone.now()

        if action == 'APPROVE':
            activation.status = SubscriptionStatus.ACTIVE
            activation.is_used = True
            activation.activated_at = now
            activation.decision_at = now
            activation.decision_by = request.user
            activation.starts_at = now
            if activation.academic_year and activation.academic_year.end_date:
                activation.expires_at = timezone.datetime.combine(
                    activation.academic_year.end_date,
                    timezone.datetime.min.time()
                ).replace(tzinfo=timezone.get_current_timezone())
            else:
                activation.expires_at = now + timedelta(days=365)
            activation.save()

            if activation.parent:
                activation.parent.is_approved = True
                activation.parent.save()
                activation.parent.user.is_active = True
                activation.parent.user.save()

                ParentStudentRelation.objects.filter(
                    parent=activation.parent,
                    student=activation.student
                ).update(is_confirmed=True)

                MobileNotification.objects.create(
                    user=activation.parent.user,
                    title='✅ تم تفعيل حساب ولي الأمر بنجاح',
                    body=f'تمت موافقة المالك على تفعيل حساب الطالب [{activation.student}] لمدة سنة كاملة.',
                    notification_type='SUBSCRIPTION'
                )

            # تسجيل التدقيق الشامل
            AuditTrailLog.objects.create(
                user=request.user,
                action='موافقة وتفعيل كود ولي أمر',
                entity_name='StudentActivation',
                entity_id=str(activation.id),
                details=(
                    f"المالك [{request.user.username}] وافق على تفعيل الكود [{activation.activation_code}] "
                    f"للطالب [{activation.student}] بمدرسة [{activation.school or activation.student.school}]. "
                    f"منشئ الكود: {activation.created_by}. وقت الاعتماد: {now.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            )

            return JsonResponse({
                'status': 'success',
                'message': f'تمت الموافقة وتفعيل كود الطالب [{activation.student}] بنجاح لمدة سنة.',
                'code_status': 'ACTIVE'
            })
        else:
            activation.status = SubscriptionStatus.REJECTED
            activation.decision_at = now
            activation.decision_by = request.user
            activation.rejection_reason = reason or 'تم رفض الطلب لعدم استيفاء الشروط'
            activation.save()

            if activation.parent:
                MobileNotification.objects.create(
                    user=activation.parent.user,
                    title='❌ تم رفض طلب التفعيل',
                    body=f'سبب الرفض: {activation.rejection_reason}',
                    notification_type='SUBSCRIPTION'
                )

            AuditTrailLog.objects.create(
                user=request.user,
                action='رفض طلب تفعيل ولي أمر',
                entity_name='StudentActivation',
                entity_id=str(activation.id),
                details=f"المالك [{request.user.username}] رفض تفعيل الكود [{activation.activation_code}] للطالب [{activation.student}]. السبب: {activation.rejection_reason}"
            )

            return JsonResponse({
                'status': 'success',
                'message': 'تم رفض طلب التفعيل وتسجيل السبب بنجاح.',
                'code_status': 'REJECTED'
            })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_mobile_auth()
def generate_activation_code_view(request):
    """
    توليد كود تفعيل فريد من برنامج الحاسوب / الإدارة:
    - الكود مرتبط بالمدرسة، الطالب، والسنة الدراسية.
    - يتحقق من سريان اشتراك المدرسة السنوي.
    - صالح لسنة دراسية واحدة فقط.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        student_id = data.get('student_id')
        year_id = data.get('academic_year_id') or data.get('year_id')
        if not student_id:
            return JsonResponse({'error': 'معرف الطالب مطلوب'}, status=400)

        student = get_object_or_404(Student, pk=student_id)

        # فحص عزل المدرسة
        if not verify_school_access(request, student.school_id):
            return JsonResponse({'error': 'غير مصرح بتوليد كود لطالب خارج مدرستك'}, status=403)

        if year_id:
            target_year = AcademicYear.objects.filter(id=year_id).first()
        else:
            target_year = AcademicYear.objects.filter(is_current=True).first()
        if not target_year:
            target_year = AcademicYear.objects.order_by('-start_date').first()

        # التحقق من أن اشتراك المدرسة السنوي فعال
        sch = student.school
        if sch and not sch.is_year_subscription_active(target_year):
            return JsonResponse({'error': f'اشتراك مدرسة [{sch.school_name}] للعام ({target_year.name}) غير مفعل. يجب تفعيل اشتراك المدرسة أولاً.'}, status=403)

        # توليد كود عشوائي فريد
        unique_suffix = uuid.uuid4().hex[:6].upper()
        sch_id = student.school_id or 1
        year_code = target_year.name.replace('/', '-').replace(' ', '')
        activation_code = f"ACT-SCH{sch_id}-{year_code}-STU{student.id}-{unique_suffix}"

        # إنهاء أي كود قديم معلق لنفس السنة إن وجد
        StudentActivation.objects.filter(
            student=student,
            academic_year=target_year,
            status=SubscriptionStatus.PENDING
        ).delete()

        activation = StudentActivation.objects.create(
            student=student,
            school=student.school,
            academic_year=target_year,
            activation_code=activation_code,
            status=SubscriptionStatus.PENDING,
            created_by=request.user,
            requested_at=timezone.now()
        )

        # إرسال إشعار للمالك
        owner_users = User.objects.filter(Q(is_superuser=True) | Q(mobile_profile__role=UserRole.OWNER)).distinct()
        for o_user in owner_users:
            MobileNotification.objects.create(
                user=o_user,
                title='طلب تفعيل حساب ولي أمر جديد',
                body=f"المدرسة: {student.school or 'مدرسة المنظومة'} | الطالب: {student} | كود التفعيل: {activation_code} | الحالة: بانتظار موافقة المالك",
                notification_type='ACTIVATION_REQUEST'
            )

        AuditTrailLog.objects.create(
            user=request.user,
            action='توليد كود تفعيل',
            entity_name='StudentActivation',
            entity_id=str(activation.id),
            details=f"المستخدم [{request.user.username}] أنشأ كود التفعيل [{activation_code}] للطالب [{student}] بمدرسة [{student.school}]"
        )

        return JsonResponse({
            'status': 'success',
            'message': 'تم توليد كود التفعيل بنجاح وإرسال إشعار للمالك بانتظار الموافقة.',
            'activation_code': activation_code,
            'student_id': student.id,
            'student_name': str(student),
            'status_label': 'بانتظار موافقة المالك'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.PARENT])
@transaction.atomic
def submit_activation_code_view(request):
    """
    تطبيق ولي الأمر: إدخال كود التفعيل
    - الكود فريد ولا يمكن استخدامه مرتين.
    - لا يمكن تفعيله لطالب آخر.
    - يتحول لـ PENDING بانتظار موافقة المالك.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        code = data.get('code', '').strip().upper()

        if not code:
            return JsonResponse({'error': 'يرجى إدخال كود التفعيل المستلم من المدرسة'}, status=400)

        activation = StudentActivation.objects.select_for_update().filter(activation_code=code).first()
        if not activation:
            return JsonResponse({'error': 'كود التفعيل غير صحيح أو لم يصدر من المنظومة'}, status=404)

        if activation.status == SubscriptionStatus.ACTIVE or activation.is_used:
            return JsonResponse({'error': 'هذا الكود تم استخدامه وتفعيله مسبقاً ولا يمكن استخدامه مرة أخرى'}, status=400)

        parent_profile = request.user_profile
        if activation.status == SubscriptionStatus.PENDING and activation.parent_id is not None:
            if activation.parent_id == parent_profile.id:
                return JsonResponse({
                    'status': 'success',
                    'message': 'تم تقديم طلب التفعيل مسبقاً، وهو بانتظار اعتماد وموافقة المالك.'
                })
            return JsonResponse({
                'error': 'هذا الكود مرتبط بطلب تفعيل آخر وهو بانتظار الموافقة'
            }, status=400)

        if activation.academic_year:
            if activation.academic_year.is_archived:
                return JsonResponse({'error': f'انتهت صلاحية هذا الكود لانتهاء سنته الدراسية ({activation.academic_year.name}). يرجى استلام كود العام الجديد من المدرسة.'}, status=400)
            if activation.expires_at and timezone.now() > activation.expires_at:
                return JsonResponse({'error': 'هذا الكود منتهي الصلاحية.'}, status=400)

        sch = activation.school or activation.student.school
        if sch and activation.academic_year and not sch.is_year_subscription_active(activation.academic_year):
            return JsonResponse({'error': f'اشتراك المدرسة للعام ({activation.academic_year.name}) غير مفعل حالياً. يرجى مراجعة إدارة المدرسة.'}, status=403)

        activation.parent = parent_profile
        activation.status = SubscriptionStatus.PENDING
        activation.requested_at = timezone.now()
        activation.save()

        # ربط ولي الأمر بالطالب بانتظار التأكيد
        ParentStudentRelation.objects.get_or_create(
            parent=parent_profile,
            student=activation.student,
            defaults={'is_confirmed': False}
        )

        # إشعار المالك
        owner_users = User.objects.filter(Q(is_superuser=True) | Q(mobile_profile__role=UserRole.OWNER)).distinct()
        for o_user in owner_users:
            MobileNotification.objects.create(
                user=o_user,
                title='طلب تفعيل حساب ولي أمر جديد',
                body=f"المدرسة: {activation.school or activation.student.school} | الطالب: {activation.student} | كود التفعيل: {activation.activation_code} | الحالة: بانتظار موافقة المالك",
                notification_type='ACTIVATION_REQUEST'
            )

        AuditTrailLog.objects.create(
            user=request.user,
            action='طلب تفعيل كود',
            entity_name='StudentActivation',
            entity_id=str(activation.id),
            details=f"ولي الأمر [{request.user.username}] طلب تفعيل الكود [{code}] للطالب [{activation.student}]"
        )

        return JsonResponse({
            'status': 'success',
            'message': 'تم استلام كود التفعيل، وهو بانتظار اعتماد وموافقة المالك لتفعيل الحساب.'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
# 4. بوابة مدير المدرسة والعزل الصارم (Manager Multi-School Isolation)
# =============================================================================

@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.MANAGER, UserRole.OWNER])
def manager_dashboard_view(request):
    """
    لوحة مدير المدرسة:
    المدير يرى مدرسة واحدة فقط، ولا يمكنه رؤية أي بيانات لمدرسة أخرى.
    """
    school_id = request.school_id
    if not school_id and request.user_role != UserRole.OWNER:
        return JsonResponse({'error': 'حسابك غير مرتبط بمدرسة'}, status=403)

    if request.user_role == UserRole.OWNER and not school_id:
        first_sch = SchoolSettings.objects.first()
        school_id = first_sch.id if first_sch else 1

    school = get_object_or_404(SchoolSettings, pk=school_id)

    students_count = Student.objects.filter(school=school, is_deleted=False).count()
    teachers_count = Teacher.objects.filter(school=school, is_active=True).count()

    today = timezone.now().date()
    att_today = Attendance.objects.filter(student__school=school, date=today)
    present_count = att_today.filter(status='present').count()
    absent_count = att_today.filter(status='absent').count()

    pending_grades = GradeEntry.objects.filter(student__school=school, status=GradeStatus.SUBMITTED).count()
    pending_activations = StudentActivation.objects.filter(school=school, status=SubscriptionStatus.PENDING).count()

    return JsonResponse({
        'status': 'success',
        'school_name': school.school_name,
        'school_code': school.ministry_school_code,
        'stats': {
            'students_count': students_count,
            'teachers_count': teachers_count,
            'today_present': present_count,
            'today_absent': absent_count,
            'pending_grades': pending_grades,
            'pending_activations': pending_activations,
        }
    })


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.MANAGER, UserRole.OWNER])
def manager_grades_approval_view(request):
    """استعراض واعتماد الدرجات المعلقة بمدرسة المدير حصراً مع دعم GET و POST"""
    if request.method == 'POST':
        return manager_approve_grade_view(request)

    school_id = request.school_id or 1
    # 1. الدرجات المرفوعة في جدول core.Grade
    core_grades = Grade.objects.filter(
        student__school_id=school_id,
        approval_state='SUBMITTED'
    ).select_related('student', 'subject', 'student__current_class')

    data = []
    for g in core_grades:
        data.append({
            'record_id': g.id,
            'id': g.id,
            'student_name': str(g.student),
            'class_name': str(g.student.current_class or ''),
            'subject': g.subject.name if hasattr(g.subject, 'name') else str(g.subject),
            'teacher_name': g.last_amended_by.username if g.last_amended_by else 'معلم المادة',
            'exam': 'كشف درجات معتمد',
            'students_count': 1,
            'final_score': float(g.final_grade or 0),
            'score': float(g.final_grade or 0),
            'status': 'SUBMITTED',
        })

    # 2. درجات مسودة الموبايل إن وجدت
    entries = GradeEntry.objects.filter(
        student__school_id=school_id,
        status=GradeStatus.SUBMITTED
    ).select_related('student', 'subject', 'teacher')

    for g in entries:
        data.append({
            'record_id': g.id,
            'id': g.id,
            'student_name': str(g.student),
            'class_name': str(g.student.current_class or ''),
            'subject': str(g.subject),
            'teacher_name': g.teacher.full_name or g.teacher.user.username if g.teacher else 'المعلم',
            'exam': g.exam_type,
            'students_count': 1,
            'final_score': float(g.final_score or 0),
            'score': float(g.final_score or 0),
            'status': g.status,
        })

    return JsonResponse({'status': 'success', 'records': data, 'pending_grades': data})


# الاسم المستعار المعتمد لتطبيق الموبايل
manager_pending_grades_view = manager_grades_approval_view


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.MANAGER, UserRole.OWNER])
def manager_approve_grade_view(request):
    """مصادقة المدير على درجة الطالب في مدرسته مع فحص IDOR الصارم وحماية الدرجات المقفلة"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        record_id = data.get('record_id') or data.get('grade_id') or data.get('id')
        action = data.get('action', 'APPROVE').strip().upper()

        # فحص أولاً في جدول core.Grade
        core_g = Grade.objects.filter(pk=record_id).select_related('student').first()
        if core_g:
            if not verify_school_access(request, core_g.student.school_id):
                return JsonResponse({'error': 'غير مصرح لك بالمصادقة على درجات مدرسة أخرى'}, status=403)

            if core_g.is_locked:
                return JsonResponse({'error': 'لا يمكن تعديل درجة مقفلة نهائياً.'}, status=403)

            if action in ('APPROVE', 'APPROVED'):
                core_g.approval_state = 'APPROVED'
                msg = f'تمت مصادقة واعتماد درجة الطالب [{core_g.student}] رسمياً في المنظومة.'
            else:
                core_g.approval_state = 'DRAFT'
                msg = f'تمت إعادة كشف الدرجات للمعلم للتدقيق.'

            core_g.last_amended_by = request.user
            core_g.last_amended_at = timezone.now()
            core_g.save()

            AuditTrailLog.objects.create(
                user=request.user,
                action='اعتماد درجات' if action in ('APPROVE', 'APPROVED') else 'إعادة تدقيق درجات',
                entity_name='Grade',
                entity_id=str(core_g.id),
                details=f"المدير [{request.user.username}] أجرى [{action}] على درجة الطالب [{core_g.student}]"
            )
            return JsonResponse({'status': 'success', 'message': msg})

        # إذا كانت في GradeEntry
        entry = get_object_or_404(GradeEntry.objects.select_related('student'), pk=record_id)
        if not verify_school_access(request, entry.student.school_id):
            return JsonResponse({'error': 'غير مصرح لك بالمصادقة على درجات مدرسة أخرى'}, status=403)

        if action in ('APPROVE', 'APPROVED'):
            entry.status = GradeStatus.APPROVED
            entry.approved_at = timezone.now()
            entry.approved_by = request.user
            entry.save()
            msg = f'تمت مصادقة درجة الطالب [{entry.student}] بنجاح.'
        else:
            entry.status = GradeStatus.REJECTED
            entry.rejection_reason = data.get('reason', 'معادة للتدقيق')
            entry.save()
            msg = f'تمت إعادة كشف الدرجات للمعلم للتدقيق.'

        AuditTrailLog.objects.create(
            user=request.user,
            action='مصادقة درجة',
            entity_name='GradeEntry',
            entity_id=str(entry.id),
            details=f"المدير [{request.user.username}] نفذ [{action}] لدرجة الطالب [{entry.student}]"
        )
        return JsonResponse({'status': 'success', 'message': msg})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.MANAGER, UserRole.OWNER])
def manager_pending_activations_view(request):
    """استعراض واعتماد طلبات تفعيل أولياء الأمور لمدرسة المدير حصراً مع عزل المدارس"""
    school_id = request.school_id or 1

    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            act_id = data.get('activation_id') or data.get('id')
            action = data.get('action', 'approve').strip().lower()

            activation = get_object_or_404(StudentActivation.objects.select_related('student', 'parent', 'school'), pk=act_id)
            target_sch = activation.school_id or (activation.student.school_id if activation.student else None)
            if not verify_school_access(request, target_sch):
                return JsonResponse({'error': 'غير مصرح لك بالبت في تفعيلات مدرسة أخرى'}, status=403)

            now = timezone.now()
            if action in ('approve', 'active'):
                activation.status = SubscriptionStatus.ACTIVE
                activation.is_used = True
                activation.activated_at = now
                activation.decision_at = now
                activation.decision_by = request.user
                activation.starts_at = now
                if activation.academic_year and activation.academic_year.end_date:
                    activation.expires_at = timezone.datetime.combine(
                        activation.academic_year.end_date,
                        timezone.datetime.min.time()
                    ).replace(tzinfo=timezone.get_current_timezone())
                else:
                    activation.expires_at = now + timedelta(days=365)
                activation.save()

                if activation.parent:
                    activation.parent.is_approved = True
                    activation.parent.save()
                    activation.parent.user.is_active = True
                    activation.parent.user.save()
                    ParentStudentRelation.objects.filter(
                        parent=activation.parent,
                        student=activation.student
                    ).update(is_confirmed=True)

                msg = f'تم تفعيل حساب ولي الأمر للطالب [{activation.student}] بنجاح.'
            else:
                activation.status = SubscriptionStatus.REJECTED
                activation.rejection_reason = data.get('reason', 'مرفوض من إدارة المدرسة')
                activation.decision_at = now
                activation.decision_by = request.user
                activation.save()
                msg = f'تم رفض طلب تفعيل الحساب.'

            AuditTrailLog.objects.create(
                user=request.user,
                action='معالجة تفعيل ولي أمر',
                entity_name='StudentActivation',
                entity_id=str(activation.id),
                details=f"المدير [{request.user.username}] نفذ [{action}] على كود [{activation.activation_code}]"
            )
            return JsonResponse({'status': 'success', 'message': msg})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # GET: عرض الطلبات المعلقة بالمدرسة
    acts = StudentActivation.objects.filter(
        school_id=school_id,
        status=SubscriptionStatus.PENDING
    ).select_related('student', 'parent', 'academic_year', 'student__current_class')

    data = []
    for a in acts:
        p_name = a.parent.full_name or a.parent.user.username if a.parent else 'ولي الأمر'
        data.append({
            'id': a.id,
            'activation_id': a.id,
            'parent_name': p_name,
            'phone': a.parent.phone if a.parent else '',
            'student_name': str(a.student),
            'class_name': str(a.student.current_class or ''),
            'activation_code': a.activation_code,
            'requested_at': a.requested_at.strftime('%Y-%m-%d %H:%M') if a.requested_at else '',
        })

    return JsonResponse({'status': 'success', 'count': len(data), 'pending_activations': data})


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.MANAGER, UserRole.OWNER])
def manager_pending_requests_view(request):
    """استعراض ومعالجة طلبات الوثائق والتأييدات المدرسية مع عزل المدرسة الصارم"""
    school_id = request.school_id or 1

    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            req_id = data.get('request_id') or data.get('id')
            action = data.get('action', 'approve').strip().lower()

            req_obj = get_object_or_404(DocumentRequest.objects.select_related('student', 'parent'), pk=req_id)
            target_sch = req_obj.student.school_id if req_obj.student else None
            if not verify_school_access(request, target_sch):
                return JsonResponse({'error': 'غير مصرح لك بمعالجة طلبات مدرسة أخرى'}, status=403)

            if action in ('approve', 'process'):
                req_obj.status = DocumentRequestStatus.APPROVED
                req_obj.admin_response = data.get('response', 'تمت الموافقة وتصديق الوثيقة رسمياً من إدارة المدرسة.')
                msg = 'تمت معالجة الطلب وتصديقه بنجاح.'
            else:
                req_obj.status = DocumentRequestStatus.REJECTED
                req_obj.admin_response = data.get('response', 'معتذر لعدم استيفاء الشروط.')
                msg = 'تم رفض طلب الوثيقة.'

            req_obj.save()

            if req_obj.parent and req_obj.parent.user:
                MobileNotification.objects.create(
                    user=req_obj.parent.user,
                    title='رد إدارة المدرسة على معاملتك',
                    body=f"المعاملة: {req_obj.doc_type} للطالب {req_obj.student}. الرد: {req_obj.admin_response}",
                    notification_type='DOCUMENT_REQUEST'
                )

            AuditTrailLog.objects.create(
                user=request.user,
                action='معالجة طلب وثيقة',
                entity_name='DocumentRequest',
                entity_id=str(req_obj.id),
                details=f"المدير [{request.user.username}] نفذ [{action}] على طلب [{req_obj.doc_type}]"
            )
            return JsonResponse({'status': 'success', 'message': msg})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # GET: قائمة المعاملات المدرسية الواردة
    reqs = DocumentRequest.objects.filter(
        student__school_id=school_id,
        status=DocumentRequestStatus.SUBMITTED
    ).select_related('student', 'parent', 'parent__user').order_by('-created_at')

    data = []
    for r in reqs:
        data.append({
            'id': r.id,
            'request_id': r.id,
            'request_number': r.request_number,
            'request_type': r.doc_type,
            'student_name': str(r.student) if r.student else '',
            'parent_name': str(r.parent) if r.parent else 'ولي الأمر',
            'destination': r.destination,
            'notes': r.details,
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '',
        })

    return JsonResponse({'status': 'success', 'count': len(data), 'pending_requests': data})


# =============================================================================
# 5. بوابة المعلم وحماية الدرجات وسجل الحضور (Teacher Hub & Class Operations)
# =============================================================================

@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.TEACHER, UserRole.OWNER, UserRole.MANAGER])
def teacher_dashboard_view(request):
    """بيانات المعلم وصفوفه ومواده في مدرسته الحالية فقط دون أي fallback عام"""
    profile = request.user_profile
    classes_list = []
    subjects_list = []
    teacher_school = None

    if request.user_role == UserRole.TEACHER:
        teacher = Teacher.objects.filter(user=request.user, is_active=True).first()
        if not teacher:
            return JsonResponse({'error': 'لا يوجد ملف كادر تدريسي فعال مرتبط بهذا الحساب'}, status=403)

        if profile.school_id and teacher.school_id and profile.school_id != teacher.school_id:
            return JsonResponse({'error': 'تعارض في بيانات مدرسة المعلم'}, status=403)

        teacher_school = teacher.school or profile.school
        if not teacher_school:
            return JsonResponse({'error': 'المعلم غير مرتبط بمدرسة معتمدة'}, status=403)

        classes_list = [{'id': c.id, 'name': c.name} for c in teacher.school_classes.all()]
        subjects_list = [{'id': s.id, 'name': s.name} for s in teacher.subjects.all()]

    elif request.user_role == UserRole.MANAGER:
        teacher_school = profile.school
        if not teacher_school:
            return JsonResponse({'error': 'المدير غير مرتبط بمدرسة معتمدة'}, status=403)
        teacher = Teacher.objects.filter(user=request.user, is_active=True).first()
        if teacher:
            classes_list = [{'id': c.id, 'name': c.name} for c in teacher.school_classes.all()]
            subjects_list = [{'id': s.id, 'name': s.name} for s in teacher.subjects.all()]

    elif request.user_role == UserRole.OWNER:
        school_param = request.GET.get('school_id')
        if school_param:
            teacher_school = SchoolSettings.objects.filter(id=school_param).first()

    return JsonResponse({
        'status': 'success',
        'teacher_name': profile.full_name or request.user.get_full_name() or request.user.username,
        'school_name': teacher_school.school_name if teacher_school else 'المنظومة',
        'school_id': teacher_school.id if teacher_school else None,
        'classes': classes_list,
        'subjects': subjects_list,
    })


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.TEACHER, UserRole.OWNER, UserRole.MANAGER])
def teacher_classroom_view(request):
    """جلب طلاب صفوف المعلم المعتمدة في مدرسته فقط مع عزل كامل وإلغاء أي بيانات وهمية"""
    profile = request.user_profile
    teacher_classes = None
    school_id = None

    if request.user_role == UserRole.TEACHER:
        teacher = Teacher.objects.filter(user=request.user, is_active=True).first()
        if not teacher:
            return JsonResponse({'error': 'لا يوجد حساب كادر تدريسي نشط مرتبط بالمستخدم'}, status=403)

        if profile.school_id and teacher.school_id and profile.school_id != teacher.school_id:
            return JsonResponse({'error': 'تعارض في بيانات مدرسة المعلم'}, status=403)

        school = teacher.school or profile.school
        if not school:
            return JsonResponse({'error': 'المعلم غير منسوب لمدرسة معتمدة'}, status=403)
        school_id = school.id

        teacher_classes = teacher.school_classes.all()
        if not teacher_classes.exists():
            return JsonResponse({
                'status': 'success',
                'message': 'لا توجد صفوف دراسية مسندة لهذا المعلم حالياً',
                'class_name': 'لا توجد صفوف مسندة',
                'subject': '',
                'students': []
            })
    elif request.user_role == UserRole.MANAGER:
        if not profile.school:
            return JsonResponse({'error': 'المدير غير مرتبط بمدرسة معتمدة'}, status=403)
        school_id = profile.school.id
    elif request.user_role == UserRole.OWNER:
        school_param = request.GET.get('school_id')
        if not school_param:
            return JsonResponse({'error': 'يجب تحديد معرف المدرسة للمشرف العام'}, status=400)
        target_school = SchoolSettings.objects.filter(id=school_param).first()
        if not target_school:
            return JsonResponse({'error': 'المدرسة المحددة غير موجودة'}, status=404)
        school_id = target_school.id

    class_param = request.GET.get('class_id') or request.GET.get('classroom')
    target_classes = teacher_classes

    if class_param:
        if teacher_classes is not None:
            if str(class_param).isdigit():
                matched = teacher_classes.filter(id=int(class_param)).first()
            else:
                matched = teacher_classes.filter(Q(name=str(class_param).strip()) | Q(name__iexact=str(class_param).strip())).first()
            if not matched:
                return JsonResponse({'error': 'هذا الصف غير مسند لهذا المعلم'}, status=403)
            target_classes = [matched]
        else:
            if str(class_param).isdigit():
                matched = SchoolClass.objects.filter(id=int(class_param)).first()
            else:
                matched = SchoolClass.objects.filter(Q(name=str(class_param).strip()) | Q(name__iexact=str(class_param).strip())).first()
            target_classes = [matched] if matched else []

    students_qs = Student.objects.filter(school_id=school_id, is_deleted=False)
    if target_classes is not None:
        students_qs = students_qs.filter(current_class__in=target_classes)

    students_qs = students_qs.select_related('current_class', 'section')[:50]

    current_year = AcademicYear.objects.filter(is_current=True).first()
    year_name = current_year.name if current_year else '2026-2027'

    subject_obj = None
    subject_param = request.GET.get('subject_id') or request.GET.get('subject')
    if subject_param:
        if request.user_role == UserRole.TEACHER:
            teacher_obj = Teacher.objects.filter(user=request.user, is_active=True).first()
            if teacher_obj:
                if str(subject_param).isdigit():
                    subject_obj = teacher_obj.subjects.filter(id=int(subject_param)).first()
                else:
                    subject_obj = teacher_obj.subjects.filter(Q(name=str(subject_param).strip()) | Q(code=str(subject_param).strip())).first()
                if not subject_obj:
                    return JsonResponse({'error': 'هذه المادة غير مسندة لهذا المعلم'}, status=403)
        else:
            if str(subject_param).isdigit():
                subject_obj = Subject.objects.filter(id=int(subject_param)).first()
            else:
                subject_obj = Subject.objects.filter(Q(name=str(subject_param).strip()) | Q(code=str(subject_param).strip())).first()

    st_data = []
    for s in students_qs:
        score_val = None
        if subject_obj:
            gr = Grade.objects.filter(student=s, subject=subject_obj, academic_year=year_name).first()
            if gr:
                score_val = float(gr.final_grade or gr.first_term_month1 or 0)

        st_data.append({
            'student_code': s.registration_number or f'STU-{s.id:04d}',
            'id': s.id,
            'name': str(s),
            'status': 'PRESENT',
            'current_score': score_val,
            'current_class': str(s.current_class) if s.current_class else '',
            'section': str(s.section) if s.section else '',
        })

    class_name = str(students_qs[0].current_class) if students_qs and students_qs[0].current_class else 'الصف الدراسي'
    return JsonResponse({
        'status': 'success',
        'class_name': class_name,
        'subject': subject_obj.name if subject_obj else 'المادة الدراسية',
        'students': st_data
    })


# مسار مستعار متوافق مع شاشة تسجيل الحضور في تطبيق المعلم
teacher_class_students_view = teacher_classroom_view


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.TEACHER, UserRole.OWNER, UserRole.MANAGER])
def teacher_grading_sheet_view(request):
    """
    استعراض ورصد كشف درجات الطلاب للمعلم:
    - التحقق الصارم من انتماء الطالب لمدرسة المعلم وصف مسند إليه.
    - التحقق الصارم من أن المادة مسندة للمعلم في مدرسته دون أي fallback تلقائي.
    - GET: جلب الطلاب والدرجات الحالية للمادة المحددة فقط من core.Grade.
    - POST: حفظ المسودة أو إرسال للاعتماد مع فحص حماية Locked Grades ومنع IDOR.
    """
    profile = request.user_profile
    teacher_classes = None
    teacher = None
    school_id = None

    if request.user_role == UserRole.TEACHER:
        teacher = Teacher.objects.filter(user=request.user, is_active=True).first()
        if not teacher:
            return JsonResponse({'error': 'لا يوجد حساب كادر تدريسي فعال مرتبط بهذا المستخدم'}, status=403)

        if profile.school_id and teacher.school_id and profile.school_id != teacher.school_id:
            return JsonResponse({'error': 'تعارض في بيانات مدرسة المعلم'}, status=403)

        school = teacher.school or profile.school
        if not school:
            return JsonResponse({'error': 'المعلم غير مرتبط بمدرسة معتمدة'}, status=403)
        school_id = school.id
        teacher_classes = teacher.school_classes.all()
    elif request.user_role == UserRole.MANAGER:
        if not profile.school:
            return JsonResponse({'error': 'المدير غير مرتبط بمدرسة معتمدة'}, status=403)
        school_id = profile.school.id
    elif request.user_role == UserRole.OWNER:
        school_param = request.GET.get('school_id')
        if request.method == 'POST':
            try:
                body_data = json.loads(request.body.decode('utf-8'))
                school_param = body_data.get('school_id') or school_param
            except Exception:
                pass
        if not school_param:
            return JsonResponse({'error': 'يجب تحديد معرف المدرسة للمشرف العام'}, status=400)
        target_school = SchoolSettings.objects.filter(id=school_param).first()
        if not target_school:
            return JsonResponse({'error': 'المدرسة المحددة غير موجودة'}, status=404)
        school_id = target_school.id

    current_year = AcademicYear.objects.filter(is_current=True).first()
    year_name = current_year.name if current_year else '2026-2027'

    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            action = data.get('action', 'SUBMIT').strip().upper()
            grades_payload = data.get('grades') or data.get('records', [])
            subject_param = data.get('subject_id') or data.get('subject') or request.GET.get('subject_id')

            if not subject_param:
                return JsonResponse({'error': 'يجب تحديد المادة الدراسية لرصد الدرجات'}, status=400)

            validated_subject = None
            if request.user_role == UserRole.TEACHER:
                if str(subject_param).isdigit():
                    validated_subject = teacher.subjects.filter(id=int(subject_param)).first()
                else:
                    validated_subject = teacher.subjects.filter(Q(name=str(subject_param).strip()) | Q(code=str(subject_param).strip())).first()
                if not validated_subject:
                    return JsonResponse({'error': 'هذه المادة غير مسندة لهذا المعلم'}, status=403)
            else:
                if str(subject_param).isdigit():
                    validated_subject = Subject.objects.filter(id=int(subject_param)).first()
                else:
                    validated_subject = Subject.objects.filter(Q(name=str(subject_param).strip()) | Q(code=str(subject_param).strip())).first()
                if not validated_subject:
                    return JsonResponse({'error': 'المادة الدراسية المحددة غير صالحة'}, status=400)

            updated_count = 0
            for item in grades_payload:
                st_id = item.get('student_id') or item.get('id')
                if not st_id:
                    continue

                raw_score = item.get('score', item.get('final_score', item.get('month1', 0)))
                try:
                    score_val = Decimal(str(raw_score if raw_score not in ('', None) else 0))
                except Exception:
                    score_val = Decimal('0')

                st = Student.objects.filter(pk=st_id, is_deleted=False).first()
                if not st:
                    return JsonResponse({'error': f'الطالب برقم [{st_id}] غير موجود'}, status=404)

                # 1. فحص المدرسة الصارم: الطالب يجب أن يتبع لنفس مدرسة المعلم
                if st.school_id != school_id:
                    return JsonResponse({'error': f'غير مصرح لك برصد درجة لطالب خارج مدرستك (الطالب: {st})'}, status=403)

                # 2. فحص الصف الصارم: صف الطالب يجب أن يكون مسنداً للمعلم
                if request.user_role == UserRole.TEACHER and teacher_classes is not None:
                    if not st.current_class or st.current_class not in teacher_classes:
                        return JsonResponse({'error': f'الطالب [{st}] في صف غير مسند للمعلم'}, status=403)

                gr, created = Grade.objects.get_or_create(
                    student=st,
                    subject=validated_subject,
                    academic_year=year_name,
                    defaults={
                        'final_grade': score_val,
                        'first_term_month1': score_val,
                        'approval_state': 'SUBMITTED' if action == 'SUBMIT' else 'DRAFT'
                    }
                )

                if not created:
                    if gr.is_locked:
                        return JsonResponse({'error': f'الدرجة مقفلة نهائياً للطالب [{st}] ولا يمكن تعديلها.'}, status=403)

                    gr.final_grade = score_val
                    gr.first_term_month1 = score_val
                    gr.approval_state = 'SUBMITTED' if action == 'SUBMIT' else 'DRAFT'
                    gr.last_amended_by = request.user
                    gr.last_amended_at = timezone.now()
                    gr.save()

                GradeEntry.objects.create(
                    student=st,
                    subject=validated_subject,
                    teacher=profile,
                    exam_type='رصد كشف درجات',
                    final_score=score_val,
                    status=GradeStatus.SUBMITTED if action == 'SUBMIT' else GradeStatus.DRAFT
                )

                updated_count += 1

            AuditTrailLog.objects.create(
                user=request.user,
                action='رصد درجات' if action == 'SUBMIT' else 'حفظ مسودة درجات',
                entity_name='Grade',
                entity_id=str(school_id),
                details=f"المعلم [{request.user.username}] رصد درجات لـ [{updated_count}] طالب لمادة [{validated_subject}] بحالة [{action}]"
            )

            msg = f'تم إرسال كشف الدرجات للاعتماد بنجاح ({updated_count} طالب).' if action == 'SUBMIT' else f'تم حفظ مسودة الدرجات بنجاح ({updated_count} طالب).'
            return JsonResponse({'status': 'success', 'message': msg})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # GET: جلب كشف الطلاب لرصد الدرجات
    subject_param = request.GET.get('subject_id') or request.GET.get('subject')
    if not subject_param:
        return JsonResponse({'error': 'يجب تحديد المادة الدراسية'}, status=400)

    validated_subject = None
    if request.user_role == UserRole.TEACHER:
        if str(subject_param).isdigit():
            validated_subject = teacher.subjects.filter(id=int(subject_param)).first()
        else:
            validated_subject = teacher.subjects.filter(Q(name=str(subject_param).strip()) | Q(code=str(subject_param).strip())).first()
        if not validated_subject:
            return JsonResponse({'error': 'هذه المادة غير مسندة لهذا المعلم'}, status=403)
    else:
        if str(subject_param).isdigit():
            validated_subject = Subject.objects.filter(id=int(subject_param)).first()
        else:
            validated_subject = Subject.objects.filter(Q(name=str(subject_param).strip()) | Q(code=str(subject_param).strip())).first()
        if not validated_subject:
            return JsonResponse({'error': 'المادة الدراسية غير صالحة'}, status=400)

    class_param = request.GET.get('class_id') or request.GET.get('classroom')
    target_classes = teacher_classes

    if class_param:
        if teacher_classes is not None:
            if str(class_param).isdigit():
                matched_c = teacher_classes.filter(id=int(class_param)).first()
            else:
                matched_c = teacher_classes.filter(Q(name=str(class_param).strip()) | Q(name__iexact=str(class_param).strip())).first()
            if not matched_c:
                return JsonResponse({'error': 'هذا الصف غير مسند لهذا المعلم'}, status=403)
            target_classes = [matched_c]
        else:
            if str(class_param).isdigit():
                matched_c = SchoolClass.objects.filter(id=int(class_param)).first()
            else:
                matched_c = SchoolClass.objects.filter(Q(name=str(class_param).strip()) | Q(name__iexact=str(class_param).strip())).first()
            target_classes = [matched_c] if matched_c else []

    students_qs = Student.objects.filter(school_id=school_id, is_deleted=False)
    if target_classes is not None:
        students_qs = students_qs.filter(current_class__in=target_classes)

    students = students_qs.select_related('current_class')[:50]
    st_grades = []
    for s in students:
        gr = Grade.objects.filter(student=s, subject=validated_subject, academic_year=year_name).first()
        score_val = int(gr.final_grade or gr.first_term_month1 or 0) if gr else 0
        m1 = gr.first_term_month1 if gr and gr.first_term_month1 is not None else ''
        m2 = gr.first_term_month2 if gr and gr.first_term_month2 is not None else ''
        daily = gr.daily_average if gr and gr.daily_average is not None else ''

        st_grades.append({
            'id': s.id,
            'name': str(s),
            'score': score_val,
            'max_score': 100,
            'month1': m1,
            'month2': m2,
            'daily': daily,
            'is_locked': gr.is_locked if gr else False,
        })

    return JsonResponse({
        'status': 'success',
        'subject': validated_subject.name,
        'students_grades': st_grades,
        'students': st_grades
    })


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.TEACHER, UserRole.OWNER, UserRole.MANAGER])
def teacher_submit_attendance_view(request):
    """تثبيت سجل الحضور والغياب اليومي للطلاب مع عزل المدرسة الصارم"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        students_list = data.get('students', [])
        today = timezone.now().date()
        current_year = AcademicYear.objects.filter(is_current=True).first()
        year_name = current_year.name if current_year else '2026-2027'

        saved_count = 0
        for item in students_list:
            st_id = item.get('id')
            status_code = str(item.get('status', 'PRESENT')).strip().lower()
            if status_code not in ('present', 'absent', 'excused', 'late'):
                status_code = 'present'

            st = Student.objects.filter(pk=st_id).first()
            if not st or not verify_school_access(request, st.school_id):
                continue

            Attendance.objects.update_or_create(
                student=st,
                date=today,
                defaults={
                    'status': status_code,
                    'academic_year': year_name
                }
            )
            saved_count += 1

        AuditTrailLog.objects.create(
            user=request.user,
            action='تثبيت حضور وغياب',
            entity_name='Attendance',
            entity_id=str(request.school_id or 1),
            details=f"المعلم [{request.user.username}] ثبت سجل الحضور لـ [{saved_count}] طالب ليوم [{today}]"
        )

        return JsonResponse({
            'status': 'success',
            'message': f'تم تثبيت سجل الحضور بنجاح لـ ({saved_count}) طالب.'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.TEACHER, UserRole.OWNER, UserRole.MANAGER])
def teacher_submit_grades_view(request):
    """
    رصد درجات جديدة مع حماية IDOR صارمة:
    - التحقق من مطابقة المدرسة والصف والمادة المسندة للمعلم.
    - يسجل المعلم الحالي كمن أدخل الدرجة.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        student_id = data.get('student_id')
        score = data.get('score') or data.get('final_score')
        exam_type = data.get('exam_type', 'امتحان شهري')
        subject_param = data.get('subject_id') or data.get('subject')

        student = get_object_or_404(Student, pk=student_id, is_deleted=False)

        profile = request.user_profile
        teacher = None
        school_id = None

        if request.user_role == UserRole.TEACHER:
            teacher = Teacher.objects.filter(user=request.user, is_active=True).first()
            if not teacher:
                return JsonResponse({'error': 'لا يوجد حساب معلم نشط'}, status=403)

            if profile.school_id and teacher.school_id and profile.school_id != teacher.school_id:
                return JsonResponse({'error': 'تعارض في بيانات مدرسة المعلم'}, status=403)

            school = teacher.school or profile.school
            if not school:
                return JsonResponse({'error': 'المعلم غير مرتبط بمدرسة معتمدة'}, status=403)
            school_id = school.id

            # 1. فحص المدرسة
            if student.school_id != school_id:
                return JsonResponse({'error': 'غير مصرح لك برصد درجات لطالب خارج مدرستك'}, status=403)

            # 2. فحص الصف المسند
            if not student.current_class or student.current_class not in teacher.school_classes.all():
                return JsonResponse({'error': 'صف الطالب غير مسند لهذا المعلم'}, status=403)

            # 3. فحص المادة المسندة
            if not subject_param:
                return JsonResponse({'error': 'يجب تحديد المادة الدراسية'}, status=400)

            if str(subject_param).isdigit():
                subject = teacher.subjects.filter(id=int(subject_param)).first()
            else:
                subject = teacher.subjects.filter(Q(name=str(subject_param).strip()) | Q(code=str(subject_param).strip())).first()

            if not subject:
                return JsonResponse({'error': 'هذه المادة غير مسندة لهذا المعلم'}, status=403)

        elif request.user_role == UserRole.MANAGER:
            if not profile.school:
                return JsonResponse({'error': 'المدير غير مرتبط بمدرسة معتمدة'}, status=403)
            school_id = profile.school.id

            if student.school_id != school_id:
                return JsonResponse({'error': 'غير مصرح لك برصد درجات لطالب خارج مدرستك'}, status=403)

            if str(subject_param).isdigit():
                subject = Subject.objects.filter(id=int(subject_param)).first()
            else:
                subject = Subject.objects.filter(Q(name=str(subject_param).strip()) | Q(code=str(subject_param).strip())).first()

            if not subject:
                return JsonResponse({'error': 'المادة الدراسية غير صالحة'}, status=400)

        elif request.user_role == UserRole.OWNER:
            if str(subject_param).isdigit():
                subject = Subject.objects.filter(id=int(subject_param)).first()
            else:
                subject = Subject.objects.filter(Q(name=str(subject_param).strip()) | Q(code=str(subject_param).strip())).first()

            if not subject:
                return JsonResponse({'error': 'المادة الدراسية غير صالحة'}, status=400)

        current_year = AcademicYear.objects.filter(is_current=True).first()
        year_name = current_year.name if current_year else '2026-2027'

        # التثبيت المزدوج في core.Grade وفي GradeEntry
        gr, _ = Grade.objects.get_or_create(
            student=student,
            subject=subject,
            academic_year=year_name,
            defaults={'final_grade': Decimal(str(score or 0)), 'approval_state': 'SUBMITTED'}
        )
        if gr.is_locked:
            return JsonResponse({'error': 'الدرجة مقفلة نهائياً ولا يمكن تعديلها.'}, status=403)

        gr.final_grade = Decimal(str(score or 0))
        gr.approval_state = 'SUBMITTED'
        gr.last_amended_by = request.user
        gr.last_amended_at = timezone.now()
        gr.save()

        entry = GradeEntry.objects.create(
            student=student,
            subject=subject,
            teacher=request.user_profile,
            exam_type=exam_type,
            final_score=Decimal(str(score or 0)),
            status=GradeStatus.SUBMITTED
        )

        AuditTrailLog.objects.create(
            user=request.user,
            action='رصد درجة جديدة',
            entity_name='Grade',
            entity_id=str(gr.id),
            details=f"المعلم [{request.user.username}] رصد درجة [{score}] للطالب [{student}] في مادة [{subject}]"
        )

        return JsonResponse({
            'status': 'success',
            'message': f'تم رصد الدرجة بنجاح وتسجيل المعلم الحالي [{request.user.username}] كمدخل لها.',
            'entry_id': gr.id
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



# =============================================================================
# 6. بوابة ولي الأمر وحماية الأبناء (Parent Portal & IDOR Protection)
# =============================================================================

@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.PARENT, UserRole.OWNER])
def parent_dashboard_view(request):
    """
    لوحة تحكم ولي الأمر لأبنائه المعتمدين:
    تعرض الطالب، صفه الحالي بعد الترحيل، شعبته، السنة الدراسية الحالية، وحالة الكود الفعلي.
    """
    profile = request.user_profile
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if not current_year:
        current_year = AcademicYear.objects.order_by('-start_date').first()

    # إذا كان المالك يستعرض للتجربة
    if request.user_role == UserRole.OWNER:
        students = Student.objects.filter(is_deleted=False)[:2]
    else:
        relations = ParentStudentRelation.objects.filter(parent=profile, is_confirmed=True).select_related('student', 'student__current_class', 'student__section', 'student__school')
        students = [r.student for r in relations]

    students_data = []
    primary_code_status = 'EXPIRED'
    primary_school_active = True
    primary_grades = []
    primary_attendance = {}
    primary_avg = 0.0

    for idx, st in enumerate(students):
        year_name = current_year.name if current_year else '2026-2027'
        grades_query = Grade.objects.filter(student=st, academic_year=year_name).select_related('subject')
        if not grades_query.exists():
            grades_query = Grade.objects.filter(student=st).select_related('subject')

        grades_list = []
        total_score = Decimal('0')
        valid_count = 0
        for g in grades_query:
            final_val = g.final_grade_after_decision if g.final_grade_after_decision is not None else g.final_grade
            val_float = float(final_val) if final_val is not None else 0.0
            if final_val is not None:
                total_score += final_val
                valid_count += 1

            sub_name = g.subject.name if hasattr(g.subject, 'name') else str(g.subject)
            eval_str = g.get_status_display() or ('ناجح' if val_float >= 50 else 'راسب')
            note_str = f"سعي 1: {g.first_term_effort or '-'} | نصف سنة: {g.midyear_exam or '-'} | سعي 2: {g.second_term_effort or '-'}"

            grades_list.append({
                'id': g.id,
                'subject': sub_name,
                'subject_name': sub_name,
                'score': val_float,
                'final_score': val_float,
                'final': f"{val_float:.0f}%",
                'max': 100,
                'exam': 'النتيجة السنوية',
                'exam_title': 'الامتحان النهائي',
                'eval': eval_str,
                'status': g.status,
                'approval_state': g.approval_state,
                'approved': g.approval_state in ('APPROVED', 'AMENDED'),
                'note': note_str,
                'month1': float(g.first_term_month1 or 0),
                'month2': float(g.first_term_month2 or 0),
                'midyear': float(g.midyear_exam or 0),
                'annual_effort': float(g.annual_effort or 0),
            })

        avg_score = round(float(total_score / valid_count), 1) if valid_count > 0 else 0.0

        # سجل الحضور والغياب الحقيقي للطالب
        att_qs = Attendance.objects.filter(student=st)
        present_count = att_qs.filter(status='present').count()
        absent_count = att_qs.filter(status='absent').count()
        excused_count = att_qs.filter(status='excused').count()
        total_days = present_count + absent_count + excused_count
        att_rate = round((present_count / total_days) * 100, 1) if total_days > 0 else 100.0
        att_dict = {
            'present': present_count,
            'absent': absent_count,
            'excused': excused_count,
            'rate': att_rate,
            'total_days': total_days
        }

        # فحص كود الطالب الفعلي للعام الدراسي الحالي
        act = StudentActivation.objects.filter(student=st, academic_year=current_year).first()
        if not act:
            act = StudentActivation.objects.filter(student=st).order_by('-requested_at').first()

        now = timezone.now()
        if act and act.status == SubscriptionStatus.ACTIVE and (not act.expires_at or now <= act.expires_at):
            code_status = 'ACTIVE'
            code_status_display = f'سارٍ ومفعل لعام ({current_year.name if current_year else ""})'
        elif act and act.status == SubscriptionStatus.PENDING:
            code_status = 'PENDING'
            code_status_display = 'بانتظار موافقة الإدارة'
        else:
            code_status = 'EXPIRED'
            code_status_display = f'منتهي - يلزم كود عام ({current_year.name if current_year else ""})'

        school_active = st.school.is_year_subscription_active(current_year) if st.school else True
        if idx == 0:
            primary_code_status = code_status
            primary_school_active = school_active
            primary_grades = grades_list
            primary_attendance = att_dict
            primary_avg = avg_score

        students_data.append({
            'id': st.id,
            'full_name': str(st),
            'name': str(st),
            'grade_level': str(st.current_class) if st.current_class else 'المرحلة الدراسية',
            'section': str(st.section) if st.section else 'أ',
            'academic_year': current_year.name if current_year else '',
            'student_id_number': st.registration_number or f'STU-{st.id:04d}',
            'code_status': code_status,
            'code_status_display': code_status_display,
            'subscription_status': 'نشط ومفعل' if code_status == 'ACTIVE' and school_active else 'غير مفعل',
            'school_subscription_active': school_active,
            'school_name': st.school.school_name if st.school else 'المنظومة',
            'attendance': att_dict,
            'attendance_rate': f"{att_rate}%",
            'average': avg_score,
            'grades': grades_list
        })

    primary_student = students[0] if students else None
    student_info = None
    if primary_student:
        student_info = {
            'id': primary_student.id,
            'name': str(primary_student),
            'full_name': str(primary_student),
            'class_name': str(primary_student.current_class) if primary_student.current_class else '',
            'section': str(primary_student.section) if primary_student.section else '',
            'academic_year': current_year.name if current_year else '',
            'subscription_status': 'مفعل' if primary_code_status == 'ACTIVE' and primary_school_active else 'غير مفعل',
            'code_status': primary_code_status,
            'school': primary_student.school.school_name if primary_student.school else 'المنظومة',
            'average': primary_avg,
        }

    return JsonResponse({
        'status': 'success',
        'academic_year': current_year.name if current_year else '2026-2027',
        'school_subscription_active': primary_school_active,
        'student_info': student_info,
        'students': students_data,
        'approved_grades': primary_grades,
        'grades': primary_grades,
        'attendance': primary_attendance,
        'average': primary_avg,
    })


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.PARENT, UserRole.OWNER])
def parent_student_timeline_view(request, student_id):
    """
    سجل المسيرة الدراسية والترحيل التاريخي للطالب:
    يعرض تنقلات الطالب عبر الصفوف والسنوات والأكواد المرتبطة بها
    """
    if request.user_role != UserRole.OWNER and not verify_parent_student_access(request.profile_id, student_id):
        return JsonResponse({'error': 'غير مصرح لك بالاطلاع على مسيرة هذا الطالب'}, status=403)

    student = get_object_or_404(Student, pk=student_id)
    current_year = AcademicYear.objects.filter(is_current=True).first()

    histories = student.academic_history.all().select_related('academic_year', 'school_class').order_by('-academic_year__start_date')
    history_data = [{
        'academic_year': h.academic_year.name,
        'class_name': h.school_class.name,
        'section': h.section or '',
        'result_status': h.get_result_status_display(),
        'average': float(h.general_average) if h.general_average else 0,
        'recorded_at': h.recorded_at.strftime('%Y-%m-%d'),
    } for h in histories]

    activations = student.activations.all().select_related('academic_year').order_by('-requested_at')
    activations_data = [{
        'code': a.activation_code,
        'year': a.academic_year.name if a.academic_year else 'عام',
        'status': a.get_status_display(),
        'is_used': a.is_used,
        'starts_at': a.starts_at.strftime('%Y-%m-%d') if a.starts_at else '',
        'expires_at': a.expires_at.strftime('%Y-%m-%d') if a.expires_at else '',
    } for a in activations]

    return JsonResponse({
        'status': 'success',
        'student': {
            'id': student.id,
            'name': str(student),
            'school': student.school.school_name if student.school else '',
            'current_class': str(student.current_class) if student.current_class else '',
            'current_section': str(student.section) if student.section else '',
            'current_year': current_year.name if current_year else '',
        },
        'timeline': history_data,
        'activation_history': activations_data,
    })


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.PARENT, UserRole.OWNER])
def parent_student_detail_view(request, student_id):
    """تفاصيل طالب محدد لولي الأمر مع منع IDOR الصارم"""
    if request.user_role != UserRole.OWNER and not verify_parent_student_access(request.profile_id, student_id):
        return JsonResponse({'error': 'غير مصرح لك بالاطلاع على بيانات هذا الطالب'}, status=403)

    student = get_object_or_404(Student, pk=student_id)
    return JsonResponse({
        'status': 'success',
        'student': {
            'id': student.id,
            'name': str(student),
            'school_name': student.school.school_name if student.school else 'المنظومة',
            'class_name': str(student.current_class) if student.current_class else '',
            'section': str(student.section) if student.section else '',
        }
    })


# =============================================================================
# 7. الإشعارات والتعاميم والخدمات العامة (Notifications & News)
# =============================================================================

@csrf_exempt
@require_mobile_auth()
def list_notifications_view(request):
    """قائمة إشعارات المستخدم بما فيها طلبات التفعيل للمالك"""
    notes = MobileNotification.objects.filter(user=request.user).order_by('-created_at')[:30]
    unread_count = notes.filter(is_read=False).count()

    data = [{
        'id': n.id,
        'title': n.title,
        'body': n.body,
        'type': n.notification_type,
        'is_read': n.is_read,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
    } for n in notes]

    return JsonResponse({
        'status': 'success',
        'unread_count': unread_count,
        'notifications': data
    })


@csrf_exempt
@require_mobile_auth()
def mark_notifications_read_view(request):
    """تعليم كافة الإشعارات كمقروءة"""
    MobileNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'success', 'message': 'تم تحديث كافة الإشعارات'})


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.PARENT, UserRole.TEACHER, UserRole.MANAGER, UserRole.OWNER])
def school_news_view(request):
    """أخبار وتعاميم المدرسة مع عزل المدرسة الصارم وإرسال الإشعارات لمستخدمي المدرسة المعنية فقط"""
    profile = request.user_profile

    # منع أي مستخدم بدون مدرسة باستثناء المالك
    if request.user_role != UserRole.OWNER and not profile.school:
        if request.user_role == UserRole.PARENT:
            rel = ParentStudentRelation.objects.filter(parent=profile, is_confirmed=True).select_related('student__school').first()
            if not rel or not rel.student or not rel.student.school:
                return JsonResponse({'error': 'المستخدم غير مرتبط بمدرسة معتمدة'}, status=403)
        else:
            return JsonResponse({'error': 'المستخدم غير مرتبط بمدرسة معتمدة'}, status=403)

    if request.method == 'POST':
        if request.user_role not in (UserRole.MANAGER, UserRole.OWNER):
            return JsonResponse({'error': 'صلاحية غير كافية، نشر الأخبار للمدير أو المشرف حصراً'}, status=403)

        try:
            data = json.loads(request.body.decode('utf-8'))
            title = data.get('title', '').strip()
            content = data.get('content', '').strip()
            category = data.get('category', 'تعميم إداري').strip()
            is_urgent = bool(data.get('is_urgent', data.get('urgent', False)))

            if not title or not content:
                return JsonResponse({'error': 'العنوان والمحتوى مطلوبان'}, status=400)

            target_school = None
            if request.user_role == UserRole.MANAGER:
                target_school = profile.school
                client_school_id = data.get('school_id')
                if client_school_id and str(client_school_id) != str(target_school.id):
                    return JsonResponse({'error': 'غير مصرح لك بنشر أخبار لمدرسة أخرى'}, status=403)
            elif request.user_role == UserRole.OWNER:
                school_id_param = data.get('school_id')
                if school_id_param:
                    target_school = SchoolSettings.objects.filter(id=school_id_param).first()
                    if not target_school:
                        return JsonResponse({'error': 'المدرسة المحددة غير موجودة'}, status=404)

            news_item = SchoolNews.objects.create(
                school=target_school,
                title=title,
                content=content,
                category=category,
                is_urgent=is_urgent
            )

            # إشعار موجه حصرياً لمستخدمي المدرسة المستهدفة
            if target_school:
                target_profiles = UserProfile.objects.filter(
                    school=target_school,
                    user__is_active=True
                ).select_related('user')
            else:
                target_profiles = UserProfile.objects.filter(
                    user__is_active=True
                ).select_related('user')

            for prof in target_profiles:
                MobileNotification.objects.create(
                    user=prof.user,
                    title='🚨 تعميم عاجل: ' + title if is_urgent else '📢 إعلان مدرسي: ' + title,
                    body=content[:120],
                    notification_type='ANNOUNCEMENT'
                )

            return JsonResponse({'status': 'success', 'message': 'تم نشر التعميم بنجاح', 'id': news_item.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # GET: عرض أخبار مدرسة المستخدم فقط، وللمالك إمكانية تحديد مدرسة صراحة
    if request.user_role == UserRole.OWNER:
        school_param = request.GET.get('school_id')
        if school_param:
            target_school = SchoolSettings.objects.filter(id=school_param).first()
            if not target_school:
                return JsonResponse({'error': 'المدرسة المحددة غير موجودة'}, status=404)
            news_qs = SchoolNews.objects.filter(school=target_school)
        else:
            news_qs = SchoolNews.objects.all()
    elif request.user_role in (UserRole.MANAGER, UserRole.TEACHER):
        user_school = profile.school
        requested_school = request.GET.get('school_id')
        if requested_school and str(requested_school) != str(user_school.id):
            return JsonResponse({'error': 'غير مصرح بالوصول لأخبار مدرسة أخرى'}, status=403)
        news_qs = SchoolNews.objects.filter(school=user_school)
    elif request.user_role == UserRole.PARENT:
        user_school = profile.school
        if not user_school:
            rel = ParentStudentRelation.objects.filter(parent=profile, is_confirmed=True).select_related('student__school').first()
            if rel and rel.student:
                user_school = rel.student.school
        requested_school = request.GET.get('school_id')
        if requested_school and str(requested_school) != str(user_school.id):
            return JsonResponse({'status': 'success', 'news': []})
        news_qs = SchoolNews.objects.filter(school=user_school)

    news = news_qs.order_by('-is_urgent', '-created_at')[:30]
    data = [{
        'id': n.id,
        'school_id': n.school_id,
        'title': n.title,
        'body': n.content,
        'content': n.content,
        'category': n.category,
        'is_urgent': n.is_urgent,
        'urgent': n.is_urgent,
        'date': n.created_at.strftime('%Y-%m-%d')
    } for n in news]
    return JsonResponse({'status': 'success', 'news': data})


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.PARENT, UserRole.OWNER])
def parent_requests_view(request):
    """استعراض وتقديم طلبات ومعاملات ولي الأمر المدرسية مع منع IDOR"""
    profile = request.user_profile
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            student_id = data.get('student_id')
            doc_type = data.get('type') or data.get('doc_type', 'طلب تأييد استمرار بالدوام')
            destination = data.get('dest') or data.get('destination', 'إدارة المدرسة')
            details = data.get('notes') or data.get('details', '')

            student = None
            if student_id:
                if request.user_role != UserRole.OWNER and not verify_parent_student_access(request.profile_id, student_id):
                    return JsonResponse({'error': 'غير مصرح لك بتقديم طلب لهذا الطالب'}, status=403)
                student = get_object_or_404(Student, pk=student_id)
            else:
                rel = ParentStudentRelation.objects.filter(parent=profile, is_confirmed=True).first()
                if rel:
                    student = rel.student

            req_obj = DocumentRequest.objects.create(
                parent=profile,
                student=student,
                doc_type=doc_type,
                destination=destination,
                details=details,
                status=DocumentRequestStatus.SUBMITTED
            )

            if student and student.school:
                manager_users = UserProfile.objects.filter(school=student.school, role=UserRole.MANAGER).values_list('user', flat=True)
                for mu_id in manager_users:
                    MobileNotification.objects.create(
                        user_id=mu_id,
                        title='📝 معاملة جديدة واردة من ولي أمر',
                        body=f"طلب {doc_type} للطالب {student.full_name}",
                        notification_type='DOCUMENT_REQUEST'
                    )

            AuditTrailLog.objects.create(
                user=request.user,
                action='تقديم طلب معاملة مدرسية',
                entity_name='DocumentRequest',
                entity_id=str(req_obj.id),
                details=f"ولي الأمر [{request.user.username}] قدم طلب [{doc_type}] للطالب [{student}]"
            )

            return JsonResponse({'status': 'success', 'message': 'تم رفع الطلب لإدارة المدرسة بنجاح', 'id': req_obj.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # GET
    reqs = DocumentRequest.objects.filter(parent=profile).order_by('-created_at')
    data = [{
        'id': r.id,
        'type': r.doc_type,
        'doc_type': r.doc_type,
        'student': str(r.student) if r.student else '',
        'dest': r.destination,
        'destination': r.destination,
        'details': r.details,
        'status': 'تمت الموافقة بنجاح' if r.status == DocumentRequestStatus.APPROVED else ('مرفوض' if r.status == DocumentRequestStatus.REJECTED else 'قيد المراجعة والتدقيق'),
        'response': r.admin_response or 'قيد المراجعة والتدقيق من قبل الإدارة',
        'date': r.created_at.strftime('%Y-%m-%d') if r.created_at else ''
    } for r in reqs]
    return JsonResponse({'status': 'success', 'requests': data})


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.PARENT, UserRole.TEACHER, UserRole.MANAGER, UserRole.OWNER])
def homework_view(request):
    """عرض وبث الواجبات المدرسية مع عزل المدرسة الصارم والتحقق من الصف والمادة المسندة للمعلم"""
    profile = request.user_profile

    # فحص ارتباط المستخدم بمدرسة معتمدة (باستثناء المشرف العام)
    if request.user_role != UserRole.OWNER and not profile.school:
        if request.user_role == UserRole.PARENT:
            rel = ParentStudentRelation.objects.filter(parent=profile, is_confirmed=True).select_related('student__school').first()
            if not rel or not rel.student or not rel.student.school:
                return JsonResponse({'error': 'المستخدم غير مرتبط بمدرسة معتمدة'}, status=403)
        else:
            return JsonResponse({'error': 'المستخدم غير مرتبط بمدرسة معتمدة'}, status=403)

    if request.method == 'POST':
        if request.user_role == UserRole.PARENT:
            return JsonResponse({'error': 'غير مصرح لأولياء الأمور بنشر أو بث الواجبات المدرسية'}, status=403)

        try:
            data = json.loads(request.body.decode('utf-8'))
            title = data.get('title', '').strip()
            description = data.get('details') or data.get('description', '').strip()
            due_date = data.get('dueDate') or data.get('due_date', '').strip()
            raw_classroom = data.get('classroom', '').strip()
            raw_subject = data.get('subject', '').strip()

            if not title:
                return JsonResponse({'error': 'عنوان الواجب مطلوب'}, status=400)

            target_school = None
            classroom_name = raw_classroom or 'الصف الأول'
            subject_name = raw_subject or 'الرياضيات'

            if request.user_role == UserRole.TEACHER:
                teacher = Teacher.objects.filter(user=request.user, is_active=True).first()
                if not teacher:
                    return JsonResponse({'error': 'لا يوجد حساب معلم نشط'}, status=403)

                if profile.school_id and teacher.school_id and profile.school_id != teacher.school_id:
                    return JsonResponse({'error': 'تعارض في بيانات مدرسة المعلم'}, status=403)

                target_school = teacher.school or profile.school
                if not target_school:
                    return JsonResponse({'error': 'المعلم غير مرتبط بمدرسة معتمدة'}, status=403)

                client_school_id = data.get('school_id')
                if client_school_id and str(client_school_id) != str(target_school.id):
                    return JsonResponse({'error': 'غير مصرح لك ببث واجب لمدرسة أخرى'}, status=403)

                # 1. التحقق الصارم من الصف: يجب أن يكون مسنداً للمعلم
                if not raw_classroom:
                    return JsonResponse({'error': 'يرجى تحديد الصف أو الشعبة المستهدفة'}, status=400)

                matched_class = None
                if str(raw_classroom).isdigit():
                    matched_class = teacher.school_classes.filter(id=int(raw_classroom)).first()
                else:
                    matched_class = teacher.school_classes.filter(name=raw_classroom).first()
                    if not matched_class:
                        matched_class = teacher.school_classes.filter(name__iexact=raw_classroom).first()

                if not matched_class:
                    return JsonResponse({'error': 'الصف أو الشعبة غير مسندة لهذا المعلم'}, status=403)
                classroom_name = matched_class.name

                # 2. التحقق الصارم من المادة: يجب أن تكون مسندة للمعلم
                if not raw_subject:
                    return JsonResponse({'error': 'يرجى تحديد المادة الدراسية للواجب'}, status=400)

                matched_subject = None
                if str(raw_subject).isdigit():
                    matched_subject = teacher.subjects.filter(id=int(raw_subject)).first()
                else:
                    matched_subject = teacher.subjects.filter(name=raw_subject).first()
                    if not matched_subject:
                        matched_subject = teacher.subjects.filter(name__iexact=raw_subject).first()

                if not matched_subject:
                    return JsonResponse({'error': 'المادة الدراسية غير مسندة لهذا المعلم'}, status=403)
                subject_name = matched_subject.name

            elif request.user_role == UserRole.MANAGER:
                target_school = profile.school
                client_school_id = data.get('school_id')
                if client_school_id and str(client_school_id) != str(target_school.id):
                    return JsonResponse({'error': 'غير مصرح لك ببث واجب لمدرسة أخرى'}, status=403)
                classroom_name = raw_classroom or 'الصف الأول'
                subject_name = raw_subject or 'عام'

            elif request.user_role == UserRole.OWNER:
                school_id_param = data.get('school_id')
                if school_id_param:
                    target_school = SchoolSettings.objects.filter(id=school_id_param).first()
                    if not target_school:
                        return JsonResponse({'error': 'المدرسة المحددة غير موجودة'}, status=404)
                classroom_name = raw_classroom or 'الصف الأول'
                subject_name = raw_subject or 'عام'

            hw = HomeworkAssignment.objects.create(
                school=target_school,
                classroom=classroom_name,
                subject=subject_name,
                title=title,
                description=description,
                due_date=due_date
            )

            AuditTrailLog.objects.create(
                user=request.user,
                action='بث واجب مدرسي',
                entity_name='HomeworkAssignment',
                entity_id=str(hw.id),
                details=f"بث واجب [{title}] للصف [{classroom_name}] مادة [{subject_name}] لمدرسة [{target_school}]"
            )

            return JsonResponse({'status': 'success', 'message': 'تم بث الواجب للشعبة بنجاح', 'id': hw.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # GET: عرض واجبات مدرسة المستخدم فقط
    if request.user_role == UserRole.OWNER:
        school_param = request.GET.get('school_id')
        if school_param:
            target_school = SchoolSettings.objects.filter(id=school_param).first()
            if not target_school:
                return JsonResponse({'error': 'المدرسة المحددة غير موجودة'}, status=404)
            hw_qs = HomeworkAssignment.objects.filter(school=target_school)
        else:
            hw_qs = HomeworkAssignment.objects.all()
    elif request.user_role in (UserRole.MANAGER, UserRole.TEACHER):
        user_school = profile.school
        requested_school = request.GET.get('school_id')
        if requested_school and str(requested_school) != str(user_school.id):
            return JsonResponse({'error': 'غير مصرح بالوصول لواجبات مدرسة أخرى'}, status=403)
        hw_qs = HomeworkAssignment.objects.filter(school=user_school)
    elif request.user_role == UserRole.PARENT:
        user_school = profile.school
        if not user_school:
            rel = ParentStudentRelation.objects.filter(parent=profile, is_confirmed=True).select_related('student__school').first()
            if rel and rel.student:
                user_school = rel.student.school
        requested_school = request.GET.get('school_id')
        if requested_school and str(requested_school) != str(user_school.id):
            return JsonResponse({'status': 'success', 'homeworks': []})
        hw_qs = HomeworkAssignment.objects.filter(school=user_school)

    hws = hw_qs.order_by('-created_at')[:30]
    data = [{
        'id': h.id,
        'school_id': h.school_id,
        'classroom': h.classroom,
        'subject': h.subject,
        'title': h.title,
        'details': h.description,
        'description': h.description,
        'dueDate': h.due_date,
        'due_date': h.due_date,
        'teacher': 'معلم المادة',
        'date': h.created_at.strftime('%Y-%m-%d') if h.created_at else ''
    } for h in hws]
    return JsonResponse({'status': 'success', 'homeworks': data})
