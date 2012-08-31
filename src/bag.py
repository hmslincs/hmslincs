# import collections as co
# class Bag(object):
#     def __init__(self, **kwargs):
#         __dict__ = co.defaultdict(Bag)
#         __dict__.update(self.__dict__)
#         __dict__.update(**kwargs)
#         self.__dict__ = __dict__
#
# close...
#
# >>> import bag as ba
# >>> x = ba.Bag()
# >>> x.u = 3
# >>> # no prob
#
# ...but no cigar:
#
# >>> x.y.z = 5
# Traceback (most recent call last):
#   File "<stdin>", line 1, in <module>
# AttributeError: 'Bag' object has no attribute 'y'

class Bag(object):
    # the use of ____ instead of 'self' as the first argument in __init__'s
    # signature is meant to avoid conflicts with a possible 'self' keyword in
    # kwargs (a very poor solution to the problem).
    def __init__(____, **kwargs):
        ____.__dict__.update(**kwargs)
