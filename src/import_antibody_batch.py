import sys
import argparse
import xls2py as x2p
import re
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from db.models import Antibody, Protein, AntibodyBatch
from django.db import transaction

__version__ = "$Revision: 24d02504e664 $"
# $Source$

# ---------------------------------------------------------------------------

import setparams as _sg
from django.core.exceptions import ObjectDoesNotExist
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
    Read in the Antibody Batches
    """
    sheet_name = 'Sheet1'
    sheet = iu.readtable([path, sheet_name, 0]) 

    properties = ('model_field','required','default','converter')
    column_definitions = { 
              'AR_Center_Specific_ID': ('antibody_facility_id',True,None, lambda x: x[x.index('HMSL')+4:]),
              'AR_Batch_ID': ('batch_id',True,None,lambda x:util.convertdata(x,int)),
              'AR_Provider_Name': 'provider_name',
              'AR_Provider_Catalog_ ID': 'provider_catalog_id',
              'AR_Provider_Batch_ID': 'provider_batch_id',
              'AR_Antibody_Purity': 'antibody_purity',

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
            
            antibody_facility_id = initializer.pop('antibody_facility_id',None)
            if antibody_facility_id: 
                try:
                    antibody = Antibody.objects.get(facility_id=antibody_facility_id)
                    initializer['reagent'] = antibody
                except ObjectDoesNotExist, e:
                    logger.error('AR_Center_Specific_ID: "%s" does not exist, row: %d' 
                        % (antibody_facility_id,i))
            antibody_batch = AntibodyBatch(**initializer)
            antibody_batch.save()
            logger.info('antibody batch created: %s' % antibody_batch)
            rows += 1
        except Exception, e:
            logger.error("Invalid antibody_batch initializer: %s" % initializer)
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
    logging.basicConfig(level=log_level, 
        format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')        
    logger.setLevel(log_level)

    print 'importing ', args.inputFile
    main(args.inputFile)
