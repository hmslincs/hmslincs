print "THIS SCRIPT IS NOT YET USABLE."
exit(1)
"""
There's practically no data for this!
"""

import sys
import os
import os.path as op
import re

import shell_utils as su
import signature as si

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    OUTPUTDIR = re.sub(r'(^|/)do_', r'\1',
                       op.join(os.getcwd(),
                               op.splitext(op.basename(sys.argv[0]))[0])),
    OUTPUTEXT = '.%s' % si.FORMAT.lower(),
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

def write_signature(output, ):
    # calls si.signature
    # outputs a signature to output
    with open(output, 'w') as outfh:
        fig = si.signature(target_name, primary_compounds,
                           nonprimary_compounds, cell_lines)
        outfh.write(fig)

def normalize(target, _nre=re.compile(r'[/\s]')):
    # returns a string
    return _nre.sub('_', target.lower())

def outpath(target):
    # returns a filepath
    return op.join(OUTPUTDIR, '%s%s' % (normalize(target), OUTPUTEXT))

def process(inputline, _splitre=re.compile('\t')):
    # returns a pair
    parts = tuple(_splitre.split(inputline))
    return parts[0], parts

def readinput(path):
    # returns an iterable
    for line in open(path):
        yield process(line.rstrip())

def main(argv=sys.argv[1:]):
    assert len(argv) == 1

    su.mkdirp(OUTPUTDIR)

    for target, spec in readinput(argv[0]):
        output = outpath(target)
        write_signature(output, rows, marker_labels, lims=None)


if __name__ == '__main__':
    main()
