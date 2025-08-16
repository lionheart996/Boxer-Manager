from django import template

register = template.Library()

@register.filter
def dictkey(form, key):
    try:
        return form[key]
    except KeyError:
        return ''

from django import template
register = template.Library()

@register.filter
def dictkey(d, key):
    try:
        return d.get(key)
    except Exception:
        return None