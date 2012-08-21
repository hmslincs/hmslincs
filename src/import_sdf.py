import os
import os.path as op
import sys

import sdf2py as s2p
import init_utils as iu

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    APPNAME = 'example',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

_MODEL = iu.mo.get_model(APPNAME, 'SmallMolecule')
_LOOKUP = dict(
     {
       s2p.MOLDATAKEY: None,
       s2p.COMMENTKEY: None,
     },
     smiles='sm_smiles',
     cell_index=None,
     well=None,
     well_id=None,
     facility_reagent_id='facility_id',
     salt_form_id='sm_salt',
     chemical_name='sm_name',
     inchi='sm_inchi',
     vendor='sm_provider',
     vendor_reagent_id='sm_provider_catalog_id',
     vendor_batch_id='sm_provider_sample_id',
     pubchem_cid='sm_pubchem_cid',
     molecular_mass='sm_molecular_mass',
     molecular_formula='sm_molecular_formula',
)

_FIELDS = _MODEL._meta.fields
_FNAMES = [f.name for f in _FIELDS]
_TYPES = dict(zip(_FNAMES, tuple([iu.totype(f) for f in _FIELDS])))

def map_fields(**kw):
    ret = dict()
    for k, v in kw.items():
        if _LOOKUP.has_key(k):
            if _LOOKUP[k] is None: continue
            key = _LOOKUP[k]
        else:
            key = k

        try:
            ret[key] = _TYPES[key](v) if len(v) else None
        except Exception, e:
            ret[key] = None if v == 'n/a' else _TYPES[key]()

    return ret


def add_record(model, **kw):
    record = model(**kw)
    try:
        record.save()
    except Exception, e:
        # raise
        print str(e)
        for f in _FIELDS:
            maxlen = getattr(f, 'max_length', None)
            if maxlen is None: continue
            fname = f.name
            if not kw.has_key(fname): continue
            val = kw[fname]
            if len(val) <= maxlen: continue
            print '%s: %s (%d %d)' % (fname, val, maxlen, len(str(val)))
            exit(1)

if __name__ == '__main__':
    nargs = len(sys.argv) - 1

    assert nargs == 1

    path = sys.argv[1]

    with open(path) as fh:
        data = fh.read()

    for mol_record in s2p.parse_sdf(data):
        add_record(_MODEL, **map_fields(**mol_record))
