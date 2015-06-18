import sys
import argparse
import xlrd
import xls2py as x2p
import re
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from db.models import FieldInformation
from django.db import transaction

import os
import os.path as op
import csv
_mydir = op.abspath(op.dirname(__file__))
_djangodir = op.normpath(op.join(_mydir, '../django'))
import sys
sys.path.insert(0, _djangodir)
import chdir as cd
with cd.chdir(_djangodir):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hmslincs_server.settings')
    import django.db.models as models
    import django.db.models.fields as fields
del _mydir, _djangodir

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
    Read in the Data Working Group sheets
    """
    logger.info(str(('read field information file', path)))
    
    properties = ('model_field','required','default','converter')
    column_definitions = {
        'table':'table',
        'field':'field',
        'alias':'alias',
        'queryset':'queryset',
        'show in detail':('show_in_detail',True,False,util.bool_converter),
        'show in list':('show_in_list',True,False,util.bool_converter),
        'show_as_extra_field':('show_as_extra_field',False,False,util.bool_converter),
        'is_lincs_field':('is_lincs_field',True,False,util.bool_converter),
        'is_unrestricted':('is_unrestricted',False,False,util.bool_converter),
        'list_order':('list_order',True,None,lambda x:util.convertdata(x,int)),
        'detail_order':('detail_order',True,None,lambda x:util.convertdata(x,int)),
        'use_for_search_index':('use_for_search_index',True,False,util.bool_converter),
        'Data Working Group version':'dwg_version',
        'Unique ID':('unique_id',True),
        'DWG Field Name':'dwg_field_name',
        'HMS Field Name':'hms_field_name',
        'Related to':'related_to',
        'Description':'description',
        'Importance (1: essential; 2: desirable / recommended; 3: optional)':'importance',
        'Comments':'comments',
        'Ontologies / references considered':'ontology_reference',
        'Link to ontology / reference':'ontology_reference',
        'Additional Notes (for development)':'additional_notes',
        }
       
    column_definitions = util.fill_in_column_definitions(
        properties,column_definitions)

    with open(path) as f:
        reader = csv.reader(f)

        labels = reader.next()
        cols = util.find_columns(
            column_definitions, labels, all_sheet_columns_required=False)
        
        logger.info('delete current table');
        FieldInformation.objects.all().delete()
        
        for j,row in enumerate(reader):
            
            if(logger.isEnabledFor(logging.DEBUG)): 
                logger.debug(str(('row', j, row)))
            
            initializer = {}
            for i,value in enumerate(row):
    
                if i not in cols: 
                    logger.info(str(('column out of range',j+1, i)))
                    continue
                properties = cols[i]
    
                logger.debug(str(('read col: ', i, ', ', properties)))
                required = properties['required']
                default = properties['default']
                converter = properties['converter']
                model_field = properties['model_field']
    
                # Todo, refactor to a method
                logger.debug(str(('raw value', value)))
                if(converter != None):
                    logger.debug(str(('using converter',converter,value)))
                    value = converter(value)
                    logger.debug(str(('converted',value)))
                if(value == None ):
                    if( default != None ):
                        value = default
                if(value == None and  required == True):
                    raise Exception('Field is required: %s, record: %d' 
                        % (properties['column_label'],j+1))
                logger.debug(str(('model_field: ' , model_field, ', value: ', value)))
                initializer[model_field] = value
    
            try:
                logger.debug(str(('initializer: ', initializer)))
                if(initializer['field'] == None):
                    logger.warn(str((
                        'Note: table entry has no field definition (will be skipped)', 
                        initializer, 'current row:', j+1)))
                    continue;
                lfi = FieldInformation(**initializer)
                # check if the table/field exists
                if(lfi.table != None):
                    table = models.get_model(APPNAME, lfi.table)
                    if( table != None):
                        if(lfi.field not in map(lambda x: x.name,table._meta.fields) ):
                            raise Exception(str(('unknown field: ', lfi.field)))
                    else:
                        raise Exception(str(('unknown table', lfi.table )))
                lfi.save()
                logger.info(str(('fieldInformation created:', lfi)))
            except Exception, e:
                logger.error(str(( 
                    "Invalid fieldInformation, initializer so far: ", 
                    initializer, 'current row:', j+1,e)))
                raise e
        
    print "fieldInformation rows read: ", j+1
            

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
