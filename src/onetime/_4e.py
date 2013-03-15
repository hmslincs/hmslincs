from __future__ import division

import math as ma
import matplotlib.pyplot as mplpp
import matplotlib.figure as mplf
import matplotlib.backends.backend_agg as mplbb
import matplotlib.colors as mplc
import matplotlib.cm as mplcm

import collections as co

import csv
import json

import scatterplot as sp
import minmax as mm

INPUTPATH = '/Users/berriz/Work/attachments/MH/drug_erlotinib_scatterdata - Sheet1.tsv'
OUTPUTPATH = ('/Users/berriz/'
              'Sites/dev.lincs.hms.harvard.edu/_static/responses/img/4e.png')
IMGID = '/DEV_ONLY_NON_GIT/MH/4e'

FIGSIZEPX = 300
DPI = 72
CMAP_BWR = mplc.LinearSegmentedColormap.from_list('bwr', ['blue', 'white', 'red'])

def readinput(path):
    with open(path) as inh:
        reader = csv.reader(inh, delimiter='\t')
        return tuple(reader)


def make_row(annotation):
    return (('<tr>'
             '<td>%(cell_line_name)s</td>'
             '<td>%(cell_line_classification)s</td>'
             '<td>%(erlotinib_gi50).3f</td>'
             '<td>(%(x).3f, %(y).3f)</td>'
             '</tr>')
            % annotation._asdict())


def _4e():
    rows = readinput(INPUTPATH)

    headers = rows[0]

    f = mplf.Figure(figsize=(FIGSIZEPX/DPI, FIGSIZEPX/DPI), dpi=DPI)

    ax = f.gca()

    datarec = co.namedtuple('_datarec',
                            'cell_line_name cell_line_classification '
                            'erlotinib_gi50 x y')

    data = tuple(datarec(*(r[:-3] + [float(r[-3])] +
                           map(lambda z: 10**float(z), r[-2:])))
                 for r in rows[1:])

    circle = 'o'
    triangle = '^'
    square = 's'
    marker_lookup = {'TNBC': circle, 'HER2amp': triangle, 'HR+': square}

    pointspec = co.namedtuple('_pointspec', 'x y level marker')
    points = tuple(pointspec(rec.x, rec.y, rec.erlotinib_gi50,
                             marker_lookup[rec.cell_line_classification])
                   for rec in data)

    # eyeballed from PDF
    min_gi50 = -5.9 # min log_10 gi50
    max_gi50 = -3.7 # max log_10 gi50

    fixedkwargs = dict(s=200, linewidth=0.5, vmin=min_gi50, vmax=max_gi50,
                       cmap=CMAP_BWR)
    for marker in (circle, triangle, square):
        xs, ys, cs = zip(*((p.x, p.y, p.level)
                           for p in points if p.marker == marker))
        ax.scatter(xs, ys, c=cs, marker=marker, **fixedkwargs)

    ax.set_xscale('log')
    ax.set_yscale('log')

    # eyeballed from the PDF
    xlim = (0.8, 25)
    ylim = (0.9, 1.9)

    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

    # this aspect will result in a square plot
    # ax.set_aspect((xlim[1] - xlim[0])/(ylim[1] - ylim[0]))
    ax.set_aspect((ma.log10(xlim[1]/xlim[0])/ma.log10(ylim[1]/ylim[0])))

    ax.set_title('Erlotinib')

    xlabel = 'pErk[FGF-2$_1$] max (fold change)'
    ylabel = 'pAkt[EPR$_1$] max (fold change)'

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    xaxis = ax.xaxis
    xaxis.set_major_formatter(mplpp.FormatStrFormatter('%d'))
    xaxis.set_major_locator(mplpp.FixedLocator([1, 2, 5, 10, 20]))
    xaxis.set_ticks((), minor=True)

    fmtr = lambda v, _: ('%.1f' % v).rstrip('.0')
    yaxis = ax.yaxis
    yaxis.set_major_formatter(mplpp.FuncFormatter(fmtr))
    yaxis.set_major_locator(mplpp.FixedLocator([1, 1.8]))
    yaxis.set_ticks((), minor=True)


    f.subplots_adjust(left=0.2, bottom=0.15, right=0.95, top=0.9, wspace=0, hspace=0)
    mplpp.setp(f, 'facecolor', 'none')

    canvas = mplbb.FigureCanvasAgg(f)
    f.set_canvas(canvas)

    canvas.print_png(OUTPUTPATH)

    htmlrows = [dict(coords=p._asdict(), row=make_row(d))
                for p, d in zip(sp.pixels(data, f), data)]

    print '        %s: %s,' % (json.dumps(IMGID), json.dumps(htmlrows))

    return f



# def junk():

# import matplotlib.pyplot as mplpp
# import matplotlib.figure as mplf
# import matplotlib.backends.backend_agg as mplbb
# import matplotlib.colors as mplc
# import matplotlib.cm as mplcm


#     cmap = matplotlib.color.LinearSegmentedColormap.from_list('blueWhiteRed',
#                                                               ['blue', 'white', 'red'])

#     f = matplotlib.figure.Figure(figsize=(4, 4), dpi=72)
#     ax = f.gca()

#     for record in data:
#         level = record.level # a float in [0.0, 1.0]
#         marker = record.marker
#         ax.scatter(record.x, record.y,
#                    s=100, linewidth=0.5, marker=marker,
#                    c=level, vmin=0, vmax=1, cmap=cmap)

#     canvas = matplotlib.backends.backend_agg.FigureCanvasAgg(f)
#     f.set_canvas(canvas)
#     canvas.print_png('/path/to/output/fig.png')



if __name__ == '__main__':
    _4e()
