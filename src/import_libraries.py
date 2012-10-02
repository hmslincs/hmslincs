import sys
import argparse
import xls2py as x2p
import re
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from db.models import Library, LibraryMapping, SmallMolecule

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
    Read in the Library and LibraryMapping sheets
    """
    libraries = readLibraries(path,'Library')
    
    labels = { 'Facility':'facility_id',
               'Salt':'sm_salt',
               'Batch':'facility_batch_id',
               'Plate':'plate',
               'Well':'well',
               'Library Name':'short_name',
               'Concentration': 'concentration',
               'Concentration Unit':'concentration_unit'
               }
    
    small_molecule_lookup = ('facility_id', 'sm_salt', 'facility_batch_id')
    sheet = iu.readtable([path, 'LibraryMapping'])
    
    #dict to map spreadsheet fields to terms
    cols = {}
    # first put the label row in (it contains the worksheet column, and its unique)
    for i,label in enumerate(sheet.labels):
        if label in labels:
            cols[labels[label]] = i
        else:
            print 'Note: column label not found:', label    
    rows = 0
    for row in sheet:
        r = util.make_row(row)
        # small molecule
        dict = {}
        for field in small_molecule_lookup:
            dict[field] = util.convertdata(r[cols[field]],int)
        try:
            dict['facility_id'] = 'HMSL' + str(dict['facility_id']) # TODO: convert all hmsl id's to integers!!
            sm = SmallMolecule.objects.get(**dict)
        except Exception, e:
            print "Invalid small molecule identifiers: ", dict
            raise 
        short_name = r[cols['short_name']]
        if short_name not in libraries:
            print "Library not found: ", short_name
            raise
        lm = {}
        lm['concentration'] = util.convertdata(r[cols['concentration']],float)
        lm['concentration_unit'] = util.convertdata(r[cols['concentration_unit']],None)
        lm['plate'] = util.convertdata(r[cols['plate']], int)
        lm['well'] = r[cols['well']]
        lm['small_molecule'] = sm
        lm['library'] = libraries[short_name]
        lm = LibraryMapping(**lm)
        lm.save()
        rows += 1

    print 'library mappings read in: ', rows


def readLibraries(path, sheetName):
    
    sheet = iu.readtable([path, sheetName]) # Note, skipping the header row by default
    # dict to map spreadsheet fields to the Library fields
    properties = ('model_field','required','default','converter')
    date_parser = lambda x : util.convertdata(x,date)
    column_definitions = {'Name': ('name',True), # TODO use the model to determine if req'd
                          'ShortName': ('short_name',True),
                          'Date First Plated': ('date_first_plated',False,None,date_parser),
                          'Date Data Received':('date_data_received',False,None,date_parser),
                          'Date Loaded': ('date_loaded',False,None,date_parser),
                          'Date Publicly Available': ('date_publicly_available',False,None,date_parser),
                          'Is Restricted':('is_restricted',False,False) }
    # convert the labels to fleshed out dict's, with strategies for optional, default and converter
    column_definitions = util.fill_in_column_definitions(properties,column_definitions)
    # create a dict mapping the column ordinal to the proper column definition dict
    cols = util.find_columns(column_definitions, sheet.labels)
    
    rows = 0    
    libraries = {}
    for row in sheet:
        logger.debug(str(('row raw: ',row)))
        r = util.make_row(row)
        logger.debug(str(('row: ',r)))
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
            logger.info('create library:', initializer)
            library = Library(**initializer)
            library.save()
            libraries[library.short_name] = library
            rows += 1
        except Exception, e:
            print "Invalid Library, name: ", r[0]
            raise e
        
    print "libraries defined: ", rows
    return libraries
    
    
    

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
    logging.basicConfig(level=log_level, format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')        

    print 'importing ', args.inputFile
    main(args.inputFile)