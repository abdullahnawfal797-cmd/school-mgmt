from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """جلب عنصر من قاموس أو مصفوفة بأمان كامل"""
    if dictionary is None:
        return None
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    try:
        return dictionary[key]
    except (IndexError, TypeError, KeyError):
        return None

@register.filter(name='to_range')
def to_range(value):
    """توليد نطاق أرقام ديناميكي داخل القالب مباشرة"""
    try:
        return range(1, int(value) + 1)
    except (ValueError, TypeError):
        return range(0)