from __future__ import division
import collections as co
import itertools
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import RegularPolygon
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import MultipleLocator, NullLocator
from django.template import Template, Context
from django.template.loader import render_to_string
from django.template.defaultfilters import slugify
import django.conf
import numpy as np
import os.path as op
import sys

# ---------------------------------------------------------------------------

FORMAT = 'png'

# ---------------------------------------------------------------------------

SignatureData = co.namedtuple('SignatureData',
                              'drug_id drug status kinomescan '
                              'rangetested signature')
CellLineData = co.namedtuple('CellLineData',
                             'cell_id name')

dpi = 72  # 72 dpi produces perfect 1-pixel lines for 1-pt figure lines
colors = ('red', 'yellow', 'magenta', 'blue', 'green', 'cyan')  # cell line marker colors

main_template = 'pathway/signature.html'


def signature_images(target_name, compounds, target_dir):
    all_ranges = list(itertools.chain(*[c.rangetested for c in compounds
                                        if c.rangetested is not None]))
    if len(all_ranges) > 0:
        xlimits = min(all_ranges), max(all_ranges)
        for compound in compounds:
            signature_image(target_name, compound, xlimits, target_dir)
        signature_image(target_name, None, xlimits, target_dir, scale_only=True)
        

def signature_image(target_name, compound, xlimits, target_dir, scale_only=False):

    if not scale_only and compound.signature is None:
        return

    f = Figure(figsize=(250/dpi, 20/dpi), dpi=dpi)
    ax = f.add_subplot(111)
    xlimits = np.log10(xlimits)
    # fudge the limits to allow enough room for any markers at the limit
    xlimits[0] -= 0.2
    xlimits[1] += 0.2
    ax.axis((xlimits[0], xlimits[1], -1, 0))

    # hide y ticks
    ax.yaxis.set_major_locator(NullLocator())
    # tweak some other visual elements
    for a in f.axes:
        # hide all spines (the plot borders where the ticks usually sit)
        plt.setp(a.spines.values(), 'visible', False)
    # eliminate all margins
    f.subplots_adjust(left=0, bottom=0, right=1, top=1, wspace=0, hspace=0)

    if scale_only is False:
        # draw the data markers
        for ci, value in enumerate(compound.signature):
            if value is None:
                # don't draw any marker for None values
                x = np.nan
            else:
                # explicit log10 scaling
                x = np.log10(value)
            ax.scatter(x, -0.5, marker='^', s=150, facecolor=colors[ci], edgecolor='black')
        # draw the line
        line = plt.Line2D(np.log10(compound.rangetested), [-0.2, -0.2], color='black')
        ax.add_line(line)
        # hide x ticks
        ax.xaxis.set_major_locator(NullLocator())
    else:
        # draw x ticks only on every integer
        ax.xaxis.set_major_locator(MultipleLocator(1.0))
        # shift the tick labels inside the plot so we can see them
        plt.setp(ax.xaxis.get_major_ticks(), 'pad', -15)
        # ticks only on top with small labels
        ax.xaxis.tick_bottom()
        ax.xaxis.set_tick_params(labelsize=8)

    # render to png
    filename_data = { 'target': target_name, 'drug': compound.drug if compound else None }
    filename_data = dict((k, slugify(v)) for k, v in filename_data.items())
    if scale_only:
        filename_pattern = 'scale-%(target)s.png'
    else:
        filename_pattern = 'signature-%(target)s-%(drug)s.png'
    filename = op.join(target_dir, filename_pattern % filename_data)
    canvas = FigureCanvasAgg(f)
    canvas.print_png(filename)


def cell_line_images(target_dir):
    for i, color in enumerate(colors):
        f = Figure(figsize=(14/dpi, 14/dpi), dpi=dpi)
        ax = f.add_subplot(111)
        ax.scatter(0, 0, marker='^', s=150, facecolor=color, edgecolor='black')

        for axis in ax.xaxis, ax.yaxis:
            axis.set_major_locator(NullLocator())
        for a in f.axes:
            # hide all spines (the plot borders where the ticks usually sit)
            plt.setp(a.spines.values(), 'visible', False)
        # eliminate all margins
        f.subplots_adjust(left=0, bottom=0, right=1, top=1, wspace=0, hspace=0)

        filename = op.join(target_dir, 'legend-cell-line-%d.png' % i)
        canvas = FigureCanvasAgg(f)
        canvas.print_png(filename)


if __name__ == '__main__':
    if not django.conf.settings.configured:
        django.conf.settings.configure(
            TEMPLATE_LOADERS=(
                'django.template.loaders.filesystem.Loader',
                ),
            TEMPLATE_DIRS=(
                op.abspath(op.join(op.dirname(__file__), '../nui-wip/pathway')),
                ),
            DEBUG=True,
            TEMPLATE_DEBUG=True,
            )

    target_name = 'EGFR'

    compounds = (
        SignatureData(drug='Neratinib',
                      drug_id=u'HMSL10058',
                      status=u'approved', kinomescan=u'',
                      signature=(5.41E-07, 1.07E-06, 5.72E-05,
                                 1.79E-05, 1.67E-05, 2.89E-07),
                      rangetested=(8.53e-11, 6.67E-05)),
        SignatureData(drug='GSK-XXXX',
                      drug_id=u'HMSL10034',
                      status=u'approved', kinomescan=u'300030',
                      signature=(6.72E-07, 6.73E-07, 1.17E-05,
                                 1.08E-05, 6.48E-06, 6.97E-07),
                      rangetested=(1.71e-10, 3.33E-05)),
        SignatureData(drug='BMS-YYY',
                      drug_id=u'HMSL10208',
                      status=u'', kinomescan=u'',
                      signature=(6.92E-08, 2.23E-07, 1.67E-04,
                                 1.67E-04, 5.52E-06, 2.03E-07),
                      rangetested=(4.3e-08, 1.67E-04)),
        SignatureData(drug='WD40',
                      drug_id=u'HMSL10100',
                      status=u'investigational', kinomescan=u'300093',
                      signature=(None, 6.96E-05, 5.19E-05,
                                 3.23E-06, 1.67E-04, 1.67E-04),
                      rangetested=(1.23e-08, 1.67E-04)),
        SignatureData('HMSL10095', 'H', u'', u'', (6.54e-10, 7.2E-06),
                      (7.20E-06, 7.20E-06, 7.20E-06, 7.20E-06,
                       7.20E-06, None)),
        )

    signature_images(target_name, compounds, '.')

cell_lines = [
    CellLineData(cell_id=u'50106', name=u'BT-474'),
    CellLineData(cell_id=u'50578', name=u'HCC1187'),
    CellLineData(cell_id=u'50208', name=u'HCC1428'),
    CellLineData(cell_id=u'50216', name=u'HCC38'),
    CellLineData(cell_id=u'50219', name=u'HCC70'),
    CellLineData(cell_id=u'50057', name=u'SK-BR-3'),
    ]

LATEST = {
  u'JNK1': [SignatureData(drug_id=u'HMSL10058-101', drug=u'CG-930', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10095-101', drug=u'ZG-10', status=None, kinomescan=u'20078', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10100-101', drug=u'JNK-9L', status=None, kinomescan=u'20048', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10162-101', drug=u'SP600125', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10185-101', drug=u'CC-401', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'JNK3': [SignatureData(drug_id=u'HMSL10034-101', drug=u'AS-601245', status=None, kinomescan=u'20035', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10208-101', drug=u'JNK-IN-5A', status=None, kinomescan=u'20081', rangetested=(5.12e-10, 0.0002), signature=(4.05e-07, 8.3e-07, 7.28e-07, 2.27e-06, None, 5.37e-06))],
  u'JNK2': [SignatureData(drug_id=u'HMSL10208-101', drug=u'JNK-IN-5A', status=None, kinomescan=u'20081', rangetested=(5.12e-10, 0.0002), signature=(4.05e-07, 8.3e-07, 7.28e-07, 2.27e-06, None, 5.37e-06))],
  u'PLK1': [SignatureData(drug_id=u'HMSL10013-101', drug=u'GSK461364', status=u'investigational', kinomescan=u'20031', rangetested=(8.53e-11, 3.33e-05), signature=(8.51e-06, 3.33e-08, 4.67e-06, None, 1.65e-08, 1.2e-07)), SignatureData(drug_id=u'HMSL10014-101', drug=u'GW843682', status=None, kinomescan=u'20032', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10041-101', drug=u'BI-2536', status=u'investigational', kinomescan=u'20057', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10184-101', drug=u'ON-01910', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10191-101', drug=u'HMN-214', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'PLK3': [SignatureData(drug_id=u'HMSL10070-101', drug=u'NPK76-II-72-1', status=None, kinomescan=u'20061', rangetested=None, signature=None)],
  u'AKT1': [SignatureData(drug_id=u'HMSL10035-101', drug=u'KIN001-102', status=None, kinomescan=u'20083', rangetested=(8.53e-11, 3.33e-05), signature=(8.32e-07, 3.73e-06, 4.46e-06, 1.27e-05, 1.81e-06, 2.07e-06)), SignatureData(drug_id=u'HMSL10045-101', drug=u'A443654', status=None, kinomescan=u'20059', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10057-102', drug=u'MK2206', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10128-101', drug=u'GSK690693', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10154-101', drug=u'AT-7867', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10280-999', drug=u'Triciribine', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(6.76e-07, 4.99e-07, 4.14e-07, 2.83e-06, None, 2.74e-07))],
  u'AKT2': [SignatureData(drug_id=u'HMSL10035-101', drug=u'KIN001-102', status=None, kinomescan=u'20083', rangetested=(8.53e-11, 3.33e-05), signature=(8.32e-07, 3.73e-06, 4.46e-06, 1.27e-05, 1.81e-06, 2.07e-06)), SignatureData(drug_id=u'HMSL10057-102', drug=u'MK2206', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10128-101', drug=u'GSK690693', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'AKT3': [SignatureData(drug_id=u'HMSL10057-102', drug=u'MK2206', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10128-101', drug=u'GSK690693', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'PARP': [SignatureData(drug_id=u'HMSL10144-101', drug=u'Olaparib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10145-102', drug=u'Veliparib', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'PI3K-ALPHA': [SignatureData(drug_id=u'HMSL10047-101', drug=u'GDC-0941', status=None, kinomescan=u'20060', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10053-101', drug=u'ZSTK474', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10054-101', drug=u'AS-605240', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10146-101', drug=u'GSK2126458', status=u'investigational', kinomescan=u'20084', rangetested=(8.53e-11, 3.33e-05), signature=(4.35e-09, 5.03e-09, 2.72e-08, 2.44e-08, 7.46e-09, 3.87e-09)), SignatureData(drug_id=u'HMSL10147-101', drug=u'NVP-BKM120', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10148-101', drug=u'SAR245408', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10172-101', drug=u'GSK1059615', status=u'investigational', kinomescan=u'20085', rangetested=(3.41e-10, 0.000133), signature=(1.58e-07, 1.46e-07, 5.27e-07, 7.73e-07, 1.76e-07, 1.51e-07)), SignatureData(drug_id=u'HMSL10173-101', drug=u'SAR245409', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10232-101', drug=u'BEZ235', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(2.26e-07, 3.33e-05, 3.08e-06, 3.33e-05, 1.6e-07, 3.33e-05)), SignatureData(drug_id=u'HMSL10233-101', drug=u'BYL719', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10256-999', drug=u'GSK2119563', status=None, kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(1.51e-07, 6.59e-07, 8.75e-07, 9.98e-07, 7.32e-07, 2.09e-07))],
  u'DNA-PK': [SignatureData(drug_id=u'HMSL10061-101', drug=u'NU7441', status=None, kinomescan=u'20040', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10075-101', drug=u'QL-X-138', status=None, kinomescan=u'20062', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10080-101', drug=u'Torin2', status=None, kinomescan=u'20065', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10126-101', drug=u'PI103', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10173-101', drug=u'SAR245409', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'MNK2': [SignatureData(drug_id=u'HMSL10075-101', drug=u'QL-X-138', status=None, kinomescan=u'20062', rangetested=None, signature=None)],
  u'FAK': [SignatureData(drug_id=u'HMSL10072-101', drug=u'PF-562271', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10116-101', drug=u'PF-431396', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10199-101', drug=u'PF-573228', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'CAMK1': [SignatureData(drug_id=u'HMSL10089-101', drug=u'XMD14-99', status=None, kinomescan=u'20073', rangetested=None, signature=None)],
  u'NTRK1': [SignatureData(drug_id=u'HMSL10230-101', drug=u'Lestaurtinib', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(2.46e-07, 7.33e-07, 5e-07, 8.7e-08, 1.93e-07, 1.01e-06))],
  u'CSNK1E': [SignatureData(drug_id=u'HMSL10084-101', drug=u'WZ-3105', status=None, kinomescan=u'20068', rangetested=None, signature=None)],
  u'DYRK1A': [SignatureData(drug_id=u'HMSL10090-101', drug=u'XMD15-27', status=None, kinomescan=u'20074', rangetested=None, signature=None)],
  u'WEE1': [SignatureData(drug_id=u'HMSL10152-101', drug=u'MK1775', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'IRAK1': [SignatureData(drug_id=u'HMSL10078-101', drug=u'THZ-2-98-01', status=None, kinomescan=u'20045', rangetested=None, signature=None)],
  u'ERBB2': [SignatureData(drug_id=u'HMSL10010-101', drug=u'CP724714', status=None, kinomescan=u'20029', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10018-101', drug=u'Neratinib', status=u'investigational', kinomescan=u'20053', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10051-104', drug=u'Lapatinib', status=u'approved', kinomescan=None, rangetested=(4.27e-11, 1.67e-05), signature=(3.96e-07, 1.67e-05, 1.67e-05, 1.67e-05, 3.99e-06, 4.04e-07)), SignatureData(drug_id=u'HMSL10133-101', drug=u'Afatinib', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(5.85e-09, None, 1.74e-06, 1.82e-06, 4.65e-07, 1.32e-08))],
  u'IGF1R': [SignatureData(drug_id=u'HMSL10122-101', drug=u'AEW541', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10134-101', drug=u'GSK1904529A', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10135-101', drug=u'OSI-906', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10239-999', drug=u'AG1024', status=None, kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(3.33e-05, 3.33e-05, 8.7e-06, 3.33e-05, 6.21e-06, 3.33e-05)), SignatureData(drug_id=u'HMSL10255-999', drug=u'GSK1838705', status=None, kinomescan=None, rangetested=(3.07e-10, 0.00012), signature=(8.31e-06, 2.25e-06, 1.63e-06, 9.99e-06, 6.57e-06, 1.03e-05))],
  u'MEK5': [SignatureData(drug_id=u'HMSL10163-101', drug=u'BIX 02189', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'CHK': [SignatureData(drug_id=u'HMSL10006-101', drug=u'AZD-7762', status=u'investigational', kinomescan=u'20027', rangetested=None, signature=None)],
  u'CAMK2B': [SignatureData(drug_id=u'HMSL10090-101', drug=u'XMD15-27', status=None, kinomescan=u'20074', rangetested=None, signature=None)],
  u'MDM2': [SignatureData(drug_id=u'HMSL10268-999', drug=u'Nutlin 3a', status=None, kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(1.6e-05, 1.66e-05, 3.16e-05, 2.14e-05, 1.85e-05, 4.66e-05))],
  u'FGFR3': [SignatureData(drug_id=u'HMSL10026-101', drug=u'PD-173074', status=None, kinomescan=u'20055', rangetested=(8.53e-11, 3.33e-05), signature=(8.48e-06, 1.07e-05, 6.7e-06, 3.35e-06, 7e-06, 7.89e-06))],
  u'ALK': [SignatureData(drug_id=u'HMSL10024-101', drug=u'NVP-TAE684', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10201-101', drug=u'CH5424802', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10255-999', drug=u'GSK1838705', status=None, kinomescan=None, rangetested=(3.07e-10, 0.00012), signature=(8.31e-06, 2.25e-06, 1.63e-06, 9.99e-06, 6.57e-06, 1.03e-05))],
  u'C-MET': [SignatureData(drug_id=u'HMSL10027-101', drug=u'Crizotinib', status=u'approved', kinomescan=u'20033', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10113-101', drug=u'KIN001-237', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10118-101', drug=u'Amuvatinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10119-101', drug=u'PKI-SU11274', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10123-101', drug=u'SGX523', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10124-101', drug=u'MGCD265', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10125-101', drug=u'PHA-665752', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10131-101', drug=u'Tivantinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10156-101', drug=u'JNJ38877605', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10157-101', drug=u'Foretinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10165-101', drug=u'PF-04217903', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10194-106', drug=u'Cabozantinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'BCR-ABL': [SignatureData(drug_id=u'HMSL10022-101', drug=u'GNF2', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10023-103', drug=u'Imatinib', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10150-101', drug=u'Ponatinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'SYK': [SignatureData(drug_id=u'HMSL10040-101', drug=u'R406', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10166-101', drug=u'BAY61-3606', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'GSK3A': [SignatureData(drug_id=u'HMSL10160-101', drug=u'SB 216763', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10180-101', drug=u'CHIR-99021', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'GSK3B': [SignatureData(drug_id=u'HMSL10030-101', drug=u'KIN001-042', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10111-101', drug=u'TWS119', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10160-101', drug=u'SB 216763', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10180-101', drug=u'CHIR-99021', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'C-RAF': [SignatureData(drug_id=u'HMSL10029-101', drug=u'GW-5074', status=None, kinomescan=u'20022', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10206-101', drug=u'RAF 265', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'CK1': [SignatureData(drug_id=u'HMSL10202-101', drug=u'D 4476', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'P38-ALPHA': [SignatureData(drug_id=u'HMSL10060-101', drug=u'TAK-715', status=None, kinomescan=u'20039', rangetested=None, signature=None)],
  u'RSK2': [SignatureData(drug_id=u'HMSL10044-104', drug=u'Fmk', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'TAO1': [SignatureData(drug_id=u'HMSL10083-101', drug=u'WZ-7043', status=None, kinomescan=u'20067', rangetested=None, signature=None)],
  u'LRRK2': [SignatureData(drug_id=u'HMSL10086-101', drug=u'LRRK2-in-1', status=None, kinomescan=u'20070', rangetested=None, signature=None)],
  u'PDGFR2': [SignatureData(drug_id=u'HMSL10082-101', drug=u'WZ-4-145', status=None, kinomescan=u'20066', rangetested=None, signature=None)],
  u'ABL(T315I)': [SignatureData(drug_id=u'HMSL10015-101', drug=u'HG-5-113-01', status=None, kinomescan=u'20051', rangetested=None, signature=None)],
  u'PKC': [SignatureData(drug_id=u'HMSL10186-102', drug=u'Chelerythrine', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'JAK2': [SignatureData(drug_id=u'HMSL10138-101', drug=u'Ruxolitinib', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10139-101', drug=u'AZD-1480', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10141-101', drug=u'TG 101348', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'JAK3': [SignatureData(drug_id=u'HMSL10033-101', drug=u'KIN001-055', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10075-101', drug=u'QL-X-138', status=None, kinomescan=u'20062', rangetested=None, signature=None)],
  u'PKC-B': [SignatureData(drug_id=u'HMSL10069-101', drug=u'Enzastaurin', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'JAK1': [SignatureData(drug_id=u'HMSL10138-101', drug=u'Ruxolitinib', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10140-101', drug=u'CYT387', status=u'investigational', kinomescan=u'20082', rangetested=None, signature=None)],
  u'BMX': [SignatureData(drug_id=u'HMSL10077-101', drug=u'QL-XII-47', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'FGFR': [SignatureData(drug_id=u'HMSL10017-101', drug=u'HG-6-64-01', status=None, kinomescan=u'20021', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10083-101', drug=u'WZ-7043', status=None, kinomescan=u'20067', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10151-101', drug=u'Vargatef', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10183-101', drug=u'BGJ398', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'PI3K-GAMMA': [SignatureData(drug_id=u'HMSL10047-101', drug=u'GDC-0941', status=None, kinomescan=u'20060', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10053-101', drug=u'ZSTK474', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10054-101', drug=u'AS-605240', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10146-101', drug=u'GSK2126458', status=u'investigational', kinomescan=u'20084', rangetested=(8.53e-11, 3.33e-05), signature=(4.35e-09, 5.03e-09, 2.72e-08, 2.44e-08, 7.46e-09, 3.87e-09)), SignatureData(drug_id=u'HMSL10147-101', drug=u'NVP-BKM120', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10148-101', drug=u'SAR245408', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10172-101', drug=u'GSK1059615', status=u'investigational', kinomescan=u'20085', rangetested=(3.41e-10, 0.000133), signature=(1.58e-07, 1.46e-07, 5.27e-07, 7.73e-07, 1.76e-07, 1.51e-07)), SignatureData(drug_id=u'HMSL10173-101', drug=u'SAR245409', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10240-999', drug=u'AS-252424', status=None, kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(3.9e-06, 1.69e-06, 4.61e-06, 6.67e-05, 2.14e-05, 3.96e-05)), SignatureData(drug_id=u'HMSL10254-999', drug=u'GSK1487371', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'EPHB3': [SignatureData(drug_id=u'HMSL10089-101', drug=u'XMD14-99', status=None, kinomescan=u'20073', rangetested=None, signature=None)],
  u'EPHB4': [SignatureData(drug_id=u'HMSL10200-101', drug=u'NVP-BHG712', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'PIKFYVE': [SignatureData(drug_id=u'HMSL10109-101', drug=u'YM 201636', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'TUBB1': [SignatureData(drug_id=u'HMSL10102-101', drug=u'Paclitaxel', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10247-999', drug=u'Docetaxel', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10281-999', drug=u'Vinorelbine', status=u'approved', kinomescan=None, rangetested=None, signature=None)],
  u'BRAF(V600E)': [SignatureData(drug_id=u'HMSL10049-101', drug=u'PLX-4720', status=None, kinomescan=u'20024', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10050-101', drug=u'AZ-628', status=None, kinomescan=u'20025', rangetested=None, signature=None)],
  u'C-KIT': [SignatureData(drug_id=u'HMSL10017-101', drug=u'HG-6-64-01', status=None, kinomescan=u'20021', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10118-101', drug=u'Amuvatinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10130-101', drug=u'Masitinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10175-101', drug=u'Sunitinib', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(1.66e-05, 5.52e-06, 5.09e-06, 5.71e-06, 2.49e-06, 6.75e-06)), SignatureData(drug_id=u'HMSL10178-101', drug=u'OSI-930', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'PI3K-BETA': [SignatureData(drug_id=u'HMSL10047-101', drug=u'GDC-0941', status=None, kinomescan=u'20060', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10053-101', drug=u'ZSTK474', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10059-101', drug=u'AZD-6482', status=None, kinomescan=u'20038', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10146-101', drug=u'GSK2126458', status=u'investigational', kinomescan=u'20084', rangetested=(8.53e-11, 3.33e-05), signature=(4.35e-09, 5.03e-09, 2.72e-08, 2.44e-08, 7.46e-09, 3.87e-09)), SignatureData(drug_id=u'HMSL10147-101', drug=u'NVP-BKM120', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10148-101', drug=u'SAR245408', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10171-101', drug=u'TGX221', status=None, kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(7.96e-06, 3.28e-06, 1.39e-05, 7.09e-06, 1.04e-06, 4.66e-06)), SignatureData(drug_id=u'HMSL10172-101', drug=u'GSK1059615', status=u'investigational', kinomescan=u'20085', rangetested=(3.41e-10, 0.000133), signature=(1.58e-07, 1.46e-07, 5.27e-07, 7.73e-07, 1.76e-07, 1.51e-07)), SignatureData(drug_id=u'HMSL10173-101', drug=u'SAR245409', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'PI3K-DELTA': [SignatureData(drug_id=u'HMSL10047-101', drug=u'GDC-0941', status=None, kinomescan=u'20060', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10059-101', drug=u'AZD-6482', status=None, kinomescan=u'20038', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10146-101', drug=u'GSK2126458', status=u'investigational', kinomescan=u'20084', rangetested=(8.53e-11, 3.33e-05), signature=(4.35e-09, 5.03e-09, 2.72e-08, 2.44e-08, 7.46e-09, 3.87e-09)), SignatureData(drug_id=u'HMSL10147-101', drug=u'NVP-BKM120', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10148-101', drug=u'SAR245408', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10172-101', drug=u'GSK1059615', status=u'investigational', kinomescan=u'20085', rangetested=(3.41e-10, 0.000133), signature=(1.58e-07, 1.46e-07, 5.27e-07, 7.73e-07, 1.76e-07, 1.51e-07)), SignatureData(drug_id=u'HMSL10173-101', drug=u'SAR245409', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10204-101', drug=u'CAL-101', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'DDR1': [SignatureData(drug_id=u'HMSL10002-101', drug=u'ALW-II-38-3', status=None, kinomescan=u'20049', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10003-101', drug=u'ALW-II-49-7', status=None, kinomescan=u'20050', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10076-101', drug=u'QL-XI-92', status=None, kinomescan=u'20063', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10082-101', drug=u'WZ-4-145', status=None, kinomescan=u'20066', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10083-101', drug=u'WZ-7043', status=None, kinomescan=u'20067', rangetested=None, signature=None)],
  u'CHK1': [SignatureData(drug_id=u'HMSL10112-101', drug=u'PF-477736', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10276-999', drug=u'TCS 2312', status=None, kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(6.15e-07, 1.05e-06, 7.82e-07, 1.16e-07, 2.97e-07, 5.36e-07))],
  u'TPL2': [SignatureData(drug_id=u'HMSL10153-101', drug=u'KIN001-266', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'P38-BETA': [SignatureData(drug_id=u'HMSL10017-101', drug=u'HG-6-64-01', status=None, kinomescan=u'20021', rangetested=None, signature=None)],
  u'VEGFR1': [SignatureData(drug_id=u'HMSL10042-101', drug=u'Motesanib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10114-102', drug=u'Pazopanib', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10175-101', drug=u'Sunitinib', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(1.66e-05, 5.52e-06, 5.09e-06, 5.71e-06, 2.49e-06, 6.75e-06))],
  u'TIE2': [SignatureData(drug_id=u'HMSL10193-101', drug=u'Tie2 kinase inhibitor', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'STK39': [SignatureData(drug_id=u'HMSL10090-101', drug=u'XMD15-27', status=None, kinomescan=u'20074', rangetested=None, signature=None)],
  u'CLK2': [SignatureData(drug_id=u'HMSL10084-101', drug=u'WZ-3105', status=None, kinomescan=u'20068', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10090-101', drug=u'XMD15-27', status=None, kinomescan=u'20074', rangetested=None, signature=None)],
  u'TIE1': [SignatureData(drug_id=u'HMSL10082-101', drug=u'WZ-4-145', status=None, kinomescan=u'20066', rangetested=None, signature=None)],
  u'LCK': [SignatureData(drug_id=u'HMSL10019-101', drug=u'JW-7-24-1', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10020-101', drug=u'Dasatinib', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10038-101', drug=u'WH-4-023', status=None, kinomescan=u'20036', rangetested=None, signature=None)],
  u'BTK': [SignatureData(drug_id=u'HMSL10075-101', drug=u'QL-X-138', status=None, kinomescan=u'20062', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10077-101', drug=u'QL-XII-47', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10129-101', drug=u'PCI-32765', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'PDGFRB': [SignatureData(drug_id=u'HMSL10017-101', drug=u'HG-6-64-01', status=None, kinomescan=u'20021', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10118-101', drug=u'Amuvatinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10151-101', drug=u'Vargatef', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10175-101', drug=u'Sunitinib', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(1.66e-05, 5.52e-06, 5.09e-06, 5.71e-06, 2.49e-06, 6.75e-06)), SignatureData(drug_id=u'HMSL10177-101', drug=u'Brivanib', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'ATM': [SignatureData(drug_id=u'HMSL10009-101', drug=u'CP466722', status=None, kinomescan=u'20028', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10074-101', drug=u'KU-55933', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10155-101', drug=u'KU-60019', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'RET': [SignatureData(drug_id=u'HMSL10017-101', drug=u'HG-6-64-01', status=None, kinomescan=u'20021', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10087-101', drug=u'XMD11-85h', status=None, kinomescan=u'20071', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10091-101', drug=u'XMD16-144', status=None, kinomescan=u'20075', rangetested=None, signature=None)],
  u'FLT4': [SignatureData(drug_id=u'HMSL10087-101', drug=u'XMD11-85h', status=None, kinomescan=u'20071', rangetested=None, signature=None)],
  u'FLT3': [SignatureData(drug_id=u'HMSL10017-101', drug=u'HG-6-64-01', status=None, kinomescan=u'20021', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10037-101', drug=u'AC220', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10084-101', drug=u'WZ-3105', status=None, kinomescan=u'20068', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10127-101', drug=u'Dovitinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10175-101', drug=u'Sunitinib', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(1.66e-05, 5.52e-06, 5.09e-06, 5.71e-06, 2.49e-06, 6.75e-06)), SignatureData(drug_id=u'HMSL10182-101', drug=u'Linifanib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10192-101', drug=u'KW2449', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10230-101', drug=u'Lestaurtinib', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(2.46e-07, 7.33e-07, 5e-07, 8.7e-08, 1.93e-07, 1.01e-06))],
  u'TBK1': [SignatureData(drug_id=u'HMSL10188-101', drug=u'BX-795', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'CSF1R': [SignatureData(drug_id=u'HMSL10017-101', drug=u'HG-6-64-01', status=None, kinomescan=u'20021', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10082-101', drug=u'WZ-4-145', status=None, kinomescan=u'20066', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10083-101', drug=u'WZ-7043', status=None, kinomescan=u'20067', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10187-101', drug=u'Ki20227', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10195-101', drug=u'KIN001-269', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'MARK4': [SignatureData(drug_id=u'HMSL10087-101', drug=u'XMD11-85h', status=None, kinomescan=u'20071', rangetested=None, signature=None)],
  u'KDR': [SignatureData(drug_id=u'HMSL10005-101', drug=u'Tivozanib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10007-101', drug=u'AZD-8055', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10008-101', drug=u'Sorafenib', status=u'approved', kinomescan=u'20020', rangetested=(2.56e-09, 0.001), signature=(6.91e-05, 3.21e-05, 4.59e-05, 8.55e-05, 3.58e-05, 4.48e-05)), SignatureData(drug_id=u'HMSL10151-101', drug=u'Vargatef', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10175-101', drug=u'Sunitinib', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(1.66e-05, 5.52e-06, 5.09e-06, 5.71e-06, 2.49e-06, 6.75e-06)), SignatureData(drug_id=u'HMSL10177-101', drug=u'Brivanib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10178-101', drug=u'OSI-930', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10194-106', drug=u'Cabozantinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10198-101', drug=u'Vandetanib', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10206-101', drug=u'RAF 265', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'SRC': [SignatureData(drug_id=u'HMSL10020-101', drug=u'Dasatinib', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10032-101', drug=u'Saracatinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10039-101', drug=u'WH-4-025', status=None, kinomescan=u'20056', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10091-101', drug=u'XMD16-144', status=None, kinomescan=u'20075', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10189-101', drug=u'Bosutinib', status=u'approved', kinomescan=None, rangetested=(2.56e-10, 0.0001), signature=(1.94e-06, 3.14e-06, 3.75e-06, 8.86e-07, 9.32e-07, 3.92e-06))],
  u'GSK-3': [SignatureData(drug_id=u'HMSL10031-101', drug=u'KIN001-043', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'PI3K': [SignatureData(drug_id=u'HMSL10080-101', drug=u'Torin2', status=None, kinomescan=u'20065', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10203-101', drug=u'A66', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10234-101', drug=u'GDC-0980', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'PARP-2': [SignatureData(drug_id=u'HMSL10144-101', drug=u'Olaparib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10145-102', drug=u'Veliparib', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'IKK-BETA': [SignatureData(drug_id=u'HMSL10028-102', drug=u'BMS-345541', status=None, kinomescan=u'20034', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10136-101', drug=u'TPCA-1', status=None, kinomescan=None, rangetested=(3.41e-10, 0.000133), signature=(6.67e-05, 2.12e-06, 2.86e-06, 3.88e-06, 3.6e-06, 6.67e-05))],
  u'MAST1': [SignatureData(drug_id=u'HMSL10090-101', drug=u'XMD15-27', status=None, kinomescan=u'20074', rangetested=None, signature=None)],
  u'MTOR': [SignatureData(drug_id=u'HMSL10064-101', drug=u'WYE-125132', status=None, kinomescan=u'20079', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10075-101', drug=u'QL-X-138', status=None, kinomescan=u'20062', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10079-101', drug=u'Torin1', status=None, kinomescan=u'20064', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10080-101', drug=u'Torin2', status=None, kinomescan=u'20065', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10172-101', drug=u'GSK1059615', status=u'investigational', kinomescan=u'20085', rangetested=(3.41e-10, 0.000133), signature=(1.58e-07, 1.46e-07, 5.27e-07, 7.73e-07, 1.76e-07, 1.51e-07)), SignatureData(drug_id=u'HMSL10173-101', drug=u'SAR245409', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10234-101', drug=u'GDC-0980', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10277-999', drug=u'Temsirolimus', status=u'approved', kinomescan=None, rangetested=(3.41e-10, 0.000133), signature=(2.69e-08, 7.98e-07, 5.68e-06, 1.23e-05, 3.26e-07, 5.42e-08))],
  u'LTK': [SignatureData(drug_id=u'HMSL10015-101', drug=u'HG-5-113-01', status=None, kinomescan=u'20051', rangetested=None, signature=None)],
  u'ITK': [SignatureData(drug_id=u'HMSL10043-101', drug=u'KIN001-127', status=None, kinomescan=u'20058', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10137-101', drug=u'BMS-509744', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'MEK': [SignatureData(drug_id=u'HMSL10048-101', drug=u'CI-1040', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10101-101', drug=u'PD-325901', status=u'investigational', kinomescan=u'20080', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10143-101', drug=u'BMS-777607', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10164-101', drug=u'ARRY-424704', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'CDK': [SignatureData(drug_id=u'HMSL10001-101', drug=u'Seliciclib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10011-101', drug=u'Flavopiridol', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10158-101', drug=u'AZD-5438', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'CDK1': [SignatureData(drug_id=u'HMSL10025-101', drug=u'MLS000911536', status=None, kinomescan=u'20054', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10073-101', drug=u'PHA-793887', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10267-999', drug=u'NU6102', status=None, kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(1.61e-05, 7.8e-06, 1.36e-05, 9.36e-06, 1.97e-05, 3.09e-05)), SignatureData(drug_id=u'HMSL10273-999', drug=u'Purvalanol A', status=None, kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(0.000167, 2.36e-05, 6.68e-05, 0.000167, 0.000167, 6.46e-05))],
  u'CDK2': [SignatureData(drug_id=u'HMSL10073-101', drug=u'PHA-793887', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'CDK4': [SignatureData(drug_id=u'HMSL10071-101', drug=u'PD0332991', status=u'investigational', kinomescan=u'20044', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10073-101', drug=u'PHA-793887', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10251-999', drug=u'Fascaplysin', status=None, kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(1.85e-07, 1.47e-08, 3.71e-08, 2.73e-07, 1.25e-07, 2.23e-07))],
  u'CDK5': [SignatureData(drug_id=u'HMSL10073-101', drug=u'PHA-793887', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'CDK7': [SignatureData(drug_id=u'HMSL10073-101', drug=u'PHA-793887', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'CDK9': [SignatureData(drug_id=u'HMSL10004-101', drug=u'AT-7519', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10073-101', drug=u'PHA-793887', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10132-101', drug=u'BMS-387032', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10196-101', drug=u'KIN001-270', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'ALK5': [SignatureData(drug_id=u'HMSL10121-101', drug=u'SB 525334', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10202-101', drug=u'D 4476', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'ALK2': [SignatureData(drug_id=u'HMSL10115-102', drug=u'LDN-193189', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'C-ABL': [SignatureData(drug_id=u'HMSL10017-101', drug=u'HG-6-64-01', status=None, kinomescan=u'20021', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10023-103', drug=u'Imatinib', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10099-101', drug=u'Nilotinib', status=u'approved', kinomescan=None, rangetested=None, signature=None)],
  u'LOK': [SignatureData(drug_id=u'HMSL10015-101', drug=u'HG-5-113-01', status=None, kinomescan=u'20051', rangetested=None, signature=None)],
  u'AURORA': [SignatureData(drug_id=u'HMSL10065-101', drug=u'KIN001-220', status=None, kinomescan=u'20041', rangetested=None, signature=None)],
  u'EGFR': [SignatureData(drug_id=u'HMSL10016-101', drug=u'HG-5-88-01', status=None, kinomescan=u'20052', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10017-101', drug=u'HG-6-64-01', status=None, kinomescan=u'20021', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10051-104', drug=u'Lapatinib', status=u'approved', kinomescan=None, rangetested=(4.27e-11, 1.67e-05), signature=(3.96e-07, 1.67e-05, 1.67e-05, 1.67e-05, 3.99e-06, 4.04e-07)), SignatureData(drug_id=u'HMSL10082-101', drug=u'WZ-4-145', status=None, kinomescan=u'20066', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10085-101', drug=u'WZ-4002', status=None, kinomescan=u'20069', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10097-101', drug=u'Erlotinib', status=u'approved', kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(1.05e-05, 7.52e-06, 1.79e-05, 6.67e-05, 1.72e-06, 1.58e-05)), SignatureData(drug_id=u'HMSL10098-101', drug=u'Gefitinib', status=u'approved', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(7.21e-07, 2.94e-05, 1.08e-05, 1.76e-05, 8.91e-06, 2.76e-06)), SignatureData(drug_id=u'HMSL10120-102', drug=u'Canertinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10133-101', drug=u'Afatinib', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(5.85e-09, None, 1.74e-06, 1.82e-06, 4.65e-07, 1.32e-08)), SignatureData(drug_id=u'HMSL10159-101', drug=u'Pelitinib', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10223-101', drug=u'Tyrphostin', status=None, kinomescan=u'20086', rangetested=(4.27e-10, 0.000167), signature=(6.7e-07, 0.000167, 0.000167, 0.000125, 6.19e-05, 3.99e-06))],
  u'RIPK1': [SignatureData(drug_id=u'HMSL10088-101', drug=u'XMD13-2', status=None, kinomescan=u'20072', rangetested=None, signature=None)],
  u'ROCK2': [SignatureData(drug_id=u'HMSL10012-101', drug=u'GSK429286A', status=None, kinomescan=u'20030', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10149-102', drug=u'Y-39983', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10253-999', drug=u'Glycyl-H-1152', status=None, kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(6.67e-05, 6.07e-07, 6.67e-05, 1.09e-06, 9.15e-07, 4.64e-05))],
  u'HSP90 ALPHA': [SignatureData(drug_id=u'HMSL10108-101', drug=u'Geldanamycin', status=None, kinomescan=None, rangetested=(2.56e-10, 0.0001), signature=(1.44e-08, 1.57e-08, 2.84e-08, 2.75e-08, 8.06e-08, 1.62e-08)), SignatureData(drug_id=u'HMSL10161-101', drug=u'NVP-AUY922', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10236-999', drug=u'17-AAG', status=None, kinomescan=None, rangetested=(2.56e-10, 0.0001), signature=(1.46e-06, 5.13e-06, 4.12e-09, 5.71e-08, 2.39e-07, 2.85e-08))],
  u'ADCK4': [SignatureData(drug_id=u'HMSL10016-101', drug=u'HG-5-88-01', status=None, kinomescan=u'20052', rangetested=None, signature=None)],
  u'B-RAF': [SignatureData(drug_id=u'HMSL10008-101', drug=u'Sorafenib', status=u'approved', kinomescan=u'20020', rangetested=(2.56e-09, 0.001), signature=(6.91e-05, 3.21e-05, 4.59e-05, 8.55e-05, 3.58e-05, 4.48e-05)), SignatureData(drug_id=u'HMSL10017-101', drug=u'HG-6-64-01', status=None, kinomescan=u'20021', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10046-101', drug=u'SB 590885', status=None, kinomescan=u'20023', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10068-101', drug=u'R7204', status=u'approved', kinomescan=u'20026', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10181-101', drug=u'GDC-0879', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10262-999', drug=u'L-779450', status=None, kinomescan=None, rangetested=(1.28e-10, 5e-05), signature=(1.62e-05, 8.55e-06, 1.07e-05, 1.71e-05, 3.21e-05, 2.21e-05))],
  u'MEK2': [SignatureData(drug_id=u'HMSL10056-101', drug=u'Selumetinib', status=u'investigational', kinomescan=None, rangetested=(1.28e-10, 5e-05), signature=(5e-05, 5e-05, 5e-05, 5e-05, 1.79e-06, 5e-05)), SignatureData(drug_id=u'HMSL10142-101', drug=u'GSK1120212', status=u'investigational', kinomescan=None, rangetested=(4.27e-11, 1.67e-05), signature=(1.67e-05, 1.67e-05, 1.67e-05, 1.67e-05, 6.57e-09, 1.67e-05)), SignatureData(drug_id=u'HMSL10271-999', drug=u'PD-98059', status=None, kinomescan=None, rangetested=(2.56e-10, 0.0001), signature=(2.62e-05, 4.04e-06, 0.0001, 5.14e-05, 5e-05, 1.85e-05))],
  u'MEK1': [SignatureData(drug_id=u'HMSL10056-101', drug=u'Selumetinib', status=u'investigational', kinomescan=None, rangetested=(1.28e-10, 5e-05), signature=(5e-05, 5e-05, 5e-05, 5e-05, 1.79e-06, 5e-05)), SignatureData(drug_id=u'HMSL10142-101', drug=u'GSK1120212', status=u'investigational', kinomescan=None, rangetested=(4.27e-11, 1.67e-05), signature=(1.67e-05, 1.67e-05, 1.67e-05, 1.67e-05, 6.57e-09, 1.67e-05)), SignatureData(drug_id=u'HMSL10271-999', drug=u'PD-98059', status=None, kinomescan=None, rangetested=(2.56e-10, 0.0001), signature=(2.62e-05, 4.04e-06, 0.0001, 5.14e-05, 5e-05, 1.85e-05))],
  u'AURKA': [SignatureData(drug_id=u'HMSL10021-101', drug=u'Tozasertib', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(1.44e-05, 1.28e-07, 7.83e-06, 1.8e-07, 2.52e-06, 3.33e-05)), SignatureData(drug_id=u'HMSL10066-101', drug=u'MLN8054', status=None, kinomescan=u'20042', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10091-101', drug=u'XMD16-144', status=None, kinomescan=u'20075', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10092-101', drug=u'JWE-035', status=None, kinomescan=u'20046', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10096-101', drug=u'ZM-447439', status=None, kinomescan=u'20047', rangetested=None, signature=None)],
  u'AURKB': [SignatureData(drug_id=u'HMSL10021-101', drug=u'Tozasertib', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(1.44e-05, 1.28e-07, 7.83e-06, 1.8e-07, 2.52e-06, 3.33e-05)), SignatureData(drug_id=u'HMSL10062-101', drug=u'GSK1070916', status=None, kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(6.33e-06, 1.13e-08, 2.04e-06, 2.97e-07, 2.63e-07, 5.14e-06)), SignatureData(drug_id=u'HMSL10067-101', drug=u'Barasertib', status=u'investigational', kinomescan=u'20043', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10091-101', drug=u'XMD16-144', status=None, kinomescan=u'20075', rangetested=None, signature=None)],
  u'AURKC': [SignatureData(drug_id=u'HMSL10021-101', drug=u'Tozasertib', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(1.44e-05, 1.28e-07, 7.83e-06, 1.8e-07, 2.52e-06, 3.33e-05)), SignatureData(drug_id=u'HMSL10062-101', drug=u'GSK1070916', status=None, kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(6.33e-06, 1.13e-08, 2.04e-06, 2.97e-07, 2.63e-07, 5.14e-06))],
  u'HSP90 BETA': [SignatureData(drug_id=u'HMSL10161-101', drug=u'NVP-AUY922', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'P53': [SignatureData(drug_id=u'HMSL10170-101', drug=u'JNJ26854165', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'ULK1': [SignatureData(drug_id=u'HMSL10084-101', drug=u'WZ-3105', status=None, kinomescan=u'20068', rangetested=None, signature=None)],
  u'PRKCD': [SignatureData(drug_id=u'HMSL10087-101', drug=u'XMD11-85h', status=None, kinomescan=u'20071', rangetested=None, signature=None)],
  u'ERK1': [SignatureData(drug_id=u'HMSL10110-101', drug=u'FR180204', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'ERK2': [SignatureData(drug_id=u'HMSL10110-101', drug=u'FR180204', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'AMPK-ALPHA1': [SignatureData(drug_id=u'HMSL10174-101', drug=u'A769662', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'ERK5': [SignatureData(drug_id=u'HMSL10086-101', drug=u'LRRK2-in-1', status=None, kinomescan=u'20070', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10093-101', drug=u'XMD8-85', status=None, kinomescan=u'20076', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10094-101', drug=u'XMD8-92', status=None, kinomescan=u'20077', rangetested=None, signature=None)],
  u'MTORC2': [SignatureData(drug_id=u'HMSL10007-101', drug=u'AZD-8055', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10052-101', drug=u'Sirolimus', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(2.42e-08, 1.65e-08, 5.16e-08, 4.91e-08, 1.2e-07, 8.12e-09)), SignatureData(drug_id=u'HMSL10063-102', drug=u'OSI-027', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10146-101', drug=u'GSK2126458', status=u'investigational', kinomescan=u'20084', rangetested=(8.53e-11, 3.33e-05), signature=(4.35e-09, 5.03e-09, 2.72e-08, 2.44e-08, 7.46e-09, 3.87e-09)), SignatureData(drug_id=u'HMSL10235-101', drug=u'RAD001', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'MTORC1': [SignatureData(drug_id=u'HMSL10007-101', drug=u'AZD-8055', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10052-101', drug=u'Sirolimus', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(2.42e-08, 1.65e-08, 5.16e-08, 4.91e-08, 1.2e-07, 8.12e-09)), SignatureData(drug_id=u'HMSL10063-102', drug=u'OSI-027', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10146-101', drug=u'GSK2126458', status=u'investigational', kinomescan=u'20084', rangetested=(8.53e-11, 3.33e-05), signature=(4.35e-09, 5.03e-09, 2.72e-08, 2.44e-08, 7.46e-09, 3.87e-09)), SignatureData(drug_id=u'HMSL10235-101', drug=u'RAD001', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'PDK1': [SignatureData(drug_id=u'HMSL10055-101', drug=u'BX-912', status=None, kinomescan=u'20037', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10081-101', drug=u'KIN001-244', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'P38 MAPK': [SignatureData(drug_id=u'HMSL10036-101', drug=u'SB 239063', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10167-101', drug=u'SB 203580', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10168-101', drug=u'VX-745', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10169-101', drug=u'BIRB 796', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'BCL2': [SignatureData(drug_id=u'HMSL10102-101', drug=u'Paclitaxel', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10179-101', drug=u'ABT-737', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10247-999', drug=u'Docetaxel', status=u'approved', kinomescan=None, rangetested=None, signature=None)],
}
