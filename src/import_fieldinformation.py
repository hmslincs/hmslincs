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

import os
import os.path as op
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

def main(path):
    """
    Read in the Data Working Group sheets
    """
    logger.info("start")
    book = xlrd.open_workbook(path) #open our xls file, there's lots of extra default options in this call, for logging etc. take a look at the docs
 
    #sheet = book.sheets()[0] #book.sheets() returns a list of sheet objects... alternatively...
    #sheet = book.sheet_by_name("qqqq") #we can pull by name
    worksheet = book.sheet_by_index(0) #or by the index it has in excel's sheet collection
    properties = ('model_field','required','default','converter')
    column_definitions = {'table':'table',
                          'field':'field',
                          'alias':'alias',
                          'queryset':'queryset',
                          'show in detail':('show_in_detail',True,False,util.bool_converter),
                          'show in list':('show_in_list',True,False,util.bool_converter),
                          'is_lincs_field':('is_lincs_field',True,False,util.bool_converter),
                          'order':('order',True,None,lambda x:util.convertdata(x,int)),
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
       
    # convert the labels to fleshed out dict's, with strategies for optional, default and converter
    column_definitions = util.fill_in_column_definitions(properties,column_definitions)
    
    num_rows = worksheet.nrows - 1
    num_cells = worksheet.ncols - 1

    curr_row = 0 # note zero indexed
    row = worksheet.row(curr_row)
    labels = []
    i = -1
    while i < num_cells:
        i += 1
        # Cell Types: 0=Empty, 1=Text, 2=Number, 3=Date, 4=Boolean, 5=Error, 6=Blank
        # cell_type = worksheet.cell_type(curr_row, curr_cell)
        labels.append(str(worksheet.cell_value(curr_row, i)))
    
    # create a dict mapping the column ordinal to the proper column definition dict
    cols = util.find_columns(column_definitions, labels, all_sheet_columns_required=False)
    
    logger.info('delete current table');
    FieldInformation.objects.all().delete()
    
    rows = 0
    while curr_row < num_rows:
        curr_row += 1
        actual_row = curr_row + 2
        row = worksheet.row(curr_row)
        if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('row', row)))
        i = -1
        initializer = {}
        while i < num_cells:
            i += 1
            # Cell Types: 0=Empty, 1=Text, 2=Number, 3=Date, 4=Boolean, 5=Error, 6=Blank
            #cell_type = worksheet.cell_type(curr_row, curr_cell)
            value = unicode(worksheet.cell_value(curr_row, i))

            if i not in cols: 
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
                raise Exception('Field is required: %s, record: %d' % (properties['column_label'],actual_row))
            logger.debug(str(('model_field: ' , model_field, ', value: ', value)))
            initializer[model_field] = value

        try:
            logger.debug(str(('initializer: ', initializer)))
            #if((initializer['table'] == None and initializer['queryset'] == None ) or
            if(initializer['field'] == None):
                logger.warn(str(('Note: table entry has no field definition (will be skipped)', initializer, 'current row:', actual_row)))
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
            rows += 1
        except Exception, e:
            logger.error(str(( "Invalid fieldInformation, initializer so far: ", initializer, 'current row:', actual_row,e)))
            raise e
        
    print "fieldInformation read: ", rows
         
     

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