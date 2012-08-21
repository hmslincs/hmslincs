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

class populate_smallmolecule(iu.populate_from_sdf):
    _LOOKUP = dict(
        id=iu.populate.SKIP,
        molfile=s2p.MOLDATAKEY,
        sm_smiles='smiles',
        facility_id='facility_reagent_id',
        sm_provider='vendor',
        sm_salt='salt_form_id',
        sm_provider_catalog_id='vendor_reagent_id',
        sm_name='chemical_name',
        sm_pubchem_cid='pubchem_cid',
        sm_molecular_formula='molecular_formula',
        sm_molecular_mass='molecular_mass',
        sm_provider_sample_id='vendor_batch_id',
        sm_inchi='inchi',
    )

    def mapkey(this, key, _lookup=_LOOKUP):
        # RISKY!!!  this implementation acts as the identity map for
        # those keys not specifically mentioned in the initializer of
        # _LOOKUP above; this is a convenient expedient for the time
        # being, but too risk-prone for permanent use
        return _lookup.setdefault(key, key)

    def convertdata(this, field, value):
        fname = field.name
        if fname == 'JUST_AN_EXAMPLE_FOR_DOCUMENTATION_SLASH_ILLUSTRATION':
            return this.fancyschmancy(value)
        v = iu.populate.MISSINGDATA if value == u'n/a' else value
        return super(populate_smallmolecule, this).convertdata(field, v)



def main(argv=sys.argv[1:]):
    assert len(argv) == 1
    populate_smallmolecule(appname=APPNAME, modelname='SmallMolecule',
                           path=argv[0])

if __name__ == '__main__':
    main()
