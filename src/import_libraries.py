import sys
import argparse
import xls2py as x2p
import re
from datetime import date

import init_utils as iu
import import_utils as util
from example.models import Library, LibraryMapping, SmallMolecule

__version__ = "$Revision: 24d02504e664 $"
# $Source$

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    APPNAME = 'example',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

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

    print 'rows read in: ', rows


def readLibraries(path, sheetName):
    
    sheet = iu.readtable([path, sheetName]) # Note, skipping the header row by default
    # dict to map spreadsheet fields to the Library fields
    labels = { 'Name': 'name',
               'ShortName': 'short_name',
               'Date First Plated': 'date_first_plated',
               'Date Data Received':'date_data_received',
               'Date Loaded': 'date_loaded',
               'Date Publicly Available': 'date_publicly_available' }
    date_parser = lambda x : util.convertdata(x,date)
    converters = {'date_first_plated': date_parser,
                  'date_loaded': date_parser,
                  'date_data_recieved': date_parser,
                  'date_publicly_available': date_parser }
    cols = {}
    # first put the label row in (it contains the worksheet column, and its unique)
    for i,label in enumerate(sheet.labels):
        if label in labels:
            cols[i] = labels[label]
        else:
            print 'Note: column label not found:', label
            raise
            
    rows = 0    
    i = 0
    
    libraries = {}
    for row in sheet:
        r = util.make_row(row)
        dict = {}
        for i,value in enumerate(r):
            if cols[i] in converters:
                value = converters[cols[i]](value)
            dict[cols[i]]= value
        try:
            print 'create library:', dict
            library = Library(**dict)
            library.save()
            libraries[library.short_name] = library
            rows += 1
        except Exception, e:
            print "Invalid Library, name: ", r[0]
            raise
        
    print "Rows read: ", rows
    return libraries
    
    
    

parser = argparse.ArgumentParser(description='Import file')
parser.add_argument('-f', action='store', dest='inputFile',
                    metavar='FILE', required=True,
                    help='input file path')
    
if __name__ == "__main__":
    args = parser.parse_args()
    if(args.inputFile is None):
        parser.print_help();
        parser.exit(0, "\nMust define the FILE param.\n")
        
    print 'importing ', args.inputFile
    main(args.inputFile)