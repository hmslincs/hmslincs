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
                              'drug isclinical isselective isprimary '
                              'signature rangetested')

dpi = 72  # 72 dpi produces perfect 1-pixel lines for 1-pt figure lines
fig_size = (250/dpi, 20/dpi)  # inches
radius = 0.2  # radius of the cell line triangle markers
spine_y_offset = 0.25  # spacing from topmost line to x-axis spine
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
        

def signature_image(target_name, compound, xlimits, target_dir):

    fig = Figure(fig_size)
    ax = fig.add_subplot(111)
    xlimits = np.log10(xlimits)
    xlimits[0] -= 0.2
    xlimits[1] += 0.2
    ax.axis((xlimits[0], xlimits[1], -1, 0))
    #import ipdb; ipdb.set_trace()

    for ci, value in enumerate(compound.signature):
        if value is None:
            # don't draw any marker for None values
            x = np.nan
        else:
            # explicit log10 scaling
            x = np.log10(value)
        ax.scatter(x, -0.5, marker='^', s=150, facecolor=colors[ci], edgecolor='black')
        #marker = RegularPolygon([x, -radius], 3, radius=radius,
        #                        facecolor=colors[ci], edgecolor='black')
        #ax.add_patch(marker)

    # draw the line
    line = plt.Line2D(np.log10(compound.rangetested), [0, 0], color='black')
    ax.add_line(line)

    ax.xaxis.set_major_locator(NullLocator())
    ax.yaxis.set_major_locator(NullLocator())
    # draw ticks only on every integer
    #ax.xaxis.set_major_locator(MultipleLocator(1.0))
    # ticks only on top with small labels
    #ax.xaxis.tick_top()
    #ax.xaxis.set_tick_params(labelsize=8)

    # tweak some other visual elements
    for a in fig.axes:
        # hide all spines (the plot borders where the ticks usually sit)
        plt.setp(a.spines.values(), 'visible', False)
        #plt.setp(a.patch, 'facecolor', 'none', 'edgecolor', 'none')

    # render to png
    filename = op.join(target_dir,
                       '%s-%s.png' % (slugify(target_name), slugify(compound.drug)))
    canvas = FigureCanvasAgg(fig)
    canvas.print_figure(filename, dpi=dpi)


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
                      isclinical=True, isselective=False,
                      isprimary=True,
                      signature=(5.41E-07, 1.07E-06, 5.72E-05,
                                 1.79E-05, 1.67E-05, 2.89E-07),
                      rangetested=(8.53e-11, 6.67E-05)),
        SignatureData(drug='GSK-XXXX',
                      isclinical=True, isselective=True,
                      isprimary=True,
                      signature=(6.72E-07, 6.73E-07, 1.17E-05,
                                 1.08E-05, 6.48E-06, 6.97E-07),
                      rangetested=(1.71e-10, 3.33E-05)),
        SignatureData(drug='BMS-YYY',
                      isclinical=False, isselective=True,
                      isprimary=True,
                      signature=(6.92E-08, 2.23E-07, 1.67E-04,
                                 1.67E-04, 5.52E-06, 2.03E-07),
                      rangetested=(4.3e-08, 1.67E-04)),
        SignatureData(drug='WD40',
                      isclinical=False, isselective=True,
                      isprimary=False,
                      signature=(None, 6.96E-05, 5.19E-05,
                                 3.23E-06, 1.67E-04, 1.67E-04),
                      rangetested=(1.23e-08, 1.67E-04)),
        SignatureData('H', False, False, False,
                      (7.20E-06, 7.20E-06, 7.20E-06, 7.20E-06,
                       7.20E-06, None), (6.54e-10, 7.2E-06)),
        )

    cell_lines = u'MCF12A HCC1569 BT474 HCC1419 600MPE ZR751'.split()

    #print signature(target_name, compounds, cell_lines)
    signature_images(target_name, compounds, '.')

LATEST ={u'AKT': [SignatureData(drug=u'API-2(Tricir)', isclinical=False, isselective=False, isprimary=True, signature=(3.4e-07, 3.33e-05, 6.76e-07, 7.37e-06, 3.68e-06, 3.33e-05), rangetested=(8.53e-11, 3.33e-05))],
 u'AKT1-2': [SignatureData(drug=u'AKT1-2 inhibitor', isclinical=True, isselective=False, isprimary=False, signature=(9.73e-06, 8.5e-06, 8.32e-07, 9.23e-07, 7.03e-06, 7.38e-07), rangetested=(8.53e-11, 3.33e-05))],
 u'Aurora kinase': [SignatureData(drug=u'VX-680', isclinical=True, isselective=True, isprimary=True, signature=(4.64e-07, 2.07e-06, 1.44e-05, 1.56e-05, 8.7e-06, 5.16e-06), rangetested=(8.53e-11, 3.33e-05))],
 u'B-Raf': [SignatureData(drug=u'Rafi IV (L779450)', isclinical=True, isselective=True, isprimary=False, signature=(1.07e-05, 1.68e-05, 1.62e-05, 1.64e-05, 8.57e-06, 2.57e-05), rangetested=(1.28e-10, 5e-05))],
 u'CDC25S': [SignatureData(drug=u'NSC663284', isclinical=False, isselective=True, isprimary=True, signature=(1.74e-06, 4.33e-06, 2.73e-06, 1.9e-06, 4.57e-06, 1.75e-06), rangetested=(4.27e-10, 0.000167))],
 u'CDK': [SignatureData(drug=u'Fascaplysin', isclinical=True, isselective=False, isprimary=False, signature=(3.58e-07, 4.7e-07, 1.85e-07, 2.62e-07, 2.85e-07, 3.54e-07), rangetested=(8.53e-11, 3.33e-05))],
 u'CDK1': [SignatureData(drug=u'Purvalanol A', isclinical=False, isselective=True, isprimary=False, signature=(7.04e-05, 2e-05, 0.000167, 0.000167, 7.1e-05, 0.000167), rangetested=(4.27e-10, 0.000167))],
 u'CDK1/CCNB': [SignatureData(drug=u'NU6102', isclinical=True, isselective=False, isprimary=False, signature=(1.57e-05, 1.61e-05, 1.61e-05, 2.88e-05, None, 1.53e-05), rangetested=(1.71e-10, 6.67e-05))],
 u'CHK1': [SignatureData(drug=u'TCS2312 dihydrochloride', isclinical=True, isselective=True, isprimary=False, signature=(6.91e-07, 4.9e-07, 6.15e-07, 1.08e-06, 1.12e-06, 7.13e-07), rangetested=(8.53e-11, 3.33e-05))],
 u'DHFR': [SignatureData(drug=u'Methotrexate', isclinical=False, isselective=False, isprimary=False, signature=(5.97e-06, 0.000333, 0.000333, 5.7e-08, 4.09e-06, 4.91e-08), rangetested=(8.53e-10, 0.000333))],
 u'DNA': [SignatureData(drug=u'5-FdUR', isclinical=False, isselective=True, isprimary=True, signature=(1.38e-05, 0.000418, 0.000422, 0.00186, 1.56e-06, 2.79e-06), rangetested=(1.28e-08, 0.005))],
 u'DNA cross-linker': [SignatureData(drug=u'Carboplatin', isclinical=False, isselective=True, isprimary=False, signature=(8.89e-05, 0.000109, 0.000106, 9.46e-05, 0.000152, 8.02e-05), rangetested=(3.45e-09, 0.00135)),
                       SignatureData(drug=u'Cisplatin', isclinical=False, isselective=True, isprimary=True, signature=(6.61e-05, 7.83e-06, 3.78e-05, 1.24e-05, 4.66e-05, 1.02e-05), rangetested=(1.28e-09, 0.0005)),
                       SignatureData(drug=u'Oxaliplatin', isclinical=False, isselective=True, isprimary=False, signature=(1.77e-06, 4.42e-06, 1.86e-05, 1.79e-05, 1.29e-05, 2.44e-06), rangetested=(1.61e-09, 0.000629))],
 u'DNA synthesis/repair': [SignatureData(drug=u'Pemetrexed', isclinical=False, isselective=True, isprimary=False, signature=(1.91e-07, 0.00292, 0.00292, 0.00292, 0.00292, 8.88e-06), rangetested=(7.49e-09, 0.00292))],
 u'EGFR': [SignatureData(drug=u'AG1478', isclinical=True, isselective=False, isprimary=False, signature=(6.92e-08, 5.52e-06, 6.7e-07, 1.21e-06, 7.84e-05, 0.000167), rangetested=(4.27e-10, 0.000167)),
           SignatureData(drug=u'Erlotinib', isclinical=True, isselective=True, isprimary=True, signature=(5.41e-07, 1.67e-05, 1.05e-05, 6.24e-06, 5.03e-05, 6.67e-05), rangetested=(1.71e-10, 6.67e-05)),
           SignatureData(drug=u'Iressa', isclinical=True, isselective=False, isprimary=False, signature=(6.72e-07, 6.48e-06, 7.21e-07, 3.16e-06, 6.13e-06, 3.33e-05), rangetested=(8.53e-11, 3.33e-05))],
 u'EGFR/ERBB2': [SignatureData(drug=u'BIBW2992', isclinical=True, isselective=False, isprimary=True, signature=(8.69e-08, 2.76e-07, 5.85e-09, 2.98e-09, 2.33e-06, 2.32e-06), rangetested=(8.53e-11, 3.33e-05))],
 u'ESR1': [SignatureData(drug=u'Tamoxifen', isclinical=False, isselective=False, isprimary=True, signature=(1.28e-05, 0.000167, 2.39e-06, 0.000167, 4.48e-05, 0.000167), rangetested=(4.27e-10, 0.000167))],
 u'FGFR3': [SignatureData(drug=u'PD173074', isclinical=True, isselective=False, isprimary=True, signature=(2.18e-05, 6.14e-06, 8.48e-06, 7.02e-06, 9.76e-06, 1.51e-05), rangetested=(8.53e-11, 3.33e-05))],
 u'FLT-3': [SignatureData(drug=u'Lestaurtinib(CEP-701)', isclinical=False, isselective=True, isprimary=False, signature=(4.64e-07, 6.48e-07, 2.46e-07, 1.14e-06, 1.69e-06, 1.77e-06), rangetested=(8.53e-11, 3.33e-05))],
 u'FPPS (20 nM)': [SignatureData(drug=u'Ibandronate sodium salt', isclinical=True, isselective=True, isprimary=True, signature=(0.000187, 6.19e-05, 0.000104, 7.65e-06, 0.000216, 6.97e-05), rangetested=(3.84e-09, 0.0015))],
 u'HDAC': [SignatureData(drug=u'LBH589', isclinical=False, isselective=True, isprimary=True, signature=(4.46e-07, 1.55e-07, 3.5e-08, 5.83e-08, 1.89e-07, 1.58e-07), rangetested=(8.53e-11, 3.33e-05)),
           SignatureData(drug=u'Oxamflatin', isclinical=True, isselective=True, isprimary=False, signature=(1.74e-06, 1.32e-06, 2.71e-07, 1.31e-06, 2.98e-06, 2.23e-06), rangetested=(1.71e-10, 6.67e-05))],
 u'Histone deacetylase': [SignatureData(drug=u'SAHA (Vorinostat)', isclinical=False, isselective=True, isprimary=True, signature=(0.000171, 0.000104, 5.31e-05, 5.33e-05, 6.67e-05, 0.000168), rangetested=(4.8e-08, 0.0187)),
                          SignatureData(drug=u'Trichostatin A', isclinical=True, isselective=True, isprimary=True, signature=(1.97e-05, 8.68e-06, 9.71e-06, 1.27e-05, 6.43e-06, 1.83e-05), rangetested=(1.28e-08, 0.005))],
 u'Hsp90': [SignatureData(drug=u'17-AAG', isclinical=False, isselective=False, isprimary=True, signature=(3.3e-08, 1.43e-07, 1.46e-06, 3.89e-08, 2.26e-07, 1.49e-07), rangetested=(2.56e-10, 0.0001)),
            SignatureData(drug=u'Geldanamycin', isclinical=False, isselective=True, isprimary=False, signature=(1.85e-08, 3.41e-08, 1.44e-08, 3.21e-08, 3.68e-08, 8.67e-08), rangetested=(2.56e-10, 0.0001))],
 u'IGF1R': [SignatureData(drug=u'AG1024', isclinical=True, isselective=False, isprimary=False, signature=(5.66e-06, 3.33e-05, 3.33e-05, 3.33e-05, 3.33e-05, 3.24e-05), rangetested=(8.53e-11, 3.33e-05))],
 u'IKK2 (IkB kinase 2)': [SignatureData(drug=u'TPCA-1', isclinical=True, isselective=True, isprimary=False, signature=(8.3e-06, 3.21e-06, 6.67e-05, 0.000133, 6.67e-05, 3.67e-05), rangetested=(3.41e-10, 0.000133))],
 u'JNK': [SignatureData(drug=u'TCS JNK 5a', isclinical=True, isselective=True, isprimary=False, signature=(1.07e-05, 0.000185, 4.05e-07, 0.0002, 0.000133, 1.24e-05), rangetested=(5.12e-10, 0.0002))],
 u'MEK': [SignatureData(drug=u'AZD6244', isclinical=True, isselective=True, isprimary=True, signature=(2.05e-07, 5e-05, 5e-05, 1.79e-05, 5.8e-07, 1.76e-05), rangetested=(1.28e-10, 5e-05)),
          SignatureData(drug=u'PD98059(LC Labs)', isclinical=True, isselective=False, isprimary=True, signature=(5e-05, 5e-05, 2.62e-05, 0.0001, 5e-05, 5e-05), rangetested=(2.56e-10, 0.0001))],
 u'MMP2': [SignatureData(drug=u'SB-3CT', isclinical=False, isselective=True, isprimary=True, signature=(0.000167, 0.000167, 1.03e-05, 0.000167, 0.0001, 0.000167), rangetested=(4.27e-10, 0.000167))],
 u'MMP9': [SignatureData(drug=u'SB-3CT', isclinical=False, isselective=True, isprimary=True, signature=(0.000167, 0.000167, 1.03e-05, 0.000167, 0.0001, 0.000167), rangetested=(4.27e-10, 0.000167))],
 u'Microtubule  ': [SignatureData(drug=u'Docetaxel', isclinical=False, isselective=True, isprimary=True, signature=(2.57e-09, 7.53e-09, 6.34e-09, 1.59e-08, 2.47e-08, 1.84e-08), rangetested=(2.56e-11, 1e-05)),
                    SignatureData(drug=u'Ixabepilone', isclinical=False, isselective=False, isprimary=False, signature=(7.46e-09, 2.82e-07, 3.8e-09, 1.18e-05, 2.97e-09, 2.1e-07), rangetested=(1.01e-10, 3.94e-05)),
                    SignatureData(drug=u'Paclitaxel', isclinical=False, isselective=True, isprimary=True, signature=(1.07e-08, 1.11e-08, 1.02e-08, 9.06e-08, 3.11e-08, 1.73e-08), rangetested=(8.53e-11, 3.33e-05)),
                    SignatureData(drug=u'Vinorelbine', isclinical=True, isselective=True, isprimary=True, signature=(1.24e-08, 3.83e-07, 4.77e-08, 3.56e-07, 1.07e-06, 4.24e-08), rangetested=(1.19e-10, 4.64e-05))],
 u'PI3K': [SignatureData(drug=u'BEZ235', isclinical=True, isselective=False, isprimary=False, signature=(4.69e-07, 4.66e-07, 2.26e-07, 6.32e-08, 3.33e-05, 1.83e-06), rangetested=(8.53e-11, 3.33e-05))],
 u'PI3K gamma': [SignatureData(drug=u'AS-252424', isclinical=False, isselective=False, isprimary=False, signature=(2.1e-05, 2.9e-05, 3.9e-06, 2.02e-05, 6.4e-06, 6.37e-06), rangetested=(1.71e-10, 6.67e-05))],
 u'PLK1': [SignatureData(drug=u'ICRF-193', isclinical=True, isselective=True, isprimary=True, signature=(1.94e-07, 5e-05, 5e-05, 5e-05, 5e-05, 8.48e-07), rangetested=(1.28e-10, 5e-05))],
 u'ROCK': [SignatureData(drug=u'Glycyl H1152', isclinical=True, isselective=True, isprimary=False, signature=(1.26e-05, 6.16e-06, 6.67e-05, 1.71e-05, 6.67e-05, 1.54e-05), rangetested=(1.71e-10, 6.67e-05))],
 u'Ras-Net (Elk-3)': [SignatureData(drug=u'XRP44X', isclinical=True, isselective=False, isprimary=True, signature=(2.16e-07, 2.52e-05, 2.46e-05, 0.000133, 0.000133, 1.24e-06), rangetested=(3.41e-10, 0.000133))],
 u'Src': [SignatureData(drug=u'SKI-606(Bosutinib)', isclinical=True, isselective=False, isprimary=False, signature=(1.03e-06, 1.74e-06, 1.94e-06, 1.06e-06, 5.4e-06, 1.14e-05), rangetested=(2.56e-10, 0.0001))],
 u'Topoisomerase I': [SignatureData(drug=u'CPT-11(FD)', isclinical=False, isselective=True, isprimary=True, signature=(1.62e-06, 2.41e-05, 2.04e-05, 2.39e-05, 1.97e-05, 3.67e-06), rangetested=(1.89e-10, 7.38e-05)),
                      SignatureData(drug=u'TPT(FD)', isclinical=False, isselective=False, isprimary=True, signature=(2.6e-08, 1.58e-06, 2.53e-06, 3.52e-07, None, 6.93e-08), rangetested=(2.8e-10, 0.000109))],
 u'Topoisomerase II': [SignatureData(drug=u'Doxorubicin(FD)', isclinical=False, isselective=True, isprimary=False, signature=(4.58e-08, 2.59e-06, 3.08e-07, 4.69e-07, 2.03e-07, 1.34e-07), rangetested=(2.21e-10, 8.62e-05)),
                       SignatureData(drug=u'Epirubicin', isclinical=True, isselective=False, isprimary=False, signature=(5.55e-08, 8.64e-07, 6.75e-06, 7.11e-07, None, 2.52e-07), rangetested=(4.41e-10, 0.000172)),
                       SignatureData(drug=u'Etoposide', isclinical=True, isselective=False, isprimary=True, signature=(3.66e-07, 6.31e-05, 2.32e-05, 6.63e-05, 5.53e-06, 2.07e-06), rangetested=(8.53e-10, 0.000333)),
                       SignatureData(drug=u'ICRF-193', isclinical=True, isselective=True, isprimary=True, signature=(1.94e-07, 5e-05, 5e-05, 5e-05, 5e-05, 8.48e-07), rangetested=(1.28e-10, 5e-05))],
 u'TrkA': [SignatureData(drug=u'Lestaurtinib(CEP-701)', isclinical=False, isselective=True, isprimary=False, signature=(4.64e-07, 6.48e-07, 2.46e-07, 1.14e-06, 1.69e-06, 1.77e-06), rangetested=(8.53e-11, 3.33e-05))],
 u'VEGFR ': [SignatureData(drug=u'Sunitinib Malate', isclinical=True, isselective=True, isprimary=False, signature=(6.42e-06, 7.19e-06, 1.66e-05, 1.9e-05, 3.94e-06, 1.33e-05), rangetested=(4.27e-10, 0.000167))],
 u'VGEFR': [SignatureData(drug=u'Sorafenib', isclinical=True, isselective=True, isprimary=True, signature=(2.4e-05, 5.37e-05, 6.91e-05, 0.000101, 4.37e-05, 3.7e-05), rangetested=(2.56e-09, 0.001))],
 u'ZNF217 amplification': [SignatureData(drug=u'API-2(Tricir)', isclinical=False, isselective=False, isprimary=True, signature=(3.4e-07, 3.33e-05, 6.76e-07, 7.37e-06, 3.68e-06, 3.33e-05), rangetested=(8.53e-11, 3.33e-05))],
 u'farnesyl diphosphate synthase': [SignatureData(drug=u'Ibandronate sodium salt', isclinical=True, isselective=True, isprimary=True, signature=(0.000187, 6.19e-05, 0.000104, 7.65e-06, 0.000216, 6.97e-05), rangetested=(3.84e-09, 0.0015))],
 u'mTOR': [SignatureData(drug=u'Rapamycin', isclinical=True, isselective=True, isprimary=True, signature=(8.37e-08, 1.98e-07, 2.42e-08, 4.35e-09, 7.59e-06, None), rangetested=(4.27e-10, 0.000167)),
           SignatureData(drug=u'Temsirolimus(Torisel)', isclinical=False, isselective=False, isprimary=True, signature=(9.26e-06, 3.22e-06, 2.69e-08, 5.31e-08, 1.8e-05, 0.000133), rangetested=(3.41e-10, 0.000133))],
 u'pan inibitor': [SignatureData(drug=u'LBH589', isclinical=False, isselective=True, isprimary=True, signature=(4.46e-07, 1.55e-07, 3.5e-08, 5.83e-08, 1.89e-07, 1.58e-07), rangetested=(8.53e-11, 3.33e-05))],
 u'pyrimidine analog': [SignatureData(drug=u'5-FU', isclinical=True, isselective=True, isprimary=True, signature=(1.52e-05, 0.000109, 0.000177, 0.00017, 7.68e-05, 3e-05), rangetested=(4.92e-08, 0.0192))],
 #u'pyrimidine animetabolite': [SignatureData(drug=u'Gemcitabine', isclinical=True, isselective=True, isprimary=True, signature=(6.69e-08, 1.75e-07, 1.31e-05, 1.54e-05, 2.3e-08, 3.55e-08), rangetested=None)],
 u'thymidylate synthase': [SignatureData(drug=u'5-FU', isclinical=True, isselective=True, isprimary=True, signature=(1.52e-05, 0.000109, 0.000177, 0.00017, 7.68e-05, 3e-05), rangetested=(4.92e-08, 0.0192))]}
