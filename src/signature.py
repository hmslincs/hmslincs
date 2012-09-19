import collections as co
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ---------------------------------------------------------------------------

FORMAT = 'png'

# ---------------------------------------------------------------------------

SignatureData = co.namedtuple('SignatureData',
                              'name isclinical isselective signature maxtested')

size = 12
colors = ('red', 'yellow', 'magenta', 'blue', 'green', 'cyan')
vshift = 0.1

# the function below is currently only a placeholder for the real thing
def signature(target_name, primary_compounds, nonprimary_compounds, cell_lines):
    num_compounds = len(primary_compounds)
    baseline = np.zeros_like(primary_compounds[0].signature) + vshift
    for i, sd in enumerate(primary_compounds):
        plt.scatter(np.log10(sd.signature), baseline + i, marker='^', c=colors, s=size**2)
    plt.yticks(range(num_compounds))
    plt.ylim(num_compounds - vshift * 5, 0 - vshift)
    ticklabels = [sd.name for sd in primary_compounds]
    plt.gca().xaxis.set_major_locator(mticker.MultipleLocator(1.0))
    plt.gca().xaxis.set_label_position('top')
    plt.gca().yaxis.set_ticklabels(ticklabels)
    plt.gca().yaxis.grid(True, 'major', linestyle='-')
    plt.gca().tick_params(labeltop=True, labelbottom=False, left=False, right=False)
    plt.gca().set_aspect(0.8 / num_compounds)
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
