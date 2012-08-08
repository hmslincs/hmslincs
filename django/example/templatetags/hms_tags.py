from django import template

register = template.Library()
# following: http://gnuvince.wordpress.com/2007/09/14/a-django-template-tag-for-the-current-active-page/
@register.simple_tag
def selectedTag(request, pattern):
    import re
    if re.search(pattern, request.path):
        return 'selected'
    return ''
