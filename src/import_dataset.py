import sys
import argparse
import xls2py as x2p
import re
import logging

import init_utils as iu
import import_utils as util
from db.models import DataSet, DataColumn, DataRecord, DataPoint, SmallMolecule, SmallMoleculeBatch, Cell, Protein, LibraryMapping


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

def read_metadata(path):
    """
    Read in the DataSets, Datacolumns, and Data sheets.  In the Data sheet, rows are DataRecords, and columns are DataPoints
    """
    # Read in the DataSet
    sheetname = 'Meta'
    metaSheet = iu.readtable([path, sheetname]) # Note, skipping the header row by default

    # Define the Column Names -> model fields mapping
    properties = ('model_field','required','default','converter')
    field_definitions = {'Lead Screener First': 'lead_screener_firstname',
              'Lead Screener Last': 'lead_screener_lastname',
              'Lead Screener Email': 'lead_screener_email',
              'Lab Head First': 'lab_head_firstname',
              'Lab Head Last': 'lab_head_lastname',
              'Lab Head Email': 'lab_head_email',
              'Title': 'title',
              'Facility ID': ('facility_id',True,None, lambda x: util.convertdata(x,int)),
              'Summary': 'summary',
              'Protocol': 'protocol',
              'References': 'protocol_references',
              'Date Data Received':('date_data_received',False,None,util.date_converter),
              'Date Loaded': ('date_loaded',False,None,util.date_converter),
              'Date Publicly Available': ('date_publicly_available',False,None,util.date_converter),
              'Is Restricted':('is_restricted',False,False,util.bool_converter)}
    
    sheet_labels = []
    for row in metaSheet:
        rowAsUnicode = util.make_row(row)
        sheet_labels.append(rowAsUnicode[0])

    # convert the definitions to fleshed out dict's, with strategies for optional, default and converter
    field_definitions = util.fill_in_column_definitions(properties,field_definitions)
    # create a dict mapping the column/row ordinal to the proper definition dict
    cols = util.find_columns(field_definitions, sheet_labels)

    
    initializer = {}
    for i,row in enumerate(metaSheet):
        rowAsUnicode = util.make_row(row)
        properties = cols[i]
        value = rowAsUnicode[1]
        
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
            raise Exception('Field is required: %s, record: %d' % (properties['column_label'],row))
        logger.debug(str(('model_field: ' , model_field, ', value: ', value)))
        initializer[model_field] = value

    return initializer            

def readDataColumns(path):
    # Read in the DataColumn Sheet
    sheetname = 'Data Columns'
    dataColumnSheet = iu.readtable([path, sheetname])

    _fields = util.get_fields(DataColumn)
    _typelookup = dict((f.name, iu.totype(f)) for f in _fields)
    
    # TODO: Use the import_utils methods here
    
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
                    logger.debug(str(( '"Data Column definition not used: ', cellText)) ) 
                    pass
    logger.debug(str(("definitions: ", dataColumnDefinitions)) )
    
    return dataColumnDefinitions


def main(path):
    
    # read in the two columns of the meta sheet to a dict that defines a DataSet
    metadata = read_metadata(path)
    dataset = DataSet(**metadata)
    dataset.save()
    logger.info(str(('dataset created: ', metadata)))
    
    # read in the data columns sheet to an array of dict's, each dict defines a DataColumn    
    dataColumnDefinitions = readDataColumns(path)
    
    # now that the array of DataColumn dicts is created, use them to create the DataColumn instances
    dataColumns = {}
    for dc in dataColumnDefinitions:
        dc['dataset'] = dataset
        dataColumn = DataColumn(**dc)
        dataColumn.save()
        logger.info(str(('datacolumn created:', dataColumn)))
        dataColumns[dataColumn.name] = dataColumn    

    # read the Data sheet
    sheetname = 'Data'
    dataSheet = iu.readtable([path, sheetname])
    
    # First, map the sheet column indices to the DataColumns that were created
    dataColumnList = {}
    metaColumnDict = {'Control Type':-1} # meta columns contain forensic information
    mappingColumnDict = {'Small Molecule Batch':-1, 'Plate':-1, 'Well':-1, 'Cell':-1, 'Protein':-1} # what is being studied - at least one is required
    # NOTE: this scheme is matching based on the labels between the "Data Column" sheet and the "Data" sheet
    for i,label in enumerate(dataSheet.labels):
        if(label == 'None' or  label.strip()=='' or label == 'Exclude' ): continue  
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
                raise Exception(str(( "Error: no datacolumn for ", label, dataColumns.values(), metaColumnDict.keys(),metaColumnDict.keys())))
    
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
        current_row = rowsRead+2
        r = util.make_row(row)
        dataRecord = DataRecord(dataset=dataset )
        map_column = mappingColumnDict['Small Molecule Batch']
        mapped = False
        if(map_column > -1):
            try:
                value = util.convertdata(r[map_column].strip())
                if(value != None and value != '' ):
                    value = value.split("-")
                    if len(value) != 3: raise Exception('Small Molecule Batch format is #####-###-#')
                    x = value[0]
                    facility = util.convertdata(x,int) 
                    salt = value[1]
                    batch = value[2]
                    try:
                        sm = SmallMolecule.objects.get(facility_id=facility, salt_id=salt);
                    except Exception, e:
                        logger.error(str(('could not locate small molecule:', facility)))
                        raise
                    dataRecord.smallmolecule_batch = SmallMoleculeBatch.objects.get(smallmolecule=sm, facility_batch_id=batch)
                    mapped = True
            except Exception, e:
                logger.error(str(("Invalid Small Molecule Batch identifiers: ", value, e,'row',current_row)))
                raise    
        map_column = mappingColumnDict['Plate']
        if(map_column > -1):
            try:
                plate_id=None
                well_id=None
                value = util.convertdata(r[map_column].strip())
                if(value != None and value != '' ):
                    plate_id = util.convertdata(value,int)
                 
                    value = util.convertdata(r[map_column+1].strip())
                    if(value != None and value != '' ):
                        well_id = value 
                        
                    dataRecord.library_mapping = LibraryMapping.objects.get(plate=plate_id,well=well_id) 
                    if(dataRecord.smallmolecule_batch != None and (dataRecord.smallmolecule_batch != dataRecord.library_mapping.smallmolecule_batch)):
                        raise Exception(str(('SmallMolecule batch does not match the libraryMapping SMB:',
                                             dataRecord.smallmolecule_batch,dataRecord.library_mapping.smallmolecule_batch,
                                             r,'row',current_row)))
                    else:
                        dataRecord.smallmolecule_batch = dataRecord.library_mapping.smallmolecule_batch
                    mapped = True
            except Exception, e:
                logger.error(str(("Invalid plate/well identifiers",plate_id,well_id,r,e,'row',current_row)))
                raise e
        map_column = mappingColumnDict['Cell']
        if(map_column > -1):
            try:
                value = util.convertdata(r[map_column].strip())
                facility_id = None
                if(value != None and value != '' ):
                    facility_id = util.convertdata(value,int) 
                    dataRecord.cell = Cell.objects.get(facility_id=facility_id) 
                    mapped = True
            except Exception, e:
                logger.error(str(("Invalid Cell facility id: ", facility_id,'row',current_row)))
                raise    
        map_column = mappingColumnDict['Protein']
        if(map_column > -1):
            try:
                value = util.convertdata(r[map_column].strip())
                if(value != None and value != '' ):
                    facility_id = r[map_column]
                    facility_id = util.convertdata(facility_id,int) 
                    dataRecord.protein = Protein.objects.get(lincs_id=facility_id) 
                    mapped = True
            except Exception, e:
                logger.error(str(("Invalid Protein facility id: ", value,'row',current_row)))
                raise
            
        if(not mapped):
            raise Exception(str(('at least one of: ' , str(mappingColumnDict.keys()) , ' must be defined, missing for row: ',current_row)))
                
        if metaColumnDict['Control Type'] > -1: dataRecord.control_type = util.convertdata(r[metaColumnDict['Control Type']])
        dataRecord.save()
        logger.info(str(('datarecord created:', dataRecord)))
        for i,value in enumerate(r):
            # NOTE: shall there be an "empty" datapoint? no, since non-existance of data in the worksheet does not mean "null" will mean "no value entered"
            # TODO: verify/read existing code, ask Dave
            if(value.strip()==''): continue  
            if i in dataColumnList:
                dataColumn = dataColumnList[i]
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
                if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('datapoint created:', dataPoint)))
                pointsSaved += 1
        rowsRead += 1
    print 'Finished reading, rowsRead: ', rowsRead, ', points Saved: ', pointsSaved
    
    
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
    
