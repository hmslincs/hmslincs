
import sys
import argparse
import xls2py as x2p
import re
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from db.models import Ipsc, IpscBatch
from django.db import transaction

__version__ = "$Revision: 24d02504e664 $"

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
    Read in the ipsc cell batch info
    """
    sheet_name = 'Sheet1'
    start_row = 1
    sheet = iu.readtable([path, sheet_name, start_row]) # Note, skipping the header row by default

    properties = ('model_field','required','default','converter')
    column_definitions = { 
        'Facility ID':(
            'facility_id',True,None, lambda x: x[x.index('HMSL')+4:]),
        'IP_Center_Batch_ID':(
            'batch_id',True,None,lambda x:util.convertdata(x,int)),
        'IP_Center_Specific_Code': 'center_specific_code',
        'IP_Provider_Name':'provider_name',
        'IP_Provider_Catalog_ID':'provider_catalog_id',
        'IP_Provider_Batch_ID':'provider_batch_id',
        
        'IP_Source_Information': 'source_information',
        'IP_Date_Received': 'date_received',
        'IP_Quality_Verification':'quality_verification',
        'IP_Culture_Conditions': 'culture_conditions',
        'IP_Passage_Number': (
            'passage_number',False,None,lambda x:util.convertdata(x,int)),
        'IP_Transient_Modification': 'transient_modification',

        'Comments': 'comments',
        'Date Data Received':(
            'date_data_received',False,None,util.date_converter),
        'Date Loaded': ('date_loaded',False,None,util.date_converter),
        'Date Publicly Available': (
            'date_publicly_available',False,None,util.date_converter),
        'Most Recent Update': (
            'date_updated',False,None,util.date_converter),
        }

    column_definitions = util.fill_in_column_definitions(properties,column_definitions)
    cols = util.find_columns(column_definitions, sheet.labels)
    
    rows = 0    
    for row in sheet:
        
        r = util.make_row(row)
        initializer = {}
        
        for i,value in enumerate(r):

            if i not in cols: continue
            properties = cols[i]

            required = properties['required']
            default = properties['default']
            converter = properties['converter']
            model_field = properties['model_field']

            if(converter != None):
                value = converter(value)
            if(value == None ):
                if( default != None ):
                    value = default
            if(value == None and  required == True):
                raise Exception('Field is required: %s, record: %d' % (
                    properties['column_label'],rows))
            
            if model_field == 'facility_id':
                try:
                    cell = Ipsc.objects.get(facility_id=value)
                    initializer['reagent'] = cell
                except:
                    logger.exception(
                        "Ipsc Cell not found: %r, row: %d", value,rows+start_row+1)
                    raise
            else:
                initializer[model_field] = value
        try:
            logger.debug('initializer: %r', initializer)
            cell = IpscBatch(**initializer)
            cell.save()
            logger.debug('ipsc cell batch created: %r', cell)
            rows += 1
        except Exception, e:
            logger.exception(
                "Invalid Ipsc CellBatch initializer: %r, row: %d",
                initializer, rows+start_row+1)
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
