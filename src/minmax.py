FIRST = 0
LAST = -1
ALL = None

__sentinel = object()

def minmax(seq, cmp_=cmp, warg=__sentinel, key=lambda x: x, start=__sentinel,
           which=FIRST):
    """
    Return the minimum and maximum values in an iterable.

    Parameters
    ----------
    seq : iterable
        The iterable whose minimum and maximum will be returned.  It must have
        a non-zero length.  If the iterable is a generator object, then, if it
        fails to terminate, the function will loop indefinitely; otherwise, it
        will be consumed during the function's execution.
    cmp_ : callable
        This callable must accept two elements x, y from the iterable and
        return -1, 0, or 1 if x is less than, equal to, or greater than, y.
        The function is assumed to be transitive (cmp_(x, y) == cmp_(y, z)
        implies that cmp_(x, y) == cmp_(x, z)).  If this condition does not
        hold, the returned values may be incorrect.  Default: cmp.
    warg : boolean
        If True, also return the indices corresponding to the minimum and
        maximum values.  If the start parameter (q.v.) is explicitly set, then
        this parameter must either be set to True, or remain unset.  Default:
        True if the start parameter is specified; otherwise False.
    key : callable
        This callable will be called with each item encountered during the
        iteration as its sole argument.  In the search for the minimum and
        maximum values, comparisons will be based on the values returned by
        this callable.  Default: the identity function.
    start : int
        The index to assign to the first item encountered during the iteration.
        If this parameter is specified, then the warg parameter (q.v.) must
        either be set to True, or remain unset.  Default: 0.
    which : enum
        This parameter specifies which items to include in the returned values
        when several minimal or maximal elements are found.  Allowable values
        for this parameter are minmax.FIRST, minmax.LAST or minmax.ALL.
        Default: minmax.FIRST.
    
    Returns
    -------
    minmax_pair : tuple
        The returned value is always a pair (a tuple of length 2), where the
        first and second members refer to the iterable's minimum and maximum
        values, respectively.  The structure of the members of this pair is
        governed by the values of the warg and which parameters.  The table
        below summarizes the effect of the warg and which parameters on the
        structure of the first member of the returned pair.  In this table, MNS
        and MXS denote the tuples containing all the values x for which key(x)
        was, respectively, minimal or maximal (according to cmp_), in the order
        in which they were found along the iterable; IMNS and IMXS denote the
        tuples containing the indices (relative to the value of the start
        parameter) of the iterable elements contained in MNS and MXS,
        respectively.  The case corresponding to the top-left cell of the table
        (warg=False, which=minmax.FIRST) is the default behavior (i.e. the one
        resulting when the warg and which parameters, as well as the start
        parameter, are left unset).  FIRST, LAST, and ALL refer to the
        allowable values for the which parameter.

           warg: False                True
        which:
        FIRST   (MNS[0],  MXS[0])    ((MNS[0],  IMNS[0]),  (MXS[0],  IMXS[0]))
        LAST    (MNS[-1], MXS[-1])   ((MNS[-1], IMNS[-1]), (MXS[-1], IMXS[-1]))
        ALL     (MNS,     MXS)       ((MNS,     IMNS),     (MXS,     IMXS))


    Examples
    --------

    >>> minmax('minmax')
    ('a', 'x')
    >>> minmax('minmax', warg=True)
    (('a', 4), ('x', 5))
    >>> minmax('minmax', warg=True, which=LAST)
    (('a', 4), ('x', 5))
    >>> minmax('minmax', start=1)
    (('a', 5), ('x', 6))
    >>> minmax('minmax', which=LAST, start=2, warg=True)
    (('a', 6), ('x', 7))
    >>> minmax('MinMax', warg=True)
    (('M', 0), ('x', 5))
    >>> minmax('MinMax', key=str.upper)
    ('a', 'x')
    >>> minmax('MinMax', start=2, which=LAST)
    (('M', 5), ('x', 7))
    >>> minmax('MinMax', which=ALL)
    ((('M', 'M'), (0, 3)), (('x',), (5,)))
    >>> minmax('MinMax', warg=False, which=ALL)
    (('M', 'M'), ('x',))
    >>> minmax('MinMax', cmp_=lambda x, y: cmp(y, x), warg=True)
    (('x', 5), ('M', 0))
    >>> minmax('abracadABRA', start=1, which=ALL)
    ((('A', 'A'), (8, 11)), (('r',), (3,)))
    >>> minmax('abracadABRA', start=1, key=str.upper, which=ALL)
    ((('a', 'a', 'a', 'A', 'A'), (1, 4, 6, 8, 11)), (('r', 'R'), (3, 10)))
    >>> minmax('abracadABRA', start=1, key=str.upper, which=LAST)
    (('A', 11), ('R', 10))
    >>> minmax('')
    Traceback (most recent call last):
    ... 
    ValueError: minmax() arg is an empty sequence
    >>> minmax((0,), start=0, warg=False)
    Traceback (most recent call last):
    ... 
    ValueError: bool(warg) may not be False if start is specified
    >>> minmax((0,), which='nonesuch')
    Traceback (most recent call last):
    ... 
    ValueError: unsupported "which" parameter: 'nonesuch'
    """

    if not which in (FIRST, LAST, ALL):
        raise ValueError('unsupported "which" parameter: %r' % which)

    havestart = start is not __sentinel
    if warg is __sentinel:
        warg = True if havestart else (which == ALL)
    else:
        warg = bool(warg)
        if havestart and not warg:
            # if this point is reached, then the both the start and warg
            # parameter were both explicitly set, but with warg being set to
            # False, which renders the setting of start unobservable; hence the
            # exception below.
            raise ValueError('bool(warg) may not be False if start is specified')

    if not havestart:
        start = getattr(seq, 'base', getattr(seq, 'start', 0))

    iseq = iter(seq)
    try:
        x = next(iseq)
    except StopIteration:
        raise ValueError('minmax() arg is an empty sequence')

    xpfx = [x]
    k0 = key(x)
    i = start

    for i, x in enumerate(iseq, start=i + 1):
        k = key(x)
        d = cmp_(k, k0)
        if d == 0:
            xpfx.append(x)
            continue
        ipfx = range(start, i)
        if d < 0:
            kmin, xmin, imin = k, [x], [i]
            kmax, xmax, imax = k0, xpfx, ipfx
        else:
            kmax, xmax, imax = k, [x], [i]
            kmin, xmin, imin = k0, xpfx, ipfx
        break
    else:
        kmin, xmin, imin = kmax, xmax, imax = k0, xpfx, range(start, i + 1)

    for i, x in enumerate(iseq, start=i + 1):
        k = key(x)
        d = cmp_(k, kmin)
        if d < 0:
            kmin, xmin, imin = k, [x], [i]
        elif d == 0:
            kmin = k
            xmin.append(x)
            imin.append(i)
        else:
            d = cmp_(k, kmax)
            if d > 0:
                kmax, xmax, imax = k, [x], [i]
            elif d == 0:
                kmax = k
                xmax.append(x)
                imax.append(i)

    if which == ALL:
        def ret(l): return tuple(l)
    elif which == LAST:
        def ret(l): return l[-1]
    else:
        def ret(l): return l[0]

    xx = (ret(xmin), ret(xmax))
    return tuple(zip(xx, (ret(imin), ret(imax)))) if warg else xx


if __name__ == '__main__':
    import sys
    import doctest
    doctest.testmod()
    if not sys.argv[1:]:
        print 'ok (run with -v flag for verbose output)'


