import collections as co
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import RegularPolygon
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import MultipleLocator
from django.template import Template, Context
from django.template.loader import render_to_string
import django.conf
import numpy as np
import os
import sys

# ---------------------------------------------------------------------------

FORMAT = 'png'

# ---------------------------------------------------------------------------

SignatureData = co.namedtuple('SignatureData',
                              'drug isclinical isselective isprimary '
                              'signature rangetested')

fig_width = 5.0  # inches
grid_ratios = [3, 0.6, 0.5, 0.4, 10]  # widths of the "columns"
gr_sum = float(sum(grid_ratios))
radius = 0.2  # radius of the cell line triangle markers
mm_radius = radius * 0.4  # radius of the max measured dose triangle markers
mm_y_offset = 0.03  # vertical offset of the mm markers from the line
yscale = 0.55  # vertical scaling of the spacing between lines
dot_radius = fig_width / gr_sum * grid_ratios[2] * 0.4  # selectivity marker
box_size = fig_width / gr_sum * grid_ratios[1]  # clinical marker
ctext_y_offset = 0.01  # clincal marker "C" offset
y_top_padding = box_size / 2  # extra space required above topmost line
data_min = -8  # minimum x-axis value
data_max = -3  # maximum x-axis value
fig_y_scale = 0.65  # scaling for figure height (manually tweaked, derivation unknown)
spine_y_offset = 0.25  # spacing from topmost line to x-axis spine
colors = ('red', 'yellow', 'magenta', 'blue', 'green', 'cyan')  # cell line marker colors

main_template = 'signature.html'

def signature(target_name, primary_compounds, nonprimary_compounds, cell_lines):
    """Render a figure depicting "signatures" for one or more compounds.

    Saves output to a PNG file, whose filename (sans .png extension) is
    specified in the `basename` argument.

    """

    ctx = {
        'target_name': target_name,
        'primary_compounds': primary_compounds,
        'nonprimary_compounds': nonprimary_compounds,
        }
    #out_file = open('signature-%s.html' % target_name, 'w')
    out_file = sys.stdout  # temp
    out_file.write(render_to_string(main_template, ctx))

    """
    num_compounds = len(primary_compounds)

    # set width to fixed value, use arbitrary value for height to be
    # recalculated below
    fig = Figure((fig_width, 1))
    # eliminate all margins
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    # create 1xN grid with no padding
    gs = GridSpec(1, len(grid_ratios), width_ratios=grid_ratios, wspace=0)
    # all subplots will share the same y axis due to the sharey argument
    ax = fig.add_subplot(gs[4])
    ax_name = fig.add_subplot(gs[0], sharey=ax)
    ax_clinical = fig.add_subplot(gs[1], sharey=ax)
    ax_selective = fig.add_subplot(gs[2], sharey=ax)

    # plot the pieces for each drug (reversed so we get top-to-bottom visual
    # ordering as the Y axis on the plots increases bottom-to-top)
    for si, sd in enumerate(reversed(primary_compounds)):
        y = si * yscale  # y coordinate for the line
        my = y - radius  # y coordinate for the cell line markers
        mmy = y + mm_radius + mm_y_offset  # y coordinate for mm marker
        # draw the cell line markers
        for ci, value in enumerate(sd.signature):
            if value is None:
                # don't draw any marker for None values
                x = np.nan
            else:
                # explicit log10 scaling
                x = np.log10(value)
            marker = RegularPolygon([x, my], 3, radius=radius,
                                    facecolor=colors[ci], edgecolor='black')
            ax.add_patch(marker)
        # draw mm marker - also do log10 scaling here
        mmx = np.log10(sd.rangetested[1])
        # orientation of pi radians flips the triangle around to point downward
        max_marker = RegularPolygon([mmx, mmy], 3, radius=mm_radius,
                                    color='black', orientation=np.pi)
        ax.add_patch(max_marker)
        # draw the line
        line = plt.Line2D([data_min, data_max], [y, y], color='black')
        ax.add_line(line)
        # drug name - yaxis_transform has x axis in figure space and y axis in
        # data space which is perfect here
        ax_name.text(0, y, sd.drug, fontsize=14, verticalalignment='center',
                     transform=ax_name.get_yaxis_transform())
        # draw "is clinical" marker
        if sd.isclinical:
            # yaxis_transform didn't seem to produce the x axis positioning I
            # was expecting, so we'll draw in pure data space and adjust the
            # xaxis range below
            box = plt.Rectangle([-box_size / 2, y - box_size / 2],
                                box_size, box_size, color='black')
            # divide by 72 to convert fontsize in points to inches, and again by
            # 2 to get the half-width (should really ask the text renderer for
            # the actual width, but this works well enough as 'C' is squarish)
            ax_clinical.text(-11./72/2, y + ctext_y_offset, 'C', fontsize=11,
                              color='white', verticalalignment='center')
            ax_clinical.add_patch(box)
        # draw "is selective" marker
        if sd.isselective:
            # same x-axis issue as for isclinical above
            circle = plt.Circle([0, y], dot_radius, color='crimson')
            ax_selective.add_patch(circle)

    # adjust the axes to contain the full range of the data plot, plus a little
    # padding on the top
    ax.axis((data_min, data_max, -2 * radius, (num_compounds) * yscale + y_top_padding))
    # draw ticks only on every integer
    ax.xaxis.set_major_locator(MultipleLocator(1.0))
    # ticks only on top with small labels
    ax.xaxis.tick_top()
    ax.xaxis.set_tick_params(labelsize=8)
    # calculate the Y position for the spine (The final -1 is needed here but
    # I'm not sure why. The math works out perfectly other than that. -JLM)
    spine_pos = (num_compounds - 1) * yscale + spine_y_offset - 1
    ax.spines['top'].set_position(('data', spine_pos))

    # scale the "is clinical" and "is selective" subplots so the markers fill
    # their widths
    ax_clinical.set_xlim(-box_size / 2, box_size / 2)
    ax_selective.set_xlim(-dot_radius, dot_radius)

    # finally set the figure height in inches based on the data range of the
    # plot's y axis, so the final output has the right scale and aspect ratio
    bounds = ax.axis()
    # I'm still not clear on why this fig_y_scale factor is necessary or how it
    # should be derived. -JLM
    fig.set_figheight((bounds[3] - bounds[2]) * fig_y_scale)

    # set all subplots to have equal aspect ratios and no yticks
    plt.setp(fig.axes, 'aspect', 'equal', 'yticks', [])
    # tweak some other visual elements
    for a in fig.axes:
        # disable xticks for non-data subplots
        if a is not ax:
            a.set_xticks([])
        # hide all spines (the plot borders where the ticks usually sit)
        plt.setp(a.spines.values(), 'visible', False)

    # render to png
    canvas = FigureCanvasAgg(fig)
    # 72 dpi produces perfect 1-pixel lines for 1-pt figure lines
    canvas.print_figure('%s.png' % basename, dpi=72)
    """


if __name__ == '__main__':
    if not django.conf.settings.configured:
        django.conf.settings.configure(
            TEMPLATE_LOADERS=(
                'django.template.loaders.filesystem.Loader',
                ),
            TEMPLATE_DIRS=(
                os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
                ),
            TEMPLATE_DEBUG=True,
            )

    target_name = 'EGFR'

    primary_compounds = (SignatureData(drug='Neratinib',
                                       isclinical=True, isselective=False,
                                       isprimary=True,
                                       signature=(5.41E-07, 1.07E-06, 5.72E-05,
                                                  1.79E-05, 1.67E-05, 2.89E-07),
                                       rangetested=6.67E-05),
                         SignatureData(drug='GSK-XXXX',
                                       isclinical=True, isselective=True,
                                       isprimary=True,
                                       signature=(6.72E-07, 6.73E-07, 1.17E-05,
                                                  1.08E-05, 6.48E-06, 6.97E-07),
                                       rangetested=3.33E-05),
                         SignatureData(drug='BMS-YYY',
                                       isclinical=False, isselective=True,
                                       isprimary=True,
                                       signature=(6.92E-08, 2.23E-07, 1.67E-04,
                                                  1.67E-04, 5.52E-06, 2.03E-07),
                                       rangetested=1.67E-04))

    nonprimary_compounds = (SignatureData(drug='WD40',
                                          isclinical=False, isselective=True,
                                          isprimary=False,
                                          signature=(None, 6.96E-05, 5.19E-05,
                                                     3.23E-06, 1.67E-04, 1.67E-04),
                                          rangetested=1.67E-04),
                            SignatureData('H', False, False, False,
                                          (7.20E-06, 7.20E-06, 7.20E-06, 7.20E-06,
                                           7.20E-06, None), 7.2E-06))

    cell_lines = 'MCF12A MCF10A HCC1143 HCC1428 HCC1569 MCF10F'.split()

    #signature(target_name, primary_compounds, nonprimary_compounds, cell_lines)
    signature(target_name, primary_compounds, None, cell_lines, 'primary')
    signature(target_name, nonprimary_compounds, None, cell_lines, 'nonprimary')

    CELL_LINES = u'MCF12A HCC1569 BT474 HCC1419 600MPE ZR751'.split()

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
 u'pyrimidine animetabolite': [SignatureData(drug=u'Gemcitabine', isclinical=True, isselective=True, isprimary=True, signature=(6.69e-08, 1.75e-07, 1.31e-05, 1.54e-05, 2.3e-08, 3.55e-08), rangetested=None)],
 u'thymidylate synthase': [SignatureData(drug=u'5-FU', isclinical=True, isselective=True, isprimary=True, signature=(1.52e-05, 0.000109, 0.000177, 0.00017, 7.68e-05, 3e-05), rangetested=(4.92e-08, 0.0192))]}
