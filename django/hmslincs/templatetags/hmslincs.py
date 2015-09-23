from django.conf import settings
from django.template import Template, Context, Library
from django.template.defaultfilters import stringfilter

register = Library()

@register.filter(is_safe=True)
@stringfilter
def process_static_url(value):
    tpl = Template(value)
    ctx = Context({'STATIC_URL': settings.STATIC_URL,})
    return tpl.render(ctx)

@register.simple_tag
def flatpage_static():
    return '{{ STATIC_URL }}'
