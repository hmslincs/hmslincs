# -*- coding: utf-8 -*-
import re
# ---------------------------------------------------------------------------
# import setparams as _sg
# _params = dict(
#     VERBOSE = False,
#     ENCODING = u'utf8',
# )
# _sg.setparams(_params)
# del _sg, _params

# ---------------------------------------------------------------------------
def parse_mol(data):
    parts = re.split(r'((?<=\n)> <[^>]+>[^\S\n]*\n)', data)
    yield (None, parts.pop(0))
    for tag, val in zip(*[iter(parts)] * 2):
        key = tag[tag.find('<')+1:tag.rfind('>')]
        yield key, val.strip()

def first_nonempty_line(preamble):
    for txt in [line.strip() for line in preamble.splitlines()]:
        if len(txt):
            return txt

def parse_sdf(data):
    """
    for mol_iter in sdf2py.parse_sdf(sdf_data_as_a_string):
        _, preamble = next(mol_iter)
        title = first_nonempty_line(preamble) or 'WARNING: NO TITLE FOUND'
        print title
        for tag, value in mol_iter:
            print '%s: %s' % (tag, value.strip())
        print
    """
    mols = re.split('(?<=\n)\$\$\$\$\n', data.strip('\n').strip('$'))
    return [parse_mol(mol) for mol in mols]

if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        print '%s:' % p
        with open(p) as fh:
            data = fh.read()

        for mol_iter in parse_sdf(data):
            _, preamble = next(mol_iter)
            title = first_nonempty_line(preamble) or 'WARNING: NO TITLE FOUND'
            print title
            for tag, value in mol_iter:
                print '%s: %s' % (tag, value.strip())
            print
