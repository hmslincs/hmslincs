from __future__ import division

import math as ma
import itertools as it

import typecheck as tc

def partition(seq, pred):
    """
    >>> from partition import partition
    >>> pred = lambda x: int(x) % 3 == 2
    >>> seq = map(str, range(15))
    >>> partition(seq, pred)
    [('2', '5', '8', '11', '14'), ('0', '1', '3', '4', '6', '7', '9', '10', '12', '13')]
    """

    if not tc.issequence(seq):
        raise TypeError('seq is not a sequence')

    t, f = [], []
    for d in seq:
        if pred(d): t.append(d)
        else: f.append(d)
    return [tuple(t), tuple(f)]


def ipartition(seq, pred):
    """
    >>> from partition import ipartition
    >>> pred = lambda x: int(x) % 3 == 2
    >>> seq = it.imap(str, xrange(15))
    >>> map(type, ipartition(seq, pred))
    [<type 'itertools.ifilter'>, <type 'itertools.ifilterfalse'>]
    >>> map(tuple, ipartition(seq, pred))
    [('2', '5', '8', '11', '14'), ('0', '1', '3', '4', '6', '7', '9', '10', '12', '13')]
    """

    t1, t2 = it.tee(seq)
    return [it.ifilter(pred, t1), it.ifilterfalse(pred, t2)]


def kgroups(seq, k):
    """Yield successive k-sized groups from l.
    """
    if not k > 0:
        raise ValueError('k must be positive')

    for i in xrange(0, len(seq), k):
        yield seq[i:i+k]


def splitseq(seq, m, truncate=False):
    """Yield (approximately) m subsequences from seq.

    If n = len(seq), and n >= m, then the function will yield m
    consecutive subsequences of length n//m.  Then, if r = n % m > 0
    and truncate is not a true value, it will yield one more
    subsequence of length r.

    If n < m, a ValueError is raised.
    """

    n = len(seq)
    if not isinstance(m, int) or n < m:
        raise ValueError('m must be a positive integer not greater than len(seq)')

    stride = n // m
    i = 0
    while i < n:
        j = i + stride
        yield seq[i:j]
        i = j

_SENTINEL = object()
def spread(seq, N=_SENTINEL, K=1):
    """Yield (at most N) successive seq subsequences of length at least K.

    seq    any object supporting len(...) and slice-indexing
    N      a positive integer (default: L = len(seq))
    K      a positive integer not greater than L (default: 1)

    The subsequences yielded represent a "tiling" of seq.  This means that they
    are adjacent in seq, and cover all of seq.  In other words, each element of
    seq belongs to exactly one of the yielded subsequences.

    With these conventions, the specification above can be sharpened to:

    Yield n = min(N, L//K) successive subsequences of seq, the first L % n
    having length k + 1 (where k = L//n), and the remaining ones having
    length k.

    >>> tuple(spread('abcdefghij', N=4))
    ('abc', 'def', 'gh', 'ij')
    >>> tuple(spread('abcdefghij', K=3))
    ('abcd', 'efg', 'hij')
    >>> tuple(spread('abcdefghij', N=4, K=3))
    ('abcd', 'efg', 'hij')
    >>> tuple(spread('abcdefghijklmnopqrstuvwxyz', N=4))
    ('abcdefg', 'hijklmn', 'opqrst', 'uvwxyz')

    Note that n < N and k > K can simultaneously hold:
    >>> tuple(spread('abcdefghijklmnopqrstuvwxyz', N=4, K=7))
    ('abcdefghi', 'jklmnopqr', 'stuvwxyz')

    >>> tuple(spread('x', N=None))
    Traceback (most recent call last):
    TypeError: N must be a positive integer
    >>> tuple(spread('x', N=0))
    Traceback (most recent call last):
    TypeError: N must be a positive integer
    >>> tuple(spread('x', K=None))
    Traceback (most recent call last):
    TypeError: K must be a positive integer
    >>> tuple(spread('x', K=0))
    Traceback (most recent call last):
    TypeError: K must be a positive integer
    >>> tuple(spread('x', K=2))
    Traceback (most recent call last):
    TypeError: K must not exceed len(seq)
    """

    L = len(seq)
    if N is _SENTINEL: N = L
    if not (type(N) == int and 0 < N):
        raise TypeError('N must be a positive integer')
    if not (type(K) == int and 0 < K):
        raise TypeError('K must be a positive integer')
    elif K > L:
        raise TypeError('K must not exceed len(seq)')

    n = min(L//K, N)
    k, rem = divmod(L, n)
    # the generator will yield a total of n <= N subsequences, the
    # first rem of which having length k + 1, and the remaining ones
    # having length k >= K.

    start = 0
    stride = k + 1
    for i in range(rem):
        end = start + stride
        yield seq[start:end]
        start = end

    stride = k
    for i in range(rem, n):
        end = start + stride
        yield seq[start:end]
        start = end

    assert start == L


if __name__ == '__main__':
    import doctest
    doctest.testmod()
