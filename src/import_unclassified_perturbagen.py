import sys
import argparse
import xls2py as x2p
import re
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from db.models import Unclassified, UnclassifiedBatch
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
    Read in the Unclassified Perturbagen
    """
    sheet_name = 'Sheet1'
    sheet = iu.readtable([path, sheet_name, 1]) 

    properties = ('model_field','required','default','converter')
    column_definitions = { 
                          
              'UP_LINCS_ID': 'lincs_id', 
              'Facility ID': ('facility_id',True),
              'UP_Alternative_ID': 'alternative_id',
              'UP_Name': ('name',True),
              'UP_Alternative_Name': 'alternative_names',
              'UP_Relevant_Citations': 'relevant_citations',                          
              'UP_Information_Source': 'information_source',
              'UP_Information_Source_ID': 'information_source_id',

              'Date Data Received':(
                  'date_data_received',False,None,util.date_converter),
              'Date Loaded': ('date_loaded',False,None,util.date_converter),
              'Date Publicly Available': (
                  'date_publicly_available',False,None,util.date_converter),
              'Most Recent Update': (
                  'date_updated',False,None,util.date_converter),
              'Is Restricted':('is_restricted',False,False)}

    column_definitions = util.fill_in_column_definitions(
        properties,column_definitions)
    cols = util.find_columns(column_definitions, sheet.labels)

    rows = 0    
    for row in sheet:
        r = util.make_row(row)
        dict = {}
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
                raise Exception('Field is required: %s, record: %d' 
                    % (properties['column_label'],rows))
            initializer[model_field] = value
        try:
            logger.debug('initializer: %r', initializer)
            reagent = Unclassified(**initializer)
            reagent.save()
            logger.info('Unclassified Perturbagen created: %r', reagent)
            rows += 1
            
            # create a default batch - 0
            UnclassifiedBatch.objects.create(reagent=reagent,batch_id=0)
            
        except Exception, e:
            logger.error('Invalid OtherReagent initializer: %r', initializer)
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
    # NOTE this doesn't work because the config is being set by the included 
    # settings.py, and you can only set the config once
    logging.basicConfig(level=log_level, 
        format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')        
    logger.setLevel(log_level)

    print 'importing ', args.inputFile
    main(args.inputFile)
