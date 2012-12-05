# -*- coding: utf-8 -*-
from __future__ import division
import sys
import os
import os.path as op
import re
import itertools as it
import csv
import math as ma
import collections as co
import json

import shell_utils as su
import typecheck as tc

import scatterplot as sp
import minmax as mm

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    TEST = False,
    APPNAME = 'responses',
    IDPREFIX = '',
    OUTPUTDIR = None,
    OUTPUTEXT = '.%s' % sp.FORMAT.lower(),
    WITHLIMITS = False,

    COLHEADERROWNUM = 0,
    FIRSTDATAROWNUM = 1,
    CELLLINECOLNUM = 0,
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

SHAPELOOKUP = {
               'HER2amp': 'triangle',
               'TNBC': 'circle',
               'HR+': 'square',
              }

# ---------------------------------------------------------------------------

CellLineMetadata = co.namedtuple('CellLineMetadata',
                                 'cell_line_name cell_line_classification '
                                 'sensitivity')

def _seq2type(seq, type_):
    assert tc.issequence(seq)
    return type(seq)([type_(v) for v in seq])


def normalize(ax, _nre=re.compile(r'[/\s]')):
    # returns a string
    return ','.join(_nre.sub('_', s.lower()) for s in ax if s is not None)


def outpath(base_id, outputdir=OUTPUTDIR, outputext=OUTPUTEXT):
    # returns a filepath
    return op.join(outputdir, '%s%s' % (base_id, outputext))


def _base_id(axes):
    return '__'.join(normalize(ax) for ax in axes)


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


def get_specs(cell_line_metadata, _shapelookup=SHAPELOOKUP):
    assert len(cell_line_metadata)

    levelrange, minlevel = _range([n for n in (r.sensitivity
                                               for r in cell_line_metadata)
                                   if not ma.isnan(n)])[:2]
    if levelrange > 0:
        def level(lvl):
            return (LEVELFORNAN if ma.isnan(lvl)
                    else (lvl - minlevel)/levelrange)
    else:
        level = lambda lvl: None

    return tuple(sp.PointSpec(md.cell_line_name,
                              _shapelookup[md.cell_line_classification],
                              level(md.sensitivity))
                 for md in cell_line_metadata)


def parse(rows):
    # returns:
    # cl_metadata: tuple of CellLineMetadata instances (triples)
    # responses: tuple of sp.ResponseData instances (pairs)

    # The components of a CellLineMetadata instance are 'cell_line_name'
    # (='cell line name'), 'cell_line_classification', 'sensitivity'.

    # The components of a sp.ResponseData are 'metadata' (a
    # sp.ScatterplotMetaData object, initialized with info parsed from
    # column header) and 'data' (sequence of floats).

    r0 = COLHEADERROWNUM
    r1 = FIRSTDATAROWNUM

    cl = CELLLINECOLNUM
    ll = LEVELCOLNUM
    ct = CELLTYPECOLNUM

    cl_metadata = tuple(CellLineMetadata(row[cl], row[ct], float(row[ll]))
                        for row in rows[r1:])

    responses = tuple(sp.ResponseData(parse_header(col[r0]),
                                 _seq2type(col[r1:], float))
                      for col in zip(*rows)[KEYLENGTH:])

    return cl_metadata, responses

def limits(readouts):
    return _range(sum(readouts, ()))[1:]

def _one_scatterplot(cl_metadata, xy_data, xy_metadata,
                     output=None,
                     lims=None, specs=None,

                     _spd=sp.ScatterplotData,
                     _anno=co.namedtuple('_annotation',
                                         CellLineMetadata._fields +
                                         ('x', 'y')),
                     _annopxl=co.namedtuple('_annotated_pixel',
                                            'coords annotation')):
    if specs is None:
        specs = get_specs(cl_metadata)

    readouts = zip(*xy_data)
    if lims is None and WITHLIMITS:
        lims = limits(readouts)

    points = tuple(_spd(*(k + (x, y))) for k, x, y in zip(specs, *xy_data))

    fig = sp.scatterplot(points, xy_metadata, lims=lims, outpath=output)
    pixels = tuple(p for p in sp.pixels(points, fig))

    annotations = tuple(_anno(*(m + r))
                        for m, r in zip(cl_metadata, readouts))

    return tuple(sorted([_annopxl(p, a) for p, a in zip(pixels, annotations)],
                        key=lambda r: (-r.coords.y, r.coords.x,
                                        r.annotation.cell_line_name)))

def print_pixel_annotations(pixel_maps):
    for imgid, pixel_map in pixel_maps.items():
        rows = [dict(coords=p.coords._asdict(),
                     row=('<tr>'
                          '<td>%(cell_line_name)s</td>'
                          '<td>%(cell_line_classification)s</td>'
                          '<td>%(sensitivity).3f</td>'
                          '<td>(%(x).3f, %(y).3f)</td>'
                          '</tr>'
                          % p.annotation._asdict())) for p in pixel_map]

        print '        %s: %s,' % (json.dumps(imgid), json.dumps(rows))


def do_scatterplots(cl_metadata, responses, to_do, withlimits=None):
    specs = get_specs(cl_metadata)
    lims = (limits(tuple(r.data for r in responses))
            if withlimits else None)
    return dict([(item.imgid,
                  _one_scatterplot(cl_metadata, *item.args,
                                   lims=lims, specs=specs))
                 for item in to_do])
                                                  


#------------------------------------------------------------------------------

def main(argv=sys.argv[1:]):
    assert len(argv) == 1

    su.mkdirp(OUTPUTDIR)

    rows = readinput(argv[0])
    cl_metadata, responses = parse(rows)

    _to_do = co.namedtuple('_to_do', 'args imgid')
    _args = co.namedtuple('_args', 'xy_data xy_metadata output')
    to_do = []
    for xr, yr in it.product(responses, responses):
        (xmd, ymd), (xs, ys) = zip(xr, yr)
        if xmd >= ymd or xmd.time != ymd.time: continue
        base_id = _base_id((xmd, ymd))
        output = outpath(base_id)
        if not CLOBBEROK and op.exists(output):
            raise Exception("won't clobber %s" % output)

        img_id = IDPREFIX + base_id
        to_do.append(_to_do(_args((xs, ys), (xmd, ymd), output), img_id))

    pixel_maps = do_scatterplots(cl_metadata, responses, to_do, WITHLIMITS)
    print_pixel_annotations(pixel_maps)


if __name__ == '__main__':

    if not TEST:
        main()
        exit(0)

    OUTPUTPATH = '/Users/berriz/Work/Sites/hmslincs/tmp/png/test.png'

    metadata = (sp.ScatterplotMetaData(readout='pErk', ligand='EGF',
                                       concentration='100', time='m'),
                sp.ScatterplotMetaData(readout='pErk', ligand='EPR',
                                       concentration='100', time='m'))

    x0, x1 = 3.092, 4.308
    m = (x0 + x1)/2
    xy = zip((x0, x0), (x0, x1), (x1, x1), (x1, x0), (m, m))
    cl_metadata = tuple(CellLineMetadata(cl, ct, lv)
                        for cl, ct, lv in
                        zip(tuple('AU-565 BT-20 BT-474 BT-483 BT-549'.split()),
                            tuple('HR+ HER2amp TNBC HR+ TNBC'.split()),
                            (0, 1, 1, 0, 0.5)))

    responses = zip(*(metadata, xy))
    to_do = [co.namedtuple('_to_do', 'args imgid')
             ((xy, metadata, OUTPUTPATH), 'test')]
    pixel_maps = do_scatterplots(cl_metadata, responses, to_do)
    print_pixel_annotations(pixel_maps)
