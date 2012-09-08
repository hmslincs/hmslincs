import collections as co

# ---------------------------------------------------------------------------

FORMAT = 'png'

# ---------------------------------------------------------------------------

SignatureData = co.namedtuple('SignatureData',
                              'name isclinical isselective signature maxtested')

# the function below is currently only a placeholder for the real thing
def signature(target_name, primary_compounds, nonprimary_compounds, cell_lines):
    # see example below for what the various arguments are expected to
    # be
    return locals()


if __name__ == '__main__':
    target_name = 'EGFR'

    primary_compounds(SignatureData(name='Erlotinib',
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

    nonprimary_compounds(SignatureData(name='WD40',
                                       isclinical=False, isselective=True,
                                       signature=(None, 6.96E-05, 5.19E-05,
                                                  3.23E-06, 1.67E-04, 1.67E-04),
                                       maxtested=1.67E-04),
                         SignatureData('H', False, False,
                                       (7.20E-06, 7.20E-06, 7.20E-06, 7.20E-06,
                                        7.20E-06, None), 7.2E-06))

    cell_lines = 'MCF12A MCF10A HCC1143 HCC1428 HCC1569 MCF10F'.split()

    import sys
    sys.stdout.write(signature(target_name, primary_compounds, nonprimary_compounds,
                               cell_lines))
