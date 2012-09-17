import re

import typecheck as tc

_NO_TALLY = 0
_IN_PLACE_TALLY = 1
_RETURN_TALLY = 2

def unique(seq, unique_as=lambda x: x, keeplast=False, constructor=None,
           with_star=False, tally=None):
    """Remove duplicates from seq, preserving order and type.

    Testing for duplicates happens after applying unique_as to each
    element of seq.  By default, the returned value contains the first
    element x of seq for each value of unique_as(x) encountered.  If
    keeplast is set to True, then the last such element will be
    included in the returned value instead.

    The constructor argument specifies the constructor callable to use
    to create the returned value.  By default this callable is set to
    the value of type(seq).

    By default, the value returned will be constructor(nodups), where
    nodups is a sequence having the desired elements, but not
    necessarily having the desired type.  If with_star as a true
    value, then constructor(*nodups) is returned instead.

    If tally is set to a dictionary, when the function returns its
    keys will consist of the same elements as in those in the returned
    value, and its values will be the number of times each key appears
    in seq (or, more precisely, the number of times that the result
    from applying unique_as to the key appears in map(unique_as,
    seq)).  Note that if tally is set, its contents, if any, will be
    overwritten.

    If tally is set to a non-dict true value, then the function will
    return a sequence (value, count) pairs, analogous to the items of
    the tally dictionary described in the previous paragraph, but
    ordered in the way its keys would have been ordered in the default
    (i.e. with tally option unset) case.
    """

    assert tc.issequence(seq)
    seen = set()
    u = []

    tally_mode = (_IN_PLACE_TALLY if isinstance(tally, dict)
                  else _RETURN_TALLY if tally else _NO_TALLY)
    keep_tally = tally_mode != _NO_TALLY

    if keep_tally:
        temp_tally = dict()

    for x in (reversed(seq) if keeplast else seq):
        y = unique_as(x)

        if y not in seen:
            seen.add(y)
            u.append(x)

        if keep_tally:
            temp_tally.setdefault(y, [x, 0])[1] += 1

    if keep_tally:
        temp_tally = dict(temp_tally.values())
        if tally_mode == _IN_PLACE_TALLY:
            tally.clear()
            tally.update(temp_tally)
        else:
            assert tally_mode == _RETURN_TALLY
            u = [(v, temp_tally[v]) for v in u]

    if constructor is None:
        constructor = type(seq)

    return constructor(*u) if with_star else constructor(u)
