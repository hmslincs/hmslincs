import sys
import init_utils as iu
import argparse
import xls2py as x2p
import re
from example.models import Screen, DataColumn, DataRecord, DataPoint, SmallMolecule


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
    
    # Read in the Screen
    sheetname = 'Screen'
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
    
    screenSheet = iu.readtable([path, sheetname]) # Note, skipping the header row by default
    screenData = {}
    for row in screenSheet:
        rowAsUnicode = makeRow(row)
        for key,value in labels.items():
            if re.match(key, rowAsUnicode[0], re.M|re.I):
                if key == 'Facility ID':
                    screenData[value] = convertdata(rowAsUnicode[1],int)
                else:
                    screenData[value] = rowAsUnicode[1]
    assert len(screenData) == len(labels), 'Screen data sheet does not contain the necessary keys, expected: %s, read: %s' % [labels, screenData]            
    screen = Screen(**screenData)
    screen.save()
    
    # Read in the DataColumn Sheet
    sheetname = 'Data Columns'
    dataColumnSheet = iu.readtable([path, sheetname])

    _fields = getFields(DataColumn)
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
        rowAsUnicode = makeRow(row)
        keyRead = rowAsUnicode[0]
        for i,cellText in enumerate(rowAsUnicode[1:]):
            for key,fieldName in labels.items():
                if re.match(key,keyRead,re.M|re.I): # if the row is one of the DataColumn fields, then add it to the dict
                    dataColumnDefinitions[i][fieldName] = convertdata(cellText,_typelookup.get(fieldName, None)) # Note: convert the data to the model field type
                else:
                    pass
                    # print '"Data Column definition not used: ', cellText 
    print "definitions: ", dataColumnDefinitions
    
    # now that the array of DataColumn dicts is created, use them to create the DataColumn instances
    dataColumns = {}
    for dc in dataColumnDefinitions:
        dc['screen_key'] = screen
        dataColumn = DataColumn(**dc)
        dataColumn.save()
        dataColumns[dataColumn.name] = dataColumn    

    # Read in the Data sheet, create DataPoint values for each record
    sheetname = 'Data'
    dataSheet = iu.readtable([path, sheetname])
    dataColumnList = {}
    omeroWellColumnList = {}
    # NOTE: this scheme is matching based on the labels between the "Data Column" sheet and the "Data" sheet
    # TODO: store the plate/well/
    for i,label in enumerate(dataSheet.labels):
        if(label == 'None' or label == 'well_id' or label.strip()=='' or label=='Control Type' or label == 'Exclude' or label == 'Small Molecule' or label == 'Plate' or label == 'Well'): continue  
          
        if label in dataColumns:
            dataColumnList[i] = dataColumns[label] # note here "i" is the index to the dict
            #special clause here to determine if the next column is a "wellid" column - and therefore lists the omero wellid
            #if len(dataSheet.labels) >= i+2 and dataSheet.labels[i+1] == 'well_id':
            #    omeroWellColumnList[i+1] = dataColumns[label]
            
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
        #special clause here to determine if the next column is a "wellid" column - and therefore lists the omero wellid
        if len(dataSheet.labels) >= i+2 and dataSheet.labels[i+1] == 'well_id':
            omeroWellColumnList[i+1] = dataColumns[label]
    
    #TODO: add in the image columns
    # image id's will be converted to OMERO URLS of the form: https://lincs-omero.hms.harvard.edu/webclient/img_detail/128579/
    pointsSaved = 0
    rowsRead = 0
    for row in dataSheet:
        r = makeRow(row)
        try:
            value = r[0]
            facility = value.split("-")[0]
            salt = value.split("-")[1]
            sm = SmallMolecule.objects.get(facility_id=facility, sm_salt=salt)
        except Exception, e:
            print "Invalid facility id: ", value
            raise    
        dataRecord = DataRecord(screen_key=screen, small_molecule_key=sm )
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
                
                # special, messy clause here to add in the omero well id, hmmm, what would be a better way to enter omero well id's tied to the datapoints?
                if (i+1) in omeroWellColumnList and len(r) >= (i+2):
                    dataPoint.omero_well_id = r[i+1]
                dataPoint.save()
                pointsSaved += 1
        rowsRead += 1
    print 'Finished reading, rowsRead: ', rowsRead, ', points Saved: ', pointsSaved
    
    
def convertdata(value, t):
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
        
    print 'importing ', args.inputFile
    main(args.inputFile)
    
