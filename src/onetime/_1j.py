from __future__ import division

import math as ma
import matplotlib.pyplot as mplpp
import matplotlib.figure as mplf
import matplotlib.backends.backend_agg as mplbb
import matplotlib.colors as mplc

import collections as co

import csv
import json

import scatterplot as sp

INPUTPATH = '/Users/berriz/Work/attachments/MH/cluster_1_scatterdata - Sheet1.tsv'
OUTPUTPATH = ('/Users/berriz/Sites/dev.lincs.hms.harvard.edu'
              '/_static/responses/img/1j.png')
IMGID = '/DEV_ONLY_NON_GIT/MH/1j'

FIGSIZEPX = 300
DPI = 72
# CMAP_BWR = mplc.LinearSegmentedColormap.from_list('bwr', ['blue', 'white', 'red'])

def readinput(path):
    with open(path) as inh:
        reader = csv.reader(inh, delimiter='\t')
        return tuple(reader)


def make_row(annotation):
    return (('<tr>'
             '<td>%(cell_line_name)s</td>'
             '<td>%(cell_line_classification)s</td>'
             '<td>%(cluster)s</td>'
             '<td>(%(x).2g, %(y).2g)</td>'
             '</tr>')
            % annotation._asdict())


def _1j():
    rows = readinput(INPUTPATH)

    headers = rows[0]

    f = mplf.Figure(figsize=(FIGSIZEPX/DPI, FIGSIZEPX/DPI), dpi=DPI)

    ax = f.gca()

    datarec = co.namedtuple('_datarec',
                            'cell_line_name cell_line_classification '
                            'cluster x y')

    data = tuple(datarec(*(r[:-2] + map(lambda z: 10**float(z), r[-2:])))
                 for r in rows[1:])

    blue = '#1228B4'
    blue = '#4A8CF5'
    yellow = '#F9D712'
    green = '#5E9563'
    black = '#000000'
    gray0 = '#666666'
    gray0 = '#999999'
    gray1 = '#B3B3B3'
    gray2 = '#CBCBCB'
    red = 'r'

    color_lookup = {'1': blue, '2': green, '3': yellow,
                    '4': gray0, '5': black, '6': black, '7': black}
    circle = 'o'
    triangle = '^'
    square = 's'
    marker_lookup = {'TNBC': circle, 'HER2amp': triangle, 'HR+': square}

    fixedkwargs = dict(s=200, linewidth=0.5)
    for row in sorted(data, key=lambda r: r.cluster):
        color = color_lookup[row.cluster]
        marker = marker_lookup[row.cell_line_classification]
        # see http://matplotlib.org/api/axes_api.html#matplotlib.axes.Axes.scatter
        ax.scatter(row.x, row.y, c=color, marker=marker, **fixedkwargs)

    ax.set_xscale('log')
    ax.set_yscale('log')

    xlim = tuple(10**v for v in (-5, -1))
    ylim = tuple(10**v for v in (-4.5, 0))

    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

    # this aspect will result in a square plot
    ax.set_aspect((ma.log10(xlim[1]/xlim[0])/ma.log10(ylim[1]/ylim[0])))

    xlabel = 'Erb3 (pg/cell)'
    ylabel = 'EGFR (pg/cell)'

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    fmtr = lambda v, _: ('%g' % v) if v < 1e-4 else ('%.4f' % v).rstrip('.0')

    xaxis = ax.xaxis
    xaxis.set_major_locator(mplpp.FixedLocator([10**i for i in range(-5, 0)]))
    xaxis.set_major_formatter(mplpp.FuncFormatter(fmtr))
    xaxis.set_ticks((), minor=True)

    yaxis = ax.yaxis
    yaxis.set_major_locator(mplpp.FixedLocator([10**i for i in range(-4, 1)]))
    yaxis.set_major_formatter(mplpp.FuncFormatter(fmtr))
    yaxis.set_ticks((), minor=True)

    f.subplots_adjust(left=0.22, bottom=0.2, right=0.97, top=0.95,
                      wspace=0, hspace=0)
    mplpp.setp(f, 'facecolor', 'none')

    canvas = mplbb.FigureCanvasAgg(f)
    f.set_canvas(canvas)

    canvas.print_png(OUTPUTPATH)

    htmlrows = [dict(coords=pixel._asdict(), row=make_row(data))
                for pixel, data in zip(sp.pixels(data, f), data)]

    print '        %s: %s,' % (json.dumps(IMGID), json.dumps(htmlrows))

    return f

if __name__ == '__main__':
    _1j()
