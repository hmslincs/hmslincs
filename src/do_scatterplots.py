import sys
import os
import os.path as op
import re
import itertools as it
import csv
import collections as co

import shell_utils as su
import typecheck as tc

import scatterplot as sp

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    APPNAME = 'responses',
    OUTPUTDIR = None,
    OUTPUTEXT = '.%s' % sp.FORMAT.lower(),
    KEYLENGTH = 3,
    COLHEADERROWNUM = 0,
    FIRSTDATAROWNUM = 1,
)
_sg.setparams(_params)
del _sg, _params

if OUTPUTDIR is None:
    OUTPUTDIR = op.join(op.dirname(op.dirname(op.abspath(__file__))),
                        'django', APPNAME, 'static', APPNAME, 'img')

# ---------------------------------------------------------------------------

def _seq2type(seq, type_):
    assert tc.issequence(seq)
    return type(seq)([type_(v) for v in seq])

def write_scatterplot(output, points, axis_labels, lims=None):
    # calls sp.scatterplot
    # outputs a scatterplot to output
    with open(output, 'w') as out_fh:
        fig_fh = sp.scatterplot(points, axis_labels, lims)
        while True:
            buf = fig_fh.read1(4096)
            if len(buf) == 0:
                break
            out_fh.write(buf)

def normalize(ax, _nre=re.compile(r'[/\s]')):
    # returns a string
    return ','.join(_nre.sub('_', s.lower()) for s in ax if s is not None)


def outpath(axes):
    # returns a filepath
    return op.join(OUTPUTDIR,
                   '%s%s' % ('__'.join(normalize(ax) for ax in axes),
                             OUTPUTEXT))

METADATA = co.namedtuple('MetaData',
                         'readout ligand concentration time')

def parse_header(header,
                 _p0=re.compile(r'^\S+\s+(\S+)(?:\s+(\S+.*))?$'),
                 _p1=re.compile(r'^([a-zA-Z].+?)(?::(\d+))?(?:\s+(\S+.*))?$'),
                 _p2=re.compile(r'((?<=@T)\d+)?$')):
    ret = [None] * 4
    try:
        ret[0], rest = _p0.search(header).groups()
        if rest:
            ret[1], ret[2], rest = _p1.search(rest).groups()
            if rest:
                ret[3] = _p2.search(rest).group(1)
    except AttributeError, e:
        if not "'NoneType' object has no attribute 'groups'" in str(e):
            raise

    return METADATA(*ret)

def readinput(path):
    with open(path) as inh:
        reader = csv.reader(inh, delimiter='\t')
        return tuple(reader)


def _range(seq):
    min_ = min(seq)
    max_ = max(seq)
    return max_ - min_, min_, max_


def _getspecs(datarows,
              _celltype2shape={'HER2amp': 'triangle',
                               'TNBC': 'circle',
                               'HR+': 'square',
                               }):
    assert len(datarows)

    for row in datarows:
        row[1] = float(row[1])

    levelrange, minlevel = _range([r[1] for r in datarows])[:2]
    if levelrange > 0:
        def level(lvl):
            return (lvl - minlevel)/levelrange
    else:
        level = lambda lvl: None

    return tuple((row[0], _celltype2shape[row[2]], level(row[1]))
                  for row in datarows)


def process(rows):
    # returns:
    # specs: tuple of triples
    # data: tuple of pairs
    # lims: pair of floats

    r0 = COLHEADERROWNUM
    r1 = FIRSTDATAROWNUM

    specs = _getspecs(rows[r1:])

    data = tuple((parse_header(col[r0]), _seq2type(col[r1:], float))
                 for col in zip(*rows)[KEYLENGTH:])

    lims = _range(sum([pair[1] for pair in data], ()))[1:]

    return specs, data, lims


#------------------------------------------------------------------------------

def main(argv=sys.argv[1:]):
    assert len(argv) == 1

    su.mkdirp(OUTPUTDIR)

    rows = readinput(argv[0])
    specs, data, lims = process(rows)

    spd = sp.ScatterplotData

    for pair in it.product(data, data):
        md, vs = zip(*pair)
        if md[0] >= md[1]: continue
        if md[0].time != md[1].time: continue
        output = outpath(md)
        points = tuple(spd(*(k + (x, y))) for k, x, y in zip(specs, *vs))
        axis_labels = tuple(', '.join(s for s in l if not s is None)
                            for l in md)
        write_scatterplot(output, points, axis_labels)


if __name__ == '__main__':
    main()
