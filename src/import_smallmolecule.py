import sys
import argparse
import sdf2py as s2p
import re
import typecheck
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from db.models import SmallMolecule

__version__ = "$Revision: 24d02504e664 $"
# $Source$

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    APPNAME = 'db',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

DEFAULT_ENCODING = 'utf8'

logger = logging.getLogger(__name__)

def main(path):
    """
    Read in the sdf file
    """
    # map field labels to model fields
    properties = ('model_field','required','default','converter')
    labels = { s2p.MOLDATAKEY:('molfile',True),
               'smiles': ('smiles',True),
               'facility_reagent_id': ('facility_id',True,None, lambda x: util.convertdata(x[x.index('HMSL')+4:],int)),
               'vendor': ('provider',True),
               'salt_form_id': ('salt_id',True),
               'facility_batch_id':('facility_batch_id',True),
               'vendor_reagent_id':'provider_catalog_id',
               'chemical_name':('name',True),
               'pubchem_cid':'pubchem_cid',
               'molecular_formula':'molecular_formula',
               'molecular_mass':'molecular_mass',
               'vendor_batch_id':'provider_sample_id',
               'inchi':'inchi',
               'chembl':'chembl_id',
               'concentration':'concentration',
               'well_type':('well_type',False,'experimental'),
               'is_restricted':('is_restricted',False,False)}
    # convert the labels to fleshed out dict's, with strategies for optional, default and converter
    labels = util.fill_in_column_definitions(properties,labels)
    
    assert typecheck.isstring(path)
    with open(path) as fh:
        data = fh.read().decode(DEFAULT_ENCODING)

    records = s2p.parse_sdf(data)
    
    count = 0
    for record in records:
        initializer = {}
        for key,properties in labels.items():
            logger.info(str(('look for key: ', key, ', properties: ', properties)))
            required = properties['required']
            default = properties['default']
            converter = properties['converter']
            model_field = properties['model_field']
            
            value = record.get(key)

            # Todo, refactor to a method
            logger.debug(str(('raw value', value)))
            if(converter != None):
                value = converter(value)
            if(value == None ):
                if( default != None ):
                    value = default
            if(value == None and  required == True):
                raise Exception('Field is required: %s, record: %d' % (properties['column_label'],rows))
            logger.info(str(('model_field: ' , model_field, ', value: ', value)))
            initializer[model_field] = value
            
        logger.info(str(('initializer: ', initializer)))
        sm = SmallMolecule(**initializer)
        sm.save()
        count += 1
    print 'small molecule definitions read: ', count
    
    # TODO - integrity checks: no differing smiles between different batches for same facility id
            
parser = argparse.ArgumentParser(description='Import file')
parser.add_argument('-f', action='store', dest='inputFile',
                    metavar='FILE', required=True,
                    help='input file path')
parser.add_argument('-v', '--verbose', dest='verbose', action='count',
                help="Increase verbosity (specify multiple times for more)")    

if __name__ == "__main__":
    args = parser.parse_args()
    if(args.inputFile is None):
        parser.print_help();
        parser.exit(0, "\nMust define the FILE param.\n")

    log_level = logging.WARNING # default
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level, format='%(msecs)d:%(lineno)d:%(levelname)s: %(message)s')        
        
    print 'importing ', args.inputFile
    main(args.inputFile)