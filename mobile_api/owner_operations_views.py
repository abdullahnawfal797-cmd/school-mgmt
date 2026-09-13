import json
import re

from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt

from core.models import AuditChainRecord, SecurityEventLog
from .auth_utils import require_mobile_auth
from .models import AuditTrailLog, SupportTicket, SupportTicketMessage, UserRole


_SENSITIVE_KEY = re.compile(r'(password|passwd|secret|token|authorization|cookie|session|api[_-]?key|private[_-]?key)', re.I)
_SENSITIVE_INLINE = re.compile(r'(?i)(password|passwd|secret|token|authorization|cookie|session|api[_-]?key)\s*[:=]\s*[^\s,;]+')


def _redact(value, depth=0):
    if depth > 5:
        return '[مختصر]'
    if isinstance(value, dict):
        return {str(k): '[محجوب]' if _SENSITIVE_KEY.search(str(k)) else _redact(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v, depth + 1) for v in value[:25]]
    return _SENSITIVE_INLINE.sub(r'\1=[محجوب]', str(value or ''))[:1000]


def _safe_text(value):
    try:
        value = json.loads(str(value)) if not isinstance(value, (dict, list)) else value
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    safe = _redact(value)
    return json.dumps(safe, ensure_ascii=False)[:1000] if isinstance(safe, (dict, list)) else safe


def _page_params(request):
    try:
        return max(1, int(request.GET.get('page', 1))), min(100, max(1, int(request.GET.get('page_size', 30))))
    except (TypeError, ValueError):
        return 1, 30


def _user_context(user, fallback=''):
    profile = getattr(user, 'mobile_profile', None) if user else None
    school = profile.school if profile else None
    return {'username': getattr(user, 'username', '') or fallback or 'System', 'user_id': getattr(user, 'id', None), 'role': getattr(profile, 'role', '') or '', 'school': {'id': school.id, 'name': school.school_name} if school else None}


def _pagination(page_obj, page_size, key, items):
    return JsonResponse({'status': 'success', 'pagination': {'page': page_obj.number, 'page_size': page_size, 'total_items': page_obj.paginator.count, 'total_pages': page_obj.paginator.num_pages, 'has_next': page_obj.has_next(), 'has_previous': page_obj.has_previous()}, key: items})


def _get_page(queryset, page, page_size):
    paginator = Paginator(queryset, page_size)
    try:
        return paginator.page(page)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def _apply_user_filters(queryset, request):
    if request.GET.get('school_id'):
        queryset = queryset.filter(user__mobile_profile__school_id=request.GET['school_id'])
    if request.GET.get('user_id'):
        queryset = queryset.filter(user_id=request.GET['user_id'])
    if request.GET.get('role'):
        queryset = queryset.filter(user__mobile_profile__role=request.GET['role'])
    return queryset


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_audit_logs_view(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)
    source = request.GET.get('source', '').lower().strip()
    if source and source not in {'audit', 'chain', 'security'}:
        return JsonResponse({'error': 'قيمة source غير صالحة'}, status=400)
    action = (request.GET.get('action') or request.GET.get('event_type') or '').strip()
    search = request.GET.get('search', '').strip()[:200]
    date_from, date_to = parse_date(request.GET.get('date_from', '')), parse_date(request.GET.get('date_to', ''))
    page, page_size = _page_params(request)
    limit, total, items = page * page_size, 0, []

    if not source or source == 'audit':
        qs = _apply_user_filters(AuditTrailLog.objects.select_related('user', 'user__mobile_profile__school'), request)
        if action: qs = qs.filter(action__icontains=action)
        if search: qs = qs.filter(Q(action__icontains=search) | Q(entity_name__icontains=search) | Q(entity_id__icontains=search) | Q(details__icontains=search) | Q(user__username__icontains=search))
        if date_from: qs = qs.filter(timestamp__date__gte=date_from)
        if date_to: qs = qs.filter(timestamp__date__lte=date_to)
        total += qs.count()
        for row in qs.order_by('-timestamp')[:limit]:
            details = _safe_text(row.details)
            items.append({'id': row.id, 'source': 'audit', **_user_context(row.user), 'action': row.action, 'entity': row.entity_name, 'object_id': row.entity_id, 'summary': details, 'details': details, 'created_at': row.timestamp.isoformat(), 'ip_address': ''})

    if not source or source == 'chain':
        qs = _apply_user_filters(AuditChainRecord.objects.select_related('user', 'user__mobile_profile__school'), request)
        if action: qs = qs.filter(action__icontains=action)
        if search: qs = qs.filter(Q(action__icontains=search) | Q(model_name__icontains=search) | Q(object_id__icontains=search) | Q(object_repr__icontains=search) | Q(username__icontains=search))
        if date_from: qs = qs.filter(timestamp__date__gte=date_from)
        if date_to: qs = qs.filter(timestamp__date__lte=date_to)
        total += qs.count()
        for row in qs.order_by('-timestamp')[:limit]:
            details = _safe_text({'object': row.object_repr, 'old_value': row.old_value, 'new_value': row.new_value, 'reason': row.edit_reason})
            items.append({'id': row.id, 'source': 'chain', **_user_context(row.user, row.username), 'action': row.action, 'entity': row.model_name, 'object_id': row.object_id, 'summary': _safe_text(row.object_repr or row.edit_reason), 'details': details, 'created_at': row.timestamp.isoformat(), 'ip_address': ''})

    if not source or source == 'security':
        qs = _apply_user_filters(SecurityEventLog.objects.select_related('user', 'user__mobile_profile__school'), request)
        if action: qs = qs.filter(event_type__icontains=action)
        if search: qs = qs.filter(Q(event_type__icontains=search) | Q(details__icontains=search) | Q(username__icontains=search))
        if date_from: qs = qs.filter(timestamp__date__gte=date_from)
        if date_to: qs = qs.filter(timestamp__date__lte=date_to)
        total += qs.count()
        for row in qs.order_by('-timestamp')[:limit]:
            details = _safe_text(row.details)
            items.append({'id': row.id, 'source': 'security', **_user_context(row.user, row.username), 'action': row.event_type, 'event_type': row.event_type, 'severity': row.severity, 'entity': '', 'object_id': '', 'summary': details, 'details': details, 'created_at': row.timestamp.isoformat(), 'ip_address': row.ip_address})

    items.sort(key=lambda item: item['created_at'], reverse=True)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    start = (page - 1) * page_size
    return JsonResponse({'status': 'success', 'pagination': {'page': page, 'page_size': page_size, 'total_items': total, 'total_pages': total_pages, 'has_next': page < total_pages, 'has_previous': page > 1}, 'logs': items[start:start + page_size]})


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_security_events_view(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)
    qs = SecurityEventLog.objects.select_related('user', 'user__mobile_profile__school').order_by('-timestamp')
    if request.GET.get('school_id'): qs = qs.filter(user__mobile_profile__school_id=request.GET['school_id'])
    if request.GET.get('severity'): qs = qs.filter(severity=request.GET['severity'].upper())
    if request.GET.get('event_type'): qs = qs.filter(event_type__icontains=request.GET['event_type'])
    date_from, date_to = parse_date(request.GET.get('date_from', '')), parse_date(request.GET.get('date_to', ''))
    if date_from: qs = qs.filter(timestamp__date__gte=date_from)
    if date_to: qs = qs.filter(timestamp__date__lte=date_to)
    page, page_size = _page_params(request)
    page_obj = _get_page(qs, page, page_size)
    events = [{'id': row.id, **_user_context(row.user, row.username), 'event_type': row.event_type, 'severity': row.severity, 'summary': _safe_text(row.details), 'details': _safe_text(row.details), 'created_at': row.timestamp.isoformat(), 'ip_address': row.ip_address} for row in page_obj.object_list]
    return _pagination(page_obj, page_size, 'events', events)


def _ticket_item(ticket, messages=False):
    school = ticket.school
    item = {'id': ticket.id, 'school': {'id': school.id, 'name': school.school_name} if school else None, 'created_by': _user_context(ticket.created_by), 'category': ticket.category, 'priority': ticket.priority, 'priority_display': ticket.get_priority_display(), 'status': ticket.status, 'status_display': ticket.get_status_display(), 'subject': ticket.subject, 'description': _safe_text(ticket.description), 'created_at': ticket.created_at.isoformat(), 'updated_at': ticket.updated_at.isoformat(), 'closed_at': ticket.closed_at.isoformat() if ticket.closed_at else None}
    if messages:
        item['messages'] = [{'id': row.id, 'sender': _user_context(row.sender), 'message': _safe_text(row.message), 'created_at': row.created_at.isoformat(), 'is_internal_note': row.is_internal_note} for row in ticket.messages.all()]
    return item


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_support_tickets_view(request):
    if request.method != 'GET': return JsonResponse({'error': 'GET required'}, status=405)
    qs = SupportTicket.objects.select_related('school', 'created_by', 'created_by__mobile_profile').order_by('-updated_at', '-id')
    for field in ('school_id', 'status', 'priority', 'category'):
        if request.GET.get(field): qs = qs.filter(**{field: request.GET[field]})
    search = request.GET.get('search', '').strip()[:200]
    if search: qs = qs.filter(Q(subject__icontains=search) | Q(description__icontains=search) | Q(school__school_name__icontains=search) | Q(created_by__username__icontains=search))
    page, page_size = _page_params(request)
    page_obj = _get_page(qs, page, page_size)
    return _pagination(page_obj, page_size, 'tickets', [_ticket_item(row) for row in page_obj.object_list])


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_support_ticket_detail_view(request, ticket_id):
    if request.method != 'GET': return JsonResponse({'error': 'GET required'}, status=405)
    try:
        ticket = SupportTicket.objects.select_related('school', 'created_by', 'created_by__mobile_profile').prefetch_related('messages__sender', 'messages__sender__mobile_profile').get(pk=ticket_id)
    except SupportTicket.DoesNotExist:
        return JsonResponse({'error': 'التذكرة غير موجودة'}, status=404)
    return JsonResponse({'status': 'success', 'ticket': _ticket_item(ticket, True)})


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8')), None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, JsonResponse({'error': 'JSON غير صالح'}, status=400)


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_support_ticket_reply_view(request, ticket_id):
    if request.method != 'POST': return JsonResponse({'error': 'POST required'}, status=405)
    try: ticket = SupportTicket.objects.get(pk=ticket_id)
    except SupportTicket.DoesNotExist: return JsonResponse({'error': 'التذكرة غير موجودة'}, status=404)
    data, error = _json_body(request)
    if error: return error
    message = str(data.get('message', '')).strip()
    if not message or len(message) > 5000: return JsonResponse({'error': 'نص الرد مطلوب وبحد أقصى 5000 حرف'}, status=400)
    row = SupportTicketMessage.objects.create(ticket=ticket, sender=request.user, message=message, is_internal_note=bool(data.get('is_internal_note', False)))
    ticket.save(update_fields=['updated_at'])
    return JsonResponse({'status': 'success', 'message': 'تمت إضافة الرد', 'reply': {'id': row.id, 'message': _safe_text(row.message), 'created_at': row.created_at.isoformat(), 'is_internal_note': row.is_internal_note}})


@csrf_exempt
@require_mobile_auth(allowed_roles=[UserRole.OWNER])
def owner_support_ticket_update_view(request, ticket_id):
    if request.method != 'POST': return JsonResponse({'error': 'POST required'}, status=405)
    try: ticket = SupportTicket.objects.get(pk=ticket_id)
    except SupportTicket.DoesNotExist: return JsonResponse({'error': 'التذكرة غير موجودة'}, status=404)
    data, error = _json_body(request)
    if error: return error
    allowed = {'status', 'priority', 'category'}
    if not data or any(key not in allowed for key in data): return JsonResponse({'error': 'الحقول المسموحة هي status وpriority وcategory فقط'}, status=400)
    if 'status' in data and data['status'] not in dict(SupportTicket.STATUS_CHOICES): return JsonResponse({'error': 'حالة التذكرة غير صالحة'}, status=400)
    if 'priority' in data and data['priority'] not in dict(SupportTicket.PRIORITY_CHOICES): return JsonResponse({'error': 'أولوية التذكرة غير صالحة'}, status=400)
    if 'category' in data and (not str(data['category']).strip() or len(str(data['category'])) > 50): return JsonResponse({'error': 'تصنيف التذكرة غير صالح'}, status=400)
    previous = ticket.status
    for field in allowed.intersection(data): setattr(ticket, field, str(data[field]).strip().upper() if field in {'status', 'priority'} else str(data[field]).strip())
    ticket.closed_at = timezone.now() if ticket.status == 'CLOSED' and previous != 'CLOSED' else (None if ticket.status != 'CLOSED' else ticket.closed_at)
    ticket.save()
    return JsonResponse({'status': 'success', 'message': 'تم تحديث التذكرة', 'ticket': _ticket_item(ticket)})
