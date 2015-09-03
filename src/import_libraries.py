import sys
import argparse
import xls2py as x2p
import re
from datetime import date
import logging

import init_utils as iu
import import_utils as util
from db.models import Library, LibraryMapping, SmallMolecule, SmallMoleculeBatch
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
    Read in the Library and LibraryMapping sheets
    """
    libraries = readLibraries(path,'Library')
    
    sheet = iu.readtable([path, 'LibraryMapping'])
    properties = ('model_field','required','default','converter')
    date_parser = lambda x : util.convertdata(x,date)
    column_definitions = {'Facility':('facility_id',False,None, lambda x: util.convertdata(x,int)),
                          'Salt':('salt_id',False,None, lambda x: util.convertdata(x,int)),
                          'Batch':('batch_id',False,None, lambda x: util.convertdata(x,int)),
                          'Is Control':('is_control',False,False,util.bool_converter),
                          'Plate':('plate',False,None, lambda x: util.convertdata(x,int)),
                          'Well':'well',
                          'Library Name':'short_name',
                          'Concentration': 'concentration',
                          'Concentration Unit':'concentration_unit'
                          }
    # convert the labels to fleshed out dict's, with strategies for optional, default and converter
    column_definitions = util.fill_in_column_definitions(properties,column_definitions)
    
    # create a dict mapping the column ordinal to the proper column definition dict
    cols = util.find_columns(column_definitions, sheet.labels)
    
    small_molecule_batch_lookup = ('reagent', 'batch_id')
    library_mapping_lookup = ('smallmolecule_batch','library','is_control','plate','well','concentration','concentration_unit')
    rows = 0    
    logger.debug(str(('cols: ' , cols)))
    for row in sheet:
        current_row = rows + 2
        r = util.make_row(row)
        initializer = {}
        small_molecule_lookup = {'facility_id':None, 'salt_id':None}
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
                raise Exception('Field is required: %s, record: %d' % (properties['column_label'],'row',current_row))
            logger.debug(str(('model_field: ' , model_field, ', value: ', value)))
            
            initializer[model_field] = value
            
            if(model_field in small_molecule_lookup):
                small_molecule_lookup[model_field]=value
                if( None not in small_molecule_lookup.values()):
                    try:
                        sm = SmallMolecule.objects.get(**small_molecule_lookup)
                        initializer['reagent'] = sm
                    except Exception, e:
                        raise Exception(str(('sm facility id not found', small_molecule_lookup,e,'row',current_row)))
            elif(model_field == 'short_name'):
                try:
                    library = libraries[value]
                    initializer['library'] = library
                except Exception, e:
                    raise Exception(str(('library short_name not found', value,e,'row',current_row)))

        # Do some business logic checks
        if initializer['is_control'] is True:
            if 'reagent' in initializer and initializer['reagent'] is not None:
                raise Exception(str(('Must define either "is control", or the small molecule fields, not both', initializer, 'row',current_row)))
        else:
            if initializer['reagent'] is None:
                raise Exception(str(('Must define either the Small Molecule, or as a control well', initializer, 'row', current_row)))
            try:
                search = {}
                for val in small_molecule_batch_lookup:
                    search[val]=initializer[val]
                initializer['smallmolecule_batch'] = SmallMoleculeBatch.objects.get(**search)
            except Exception, e:
                logger.error(str(('smallmolecule batch not found: ', search, 'initializer', initializer, current_row)))    
                raise
        lm_initializer = {}
        try:
            for val in library_mapping_lookup:
                if val in initializer:
                    lm_initializer[val] = initializer[val]
            lm = LibraryMapping(**lm_initializer)
            lm.save()
            if logger.isEnabledFor(logging.INFO):
                logger.info(str(('librarymapping defined:',lm)))
        except Exception, e:
            logger.error(str(('librarymapping initializer problem: ', lm_initializer, 'complete initializer', initializer)))
            raise
        
        rows += 1
        
    print 'library mappings read in: ', rows


def readLibraries(path, sheetName):
    
    sheet = iu.readtable([path, sheetName]) # Note, skipping the header row by default
    # dict to map spreadsheet fields to the Library fields
    properties = ('model_field','required','default','converter')
    date_parser = lambda x : util.convertdata(x,date)
    column_definitions = {'Name': ('name',True), # TODO use the model to determine if req'd
                          'ShortName': ('short_name',True),
                          'Library Type':'type',
                          'Date First Plated': ('date_first_plated',False,None,date_parser),
                          'Date Data Received':('date_data_received',False,None,date_parser),
                          'Date Loaded': ('date_loaded',False,None,date_parser),
                          'Date Publicly Available': ('date_publicly_available',False,None,date_parser),
                          'Most Recent Update': ('date_updated',False,None,util.date_converter),
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
            library = Library(**initializer)
            library.save()
            logger.info(str(('library created', library)))
            libraries[library.short_name] = library
            rows += 1
        except Exception, e:
            logger.error(str(('library initializer problem: ', initializer)))
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
    # NOTE this doesn't work because the config is being set by the included settings.py, and you can only set the config once
    logging.basicConfig(level=log_level, format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')        
    logger.setLevel(log_level)

    print 'importing ', args.inputFile
    main(args.inputFile)
