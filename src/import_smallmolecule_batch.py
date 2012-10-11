
import sys
import argparse
import xls2py as x2p
import re
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from db.models import SmallMolecule,SmallMoleculeBatch

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

logger = logging.getLogger(__name__)

def main(path):
    """
    Read in the smallmolecule batch info
    """
    sheet_name = 'sheet 1'
    sheet = iu.readtable([path, sheet_name, 1]) # Note, skipping the header row by default

    properties = ('model_field','required','default','converter')
    date_parser = lambda x : util.convertdata(x,date)
    column_definitions = { 
                          'facility_id': ('facility_id',True,None, lambda x: util.convertdata(x,int)),
                          'salt_id': ('salt_id',True,None, lambda x: util.convertdata(x,int)),
                          'facility_batch_id':('facility_batch_id',True,None, lambda x: util.convertdata(x,int)),
                          'provider': ('provider',True),
                          'provider_catalog_id':'provider_catalog_id',
                          'provider_sample_id':'provider_sample_id',
                          'chemical_synthesis_reference':'chemical_synthesis_reference',
                          'purity':'purity',
                          'purity_method':'purity_method',
                          'aqueous_solubility':'aqueous_solubility',
                          'aqueous_solubility_unit':'aqueous_solubility_unit',    
                          'Date Data Received':('date_data_received',False,None,date_parser),
                          'Date Loaded': ('date_loaded',False,None,date_parser),
                          'Date Publicly Available': ('date_publicly_available',False,None,date_parser),
                          }
    # convert the labels to fleshed out dict's, with strategies for optional, default and converter
    column_definitions = util.fill_in_column_definitions(properties,column_definitions)
    
    # create a dict mapping the column ordinal to the proper column definition dict
    cols = util.find_columns(column_definitions, sheet.labels)
    
    rows = 0    
    logger.info(str(('cols: ' , cols)))
    for row in sheet:
        r = util.make_row(row)
        initializer = {}
        small_molecule_lookup = {'facility_id':None, 'salt_id':None}
        for i,value in enumerate(r):
            if i not in cols: continue
            properties = cols[i]

            logger.debug(str(('read col: ', i, ', ', properties)))
            required = properties['required']
            default = properties['default']
            converter = properties['converter']
            model_field = properties['model_field']

            # Todo, refactor to a method
            logger.debug(str(('raw value', value)))
            if(converter != None):
                value = converter(value)
            if(value == None ):
                if( default != None ):
                    value = default
            if(value == None and  required == True):
                raise Exception('Field is required: %s, record: %d' % (properties['column_label'],rows))
            logger.debug(str(('model_field: ' , model_field, ', value: ', value)))
            
            if(model_field in small_molecule_lookup):
                small_molecule_lookup[model_field]=value
                if( None not in small_molecule_lookup.values()):
                    try:
                        sm = SmallMolecule.objects.get(**small_molecule_lookup)
                        initializer['smallmolecule'] = sm
                    except Exception, e:
                        logger.error(str(('sm facility id not found', value)))
                        raise
            else:
                initializer[model_field] = value
        try:
            logger.debug(str(('initializer: ', initializer)))
            smb = SmallMoleculeBatch(**initializer)
            smb.save()
            logger.info(str(('smb created:', smb)))
            rows += 1
        except Exception, e:
            logger.error(str(( "Invalid smallmolecule batch initializer: ", initializer)))
            raise
        
    print "Rows read: ", rows
    
    

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
    logging.basicConfig(level=log_level, format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')        

    print 'importing ', args.inputFile
    main(args.inputFile)