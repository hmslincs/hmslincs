#!/usr/bin/env python
# -*- mode: python -*-

import sys
import itertools as it

# # ---------------------------------------------------------------------------
# import setparams as _sp
# _params = dict(
#     MODE = u'full',
#     DELIMITER = u'\t',
#     BLANK = u'',
# )
# _sp.setparams(_params)
# del _sp, _params

# assert MODE in set('full left right inner'.split())
# # ---------------------------------------------------------------------------

def parse(line, delimiter):
    rec = tuple(line.rstrip('\n').split(delimiter))
    return (rec[0], rec[1:])


# def fmt(s):
#     try: return '%6.3f' % float(s)
#     except: return s

fmt = lambda s: s

class Stream(object):
    def __init__(self, arg):
        self._arg = arg

    def __enter__(self):
        arg = self._arg
        if arg == '-':
            return sys.stdin
        if isinstance(arg, file):
            return arg
        self._handle = h = open(arg)
        return h

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, '_handle'):
            self._handle.close()


def join(stream0, stream1,
         mode='full', delimiter=u'\t', blank=u''):
    streams = (stream0, stream1)
    assert len(streams) == 2
    d = dict()
    n = [None, None]
    for i, f in enumerate(streams):
        with Stream(f) as h:
            kv0 = parse(next(h), delimiter)
            n[i] = len(kv0[1])
            for k, v in it.chain((kv0,), (parse(l, delimiter) for l in h)):
                p = d.setdefault(k, [None, None])
                # assert p[i] is None, '%s %d %s' % (k, i, p[i])
                if p[i] is None:
                    p[i] = v

    bl = tuple(tuple(blank for _ in range(m)) for m in n)

    for k, vv in sorted(d.items()):
        assert any(vv), k
        for i, v in enumerate(vv):
            if v is None:
                if (mode == 'inner' or
                    (i == 0 and mode == 'left') or
                    (i == 1 and mode == 'right')):
                    break
                vv[i] = bl[i]
        else:
            print '\t'.join((k,) + tuple(fmt(s) for s in sum(vv, ())))


def _parsecl():
    import argparse as ap
    import os.path as op

    specs = (
             ('-a', dict(metavar='1|2', action='append', choices='12')),
             ('-e', dict(metavar='MISSING', help='string for missing values')),
             ('-t', dict(metavar='DELIM', help='delimiter')),
             ('-o', dict(metavar='FORMAT', help='(must be auto)')),
             ('stream1', None),
             ('stream2', None),
            )

    clparser = ap.ArgumentParser(description=op.basename(__file__))
    for k, v in specs:
        if k.startswith('-') == 1:
            clparser.add_argument(k, required=True, **v)
        else:
            if v is None:
                v = dict(metavar=k.upper())
            clparser.add_argument(k, **v)

    return clparser.parse_args()

def main():
    
    args = _parsecl()

    assert args.o == 'auto'
    la = len(args.a)
    assert 0 < la < 3
    if la == 2:
        mode = 'full'
    # elif la == 0:
    #     mode = 'inner'
    # elif args.a[0] == '1':
    #     mode = 'left'
    else:
        assert args.a[0] == '2'
        mode = 'right'

    join(args.stream1, args.stream2, delimiter=args.t, mode=mode, blank=args.e)


if __name__ == '__main__':
    main()
