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

dpi = 72  # 72 dpi produces perfect 1-pixel lines for 1-pt figure lines
colors = ('red', 'yellow', 'magenta', 'blue', 'green', 'cyan')  # cell line marker colors

main_template = 'pathway/signature.html'


def signature(target_name, compounds, cell_lines):
    ctx = {'signature': template_context(target_name, compounds)}
    return render_to_string(main_template, ctx)


def signature_images(target_name, compounds, target_dir):
    all_ranges = list(itertools.chain(*[c.rangetested for c in compounds]))
    xlimits = min(all_ranges), max(all_ranges)
    for compound in compounds:
        signature_image(target_name, compound, xlimits, target_dir)
    signature_image(target_name, None, xlimits, target_dir, scale_only=True)
        

def signature_image(target_name, compound, xlimits, target_dir, scale_only=False):

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



def template_context(target_name, compounds):
    def filter_(compound):
        return compound.isprimary
    return {
        'target_name': target_name,
        'primary_compounds': itertools.ifilter(filter_, compounds),
        'nonprimary_compounds': itertools.ifilterfalse(filter_, compounds),
        }


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

cell_lines = (u'BT474', u'HCC1187', u'HCC1428', u'HCC38', u'HCC70', u'SKBR3')

LATEST = {
  u'JNK1': [SignatureData(drug_id=u'HMSL10058', drug=u'CG930', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10095', drug=u'ZG10', status=None, kinomescan=u'300093', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10100', drug=u'JNK9L', status=None, kinomescan=u'300030', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10162', drug=u'SP600125', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10185', drug=u'CC401', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'JNK3': [SignatureData(drug_id=u'HMSL10034', drug=u'AS601245', status=None, kinomescan=u'300017', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10208', drug=u'JNKIN5A', status=None, kinomescan=u'300112', rangetested=(5.12e-10, 0.0002), signature=(4.05e-07, 8.3e-07, 7.28e-07, 2.27e-06, None, 5.37e-06))],
  u'JNK2': [SignatureData(drug_id=u'HMSL10208', drug=u'JNKIN5A', status=None, kinomescan=u'300112', rangetested=(5.12e-10, 0.0002), signature=(4.05e-07, 8.3e-07, 7.28e-07, 2.27e-06, None, 5.37e-06))],
  u'PLK1': [SignatureData(drug_id=u'HMSL10013', drug=u'GSK461364', status=u'investigational', kinomescan=u'300013', rangetested=(8.53e-11, 3.33e-05), signature=(8.51e-06, 3.33e-08, 4.67e-06, None, 1.65e-08, 1.2e-07)), SignatureData(drug_id=u'HMSL10014', drug=u'GW843682', status=None, kinomescan=u'300014', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10041', drug=u'BI2536', status=u'investigational', kinomescan=u'300072', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10184', drug=u'ON01910', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10191', drug=u'HMN214', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'PLK3': [SignatureData(drug_id=u'HMSL10070', drug=u'NPK76II721', status=None, kinomescan=u'300076', rangetested=None, signature=None)],
  u'AKT1': [SignatureData(drug_id=u'HMSL10035', drug=u'KIN001102', status=None, kinomescan=u'300132', rangetested=(8.53e-11, 3.33e-05), signature=(8.32e-07, 3.73e-06, 4.46e-06, 1.27e-05, 1.81e-06, 2.07e-06)), SignatureData(drug_id=u'HMSL10045', drug=u'A443654', status=None, kinomescan=u'300074', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10057', drug=u'MK2206', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10128', drug=u'GSK 690693', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10154', drug=u'AT7867', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10280', drug=u'TRICIRIBINE', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(6.76e-07, 4.99e-07, 4.14e-07, 2.83e-06, None, 2.74e-07))],
  u'AKT2': [SignatureData(drug_id=u'HMSL10035', drug=u'KIN001102', status=None, kinomescan=u'300132', rangetested=(8.53e-11, 3.33e-05), signature=(8.32e-07, 3.73e-06, 4.46e-06, 1.27e-05, 1.81e-06, 2.07e-06)), SignatureData(drug_id=u'HMSL10057', drug=u'MK2206', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10128', drug=u'GSK 690693', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'AKT3': [SignatureData(drug_id=u'HMSL10057', drug=u'MK2206', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10128', drug=u'GSK 690693', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'PARP': [SignatureData(drug_id=u'HMSL10144', drug=u'OLAPARIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10145', drug=u'VELIPARIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'DNA-PK': [SignatureData(drug_id=u'HMSL10061', drug=u'NU7441', status=None, kinomescan=u'300022', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10075', drug=u'QLX138', status=None, kinomescan=u'300077', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10080', drug=u'TORIN2', status=None, kinomescan=u'300080', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10126', drug=u'PI103', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10173', drug=u'SAR245409', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'MNK2': [SignatureData(drug_id=u'HMSL10075', drug=u'QLX138', status=None, kinomescan=u'300077', rangetested=None, signature=None)],
  u'FAK': [SignatureData(drug_id=u'HMSL10072', drug=u'PF562271', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10116', drug=u'PF431396', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10199', drug=u'PF 573228', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'CAMK1': [SignatureData(drug_id=u'HMSL10089', drug=u'XMD1499', status=None, kinomescan=u'300088', rangetested=None, signature=None)],
  u'NTRK1': [SignatureData(drug_id=u'HMSL10230', drug=u'LESTAURTINIB', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(2.46e-07, 7.33e-07, 5e-07, 8.7e-08, 1.93e-07, 1.01e-06))],
  u'CSNK1E': [SignatureData(drug_id=u'HMSL10084', drug=u'WZ3105', status=None, kinomescan=u'300083', rangetested=None, signature=None)],
  u'DYRK1A': [SignatureData(drug_id=u'HMSL10090', drug=u'XMD1527', status=None, kinomescan=u'300089', rangetested=None, signature=None)],
  u'WEE1': [SignatureData(drug_id=u'HMSL10152', drug=u'MK 1775', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'IRAK1': [SignatureData(drug_id=u'HMSL10078', drug=u'THZ29801', status=None, kinomescan=u'300027', rangetested=None, signature=None)],
  u'ERBB2': [SignatureData(drug_id=u'HMSL10010', drug=u'CP724714', status=None, kinomescan=u'300011', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10018', drug=u'NERATINIB', status=u'investigational', kinomescan=u'300067', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10051', drug=u'LAPATINIB', status=u'approved', kinomescan=None, rangetested=(4.27e-11, 1.67e-05), signature=(3.96e-07, 1.67e-05, 1.67e-05, 1.67e-05, 3.99e-06, 4.04e-07)), SignatureData(drug_id=u'HMSL10133', drug=u'AFATINIB', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(5.85e-09, None, 1.74e-06, 1.82e-06, 4.65e-07, 1.32e-08))],
  u'IGF1R': [SignatureData(drug_id=u'HMSL10122', drug=u'AEW541', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10134', drug=u'GSK1904529A', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10135', drug=u'OSI 906', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10239', drug=u'AG1024', status=None, kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(3.33e-05, 3.33e-05, 8.7e-06, 3.33e-05, 6.21e-06, 3.33e-05)), SignatureData(drug_id=u'HMSL10255', drug=u'GSK1838705', status=None, kinomescan=None, rangetested=(3.07e-10, 0.00012), signature=(8.31e-06, 2.25e-06, 1.63e-06, 9.99e-06, 6.57e-06, 1.03e-05))],
  u'MEK5': [SignatureData(drug_id=u'HMSL10163', drug=u'BIX 02189', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'CHK': [SignatureData(drug_id=u'HMSL10006', drug=u'AZD7762', status=u'investigational', kinomescan=u'300009', rangetested=None, signature=None)],
  u'CAMK2B': [SignatureData(drug_id=u'HMSL10090', drug=u'XMD1527', status=None, kinomescan=u'300089', rangetested=None, signature=None)],
  u'PI3K-ALPHA': [SignatureData(drug_id=u'HMSL10047', drug=u'GDC0941', status=None, kinomescan=u'300075', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10053', drug=u'ZSTK474', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10054', drug=u'AS605240', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10146', drug=u'GSK2126458', status=u'investigational', kinomescan=u'300133', rangetested=(8.53e-11, 3.33e-05), signature=(4.35e-09, 5.03e-09, 2.72e-08, 2.44e-08, 7.46e-09, 3.87e-09)), SignatureData(drug_id=u'HMSL10147', drug=u'NVPBKM120', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10148', drug=u'SAR245408', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10172', drug=u'GSK1059615', status=u'investigational', kinomescan=u'300134', rangetested=(3.41e-10, 0.000133), signature=(1.58e-07, 1.46e-07, 5.27e-07, 7.73e-07, 1.76e-07, 1.51e-07)), SignatureData(drug_id=u'HMSL10173', drug=u'SAR245409', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10232', drug=u'BEZ235', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(2.26e-07, 3.33e-05, 3.08e-06, 3.33e-05, 1.6e-07, 3.33e-05)), SignatureData(drug_id=u'HMSL10233', drug=u'BYL719', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10256', drug=u'GSK2119563', status=None, kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(1.51e-07, 6.59e-07, 8.75e-07, 9.98e-07, 7.32e-07, 2.09e-07))],
  u'FGFR3': [SignatureData(drug_id=u'HMSL10026', drug=u'PD173074', status=None, kinomescan=u'300070', rangetested=(8.53e-11, 3.33e-05), signature=(8.48e-06, 1.07e-05, 6.7e-06, 3.35e-06, 7e-06, 7.89e-06))],
  u'ALK': [SignatureData(drug_id=u'HMSL10024', drug=u'NVPTAE684', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10201', drug=u'CH5424802', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'C-MET': [SignatureData(drug_id=u'HMSL10027', drug=u'CRIZOTINIB', status=u'approved', kinomescan=u'300015', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10113', drug=u'CMET', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10118', drug=u'AMUVATINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10119', drug=u'PKISU11274', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10123', drug=u'SGX523', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10124', drug=u'MGCD265', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10125', drug=u'PHA665752', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10131', drug=u'TIVANTINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10156', drug=u'JNJ38877605', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10157', drug=u'FORETINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10165', drug=u'PF04217903', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10194', drug=u'CABOZANTINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'BCR-ABL': [SignatureData(drug_id=u'HMSL10022', drug=u'GNF2', status=None, kinomescan=u'300068', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10023', drug=u'IMATINIB', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10150', drug=u'PONATINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'SYK': [SignatureData(drug_id=u'HMSL10040', drug=u'R406', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10166', drug=u'BAY613606', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'GSK3A': [SignatureData(drug_id=u'HMSL10160', drug=u'SB 216763', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10180', drug=u'CHIR99021', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'GSK3B': [SignatureData(drug_id=u'HMSL10030', drug=u'KIN001042', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10111', drug=u'TWS119', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10160', drug=u'SB 216763', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10180', drug=u'CHIR99021', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'C-RAF': [SignatureData(drug_id=u'HMSL10029', drug=u'GW5074', status=None, kinomescan=u'300004', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10206', drug=u'RAF 265', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'CK1': [SignatureData(drug_id=u'HMSL10202', drug=u'D 4476', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'P38-ALPHA': [SignatureData(drug_id=u'HMSL10060', drug=u'TAK715', status=None, kinomescan=u'300021', rangetested=None, signature=None)],
  u'RSK2': [SignatureData(drug_id=u'HMSL10044', drug=u'FMK', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'TAO1': [SignatureData(drug_id=u'HMSL10083', drug=u'WZ7043', status=None, kinomescan=u'300082', rangetested=None, signature=None)],
  u'LRRK2': [SignatureData(drug_id=u'HMSL10086', drug=u'LRRK2IN1', status=None, kinomescan=u'300085', rangetested=None, signature=None)],
  u'PDGFR2': [SignatureData(drug_id=u'HMSL10082', drug=u'WZ4145', status=None, kinomescan=u'300081', rangetested=None, signature=None)],
  u'ABL(T315I)': [SignatureData(drug_id=u'HMSL10015', drug=u'HG511301', status=None, kinomescan=u'300065', rangetested=None, signature=None)],
  u'PKC': [SignatureData(drug_id=u'HMSL10186', drug=u'CHELERYTHRINE', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'JAK2': [SignatureData(drug_id=u'HMSL10138', drug=u'RUXOLITINIB', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10139', drug=u'AZD1480', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10141', drug=u'TG 101348', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'JAK3': [SignatureData(drug_id=u'HMSL10033', drug=u'KIN001055', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10075', drug=u'QLX138', status=None, kinomescan=u'300077', rangetested=None, signature=None)],
  u'PKC-B': [SignatureData(drug_id=u'HMSL10069', drug=u'ENZASTAURIN', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'JAK1': [SignatureData(drug_id=u'HMSL10138', drug=u'RUXOLITINIB', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10140', drug=u'CYT387', status=u'investigational', kinomescan=u'300131', rangetested=None, signature=None)],
  u'BMX': [SignatureData(drug_id=u'HMSL10077', drug=u'QLXII47', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'FGFR': [SignatureData(drug_id=u'HMSL10017', drug=u'HG66401', status=None, kinomescan=u'300003', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10083', drug=u'WZ7043', status=None, kinomescan=u'300082', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10151', drug=u'VARGATEF', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10183', drug=u'BGJ398', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'PI3K-GAMMA': [SignatureData(drug_id=u'HMSL10047', drug=u'GDC0941', status=None, kinomescan=u'300075', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10053', drug=u'ZSTK474', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10054', drug=u'AS605240', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10146', drug=u'GSK2126458', status=u'investigational', kinomescan=u'300133', rangetested=(8.53e-11, 3.33e-05), signature=(4.35e-09, 5.03e-09, 2.72e-08, 2.44e-08, 7.46e-09, 3.87e-09)), SignatureData(drug_id=u'HMSL10147', drug=u'NVPBKM120', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10148', drug=u'SAR245408', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10172', drug=u'GSK1059615', status=u'investigational', kinomescan=u'300134', rangetested=(3.41e-10, 0.000133), signature=(1.58e-07, 1.46e-07, 5.27e-07, 7.73e-07, 1.76e-07, 1.51e-07)), SignatureData(drug_id=u'HMSL10173', drug=u'SAR245409', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10240', drug=u'AS252424', status=None, kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(3.9e-06, 1.69e-06, 4.61e-06, 6.67e-05, 2.14e-05, 3.96e-05)), SignatureData(drug_id=u'HMSL10254', drug=u'GSK1487371', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'EPHB3': [SignatureData(drug_id=u'HMSL10089', drug=u'XMD1499', status=None, kinomescan=u'300088', rangetested=None, signature=None)],
  u'EPHB4': [SignatureData(drug_id=u'HMSL10200', drug=u'NVPBHG712', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'PIKFYVE': [SignatureData(drug_id=u'HMSL10109', drug=u'YM 201636', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'TUBB1': [],
  u'BRAF(V600E)': [SignatureData(drug_id=u'HMSL10049', drug=u'PLX4720', status=None, kinomescan=u'300006', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10050', drug=u'AZ628', status=None, kinomescan=u'300007', rangetested=None, signature=None)],
  u'C-KIT': [SignatureData(drug_id=u'HMSL10017', drug=u'HG66401', status=None, kinomescan=u'300003', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10118', drug=u'AMUVATINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10130', drug=u'MASITINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10175', drug=u'SUNITINIB', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(1.66e-05, 5.52e-06, 5.09e-06, 5.71e-06, 2.49e-06, 6.75e-06)), SignatureData(drug_id=u'HMSL10178', drug=u'OSI930', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'PI3K-BETA': [SignatureData(drug_id=u'HMSL10047', drug=u'GDC0941', status=None, kinomescan=u'300075', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10053', drug=u'ZSTK474', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10059', drug=u'AZD6482', status=None, kinomescan=u'300020', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10146', drug=u'GSK2126458', status=u'investigational', kinomescan=u'300133', rangetested=(8.53e-11, 3.33e-05), signature=(4.35e-09, 5.03e-09, 2.72e-08, 2.44e-08, 7.46e-09, 3.87e-09)), SignatureData(drug_id=u'HMSL10147', drug=u'NVPBKM120', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10148', drug=u'SAR245408', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10171', drug=u'TGX221', status=None, kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(7.96e-06, 3.28e-06, 1.39e-05, 7.09e-06, 1.04e-06, 4.66e-06)), SignatureData(drug_id=u'HMSL10172', drug=u'GSK1059615', status=u'investigational', kinomescan=u'300134', rangetested=(3.41e-10, 0.000133), signature=(1.58e-07, 1.46e-07, 5.27e-07, 7.73e-07, 1.76e-07, 1.51e-07)), SignatureData(drug_id=u'HMSL10173', drug=u'SAR245409', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'PI3K-DELTA': [SignatureData(drug_id=u'HMSL10047', drug=u'GDC0941', status=None, kinomescan=u'300075', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10059', drug=u'AZD6482', status=None, kinomescan=u'300020', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10146', drug=u'GSK2126458', status=u'investigational', kinomescan=u'300133', rangetested=(8.53e-11, 3.33e-05), signature=(4.35e-09, 5.03e-09, 2.72e-08, 2.44e-08, 7.46e-09, 3.87e-09)), SignatureData(drug_id=u'HMSL10147', drug=u'NVPBKM120', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10148', drug=u'SAR245408', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10172', drug=u'GSK1059615', status=u'investigational', kinomescan=u'300134', rangetested=(3.41e-10, 0.000133), signature=(1.58e-07, 1.46e-07, 5.27e-07, 7.73e-07, 1.76e-07, 1.51e-07)), SignatureData(drug_id=u'HMSL10173', drug=u'SAR245409', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10204', drug=u'CAL101', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'DDR1': [SignatureData(drug_id=u'HMSL10002', drug=u'ALWII383', status=None, kinomescan=u'300063', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10003', drug=u'ALWII497', status=None, kinomescan=u'300064', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10076', drug=u'QLXI92', status=None, kinomescan=u'300078', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10082', drug=u'WZ4145', status=None, kinomescan=u'300081', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10083', drug=u'WZ7043', status=None, kinomescan=u'300082', rangetested=None, signature=None)],
  u'CHK1': [SignatureData(drug_id=u'HMSL10112', drug=u'PF477736', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10276', drug=u'TCS 2312', status=None, kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(6.15e-07, 1.05e-06, 7.82e-07, 1.16e-07, 2.97e-07, 5.36e-07))],
  u'TPL2': [SignatureData(drug_id=u'HMSL10153', drug=u'KIN001266', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'P38-BETA': [SignatureData(drug_id=u'HMSL10017', drug=u'HG66401', status=None, kinomescan=u'300003', rangetested=None, signature=None)],
  u'VEGFR1': [SignatureData(drug_id=u'HMSL10042', drug=u'MOTESANIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10114', drug=u'PAZOPANIB', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10175', drug=u'SUNITINIB', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(1.66e-05, 5.52e-06, 5.09e-06, 5.71e-06, 2.49e-06, 6.75e-06))],
  u'TIE2': [SignatureData(drug_id=u'HMSL10193', drug=u'TIE2 KINASE INHIBITOR', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'STK39': [SignatureData(drug_id=u'HMSL10090', drug=u'XMD1527', status=None, kinomescan=u'300089', rangetested=None, signature=None)],
  u'CLK2': [SignatureData(drug_id=u'HMSL10084', drug=u'WZ3105', status=None, kinomescan=u'300083', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10090', drug=u'XMD1527', status=None, kinomescan=u'300089', rangetested=None, signature=None)],
  u'TIE1': [SignatureData(drug_id=u'HMSL10082', drug=u'WZ4145', status=None, kinomescan=u'300081', rangetested=None, signature=None)],
  u'LCK': [SignatureData(drug_id=u'HMSL10019', drug=u'JW7241', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10020', drug=u'DASATINIB', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10038', drug=u'WH4023', status=None, kinomescan=u'300018', rangetested=None, signature=None)],
  u'BTK': [SignatureData(drug_id=u'HMSL10075', drug=u'QLX138', status=None, kinomescan=u'300077', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10077', drug=u'QLXII47', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10129', drug=u'PCI32765', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'PDGFRB': [SignatureData(drug_id=u'HMSL10017', drug=u'HG66401', status=None, kinomescan=u'300003', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10118', drug=u'AMUVATINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10151', drug=u'VARGATEF', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10175', drug=u'SUNITINIB', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(1.66e-05, 5.52e-06, 5.09e-06, 5.71e-06, 2.49e-06, 6.75e-06)), SignatureData(drug_id=u'HMSL10177', drug=u'BRIVANIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'ATM': [SignatureData(drug_id=u'HMSL10009', drug=u'CP466722', status=None, kinomescan=u'300010', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10074', drug=u'KU55933', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10155', drug=u'KU60019', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'RET': [SignatureData(drug_id=u'HMSL10017', drug=u'HG66401', status=None, kinomescan=u'300003', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10087', drug=u'XMD1185H', status=None, kinomescan=u'300086', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10091', drug=u'XMD16144', status=None, kinomescan=u'300090', rangetested=None, signature=None)],
  u'FLT4': [SignatureData(drug_id=u'HMSL10087', drug=u'XMD1185H', status=None, kinomescan=u'300086', rangetested=None, signature=None)],
  u'FLT3': [SignatureData(drug_id=u'HMSL10017', drug=u'HG66401', status=None, kinomescan=u'300003', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10037', drug=u'AC220', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10084', drug=u'WZ3105', status=None, kinomescan=u'300083', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10127', drug=u'DOVITINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10175', drug=u'SUNITINIB', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(1.66e-05, 5.52e-06, 5.09e-06, 5.71e-06, 2.49e-06, 6.75e-06)), SignatureData(drug_id=u'HMSL10182', drug=u'LINIFANIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10192', drug=u'KW2449', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10230', drug=u'LESTAURTINIB', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(2.46e-07, 7.33e-07, 5e-07, 8.7e-08, 1.93e-07, 1.01e-06))],
  u'TBK1': [SignatureData(drug_id=u'HMSL10188', drug=u'BX795', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'CSF1R': [SignatureData(drug_id=u'HMSL10017', drug=u'HG66401', status=None, kinomescan=u'300003', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10082', drug=u'WZ4145', status=None, kinomescan=u'300081', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10083', drug=u'WZ7043', status=None, kinomescan=u'300082', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10187', drug=u'KI20227', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10195', drug=u'KIN001269', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'MARK4': [SignatureData(drug_id=u'HMSL10087', drug=u'XMD1185H', status=None, kinomescan=u'300086', rangetested=None, signature=None)],
  u'KDR': [SignatureData(drug_id=u'HMSL10005', drug=u'TIVOZANIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10007', drug=u'AZD8055', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10008', drug=u'SORAFENIB', status=u'approved', kinomescan=u'300002', rangetested=(2.56e-09, 0.001), signature=(6.91e-05, 3.21e-05, 4.59e-05, 8.55e-05, 3.58e-05, 4.48e-05)), SignatureData(drug_id=u'HMSL10151', drug=u'VARGATEF', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10175', drug=u'SUNITINIB', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(1.66e-05, 5.52e-06, 5.09e-06, 5.71e-06, 2.49e-06, 6.75e-06)), SignatureData(drug_id=u'HMSL10177', drug=u'BRIVANIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10178', drug=u'OSI930', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10194', drug=u'CABOZANTINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10198', drug=u'VANDETANIB', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10206', drug=u'RAF 265', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'SRC': [SignatureData(drug_id=u'HMSL10020', drug=u'DASATINIB', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10032', drug=u'SARACATINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10039', drug=u'WH4025', status=None, kinomescan=u'300071', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10091', drug=u'XMD16144', status=None, kinomescan=u'300090', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10189', drug=u'BOSUTINIB', status=u'approved', kinomescan=None, rangetested=(2.56e-10, 0.0001), signature=(1.94e-06, 3.14e-06, 3.75e-06, 8.86e-07, 9.32e-07, 3.92e-06))],
  u'GSK-3': [SignatureData(drug_id=u'HMSL10031', drug=u'KIN001043', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'PI3K': [SignatureData(drug_id=u'HMSL10080', drug=u'TORIN2', status=None, kinomescan=u'300080', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10203', drug=u'A66', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10234', drug=u'GDC0980', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'PARP-2': [SignatureData(drug_id=u'HMSL10144', drug=u'OLAPARIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10145', drug=u'VELIPARIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'IKK-BETA': [SignatureData(drug_id=u'HMSL10028', drug=u'BMS345541', status=None, kinomescan=u'300016', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10136', drug=u'TPCA1', status=None, kinomescan=None, rangetested=(3.41e-10, 0.000133), signature=(6.67e-05, 2.12e-06, 2.86e-06, 3.88e-06, 3.6e-06, 6.67e-05))],
  u'MAST1': [SignatureData(drug_id=u'HMSL10090', drug=u'XMD1527', status=None, kinomescan=u'300089', rangetested=None, signature=None)],
  u'MTOR': [SignatureData(drug_id=u'HMSL10064', drug=u'WYE125132', status=None, kinomescan=u'300110', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10075', drug=u'QLX138', status=None, kinomescan=u'300077', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10079', drug=u'TORIN1', status=None, kinomescan=u'300079', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10080', drug=u'TORIN2', status=None, kinomescan=u'300080', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10172', drug=u'GSK1059615', status=u'investigational', kinomescan=u'300134', rangetested=(3.41e-10, 0.000133), signature=(1.58e-07, 1.46e-07, 5.27e-07, 7.73e-07, 1.76e-07, 1.51e-07)), SignatureData(drug_id=u'HMSL10173', drug=u'SAR245409', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10234', drug=u'GDC0980', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10277', drug=u'TEMSIROLIMUS', status=u'approved', kinomescan=None, rangetested=(3.41e-10, 0.000133), signature=(2.69e-08, 7.98e-07, 5.68e-06, 1.23e-05, 3.26e-07, 5.42e-08))],
  u'LTK': [SignatureData(drug_id=u'HMSL10015', drug=u'HG511301', status=None, kinomescan=u'300065', rangetested=None, signature=None)],
  u'ITK': [SignatureData(drug_id=u'HMSL10043', drug=u'KIN001127', status=None, kinomescan=u'300073', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10137', drug=u'BMS509744', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'MEK': [SignatureData(drug_id=u'HMSL10048', drug=u'CI1040', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10101', drug=u'PD325901', status=u'investigational', kinomescan=u'300111', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10143', drug=u'BMS 777607', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10164', drug=u'ARRY424704', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'CDK': [SignatureData(drug_id=u'HMSL10001', drug=u'SELICICLIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10011', drug=u'FLAVOPIRIDOL', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10158', drug=u'AZD 5438', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'CDK1': [SignatureData(drug_id=u'HMSL10025', drug=u'MLS000911536', status=None, kinomescan=u'300069', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10073', drug=u'PHA793887', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10267', drug=u'NU6102', status=None, kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(1.61e-05, 7.8e-06, 1.36e-05, 9.36e-06, 1.97e-05, 3.09e-05)), SignatureData(drug_id=u'HMSL10273', drug=u'PURVALANOL A', status=None, kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(0.000167, 2.36e-05, 6.68e-05, 0.000167, 0.000167, 6.46e-05))],
  u'CDK2': [SignatureData(drug_id=u'HMSL10073', drug=u'PHA793887', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'CDK4': [SignatureData(drug_id=u'HMSL10071', drug=u'PD0332991', status=u'investigational', kinomescan=u'300026', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10073', drug=u'PHA793887', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10251', drug=u'FASCAPLYSIN', status=None, kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(1.85e-07, 1.47e-08, 3.71e-08, 2.73e-07, 1.25e-07, 2.23e-07))],
  u'CDK5': [SignatureData(drug_id=u'HMSL10073', drug=u'PHA793887', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'CDK7': [SignatureData(drug_id=u'HMSL10073', drug=u'PHA793887', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'CDK9': [SignatureData(drug_id=u'HMSL10004', drug=u'AT7519', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10073', drug=u'PHA793887', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10132', drug=u'BMS387032', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10196', drug=u'KIN001270', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'ALK5': [SignatureData(drug_id=u'HMSL10121', drug=u'SB525334', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10202', drug=u'D 4476', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'ALK2': [SignatureData(drug_id=u'HMSL10115', drug=u'LDN193189', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'C-ABL': [SignatureData(drug_id=u'HMSL10017', drug=u'HG66401', status=None, kinomescan=u'300003', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10023', drug=u'IMATINIB', status=u'approved', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10099', drug=u'NILOTINIB', status=u'approved', kinomescan=None, rangetested=None, signature=None)],
  u'LOK': [SignatureData(drug_id=u'HMSL10015', drug=u'HG511301', status=None, kinomescan=u'300065', rangetested=None, signature=None)],
  u'AURORA': [SignatureData(drug_id=u'HMSL10065', drug=u'KIN001220', status=None, kinomescan=u'300023', rangetested=None, signature=None)],
  u'EGFR': [SignatureData(drug_id=u'HMSL10016', drug=u'HG58801', status=None, kinomescan=u'300066', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10017', drug=u'HG66401', status=None, kinomescan=u'300003', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10051', drug=u'LAPATINIB', status=u'approved', kinomescan=None, rangetested=(4.27e-11, 1.67e-05), signature=(3.96e-07, 1.67e-05, 1.67e-05, 1.67e-05, 3.99e-06, 4.04e-07)), SignatureData(drug_id=u'HMSL10082', drug=u'WZ4145', status=None, kinomescan=u'300081', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10085', drug=u'WZ4002', status=None, kinomescan=u'300084', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10097', drug=u'ERLOTINIB', status=u'approved', kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(1.05e-05, 7.52e-06, 1.79e-05, 6.67e-05, 1.72e-06, 1.58e-05)), SignatureData(drug_id=u'HMSL10098', drug=u'GEFITINIB', status=u'approved', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(7.21e-07, 2.94e-05, 1.08e-05, 1.76e-05, 8.91e-06, 2.76e-06)), SignatureData(drug_id=u'HMSL10120', drug=u'CANERTINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10133', drug=u'AFATINIB', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(5.85e-09, None, 1.74e-06, 1.82e-06, 4.65e-07, 1.32e-08)), SignatureData(drug_id=u'HMSL10159', drug=u'PELITINIB', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10223', drug=u'TYRPHOSTIN', status=None, kinomescan=u'300135', rangetested=(4.27e-10, 0.000167), signature=(6.7e-07, 0.000167, 0.000167, 0.000125, 6.19e-05, 3.99e-06))],
  u'RIPK1': [SignatureData(drug_id=u'HMSL10088', drug=u'XMD132', status=None, kinomescan=u'300087', rangetested=None, signature=None)],
  u'ROCK2': [SignatureData(drug_id=u'HMSL10012', drug=u'GSK429286A', status=None, kinomescan=u'300012', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10149', drug=u'Y39983', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10253', drug=u'GLYCYLH1152', status=None, kinomescan=None, rangetested=(1.71e-10, 6.67e-05), signature=(6.67e-05, 6.07e-07, 6.67e-05, 1.09e-06, 9.15e-07, 4.64e-05))],
  u'HSP90 ALPHA': [SignatureData(drug_id=u'HMSL10108', drug=u'GELDANAMYCIN', status=None, kinomescan=None, rangetested=(2.56e-10, 0.0001), signature=(1.44e-08, 1.57e-08, 2.84e-08, 2.75e-08, 8.06e-08, 1.62e-08)), SignatureData(drug_id=u'HMSL10161', drug=u'NVPAUY922', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10236', drug=u'17AAG', status=None, kinomescan=None, rangetested=(2.56e-10, 0.0001), signature=(1.46e-06, 5.13e-06, 4.12e-09, 5.71e-08, 2.39e-07, 2.85e-08))],
  u'ADCK4': [SignatureData(drug_id=u'HMSL10016', drug=u'HG58801', status=None, kinomescan=u'300066', rangetested=None, signature=None)],
  u'B-RAF': [SignatureData(drug_id=u'HMSL10008', drug=u'SORAFENIB', status=u'approved', kinomescan=u'300002', rangetested=(2.56e-09, 0.001), signature=(6.91e-05, 3.21e-05, 4.59e-05, 8.55e-05, 3.58e-05, 4.48e-05)), SignatureData(drug_id=u'HMSL10017', drug=u'HG66401', status=None, kinomescan=u'300003', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10046', drug=u'SB590885', status=None, kinomescan=u'300005', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10068', drug=u'R7204', status=u'approved', kinomescan=u'300008', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10181', drug=u'GDC0879', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10262', drug=u'L779450', status=None, kinomescan=None, rangetested=(1.28e-10, 5e-05), signature=(1.62e-05, 8.55e-06, 1.07e-05, 1.71e-05, 3.21e-05, 2.21e-05))],
  u'MEK2': [SignatureData(drug_id=u'HMSL10056', drug=u'SELUMETINIB', status=u'investigational', kinomescan=None, rangetested=(1.28e-10, 5e-05), signature=(5e-05, 5e-05, 5e-05, 5e-05, 1.79e-06, 5e-05)), SignatureData(drug_id=u'HMSL10142', drug=u'GSK1120212', status=u'investigational', kinomescan=None, rangetested=(4.27e-11, 1.67e-05), signature=(1.67e-05, 1.67e-05, 1.67e-05, 1.67e-05, 6.57e-09, 1.67e-05)), SignatureData(drug_id=u'HMSL10271', drug=u'PD 98059', status=None, kinomescan=None, rangetested=(2.56e-10, 0.0001), signature=(2.62e-05, 4.04e-06, 0.0001, 5.14e-05, 5e-05, 1.85e-05))],
  u'MEK1': [SignatureData(drug_id=u'HMSL10056', drug=u'SELUMETINIB', status=u'investigational', kinomescan=None, rangetested=(1.28e-10, 5e-05), signature=(5e-05, 5e-05, 5e-05, 5e-05, 1.79e-06, 5e-05)), SignatureData(drug_id=u'HMSL10142', drug=u'GSK1120212', status=u'investigational', kinomescan=None, rangetested=(4.27e-11, 1.67e-05), signature=(1.67e-05, 1.67e-05, 1.67e-05, 1.67e-05, 6.57e-09, 1.67e-05)), SignatureData(drug_id=u'HMSL10271', drug=u'PD 98059', status=None, kinomescan=None, rangetested=(2.56e-10, 0.0001), signature=(2.62e-05, 4.04e-06, 0.0001, 5.14e-05, 5e-05, 1.85e-05))],
  u'AURKA': [SignatureData(drug_id=u'HMSL10021', drug=u'TOZASERTIB', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(1.44e-05, 1.28e-07, 7.83e-06, 1.8e-07, 2.52e-06, 3.33e-05)), SignatureData(drug_id=u'HMSL10066', drug=u'MLN8054', status=None, kinomescan=u'300024', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10091', drug=u'XMD16144', status=None, kinomescan=u'300090', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10092', drug=u'JWE035', status=None, kinomescan=u'300028', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10096', drug=u'ZM447439', status=None, kinomescan=u'300029', rangetested=None, signature=None)],
  u'AURKB': [SignatureData(drug_id=u'HMSL10021', drug=u'TOZASERTIB', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(1.44e-05, 1.28e-07, 7.83e-06, 1.8e-07, 2.52e-06, 3.33e-05)), SignatureData(drug_id=u'HMSL10062', drug=u'GSK1070916', status=None, kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(6.33e-06, 1.13e-08, 2.04e-06, 2.97e-07, 2.63e-07, 5.14e-06)), SignatureData(drug_id=u'HMSL10067', drug=u'BARASERTIB', status=u'investigational', kinomescan=u'300025', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10091', drug=u'XMD16144', status=None, kinomescan=u'300090', rangetested=None, signature=None)],
  u'AURKC': [SignatureData(drug_id=u'HMSL10021', drug=u'TOZASERTIB', status=u'investigational', kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(1.44e-05, 1.28e-07, 7.83e-06, 1.8e-07, 2.52e-06, 3.33e-05)), SignatureData(drug_id=u'HMSL10062', drug=u'GSK1070916', status=None, kinomescan=None, rangetested=(8.53e-11, 3.33e-05), signature=(6.33e-06, 1.13e-08, 2.04e-06, 2.97e-07, 2.63e-07, 5.14e-06))],
  u'HSP90 BETA': [SignatureData(drug_id=u'HMSL10161', drug=u'NVPAUY922', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'P53': [SignatureData(drug_id=u'HMSL10170', drug=u'JNJ 26854165', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
  u'ULK1': [SignatureData(drug_id=u'HMSL10084', drug=u'WZ3105', status=None, kinomescan=u'300083', rangetested=None, signature=None)],
  u'PRKCD': [SignatureData(drug_id=u'HMSL10087', drug=u'XMD1185H', status=None, kinomescan=u'300086', rangetested=None, signature=None)],
  u'ERK1': [SignatureData(drug_id=u'HMSL10110', drug=u'FR180204', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'ERK2': [SignatureData(drug_id=u'HMSL10110', drug=u'FR180204', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'AMPK-ALPHA1': [SignatureData(drug_id=u'HMSL10174', drug=u'A 769662', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'ERK5': [SignatureData(drug_id=u'HMSL10086', drug=u'LRRK2IN1', status=None, kinomescan=u'300085', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10093', drug=u'XMD885', status=None, kinomescan=u'300091', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10094', drug=u'XMD892', status=None, kinomescan=u'300092', rangetested=None, signature=None)],
  u'MTORC2': [SignatureData(drug_id=u'HMSL10007', drug=u'AZD8055', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10052', drug=u'SIROLIMUS', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(2.42e-08, 1.65e-08, 5.16e-08, 4.91e-08, 1.2e-07, 8.12e-09)), SignatureData(drug_id=u'HMSL10063', drug=u'OSI027', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10146', drug=u'GSK2126458', status=u'investigational', kinomescan=u'300133', rangetested=(8.53e-11, 3.33e-05), signature=(4.35e-09, 5.03e-09, 2.72e-08, 2.44e-08, 7.46e-09, 3.87e-09)), SignatureData(drug_id=u'HMSL10235', drug=u'RAD001', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'MTORC1': [SignatureData(drug_id=u'HMSL10007', drug=u'AZD8055', status=u'investigational', kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10052', drug=u'SIROLIMUS', status=u'approved', kinomescan=None, rangetested=(4.27e-10, 0.000167), signature=(2.42e-08, 1.65e-08, 5.16e-08, 4.91e-08, 1.2e-07, 8.12e-09)), SignatureData(drug_id=u'HMSL10063', drug=u'OSI027', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10146', drug=u'GSK2126458', status=u'investigational', kinomescan=u'300133', rangetested=(8.53e-11, 3.33e-05), signature=(4.35e-09, 5.03e-09, 2.72e-08, 2.44e-08, 7.46e-09, 3.87e-09)), SignatureData(drug_id=u'HMSL10235', drug=u'RAD001', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'PDK1': [SignatureData(drug_id=u'HMSL10055', drug=u'BX912', status=None, kinomescan=u'300019', rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10081', drug=u'KIN001244', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'P38 MAPK': [SignatureData(drug_id=u'HMSL10036', drug=u'SB 239063', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10167', drug=u'SB 203580', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10168', drug=u'VX745', status=None, kinomescan=None, rangetested=None, signature=None), SignatureData(drug_id=u'HMSL10169', drug=u'BIRB 796', status=None, kinomescan=None, rangetested=None, signature=None)],
  u'BCL2': [SignatureData(drug_id=u'HMSL10179', drug=u'ABT737', status=u'investigational', kinomescan=None, rangetested=None, signature=None)],
}
