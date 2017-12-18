
import sys
import argparse
import xls2py as x2p
import re
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

__version__ = "$Revision: 24d02504e664 $"
# $Source$

# ---------------------------------------------------------------------------

import setparams as _sg
from db.models import OtherReagent, OtherReagentBatch
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
    sheet_name = 'sheet 1'
    start_row = 1
    sheet = iu.readtable([path, sheet_name, start_row])

    properties = ('model_field','required','default','converter')
    column_definitions = { 
        'facility_id': (
            'facility_id',True,None, lambda x: util.convertdata(x,int)),
        'facility_batch_id':(
            'batch_id',True,None, lambda x: util.convertdata(x,int)),
        'provider': ('provider_name',False),
        'provider_catalog_id':'provider_catalog_id',
        'provider_sample_id':'provider_batch_id',
        
        'Comments': 'comments',
        'Date Data Received':(
            'date_data_received',False,None,util.date_converter),
        'Date Loaded': ('date_loaded',False,None,util.date_converter),
        'Date Publicly Available': (
            'date_publicly_available',False,None,util.date_converter),
        'Most Recent Update': (
            'date_updated',False,None,util.date_converter),
        }
    column_definitions = util.fill_in_column_definitions(
        properties,column_definitions)
    
    cols = util.find_columns(column_definitions, sheet.labels,
        all_sheet_columns_required=False)
    
    rows = 0    
    logger.debug('cols: %s' % cols)
    for row in sheet:
        r = util.make_row(row)
        dict = {}
        initializer = {}
        for i,value in enumerate(r):
            if i not in cols: continue
            properties = cols[i]

            logger.debug('read col: %d: %s' % (i,properties))
            required = properties['required']
            default = properties['default']
            converter = properties['converter']
            model_field = properties['model_field']

            logger.debug('raw value %r' % value)
            if(converter != None):
                value = converter(value)
            if(value == None ):
                if( default != None ):
                    value = default
            if(value == None and  required == True):
                raise Exception('Field is required: %s, record: %d' 
                    % (properties['column_label'],rows))

            logger.debug('model_field: %s, converted value %r'
                % (model_field, value) )
            initializer[model_field] = value
        try:
            logger.debug('initializer: %s' % initializer)
            
            facility_id = initializer.pop('facility_id',None)
            try:
                other_reagent = OtherReagent.objects.get(facility_id=facility_id)
                initializer['reagent'] = other_reagent
            except ObjectDoesNotExist, e:
                logger.error('facility_id: "%s" does not exist, row: %d' 
                    % (facility_id,i))
            batch = OtherReagentBatch(**initializer)
            batch.save()
            logger.debug('batch created: %s', batch)
            rows += 1
        except Exception, e:
            logger.error("Invalid other_reagent_batch initializer: %s" % initializer)
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
    logging.basicConfig(
        level=log_level, 
        format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')        

    print 'importing ', args.inputFile
    main(args.inputFile)
