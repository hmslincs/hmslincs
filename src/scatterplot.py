import collections as co
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.backends.backend_agg import FigureCanvasAgg
import io
# ---------------------------------------------------------------------------

FORMAT = 'png'

# ---------------------------------------------------------------------------

ScatterplotData = co.namedtuple('ScatterplotData', 'label shape level x y')
ScatterplotMetaData = co.namedtuple('ScatterplotMetaData',
                                    'readout ligand concentration time')
PointSpec = co.namedtuple('PointSpec', 'label shape level')
ResponseData = co.namedtuple('ResponseData', 'metadata data')
MarkerSpec = co.namedtuple('MarkerSpec', 'marker color')

marker_map = {
              'triangle': MarkerSpec('^', 'orange'),
              'circle': MarkerSpec('o', 'mediumpurple'),
              'square': MarkerSpec('s', 'mediumseagreen'),
              }

dpi = 72.0

cmap_bwr = LinearSegmentedColormap.from_list('bwr', ['blue', 'white', 'red'])

def scatterplot(points, metadata, lims=None, display=False):
    f = Figure(figsize=(300 / dpi, 300 / dpi), dpi=dpi)
    ax = f.gca()
    for p in points:
        if p.level is None:
            # overrides cmap
            color = marker_map[p.shape].color
        else:
            color = p.level
        ax.scatter(p.x, p.y, c=color, vmin=0, vmax=1, linewidth=0.5,
                   marker=marker_map[p.shape].marker, s=100, cmap=cmap_bwr)
    if lims is None:
        all_data = sum(([p.x, p.y] for p in points), [])
        dmin = min(all_data)
        dmax = max(all_data)
        drange = dmax - dmin
        lims = dmin - drange * 0.1, dmax + drange * 0.1
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_aspect('equal')
    ax.set_xlabel(build_label(metadata[0]))
    ax.set_ylabel(build_label(metadata[1]))
    for loc in 'top', 'right':
        ax.spines[loc].set_color('none')
    ax.xaxis.set_ticks_position('bottom')
    ax.yaxis.set_ticks_position('left')
    f.subplots_adjust(left=0.2, bottom=0.1, right=1, top=1, wspace=0, hspace=0)
    plt.setp(f, 'facecolor', 'none')
    if display:
        plt.show()
    else:
        output = io.BytesIO()
        canvas = FigureCanvasAgg(f)
        canvas.print_png(output)
        output.seek(0)
        return output

def build_label(metadata):
    readout, ligand, concentration, time = metadata
    if readout is not None and all(x is None for x in (ligand, concentration, time)):
        # basal
        label = 'basal %s (a.u.)' % readout
    elif all(x is not None for x in metadata):
        # ligand response
        label = '%s [%s]\n(fold change over basal)' % (readout, ligand)
    else:
        raise ValueError("unknown combination of metadata values")
    return label

if __name__ == '__main__':
    points = (ScatterplotData('AU-565', 'triangle', 0.554, 4.308, 4.311),
              ScatterplotData('BT-20', 'circle', 0.043, 3.843, 3.877),
              ScatterplotData('BT-474', 'triangle', 0.496, 3.455, 3.535),
              ScatterplotData('BT-483', 'square', 1.000, 3.805, 3.685),
              ScatterplotData('BT-549', 'circle', 0.873, 3.333, 3.197),
              ScatterplotData('CAMA-1', 'square', 1.000, 3.343, 3.230),
              ScatterplotData('HCC1187', 'circle', 0.403, 3.818, 3.723),
              ScatterplotData('HCC1395', 'circle', 0.859, 3.682, 3.720),
              ScatterplotData('HCC1419', 'triangle', 0.501, 4.068, 4.051),
              ScatterplotData('HCC1428', 'square', 0.640, 3.590, 3.376),
              ScatterplotData('HCC1806', 'circle', 0.246, 3.877, 3.843),
              ScatterplotData('HCC1937', 'circle', 0.854, 3.862, 3.727),
              ScatterplotData('HCC1954', 'triangle', 0.162, 4.032, 3.996),
              ScatterplotData('HCC202', 'triangle', 0.838, 4.199, 4.197),
              ScatterplotData('HCC38', 'circle', 1.000, 3.919, 3.838),
              ScatterplotData('HCC70', 'circle', 0.000, 4.263, 4.307),
              ScatterplotData('MCF7__b', 'square', 1.000, 3.148, 2.951),
              ScatterplotData('MDA-MB-134-VI', 'square', 1.000, 3.442, 3.475),
              ScatterplotData('MDA-MB-157', 'circle', 0.921, 3.294, 2.611),
              ScatterplotData('MDA-MB-175-VII', 'square', 0.163, 4.052, 3.831),
              ScatterplotData('MDA-MB-231__a', 'circle', 0.860, 3.903, 3.524),
              ScatterplotData('MDA-MB-361', 'triangle', 0.994, 3.092, 2.991),
              ScatterplotData('MDA-MB-436', 'circle', 0.950, 3.781, 3.635),
              ScatterplotData('MDA-MB-453', 'circle', 0.889, 3.290, 3.424),
              ScatterplotData('SK-BR-3__a', 'triangle', 0.608, 3.986, 3.999),
              ScatterplotData('T47D', 'square', 0.921, 3.804, 3.835),
              ScatterplotData('UACC-812', 'triangle', 0.537, 3.908, 3.907),
              ScatterplotData('UACC-893', 'triangle', 0.539, 3.677, 3.709),
              ScatterplotData('ZR-75-1', 'square', 1.000, 3.884, 3.569))
    metadata = (ScatterplotMetaData(readout='pErk', ligand='EGF', concentration='100', time=None),
                ScatterplotMetaData(readout='pErk', ligand='EPR', concentration='100', time=None))
    lims = (1.518, 4.395)

    scatterplot(points, metadata, lims, display=True)
