import functools as ft

def actual_args(fn):
    """Make function wrapper that saves actual arguments as function attributes.

    The actual arguments are saved into the wrapper's args and kwargs
    attributes.

    >>> @actual_args
    ... def spam(x, y=None, z=1):
    ...     return dict(args=spam.args, kwargs=spam.kwargs,
    ...                 locals=locals().copy())
    >>> spam(1)
    {'args': (1,), 'locals': {'y': None, 'x': 1, 'z': 1}, 'kwargs': {}}
    >>> spam(1, 3)
    {'args': (1, 3), 'locals': {'y': 3, 'x': 1, 'z': 1}, 'kwargs': {}}
    >>> spam(1, z=4)
    {'args': (1,), 'locals': {'y': None, 'x': 1, 'z': 4}, 'kwargs': {'z': 4}}
    >>> spam(1, 3, 4)
    {'args': (1, 3, 4), 'locals': {'y': 3, 'x': 1, 'z': 4}, 'kwargs': {}}
    >>> spam(1, 2, y=True)
    Traceback (most recent call last):
    TypeError: spam() got multiple values for keyword argument 'y'
    >>> spam(1, w=True)
    Traceback (most recent call last):
    TypeError: spam() got an unexpected keyword argument 'w'
    >>> spam()
    Traceback (most recent call last):
    TypeError: spam() takes at least 1 argument (0 given)
    """

    @ft.wraps(fn)
    def wrapper(*args, **kwargs):
        wrapper.args = args
        wrapper.kwargs = kwargs
        return fn(*args, **kwargs)
    return wrapper

if __name__ == '__main__':
    import doctest
    doctest.testmod()
