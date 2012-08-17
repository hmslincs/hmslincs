import os
_initdir = os.getcwd()
import os.path as op
import sys

_scriptdir = op.abspath(op.dirname(__file__))
_djangodir = op.realpath(op.join(_scriptdir, '../django'))
os.chdir(_djangodir)
sys.path.insert(0, _djangodir)
sys.path.insert(0, _scriptdir)
del _scriptdir, _djangodir

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hmslincs_server.settings")

import re
import platform as pl
import django.db.models as mo
import django.db.models.fields as fl

import sdf2py as s2p

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    APPNAME = 'example',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

def _abspath(path):
    return path if op.isabs(path) else op.join(_initdir, path)

def totype(field):
    if isinstance(field, fl.CharField) or isinstance(field, fl.TextField):
        return unicode
    if isinstance(field, fl.IntegerField):
        return int
    if isinstance(field, fl.AutoField):
        return None

    assert False, '(as yet) unsupported field class: %s (%s)' % (type(field).__name__, type(field))

_MODEL = mo.get_model(APPNAME, 'SmallMolecule')
_LOOKUP = dict(
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
_TYPES = dict(zip(_FNAMES, tuple([totype(f) for f in _FIELDS])))

def map_fields(**kw):
    ret = dict()
    for k, v in kw.items():
        if _LOOKUP.has_key(k):
            if _LOOKUP[k] is None:
                continue
            key = _LOOKUP[k]
        else:
            key = k

        try:
            ret[key] = _TYPES[key](v) if len(v) else None
        except Exception, e:
            # raise
            # print str(e)
            # import traceback as tb
            # tb.print_exc()
            ret[key] = _TYPES[key]()


    return ret


def add_record(**kw):
    mapped_kw=map_fields(**kw)
    record = _MODEL(**mapped_kw)
    try:
        record.save()
    except Exception, e:
        # raise
        print str(e)
        for f in _FIELDS:
            maxlen = getattr(f, 'max_length', None)
            if maxlen is None: continue
            fname = f.name
            if not mapped_kw.has_key(fname): continue
            val = mapped_kw[fname]
            if len(val) <= maxlen: continue
            print '%s: %s (%d %d)' % (fname, val, maxlen, len(str(val)))
            exit(1)

if __name__ == '__main__':
    nargs = len(sys.argv) - 1

    assert nargs == 1

    path = _abspath(sys.argv[1])

    with open(path) as fh:
        data = fh.read()

    for mol_iter in s2p.parse_sdf(data):
        _, molfile = next(mol_iter)
        kw = dict(mol_iter)
        kw['molfile'] = molfile
        add_record(**kw)
