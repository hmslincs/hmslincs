
import sys
import argparse
import xls2py as x2p
import re
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from db.models import Cell, CellBatch
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

logger = logging.getLogger(__name__)

@transaction.commit_on_success
def main(path):
    """
    Read in the cell batch info
    """
    sheet_name = 'Sheet1'
    start_row = 1
    sheet = iu.readtable([path, sheet_name, start_row]) # Note, skipping the header row by default

    properties = ('model_field','required','default','converter')
    column_definitions = { 
              'Facility ID':('facility_id',True,None, lambda x: x[x.index('HMSL')+4:]),
              'CL_Batch_ID':('batch_id',True,None,lambda x:util.convertdata(x,int)),
              'CL_Provider_Name':'provider_name',
              'CL_Provider_Catalog_ID':'provider_catalog_id',
              'CL_Verification_Profile':'verification_profile',
              'Date Data Received':('date_data_received',False,None,util.date_converter),
              'Date Loaded': ('date_loaded',False,None,util.date_converter),
              'Date Publicly Available': ('date_publicly_available',False,None,util.date_converter),
              'Most Recent Update': ('date_updated',False,None,util.date_converter),
              }
    # convert the labels to fleshed out dict's, with strategies for optional, default and converter
    column_definitions = util.fill_in_column_definitions(properties,column_definitions)
    
    # create a dict mapping the column ordinal to the proper column definition dict
    cols = util.find_columns(column_definitions, sheet.labels)
    
    rows = 0    
    logger.debug(str(('cols: ' , cols)))
    for row in sheet:
        r = util.make_row(row)
        initializer = {}
        for i,value in enumerate(r):
            if i not in cols: continue
            properties = cols[i]

            logger.debug(str(('read col: ', i, ', ', properties)))
            required = properties['required']
            default = properties['default']
            converter = properties['converter']
            model_field = properties['model_field']

            logger.debug(str(('raw value', value)))
            if(converter != None):
                value = converter(value)
            if(value == None ):
                if( default != None ):
                    value = default
            if(value == None and  required == True):
                raise Exception('Field is required: %s, record: %d' % (
                    properties['column_label'],rows))
            logger.debug(str(('model_field: ' , model_field, ', value: ', value)))
            
            if model_field == 'facility_id':
                try:
                    cell = Cell.objects.get(facility_id=value)
                    initializer['cell'] = cell
                except:
                    logger.error(str(("Cell not found", value, 'row',rows+start_row+2)))
                    raise
            else:
                initializer[model_field] = value
        try:
            logger.debug(str(('initializer: ', initializer)))
            cell = CellBatch(**initializer)
            cell.save()
            logger.debug(str(('cell created:', cell)))
            rows += 1
        except Exception, e:
            logger.error(str(( "Invalid CellBatch initializer: ", initializer, 
                'row', rows+start_row+2, e)))
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
