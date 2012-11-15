import sys
import os
import os.path as op
import re
import itertools as it
import csv
import math as ma

import shell_utils as su
import typecheck as tc

import scatterplot as sp
import minmax as mm

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    APPNAME = 'responses',
    OUTPUTDIR = None,
    OUTPUTEXT = '.%s' % sp.FORMAT.lower(),
    WITHLIMITS = False,

    COLHEADERROWNUM = 0,
    FIRSTDATAROWNUM = 1,
    LEVELCOLNUM = 2,
    CELLTYPECOLNUM = 3,

    # Each data row is construed as a key-value pair, where the row's
    # KEYLENGTH leftmost cells comprise the "key", and remaining cells
    # comprise the "value".
    KEYLENGTH = 4,

    LEVELFORNAN = 0.5,
    CLOBBEROK = False,
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

def write_scatterplot(output, points, metadata,
                      lims=None):
    # calls sp.scatterplot
    # outputs a scatterplot to output
    with open(output, 'w') as out_fh:
        fig_fh = sp.scatterplot(points, metadata, lims)
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

def parse_header(header, _width=4):
    parts = header.split(',')
    assert len(parts) <= _width
    ret = (parts + [None] * _width)[:_width]
    tm = ret[-1]
    if tm and tm.lower().startswith('t'): ret[-1] = tm[1:]
    return sp.ScatterplotMetaData(*ret)


def readinput(path):
    with open(path) as inh:
        reader = csv.reader(inh, delimiter='\t')
        return tuple(reader)


def _range(seq):
    if not seq: return 0, None
    min_, max_ = mm.minmax(seq)
    return max_ - min_, min_, max_


def _getspecs(datarows,
              _celltype2shape={'HER2amp': 'triangle',
                               'TNBC': 'circle',
                               'HR+': 'square',
                               }):
    assert len(datarows)

    l = LEVELCOLNUM
    ct = CELLTYPECOLNUM
    for row in datarows:
        row[l] = float(row[l])

    levelrange, minlevel = _range([n for n in (r[l] for r in datarows)
                                   if not ma.isnan(n)])[:2]
    if levelrange > 0:
        def level(lvl):
            return (LEVELFORNAN if ma.isnan(lvl)
                    else (lvl - minlevel)/levelrange)
    else:
        level = lambda lvl: None

    return tuple(sp.PointSpec(row[0], _celltype2shape[row[ct]], level(row[l]))
                 for row in datarows)


def process(rows, withlimits=WITHLIMITS):
    # returns:
    # specs: tuple of sp.PointSpec instances (triples)
    # data: tuple of sp.ResponseData instances (pairs)
    # lims: pair of floats

    # The components of a sp.PointSpec instance are 'label'
    # (=cell line), 'shape' (=cell type), 'level' (=sensitivity score).

    # The components of a sp.ResponseData are 'metadata' (a
    # sp.ScatterplotMetaData object, initialized with info parsed from
    # column header) and 'data' (sequence of floats).

    r0 = COLHEADERROWNUM
    r1 = FIRSTDATAROWNUM

    specs = _getspecs(rows[r1:])

    data = tuple(sp.ResponseData(parse_header(col[r0]),
                                 _seq2type(col[r1:], float))
                 for col in zip(*rows)[KEYLENGTH:])

    if withlimits:
        lims = _range(sum([pair[1] for pair in data], ()))[1:]
    else:
        lims = None

    return specs, data, lims


#------------------------------------------------------------------------------

def main(argv=sys.argv[1:]):
    assert len(argv) == 1

    su.mkdirp(OUTPUTDIR)

    rows = readinput(argv[0])
    specs, data, lims = process(rows, withlimits=WITHLIMITS)

    spd = sp.ScatterplotData

    for pair in it.product(data, data):
        md, vs = zip(*pair)
        if md[0] >= md[1]: continue
        if md[0].time != md[1].time: continue
        output = outpath(md)

        if not CLOBBEROK and op.exists(output):
            raise Exception("won't clobber %s" % output)

        points = tuple(spd(*(k + (x, y))) for k, x, y in zip(specs, *vs))
        write_scatterplot(output, points, md, lims)


if __name__ == '__main__':
    main()
