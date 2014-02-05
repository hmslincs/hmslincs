import sys
import argparse
import xls2py as x2p
import re
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from db.models import Antibody
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
    Read in the Antibody
    """
    sheet_name = 'Sheet1'
    sheet = iu.readtable([path, sheet_name, 1]) # Note, skipping the header row by default

    properties = ('model_field','required','default','converter')
    column_definitions = { 
              'AR_Name': ('name',True),
              'AR_LINCS_ID': 'lincs_id', 
              'AR_Alternative_Name': 'alternative_names',
              'AR_Center_ID': ('facility_id', True),
              'AR_Target_Protein': 'target_protein_name',
              'AR_Target_Protein_ID': 'target_protein_uniprot_id',
              'AR_Target_Gene': 'target_gene_name',
              'AR_Target_Gene_ID': 'target_gene_id',
              'AR_Target_Organism': 'target_organism',
              'AR_Immunogen': 'immunogen',
              'AR_Immunogen_Sequence': 'immunogen_sequence',
              'AR_AntibodyClonality': 'antibody_clonality',
              'AR_Source_Organism': 'source_organism',
              'AR_Antibody_Isotype': 'antibody_isotype',
              'AR_Engineering': 'engineering',
              'AR_Antibody_Purity': 'antibody_purity',
              'AR_Antibody_Labeling': 'antibody_labeling',
              'AR_Recommended_Experiment_Type': 'recommended_experiment_type',
              'AR_Relevant_Reference': 'relevant_reference',
              'AR_Specificity': 'specificity',
              'Date Data Received':('date_data_received',False,None,util.date_converter),
              'Date Loaded': ('date_loaded',False,None,util.date_converter),
              'Date Publicly Available': ('date_publicly_available',False,None,util.date_converter),
              'Most Recent Update': ('date_updated',False,None,util.date_converter),
              'Is Restricted':('is_restricted',False,False)}

              
    # convert the labels to fleshed out dict's, with strategies for optional, default and converter
    column_definitions = util.fill_in_column_definitions(properties,column_definitions)
    
    # create a dict mapping the column ordinal to the proper column definition dict
    cols = util.find_columns(column_definitions, sheet.labels)

    rows = 0    
    logger.debug(str(('cols: ' , cols)))
    for row in sheet:
        r = util.make_row(row)
        dict = {}
        initializer = {}
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
            initializer[model_field] = value
        try:
            logger.debug(str(('initializer: ', initializer)))
            antibody = Antibody(**initializer)
            antibody.save()
            logger.info(str(('antibody created: ', antibody)))
            rows += 1
        except Exception, e:
            logger.error(str(( "Invalid antibody initializer: ", initializer)))
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
    # NOTE this doesn't work because the config is being set by the included settings.py, and you can only set the config once
    logging.basicConfig(level=log_level, format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')        
    logger.setLevel(log_level)

    print 'importing ', args.inputFile
    main(args.inputFile)
