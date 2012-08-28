import sys
import os
import os.path as op
import re
import itertools as it
import csv

import shell_utils as su
import typecheck as tc

import scatterplot as sp

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    OUTPUTDIR = re.sub(r'(^|/)do_', r'\1',
                       op.join(os.getcwd(),
                               op.splitext(op.basename(sys.argv[0]))[0])),
    OUTPUTEXT = '.%s' % sp.FORMAT.lower(),
    KEYLENGTH = 3,
    COLHEADERROWNUM = 0,
    FIRSTDATAROWNUM = 1,
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

def _seq2type(seq, type_):
    assert tc.issequence(seq)
    return type(seq)([type_(v) for v in seq])

def write_scatterplot(output, points, axis_labels, lims=None):
    # calls sp.scatterplot
    # outputs a scatterplot to output
    with open(output, 'w') as outfh:
        fig = sp.scatterplot(points, axis_labels, lims)
        outfh.write(fig)

def normalize(ax, _nre=re.compile(r'[/\s]')):
    # returns a string
    return ','.join(_nre.sub('_', s.lower()) for s in ax)


def outpath(axes):
    # returns a filepath
    return op.join(OUTPUTDIR,
                   '%s%s' % ('__'.join(normalize(ax) for ax in axes),
                             OUTPUTEXT))

def parse_header(header,
                 _parsere=re.compile(r'^\S+\s+(\S+\s+\S+):\d+\s+\w$'),
                 _splitre=re.compile(r'\s+')):
    core = _parsere.sub(r'\1', header)
    return tuple(_splitre.split(core))


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
    assert levelrange > 0

    return tuple((row[0], _celltype2shape[row[2]],
                  (row[1] - minlevel)/levelrange)
                 for row in datarows)


def process(rows):
    # returns:
    # specs: tuple of triples
    # data: tuple of doubles
    # lims: double of floats

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

    for pair in it.product(data, data):
        ax, vs = zip(*pair)
        if ax[0] == ax[1]: continue
        output = outpath(ax)
        spd = tuple(sp.ScatterplotData(*(k + (x, y)))
                    for k, x, y in zip(specs, *vs))
        axis_labels = tuple(', '.join(l) for l in ax)
        write_scatterplot(output, spd, axis_labels, lims)


if __name__ == '__main__':

    main()
