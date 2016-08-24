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
    sheet_name = 'Sheet1'
    sheet = iu.readtable([path, sheet_name, 1]) 

    properties = ('model_field','required','default','converter')
    column_definitions = { 
        'AR_Name': ('name',True),
        'AR_LINCS_ID': 'lincs_id', 
        'AR_Alternative_Name': 'alternative_names',
        'AR_Alternative_ID': 'alternative_id',
        'AR_Center_Canonical_ID': (
            'facility_id',True,None, lambda x: x[x.index('HMSL')+4:]),
        'AR_Clone_Name': 'clone_name',
        'AR_RRID': 'rrid',
        'AR_Antibody_Type': 'type',
        'target_protein_center_ids': 'target_protein_center_ids',
        'AR_Non-Protein_Target': 'non_protein_target_name',
        'AR_Target_Organism': 'target_organism',
        'AR_Immunogen': 'immunogen',
        'AR_Immunogen_Sequence': 'immunogen_sequence',
        'AR_Antibody_Species': 'species',
        'AR_Antibody_Clonality': 'clonality',
        'AR_Antibody_Isotype': 'isotype',
        'AR_Antibody_Production_Source_Organism': 'source_organism',
        'AR_Antibody_Production_Details': 'production_details',
        'AR_Antibody_Labeling': 'labeling',
        'AR_Antibody_Labeling_Details': 'labeling_details',
        'AR_Relevant_Citations': 'relevant_citations',
        
        'Date Data Received':(
            'date_data_received',False,None,util.date_converter),
        'Date Loaded': ('date_loaded',False,None,util.date_converter),
        'Date Publicly Available': (
            'date_publicly_available',False,None,util.date_converter),
        'Most Recent Update': ('date_updated',False,None,util.date_converter),
        'Is Restricted':('is_restricted',False,False,util.bool_converter)}
              
    column_definitions = util.fill_in_column_definitions(properties,column_definitions)
    
    cols = util.find_columns(column_definitions, sheet.labels, 
        all_sheet_columns_required=False)

    rows = 0    
    logger.debug('cols: %s' % cols)
    for row in sheet:
        logger.debug('row %s - %s' %(rows,row))
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
            if(value == None or value == 'None'):
                value = None
                if( default != None ):
                    value = default
            if(value == None and  required == True):
                raise Exception('Field is required: %s, record: %d' 
                    % (properties['column_label'],rows))
            if(value and converter != None):
                value = converter(value)

            logger.debug('model_field: %s, converted value %r'
                % (model_field, value) )
            initializer[model_field] = value
        try:
            logger.debug('row: %s, initializer: %s' % (rows,initializer))
            
            target_protein_center_ids = initializer.pop(
                'target_protein_center_ids',None)
            if target_protein_center_ids: 
                ids = [x for x in target_protein_center_ids.split(';')]
                try:
                    target_proteins = []
                    for id in ids:
                        id = id[id.index('HMSL')+4:]
                        target_proteins.append(Protein.objects.get(facility_id=id))
                except ObjectDoesNotExist, e:
                    logger.error(
                        'target_protein_center_ids "%s" does not exist, row: %d' 
                        % (id,i))
                    raise
            antibody = Antibody.objects.create(**initializer)
            if target_proteins:
                antibody.target_proteins = target_proteins
            antibody.save()
            logger.info('antibody created: %s' % antibody)
            rows += 1

            # create a default batch - 0
            AntibodyBatch.objects.create(reagent=antibody,batch_id=0)
            
        except Exception, e:
            logger.error("Invalid antibody initializer: %s" % initializer)
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
