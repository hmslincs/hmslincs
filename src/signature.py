import collections as co
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import RegularPolygon
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import MultipleLocator
import numpy as np

# ---------------------------------------------------------------------------

FORMAT = 'png'

# ---------------------------------------------------------------------------

SignatureData = co.namedtuple('SignatureData',
                              'name isclinical isselective signature maxtested')

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

def signature(target_name, primary_compounds, nonprimary_compounds, cell_lines,
              basename):
    """Render a figure depicting "signatures" for one or more compounds.

    Saves output to a PNG file, whose filename (sans .png extension) is
    specified in the `basename` argument.

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
        mmx = np.log10(sd.maxtested)
        # orientation of pi radians flips the triangle around to point downward
        max_marker = RegularPolygon([mmx, mmy], 3, radius=mm_radius,
                                    color='black', orientation=np.pi)
        ax.add_patch(max_marker)
        # draw the line
        line = plt.Line2D([data_min, data_max], [y, y], color='black')
        ax.add_line(line)
        # drug name - yaxis_transform has x axis in figure space and y axis in
        # data space which is perfect here
        ax_name.text(0, y, sd.name, fontsize=14, verticalalignment='center',
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


if __name__ == '__main__':
    target_name = 'EGFR'

    primary_compounds = (SignatureData(name='Neratinib',
                                       isclinical=True, isselective=False,
                                       signature=(5.41E-07, 1.07E-06, 5.72E-05,
                                                  1.79E-05, 1.67E-05, 2.89E-07),
                                       maxtested=6.67E-05),
                         SignatureData(name='GSK-XXXX',
                                       isclinical=True, isselective=True,
                                       signature=(6.72E-07, 6.73E-07, 1.17E-05,
                                                  1.08E-05, 6.48E-06, 6.97E-07),
                                       maxtested=3.33E-05),
                         SignatureData(name='BMS-YYY',
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

    #signature(target_name, primary_compounds, nonprimary_compounds, cell_lines)
    signature(target_name, primary_compounds, None, cell_lines, 'primary')
    signature(target_name, nonprimary_compounds, None, cell_lines, 'nonprimary')
