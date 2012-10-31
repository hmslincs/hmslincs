# -*- coding: utf-8 -*-
import re
# ---------------------------------------------------------------------------
import setparams as _sg
_params = dict(
    VERBOSE = False,
    ENCODING = u'utf8',
    MOLDATAKEY = u'moldata',
    COMMENTKEY = u'comment',
    COMMENTTAG = u'comment',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------
def parse_mol(data, _delimre=re.compile(ur'((?<=\n)> <[^>]+>[^\S\n]*\n)')):
    parts = _delimre.split(data)
    yield (MOLDATAKEY, parts.pop(0))
    comments = {}
    last_comment = None
    for tag, val in zip(*[iter(parts)] * 2):
        key = tag[tag.find(u'<')+1:tag.rfind(u'>')]
        v = val.strip()
        if key == COMMENTKEY:
            last_comment = v
            continue

        if last_comment is not None:
            comments[key] = last_comment
            last_comment = None
        yield key, v

    assert last_comment is None

    yield (COMMENTTAG, comments if comments else None)

def first_nonempty_line(preamble):
    for txt in [line.strip() for line in preamble.splitlines()]:
        if len(txt):
            return txt

def parse_sdf(data, _delimre=re.compile(ur'(?<=\n)\$\$\$\$\n')):
    """
    for mol_record in sdf2py.parse_sdf(sdf_data_as_a_string):
        preamble = mol_record.pop(MOLDATAKEY)
        title = first_nonempty_line(preamble) or 'WARNING: NO TITLE FOUND'
        print title
        for tag, value in mol_record.items():
            print (u'%s: %s' % (tag, value)).encode(ENCODING)
        print
    """
    mols = _delimre.split(data.strip(u'\n').strip(u'$'))
    return tuple(dict(parse_mol(mol)) for mol in mols)

if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        print '%s:' % p
        with open(p) as fh:
            data = fh.read().decode(ENCODING)

        for mol_record in parse_sdf(data):
            preamble = mol_record.pop(MOLDATAKEY)
            title = first_nonempty_line(preamble) or 'WARNING: NO TITLE FOUND'
            print title
            for tag, value in mol_record.items():
                print (u'%s: %s' % (tag, value)).encode(ENCODING)
            print
