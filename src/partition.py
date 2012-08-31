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
    [('2', '5', '8', '11', '14'),
     ('0', '1', '3', '4', '6', '7', '9', '10', '12', '13')]
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
    >>> seq = imap(str, xrange(15))
    >>> ipartition(seq, pred)
    [<itertools.ifilter at 0x33193d0>, <itertools.ifilterfalse at 0x3319a10>]
    >>> map(tuple, ipartition(seq, pred))
    [('2', '5', '8', '11', '14'),
     ('0', '1', '3', '4', '6', '7', '9', '10', '12', '13')]
    """
    if not tc.issequence(seq):
        raise TypeError('seq is not a sequence')

    t1, t2 = it.tee(seq)
    return [it.ifilter(pred, t1), it.ifilterfalse(pred, t2)]


def kgroups(seq, k):
    """ Yield successive k-sized groups from l.
    """
    if not tc.issequence(seq):
        raise TypeError('seq is not a sequence')
    if not k > 0:
        raise ValueError('k must be positive')

    for i in xrange(0, len(seq), k):
        yield seq[i:i+k]


def splitseq(seq, m, truncate=False):
    """ Yield (approximately) m subsequences from seq.

    If n = len(seq), and n >= m, then the function will yield m
    consecutive subsequences of length n//m.  Then, if r = n % m > 0
    and truncate is not a true value, it will yield one more
    subsequence of length r.

    If n < m, a ValueError is raised.
    """

    if not tc.issequence(seq):
        raise TypeError('seq is not a sequence')

    n = len(seq)
    if not isinstance(m, int) or n < m:
        raise ValueError('m must be a positive integer not greater than len(seq)')

    stride = n // m
    i = 0
    while i < n:
        j = i + stride
        yield seq[i:j]
        i = j

