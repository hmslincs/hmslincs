import sys
import init_utils as iu
import argparse
import xls2py as x2p
import re
from example.models import Screen, DataColumn, DataRecord, DataPoint


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
    
    # TODO: look up the screen, read in the screens from a screen sheet, prior to this process...
    screen = Screen(facility_id = 'test1',
                    name = 'test1')
    screen.save()
    
    sheetname = 'Data Columns'
    #sheet = x2p.Workbook(path)[sheetname]
    table = iu.readtable(path, sheetname)
    #values = tuple(unicode(cell) for cell in sheet[0][1:])

    _fields = getFields(DataColumn)
    _typelookup = dict((f.name, iu.totype(f)) for f in _fields)
    
    print "typeLookup: ", _typelookup
    
    labels = {'Worksheet Column':'worksheet_column',
              'Name':'name',
              'Data Type':'data_type',
              'Decimal Places':'precision',
              'Description':'description',
              'Replicate Number':'replicate',
              'Time point':'time_point', 
              'Assay readout type':'readout_type',
              'Comments':'comments'}

    # create an array of dict's, each dict defines a DataColumn    
    array = []
    # first put the label row in (only because it is distinct already)
    for v in table.labels[1:]:
        array.append({labels['Worksheet Column']:v})
    # now, for each row, create the appropriate dictionary entry in the array
    for row in table:
        rowAsUnicode = makeRow(row)
        keyRead = rowAsUnicode[0]
        for i,cellText in enumerate(rowAsUnicode[1:]):
            for key,fieldName in labels.items():
                if re.match(key,keyRead,re.M|re.I): # if the row is one of the DataColumn fields, then add it to the dict
                    array[i][fieldName] = convertdata(cellText,_typelookup.get(fieldName, None))
    print "definitions: ", array

    dataColumns = {}
    for dc in array:
        dc['screen_key'] = screen
        dataColumn = DataColumn(**dc)
        dataColumn.save()
        dataColumns[dataColumn.name] = dataColumn    

    #TODO: next: read in the values sheet, create DataPoint values for each record
    sheetname = 'Data'
    #sheet = x2p.Workbook(path)[sheetname]
    table = iu.readtable(path, sheetname)
    dataColumnList = {}
    for i,label in enumerate(table.labels):
        if label in dataColumns:
            dataColumnList[i] = dataColumns[label]
        else:
            #raise Exception("no datacolumn for the label: " + label)
            print "Note: no datacolumn for ", label
    pointsSaved = 0
    rowsRead = 0
    for row in table:
        r = makeRow(row)
        dataRecord = DataRecord(screen_key=screen
                   #, small_molecule_key=smallMolecule    # TODO: lookup small molecule
                   )
        dataRecord.save()
        for i,value in enumerate(r):
            # NOTE: shall there be an "empty" datapoint? no, since non-existance of data in the worksheet does not mean "null" will mean "no value entered"
            # TODO: verify/read existing code, ask Dave
            if(value.strip()==''): continue  
            if i in dataColumnList:
                dataColumn = dataColumnList[i]
                print "dc: " , dataColumn.name , ', value: ', value
                dataPoint = None
                if (dataColumn.data_type == 'Numeric'): # TODO: define allowed "types" for the input sheet (this is listed in current SS code, but we may want to rework)
                    if (dataColumn.precision != 0): # float, TODO: set precision
                        dataPoint = DataPoint(data_column_key = dataColumn,
                                              screen_key = screen,
                                              record_key = dataRecord,
                                              float_value=convertdata(value, float))
                    else:
                        dataPoint = DataPoint(data_column_key=dataColumn,
                                              screen_key = screen,
                                              record_key = dataRecord,
                                              int_value=convertdata(value,int))
                else: # ONLY text, for now, we'll need to define the allowed types, next!
                    dataPoint = DataPoint(data_column_key=dataColumn,
                                          screen_key = screen,
                                          record_key = dataRecord,
                                          text_value=value)
                dataPoint.save()
                pointsSaved += 1
        rowsRead += 1
    print 'Finished reading, rowsRead: ', rowsRead, ', points Saved: ', pointsSaved
    
    
def convertdata(value, t):
    print 'convert: value: ', value, ', type: ', t
    if value == 'None':  # todo: because all values are returned as unicode, and xls2py is converting empty values to "None", we need this clause
        return None
    if t is None:
        return value
    elif t is int: # todo: this is a kludge, since we want an integer from values like "5.0"
        return int(float(value))
    else:
        return t(value)

def getFields(model):
    return tuple(model._meta.fields)
        

def makeRow(sheetRow):
    r = []
    for c in sheetRow:
        r.append(unicode(c))
    return r
parser = argparse.ArgumentParser(description='Import file')
parser.add_argument('-f', action='store', dest='inputFile',
                    metavar='FILE', required=True,
                    help='input file path')
    
if __name__ == "__main__":
    args = parser.parse_args()
    if(args.inputFile is None):
        parser.print_help();
        parser.exit(0, "\nMust define the FILE param.\n")
    main(args.inputFile)
    
