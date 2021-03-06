import sys
import argparse
import xls2py as x2p
import re
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from db.models import DiffCell, DiffCellBatch, IpscBatch
from django.db import transaction

__version__ = "$Revision: 24d02504e664 $"
# $Source$

# ---------------------------------------------------------------------------

import setparams as _sg
from import_utils import convertdata
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
    sheet = iu.readtable([path, sheet_name,1]) 

    properties = ('model_field','required','default','converter')

    
    column_definitions = {
        'Facility ID':(
            'facility_id',True,None, lambda x: x[x.index('HMSL')+4:]),
        'DC_Name':('name',True),
        'DC_LINCS_ID':'lincs_id',
        'DC_Alternative_Name':'alternative_names',
        'DC_Alternative_ID': 'alternative_id',
        'Precursor_IPSC':'precursor_facility_batch_id',
        
        'DC_Differentiation_Protocol': 'differentiation_protocol',
        'DC_Cell_Type': 'cell_type',
        'DC_Cell_Type_Detail': 'cell_type_detail',
        'DC_Known_Mutations': 'mutations_known',
        'DC_Mutation_Citations': 'mutation_citations',
        'DC_Molecular_Features': 'molecular_features',
        'DC_Recommended_Culture_Conditions': 'recommended_culture_conditions',
        'DC_Relevant_Citations': 'relevant_citations',
        'DC_Related_Projects': 'related_projects',
        'DC_Cell_Markers': 'cell_markers',
        'DC_Genetic_Modification': 'genetic_modification',
        
        'Comments': 'comments',
        'Date Data Received':(
            'date_data_received',False,None,util.date_converter),
        'Date Loaded': ('date_loaded',False,None,util.date_converter),
        'Date Publicly Available': (
            'date_publicly_available',False,None,util.date_converter),
        'Most Recent Update': ('date_updated',False,None,util.date_converter),
        'Is Restricted':('is_restricted',False,False,util.bool_converter)
    }
    
    column_definitions = util.fill_in_column_definitions(
        properties,column_definitions)
    cols = util.find_columns(
        column_definitions, sheet.labels, all_sheet_columns_required=False)
            
    rows = 0    
    precursor_map = {}
    precursor_pattern = re.compile(r'HMSL(7\d{4})-(\d+)')
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
                raise Exception('Field is required: %s, record: %d' 
                    % (properties['column_label'],rows))

            logger.debug('model_field: %r, value: %r' , model_field, value)
            initializer[model_field] = value
            
        precursor_facility_batch_id = initializer.pop('precursor_facility_batch_id')
        if precursor_facility_batch_id:
            match = precursor_pattern.match(precursor_facility_batch_id)
            if not match:
                raise Exception('Invalid precursor pattern: needs: %s: %r, row: %d'
                    % (precursor_pattern, initializer, rows))
            precursor_map[initializer['facility_id']] = (match.group(1),match.group(2))
        
        try:
            logger.info('initializer: %r', initializer)
            diff_cell = DiffCell(**initializer)
            diff_cell.save()
            logger.info(str(('diff_cell created:', diff_cell)))

            # create a default batch - 0
            DiffCellBatch.objects.create(reagent=diff_cell,batch_id=0)
            
        except Exception, e:
            print "Invalid Primary Cell, name: ", r[0]
            raise e
        
        rows += 1
    print "Differentiated Cells read: ", rows
    
    for facility_id,(precursor_facility_id,batch_id) in precursor_map.items():
        try:
            logger.info('find precursor for cell: %r, (%r,%r)', 
                facility_id,precursor_facility_id, batch_id)
            precursor = IpscBatch.objects.get(
                reagent__facility_id=precursor_facility_id,
                batch_id=batch_id)
            diff_cell = DiffCell.objects.get(facility_id=facility_id)
            diff_cell.precursor = precursor
            diff_cell.save()
            
        except ObjectDoesNotExist:
            raise Exception('Precursor not found: %r-%r, for %r'
                % (precursor_facility_id,batch_id,facility_id))
        
    print 'Differentiated (Ipsc Cell) Precursors found:', len(precursor_map)
    

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
