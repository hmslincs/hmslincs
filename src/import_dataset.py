import sys
import argparse
import xls2py as x2p
import re

import init_utils as iu
import import_utils as util
from example.models import DataSet, DataColumn, DataRecord, DataPoint, SmallMolecule, Cell, Protein


# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    APPNAME = 'example',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

def read_metadata(path):
    """
    Read in the DataSets, Datacolumns, and Data sheets.  In the Data sheet, rows are DataRecords, and columns are DataPoints
    """
    # Read in the DataSet
    sheetname = 'Meta'
    # Define the Column Names -> model fields mapping
    labels = {'Lead Screener First': 'lead_screener_firstname',
              'Lead Screener Last': 'lead_screener_lastname',
              'Lead Screener Email': 'lead_screener_email',
              'Lab Head First': 'lab_head_firstname',
              'Lab Head Last': 'lab_head_lastname',
              'Lab Head Email': 'lab_head_email',
              'Title': 'title',
              'Facility ID': 'facility_id',
              'Summary': 'summary',
              'Protocol': 'protocol',
              'References': 'protocol_references'}
    
    metaSheet = iu.readtable([path, sheetname]) # Note, skipping the header row by default
    metaData = {}
    for row in metaSheet:
        rowAsUnicode = util.make_row(row)
        for key,value in labels.items():
            if re.match(key, rowAsUnicode[0], re.M|re.I):
                if key == 'Facility ID':
                    metaData[value] = util.convertdata(rowAsUnicode[1],int)
                else:
                    metaData[value] = rowAsUnicode[1]
    assert len(metaData) == len(labels), 'Meta data sheet does not contain the necessary keys, expected: %s, read: %s' % [labels, metaData]
    
    return metaData            

def readDataColumns(path):
        # Read in the DataColumn Sheet
    sheetname = 'Data Columns'
    dataColumnSheet = iu.readtable([path, sheetname])

    _fields = util.get_fields(DataColumn)
    _typelookup = dict((f.name, iu.totype(f)) for f in _fields)
    
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
    dataColumnDefinitions = []
    # first put the label row in (it contains the worksheet column, and its unique)
    for v in dataColumnSheet.labels[1:]:
        dataColumnDefinitions.append({labels['Worksheet Column']:v})
    # now, for each row, create the appropriate dictionary entry in the dataColumnDefinitions
    for row in dataColumnSheet:
        rowAsUnicode = util.make_row(row)
        keyRead = rowAsUnicode[0]
        for i,cellText in enumerate(rowAsUnicode[1:]):
            for key,fieldName in labels.items():
                if re.match(key,keyRead,re.M|re.I): # if the row is one of the DataColumn fields, then add it to the dict
                    dataColumnDefinitions[i][fieldName] = util.convertdata(cellText,_typelookup.get(fieldName, None)) # Note: convert the data to the model field type
                else:
                    pass
                    # print '"Data Column definition not used: ', cellText 
    print "definitions: ", dataColumnDefinitions
    
    return dataColumnDefinitions


def main(path):
    
    # read in the two columns of the meta sheet to a dict that defines a DataSet
    metadata = read_metadata(path)
    dataset = DataSet(**metadata)
    dataset.save()
    
    # read in the data columns sheet to an array of dict's, each dict defines a DataColumn    
    dataColumnDefinitions = readDataColumns(path)
    
    # now that the array of DataColumn dicts is created, use them to create the DataColumn instances
    dataColumns = {}
    for dc in dataColumnDefinitions:
        dc['dataset'] = dataset
        dataColumn = DataColumn(**dc)
        dataColumn.save()
        dataColumns[dataColumn.name] = dataColumn    

    # read the Data sheet
    sheetname = 'Data'
    dataSheet = iu.readtable([path, sheetname])
    
    # First, map the sheet column indices to the DataColumns that were created
    dataColumnList = {}
    metaColumnDict = {'Well':-1, 'Plate':-1, 'Control Type':-1} # meta columns contain forensic information
    mappingColumnDict = {'Small Molecule':-1, 'Cell':-1, 'Protein':-1} # what is being studied - at least one is required
    # NOTE: this scheme is matching based on the labels between the "Data Column" sheet and the "Data" sheet
    for i,label in enumerate(dataSheet.labels):
        if(label == 'None' or label == 'well_id' or label.strip()=='' or label == 'Exclude' ): continue  
        if label in metaColumnDict: 
            metaColumnDict[label] = i
            continue
        if label in mappingColumnDict: 
            mappingColumnDict[label] = i
            continue
        if label in dataColumns:
            dataColumnList[i] = dataColumns[label] # note here "i" is the index to the dict
            
        else:
            #raise Exception("no datacolumn for the label: " + label)
            columnName = chr(ord('A') + i)
            findError = True
            for column in dataColumns.values():
                if(column.worksheet_column == columnName):
                    dataColumnList[i] = column
                    findError = False
                    break
            if findError:    
                print "Error: no datacolumn for ", label
                sys.exit(-1)
    
    found=False
    for key,value in mappingColumnDict.items():
        if(value != -1): 
            found=True
    if(not found):
        raise Exception('at least one of: ' + str(mappingColumnDict.keys()) + ' must be defined and used in the Data sheet.')
    
    # Read in the Data sheet, create DataPoint values for mapped column in each row
    pointsSaved = 0
    rowsRead = 0
    for row in dataSheet:
        r = util.make_row(row)
        dataRecord = DataRecord(dataset=dataset )
        map_column = mappingColumnDict['Small Molecule']
        mapped = False
        if(map_column > -1):
            try:
                value = util.convertdata(r[map_column].strip())
                if(value != None and value != '' ):
                    facility = value.split("-")[0] # TODO: purge "HMSL" from the db
                    salt = value.split("-")[1]
                    dataRecord.small_molecule = SmallMolecule.objects.get(facility_id=facility, sm_salt=salt)
                    mapped = True
            except Exception, e:
                print "Invalid Small Molecule facility id: ", value
                raise    
        map_column = mappingColumnDict['Cell']
        if(map_column > -1):
            try:
                value = util.convertdata(r[map_column].strip())
                if(value != None and value != '' ):
                    facility_id = value
                    dataRecord.cell = Cell.objects.get(facility_id=facility_id) # TODO: purge "HMSL" from the db
                    mapped = True
            except Exception, e:
                print "Invalid Cell facility id: ", facility_id
                raise    
        map_column = mappingColumnDict['Protein']
        if(map_column > -1):
            try:
                value = util.convertdata(r[map_column].strip())
                if(value != None and value != '' ):
                    facility_id = r[map_column]
                    dataRecord.protein = Protein.objects.get(lincs_id=facility_id[facility_id.index('HMSL')+4:]) #TODO: purge "HMSL"
                    mapped = True
            except Exception, e:
                print "Invalid Protein facility id: ", value
                raise
            
        if(not mapped):
            raise Exception('at least one of: ' + str(mappingColumnDict.keys()) + ' must be defined, missing for row: ' + str(rowsRead+2))
                
        if metaColumnDict['Plate'] > -1 : dataRecord.plate = util.convertdata(r[metaColumnDict['Plate']],int)
        if metaColumnDict['Well'] > -1 : dataRecord.well = util.convertdata(r[metaColumnDict['Well']])
        if metaColumnDict['Control Type'] > -1: dataRecord.control_type = util.convertdata(r[metaColumnDict['Control Type']])
        dataRecord.save()
        for i,value in enumerate(r):
            # NOTE: shall there be an "empty" datapoint? no, since non-existance of data in the worksheet does not mean "null" will mean "no value entered"
            # TODO: verify/read existing code, ask Dave
            if(value.strip()==''): continue  
            if i in dataColumnList:
                dataColumn = dataColumnList[i]
                #print 'i, value, datacolumn: ', i, value, dataColumn
                dataPoint = None
                if (dataColumn.data_type == 'Numeric'): # TODO: define allowed "types" for the input sheet (this is listed in current SS code, but we may want to rework)
                    if (dataColumn.precision != 0): # float, TODO: set precision
                        dataPoint = DataPoint(datacolumn = dataColumn,
                                              dataset = dataset,
                                              datarecord = dataRecord,
                                              float_value=util.convertdata(value, float))
                    else:
                        dataPoint = DataPoint(datacolumn=dataColumn,
                                              dataset = dataset,
                                              datarecord = dataRecord,
                                              int_value=util.convertdata(value,int))
                else: # ONLY text, for now, we'll need to define the allowed types, next!
                    dataPoint = DataPoint(datacolumn=dataColumn,
                                          dataset = dataset,
                                          datarecord = dataRecord,
                                          text_value=util.convertdata(value))
                
                dataPoint.save()
                pointsSaved += 1
        rowsRead += 1
    print 'Finished reading, rowsRead: ', rowsRead, ', points Saved: ', pointsSaved
    
    
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
    
