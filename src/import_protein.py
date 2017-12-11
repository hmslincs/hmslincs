import argparse
import logging

import init_utils as iu
import import_utils as util
from db.models import Protein, ProteinBatch
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
    Read in the Protein
    """
    sheet_name = 'HMS-LINCS Kinases'

    # Note, skipping the header row by default
    sheet = iu.readtable([path, sheet_name, 1]) 

    properties = ('model_field','required','default','converter')
    column_definitions = { 
            'PP_Name':('name',True), 
            'PP_LINCS_ID':('facility_id',True,None,lambda x: x[x.index('HMSL')+4:]), 
            'PP_UniProt_ID':'uniprot_id', 
            'PP_Alternate_Name':'alternative_names',
            'PP_Alternate_Name[2]':'alternate_name_2',
            'PP_Provider':'provider',
            'PP_Provider_Catalog_ID':'provider_catalog_id',
            'PP_Batch_ID':'batch_id', 
            'PP_Amino_Acid_Sequence':'amino_acid_sequence',
            'PP_Gene_Symbol':'gene_symbol', 
            'PP_Gene_ID':'gene_id',
            'PP_Protein_Source':'protein_source',
            'PP_Protein_Form':'protein_form', 
            'PP_Mutation':'mutation', 
            'PP_Phosphorylation_State':'phosphlorylation', 
            'PP_Domain':'protein_domain', 
            'PP_Protein_Purity':'protein_purity', 
            'PP_Protein_Complex':'protein_complex', 
            'PP_Isoform':'isoform', 
            'PP_Protein_Type':'protein_type', 
            'PP_Source_Organism':'source_organism', 
            'PP_Reference':'reference',
            'Comments': 'comments',
            'Date Data Received':('date_data_received',False,None,
                                  util.date_converter),
            'Date Loaded': ('date_loaded',False,None,util.date_converter),
            'Date Publicly Available': ('date_publicly_available',False,None,
                                        util.date_converter),
            'Most Recent Update': ('date_updated',False,None,util.date_converter),
            'Is Restricted':('is_restricted',False,False)}
    
    # convert the labels to fleshed out dict's, with strategies for optional, 
    # default and converter
    column_definitions = \
        util.fill_in_column_definitions(properties,column_definitions)
    
    # create a dict mapping the column ordinal to the proper column definition
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
                raise Exception('Field is required: %s, record: %d' 
                                    % (properties['column_label'],rows))
            logger.debug(str((
                'model_field: ' , model_field, ', value: ', value)))
            initializer[model_field] = value
        try:
            logger.debug(str(('initializer: ', initializer)))
            protein = Protein(**initializer)
            
            # FIXME: LINCS IDS for Protein
            protein.lincs_id = protein.facility_id
            
            protein.save()
            logger.info(str(('protein created: ', protein)))
            rows += 1
            
            # create a default batch - 0
            ProteinBatch.objects.create(reagent=protein,batch_id=0)
            
        except Exception, e:
            logger.error(str(("Invalid protein initializer: ", initializer, e)))
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
    logging.basicConfig(
        level=log_level, 
        format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')        
    logger.setLevel(log_level)

    print 'importing ', args.inputFile
    main(args.inputFile)
