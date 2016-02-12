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
from django.core.exceptions import ObjectDoesNotExist
from import_utils import convertdata
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
    Read in the Cell
    """
    sheet_name = 'HMS-LINCS cell line metadata'
    sheet = iu.readtable([path, sheet_name, 1]) # Note, skipping the header row by default

    properties = ('model_field','required','default','converter')
    column_definitions = {
              'Facility ID':('facility_id',True,None, lambda x: x[x.index('HMSL')+4:]),
              'CL_Name':('name',True),
              'CL_LINCS_ID':'lincs_id',
              'CL_Alternate_Name':'alternative_names',
              'CL_Alternate_ID':'alternative_id',
              
              'CL_Precursor_Cell_ID':('precursor_facility_id',False,None, 
                  lambda x: x[x.index('HMSL')+4:]),

              'MGH_ID':('mgh_id',False,None,lambda x:util.convertdata(x,int)),
              'Assay':'assay',
              'CL_Organism':'organism',
              'CL_Organ':'organ',
              'CL_Tissue':'tissue',
              'CL_Cell_Type':'cell_type',
              'CL_Cell_Type_Detail':'cell_type_detail',
              'CL_Donor_Sex': 'donor_sex',
              'CL_Donor_Age': ('donor_age_years',False,None,lambda x:util.convertdata(x,int)),
              'CL_Donor_Ethnicity': 'donor_ethnicity',
              'CL_Donor_Health_Status': 'donor_health_status',
              'CL_Disease':'disease',
              'CL_Disease_Detail':'disease_detail',
              'CL_Growth_Properties':'growth_properties',
              'CL_Genetic_Modification':'genetic_modification',
              'CL_Related_Projects':'related_projects',
              'CL_Recommended_Culture_Conditions':'recommended_culture_conditions',
              'CL_Verification_Reference_Profile':'verification_reference_profile',
              'CL_Known_Mutations':'mutations_known',
              'CL_Mutations_Citations':'mutations_citations',
              'CL_Molecular_Features': 'molecular_features',
              'CL_Production_Details': 'production_details',
              'CL_Relevant_Citations': 'relevant_citations',
              'CL_Reference_Source': 'reference_source',
              'Reference Source URL': 'reference_source_url',
              'Usage Note': 'usage_note',
              
              'Date Data Received':('date_data_received',False,None,util.date_converter),
              'Date Loaded': ('date_loaded',False,None,util.date_converter),
              'Date Publicly Available': ('date_publicly_available',False,None,util.date_converter),
              'Most Recent Update': ('date_updated',False,None,util.date_converter),
              'Is Restricted':('is_restricted',False,False,util.bool_converter)}
    # convert the labels to fleshed out dict's, with strategies for optional, default and converter
    column_definitions = util.fill_in_column_definitions(properties,column_definitions)
    
    # create a dict mapping the column ordinal to the proper column definition dict
    cols = util.find_columns(column_definitions, sheet.labels, all_sheet_columns_required=False)
            
    rows = 0    
    precursor_map = {}
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
            
            value = convertdata(value)
            if value is not None:
                if converter:
                    try:
                        value = converter(value)
                    except Exception:
                        logger.error('field parse error: %r, value: %r, row: %d',
                            properties['column_label'],value,rows+2)
                        raise 
            if value is None:
                if default is not None:
                    value = default
            if value is None and required:
                raise Exception('Field is required: %s, record: %d' % (properties['column_label'],rows))

            logger.debug('model_field: %r, value: %r' , model_field, value)
            initializer[model_field] = value
            
        precursor_facility_id = initializer.pop('precursor_facility_id')
        if precursor_facility_id:
            precursor_map[initializer['facility_id']] = precursor_facility_id

        try:
            logger.info('initializer: %r', initializer)
            cell = Cell(**initializer)
            cell.save()
            logger.info(str(('cell created:', cell)))

            # create a default batch - 0
            CellBatch.objects.create(reagent=cell,batch_id=0)
            
        except Exception, e:
            print "Invalid Cell, name: ", r[0]
            raise e
        
        rows += 1
    
    for facility_id,precursor_facility_id in precursor_map.items():
        try:
            precursor = Cell.objects.get(facility_id=precursor_facility_id)
            cell = Cell.objects.get(facility_id=facility_id)
            cell.precursor = precursor
            cell.save()
            
        except ObjectDoesNotExist:
            raise Exception('Precursor not found: %r, for %r'
                % (precursor_facility_id,facility_id))
    print "Cells read: ", rows
    
    

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
