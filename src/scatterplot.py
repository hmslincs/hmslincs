import collections as co

# ---------------------------------------------------------------------------

FORMAT = 'png'

# ---------------------------------------------------------------------------

ScatterplotData = co.namedtuple('ScatterplotData', 'label shape level x y')

# the function below is currently only a placeholder for the real thing
def scatterplot(points, axis_labels, lims=None):
    # see example below for what the various arguments are expected to
    # be
    ret = []
    ret.append('# lims: %s' % str(lims))
    ret.append('\t'.join('cell_line shape level'.split() + list(axis_labels)))
    ret.extend(['\t'.join(str(x) for x in p) for p in points])
    return ''.join('%s\n' % l for l in ret)


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
    axis_labels = ('pErk, EGF', 'pErk, EPR')
    lims = (1.518, 4.395)

    import sys
    sys.stdout.write(scatterplot(points, axis_labels, lims))
