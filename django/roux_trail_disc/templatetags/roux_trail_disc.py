from django import template

register = template.Library()

# The obvious thing is to return the number with the spaces prepended, and this
# is what align_decimal does. However sometimes you want the spaces as a
# separate value (like when you have the number inside a tag, but the spaces
# need to be outside it), which is what figurespace_padding does.

@register.filter
def align_decimal(number, width):
  """
  Pad a number with "figure spaces" to assist in table alignment.

  Given an int or float, return a string left-padded with unicode "FIGURE SPACE"
  characters sufficient to make the integer portion 'width' characters wide.
  """
  number = unicode(number)
  return figurespace_padding(number, width) + number

@register.filter
def figurespace_padding(number, width):
  """
  Return a string of padding spaces to assist in numeric table column alignment.

  Given an int or float, return a string of unicode "FIGURE SPACE" characters
  which can be prepended to the number to make the integer portion 'width'
  characters wide.
  """
  integer, point, fraction = unicode(number).partition('.')
  return u'\u2007' * (width-len(integer))
