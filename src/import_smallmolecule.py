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
from django.db import transaction

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

@transaction.commit_on_success
def main(path):
    """
    Read in the sdf file
    """
    # map field labels to model fields
    properties = ('model_field','required','default','converter')
    get_primary_name = lambda x: x.split(';')[0].strip()
    get_alternate_names = lambda x: ';'.join([x.strip() for x in x.split(';')[1:]])
    
    labels = { s2p.MOLDATAKEY:('molfile',True),
              # NOTE: even though these db field are not integers, 
              # it is convenient to convert the read in values to INT to make sure they are not interpreted as float values
               'facility_reagent_id': ('facility_id',True,None, lambda x: util.convertdata(x[x.index('HMSL')+4:],int)), 
               'salt_id': ('salt_id',True,None, lambda x: util.convertdata(x,int)),
               'lincs_id':('lincs_id',False), #None,lambda x:util.convertdata(x,int)),
               'chemical_name':('name',True),
               'alternative_names':'alternative_names',
               'pubchem_cid':'pubchem_cid',
               'chembl_id':'chembl_id',
               'chebi_id':'chebi_id',
               'inchi':'inchi',
               'inchi_key':'inchi_key',
               'smiles': ('smiles',True),
               'molecular_mass':('molecular_mass',False,None, lambda x: round(util.convertdata(x, float),2)),
               'molecular_formula':'molecular_formula',
               'software':'software',
               # 'concentration':'concentration',
               #'well_type':('well_type',False,'experimental'),
               'is_restricted':('is_restricted',False,False,util.bool_converter)}
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
            logger.debug(str(('look for key: ', key, ', properties: ', properties)))
            required = properties['required']
            default = properties['default']
            converter = properties['converter']
            model_field = properties['model_field']
            
            value = record.get(key)

            # Todo, refactor to a method
            try:
                logger.debug(str(('raw value', value)))
                if(converter != None):
                    value = converter(value)
                if(value == None ):
                    if( default != None ):
                        value = default
                if(value == 'n/a'): value = None
                if(value == None and  required == True):
                    raise Exception(str(('Field is required: ', key, initializer, 'record:', count)))
                logger.debug(str(('model_field: ' , model_field, ', value: ', value)))
                initializer[model_field] = value
            except Exception, e:
                logger.error(str(('invalid input', e, 'count', count)))
                raise e
        # follows is a kludge, to split up the entered "chemical_name" field, on ';' - TODO: just have two fields that get entered
        if(initializer['name']):
            initializer['alternative_names']=get_alternate_names(initializer['name'])
            initializer['name']=get_primary_name(initializer['name'])
                
        if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('initializer: ', initializer)))
        try:
            sm = SmallMolecule(**initializer)
            sm.save()
            logger.info(str(('sm created:', sm)))
            count += 1
        except Exception, e:
            logger.error(str(('save failed for: ', initializer, 'error',e, 'count: ', count)))
            raise e
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
    # NOTE this doesn't work because the config is being set by the included settings.py, and you can only set the config once
    logging.basicConfig(level=log_level, format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')        
    logger.setLevel(log_level)
        
    print 'importing ', args.inputFile
    main(args.inputFile)
