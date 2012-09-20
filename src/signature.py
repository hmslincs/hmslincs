import collections as co
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import matplotlib.transforms as mtransforms
import numpy as np

# ---------------------------------------------------------------------------

FORMAT = 'png'

# ---------------------------------------------------------------------------

SignatureData = co.namedtuple('SignatureData',
                              'name isclinical isselective signature maxtested')

radius = 0.2
colors = ('red', 'yellow', 'magenta', 'blue', 'green', 'cyan')
yscale = 0.5
# The distance between the center of an edge of a unit-radius regular polygon
# and its circumscribed circle is 1-sin(x/2) where x is the polygon's internal
# angle. pi/3 is the angle of an equilateral triangle, and 1-sin(pi/6) = 0.5.
y_top_padding = 0.5 * radius

# the function below is currently only a placeholder for the real thing
def signature(target_name, primary_compounds, nonprimary_compounds, cell_lines):
    num_compounds = len(primary_compounds)
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.axis((-8, -3, -2 * radius, (num_compounds - 1) * yscale + y_top_padding))
    for si, sd in enumerate(primary_compounds):
        y = si * yscale
        my = y - radius
        ty = y - radius
        for ci, value in enumerate(sd.signature):
            x = np.log10(value)
            marker = mpatches.RegularPolygon([x, my], 3, radius=radius,
                                             facecolor=colors[ci],
                                             edgecolor='black')
            ax.add_patch(marker)
        line = plt.Line2D([-8, -3], [y, y], color='black')
        ax.add_line(line)
        ax.text(-.01, ty, sd.name, transform=ax.get_yaxis_transform(),
                  ha='right')
    ax.set_aspect('equal')
    ax.tick_params(labeltop=True, labelbottom=False, labelleft=False,
                          left=False, right=False)
    plt.show()

if __name__ == '__main__':
    target_name = 'EGFR'

    primary_compounds = (SignatureData(name='Erlotinib',
                                       isclinical=True, isselective=False,
                                       signature=(5.41E-07, 1.07E-06, 5.72E-05,
                                                  1.79E-05, 1.67E-05, 2.89E-07),
                                       maxtested=6.67E-05),
                         SignatureData(name='Iressa',
                                       isclinical=True, isselective=True,
                                       signature=(6.72E-07, 6.73E-07, 1.17E-05,
                                                  1.08E-05, 6.48E-06, 6.97E-07),
                                       maxtested=3.33E-05),
                         SignatureData(name='AG1458',
                                       isclinical=False, isselective=True,
                                       signature=(6.92E-08, 2.23E-07, 1.67E-04,
                                                  1.67E-04, 5.52E-06, 2.03E-07),
                                       maxtested=1.67E-04))

    nonprimary_compounds = (SignatureData(name='WD40',
                                          isclinical=False, isselective=True,
                                          signature=(None, 6.96E-05, 5.19E-05,
                                                     3.23E-06, 1.67E-04, 1.67E-04),
                                          maxtested=1.67E-04),
                            SignatureData('H', False, False,
                                          (7.20E-06, 7.20E-06, 7.20E-06, 7.20E-06,
                                           7.20E-06, None), 7.2E-06))

    cell_lines = 'MCF12A MCF10A HCC1143 HCC1428 HCC1569 MCF10F'.split()

    signature(target_name, primary_compounds, nonprimary_compounds, cell_lines)
