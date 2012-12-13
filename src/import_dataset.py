import argparse
import re
import logging
import time;  

import init_utils as iu
import import_utils as util
from django.core.exceptions import ObjectDoesNotExist
from db.models import DataSet, DataColumn, DataRecord, DataPoint, SmallMolecule, SmallMoleculeBatch, Cell, Protein, LibraryMapping
from django.db import transaction, models


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
              'Is Restricted':('is_restricted',False,False,util.bool_converter),
              'Dataset Type':('dataset_type',False),
              'Usage Message':('usage_message',False),
              }
    
    sheet_labels = []
    for row in metaSheet:
        rowAsUnicode = util.make_row(row)
        sheet_labels.append(rowAsUnicode[0])

    # convert the definitions to fleshed out dict's, with strategies for optional, default and converter
    field_definitions = util.fill_in_column_definitions(properties,field_definitions)
    # create a dict mapping the column/row ordinal to the proper definition dict
    cols = util.find_columns(field_definitions, sheet_labels,all_column_definitions_required=False)

    
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

#def read_metadata(worksheet):
#    """
#    Read in the DataSets, Datacolumns, and Data sheets.  In the Data sheet, rows are DataRecords, and columns are DataPoints
#    """
##    # Read in the DataSet
##    sheetname = 'Meta'
##    metaSheet = iu.readtable([path, sheetname]) # Note, skipping the header row by default
#
#    # Define the Column Names -> model fields mapping
#    properties = ('model_field','required','default','converter')
#    field_definitions = {'Lead Screener First': 'lead_screener_firstname',
#              'Lead Screener Last': 'lead_screener_lastname',
#              'Lead Screener Email': 'lead_screener_email',
#              'Lab Head First': 'lab_head_firstname',
#              'Lab Head Last': 'lab_head_lastname',
#              'Lab Head Email': 'lab_head_email',
#              'Title': 'title',
#              'Facility ID': ('facility_id',True,None, lambda x: util.convertdata(x,int)),
#              'Summary': 'summary',
#              'Protocol': 'protocol',
#              'References': 'protocol_references',
#              'Date Data Received':('date_data_received',False,None,util.date_converter),
#              'Date Loaded': ('date_loaded',False,None,util.date_converter),
#              'Date Publicly Available': ('date_publicly_available',False,None,util.date_converter),
#              'Is Restricted':('is_restricted',False,False,util.bool_converter),
#              'Dataset Type':('dataset_type',False)}
#    
#    sheet_labels = []
#    curr_row = 1 # note zero indexed
#    row = worksheet.row(curr_row)
#    while curr_row < worksheet.nrows:
#        sheet_labels.append(str(worksheet.cell_value(curr_row, 0)))
#        curr_row += 1
#    
#    for row in metaSheet:
#        rowAsUnicode = util.make_row(row)
#        sheet_labels.append(rowAsUnicode[0])
#
#    # convert the definitions to fleshed out dict's, with strategies for optional, default and converter
#    field_definitions = util.fill_in_column_definitions(properties,field_definitions)
#    # create a dict mapping the column/row ordinal to the proper definition dict
#    cols = util.find_columns(field_definitions, sheet_labels,all_column_definitions_required=False)
#
#    
#    initializer = {}
#    for i,row in enumerate(metaSheet):
#        rowAsUnicode = util.make_row(row)
#        properties = cols[i]
#        value = rowAsUnicode[1]
#        
#        logger.debug(str(('read col: ', i, ', ', properties)))
#        required = properties['required']
#        default = properties['default']
#        converter = properties['converter']
#        model_field = properties['model_field']
#
#        # Todo, refactor to a method
#        logger.debug(str(('raw value', value)))
#        if(converter != None):
#            value = converter(value)
#        if(value == None ):
#            if( default != None ):
#                value = default
#        if(value == None and  required == True):
#            raise Exception('Field is required: %s, record: %d' % (properties['column_label'],row))
#        logger.debug(str(('model_field: ' , model_field, ', value: ', value)))
#        initializer[model_field] = value
#
#    return initializer            

def readDataColumns(path):
    # Read in the DataColumn Sheet
    sheetname = 'Data Columns'
    dataColumnSheet = iu.readtable([path, sheetname])

    _fields = util.get_fields(DataColumn)
    _typelookup = dict((f.name, iu.totype(f)) for f in _fields)
    
    # TODO: Use the import_utils methods here
    # TODO: compare and combine this with the fieldinformation entity
    labels = {'Worksheet Column':'worksheet_column',
              'Display Order':'display_order',
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

import xlrd


def main(path):
    datarecord_batch = []
    save_interval = 1000
    # read in the two columns of the meta sheet to a dict that defines a DataSet
    # TODO: Need a transaction, in case loading fails!
    logger.info('read metadata...')

#    book = xlrd.open_workbook(path) #open our xls file, there's lots of extra default options in this call, for logging etc. take a look at the docs
#    sheetname = 'Meta'
#    worksheet = book.sheet_by_name(sheetname) #we can pull by name

    metadata = read_metadata(path)
    dataset = None
    try:
        metadata = read_metadata(path)
        try:
            extant_dataset = DataSet.objects.get(facility_id=metadata['facility_id'])
            logger.info(str(('extent_dataset',extant_dataset)))
            if(extant_dataset):
                logger.warn(str(('deleting extant dataset for facility id: ', metadata['facility_id'])))
                extant_dataset.delete()
        except Exception,e:
            logger.info(str(('on trying to delete',e)))
#            raise e
        dataset = DataSet(**metadata)
        dataset.save()
        logger.info(str(('dataset created: ', dataset)))
    except Exception, e:
        logger.error(str(('Exception reading metadata or saving the dataset', metadata, e)))
        raise e
    
    # read in the data columns sheet to an array of dict's, each dict defines a DataColumn    
    logger.info('read data columns...')
    dataColumnDefinitions = readDataColumns(path)
    
    # now that the array of DataColumn dicts is created, use them to create the DataColumn instances
    dataColumns = {}
    for i,dc in enumerate(dataColumnDefinitions):
        dc['dataset'] = dataset
        if(not 'display_order' in dc or dc['display_order']==None): dc['display_order']=i
        dataColumn = DataColumn(**dc)
        dataColumn.save()
        logger.info(str(('datacolumn created:', dataColumn)))
        dataColumns[dataColumn.name] = dataColumn    

    logger.info('read the Data sheet')
    sheetname = 'Data'
    dataSheet = iu.readtable([path, sheetname])
    
    # First, map the sheet column indices to the DataColumns that were created
    dataColumnList = {}
    # follows are optional columns
    metaColumnDict = {'Control Type':-1, 'batch_id':-1} # meta columns contain forensic information, all are optional
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
                #raise Exception(str(( "Error: no datacolumn for ", label, dataColumns.values(), metaColumnDict.keys(),metaColumnDict.keys())))
                logger.warn(str(( "Warn: ignoring undefined column: ", label, " (not found in the datacolumns sheet), columns: ", 
                                  dataColumns.values(), metaColumnDict.keys(),metaColumnDict.keys())))
    
    found=False
    for key,value in mappingColumnDict.items():
        if(value != -1): 
            found=True
    if(not found):
        raise Exception('at least one of: ' + str(mappingColumnDict.keys()) + ' must be defined and used in the Data sheet.')
    
    # Read in the Data sheet, create DataPoint values for mapped column in each row
    logger.info(str(('data sheet columns identified, read rows, save_interval:', save_interval)))
    loopStart = time.time()
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
                    if len(value) < 2: raise Exception('Small Molecule (Batch) format is #####-###(-#) **Note that (batch) is optional')
                    x = value[0]
                    facility = util.convertdata(x,int) 
                    salt = value[1]
                    try:
                        dataRecord.smallmolecule = SmallMolecule.objects.get(facility_id=facility, salt_id=salt)
                    except Exception, e:
                        logger.error(str(('could not locate small molecule:', facility)))
                        raise
                    if(len(value)>2):
                        dataRecord.batch_id = util.convertdata(value[2],int)
                        # TODO: validate that the batch exists?  (would need to do for all types, not just Small Molecule
                    mapped = True
            except Exception, e:
                logger.error(str(("Invalid Small Molecule (or batch) identifiers: ", value, e,'row',current_row)))
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
                    else:
                        raise Exception(str(('Must define both plate and well (not just plate), row', current_row)))
                        
                    dataRecord.plate = plate_id
                    dataRecord.well = well_id
                    try:
                        # TODO: what if the plate/well does not correlate to a librarymapping?  i.e. if this is the plate/well for a cell/protein study?
                        # For now, the effect of the followinlogger.info(str((g logic is that plate/well either maps a librarymapping, or is a an arbitrary plate/well
                        dataRecord.library_mapping = LibraryMapping.objects.get(plate=plate_id,well=well_id)
                        if(dataRecord.smallmolecule != None):
                            if(dataRecord.smallmolecule != None and dataRecord.library_mapping.smallmolecule_batch != None and (dataRecord.smallmolecule != dataRecord.library_mapping.smallmolecule_batch.smallmolecule)):
                                raise Exception(str(('SmallMolecule does not match the libraryMapping.smallmolecule_batch.smallmolecule pointed to by the plate/well:',plate_id,well_id,
                                                     dataRecord.smallmolecule,dataRecord.library_mapping.smallmolecule_batch.smallmolecule,
                                                     r,'row',current_row)))
                        elif(dataRecord.library_mapping.smallmolecule_batch != None):
                            dataRecord.smallmolecule = dataRecord.library_mapping.smallmolecule_batch.smallmolecule
                    except ObjectDoesNotExist, e:
                        logger.warn(str(('No librarymapping defined (plate/well do not point to a librarymapping), row', current_row))) 
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
                
        if metaColumnDict['Control Type'] > -1: 
            dataRecord.control_type = util.convertdata(r[metaColumnDict['Control Type']])
            if(dataRecord.control_type is not None and dataRecord.smallmolecule is not None):
                raise Exception(str(('Cannot define a control type for a non-control well (well mapped to a small molecule batch)',dataRecord.smallmolecule,dataRecord.control_type, 'row',current_row)))
        if metaColumnDict['batch_id'] > -1: 
            temp = util.convertdata(r[metaColumnDict['batch_id']], int)
            if(temp != None):
                if(dataRecord.batch_id is not None and temp is not None and dataRecord.batch_id != temp):
                    raise Exception(str(('batch id field(1) does not match batch id set with entity(2):',temp,dataRecord.batch_id)))
                dataRecord.batch_id = temp
        
        #dataRecord.save()
        logger.debug(str(('datarecord created:', dataRecord)))
        datapoint_batch = [] 
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
                elif (dataColumn.data_type == 'omero_image'): # TODO: define allowed "types" for the input sheet (this is listed in current SS code, but we may want to rework)
                    dataPoint = DataPoint(datacolumn=dataColumn,
                                          dataset = dataset,
                                          datarecord = dataRecord,
                                          int_value=util.convertdata(value,int))
                else: # ONLY text, for now, we'll need to define the allowed types, next!
                    dataPoint = DataPoint(datacolumn=dataColumn,
                                          dataset = dataset,
                                          datarecord = dataRecord,
                                          text_value=util.convertdata(value))
                
                
                #dataPoint.save()
                datapoint_batch.append(dataPoint)
                #if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('datapoint created:', dataPoint)))
                pointsSaved += 1
        datarecord_batch.append((dataRecord,datapoint_batch))
        rowsRead += 1
        
        if(rowsRead % save_interval == 0 ):
            new_datarecords = bulk_create_datarecords(datarecord_batch)
            logger.info(str(("save datarecord_batch, rowsRead", rowsRead, "time:", time.time() - loopStart )))
            if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('new drs',new_datarecords)))
            new_dps = bulk_create_with_manual_ids(datarecord_batch)
            if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('new dps',new_dps)))
            datarecord_batch=[]

    new_datarecords = bulk_create_datarecords(datarecord_batch)
    logger.info(str(("save datarecord_batch, time:", time.time() - loopStart )))
    if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('new drs',new_datarecords)))
    new_dps = bulk_create_with_manual_ids(datarecord_batch)
    if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('new dps',new_dps)))
    print 'Finished reading, rowsRead: ', rowsRead, ', points Saved: ', pointsSaved
    et = time.time()-loopStart
    print'elapsed: ',et , 'avg: ', et/rowsRead
    
    
@transaction.commit_on_success
def bulk_create_with_manual_ids(datarecord_batch):
    datapoint_id_start = DataPoint.objects.all().aggregate(models.Max('id'))['id__max']
    if(not isinstance(datapoint_id_start ,int)): datapoint_id_start = 0
    datapoint_id_start +=1
    datapoint_list = []
    for j, (datarecord,datapoints) in enumerate(datarecord_batch):
        for i,datapoint in enumerate(datapoints): 
            datapoint.datarecord = datarecord
        datapoint_id_start += len(datapoints)
        datapoint_list.extend(datapoints)
    DataPoint.objects.bulk_create(datapoint_list)

@transaction.commit_on_success
def bulk_create_datarecords(datarecord_batch):
    datarecord_id_start = DataRecord.objects.all().aggregate(models.Max('id'))['id__max']
    if(not isinstance(datarecord_id_start ,int)): datarecord_id_start = 0
    datarecord_id_start +=1
    datarecords = []
    for j, (datarecord,datapoints) in enumerate(datarecord_batch):
        datarecord.id = datarecord_id_start + j
    DataRecord.objects.bulk_create([x for (x,y) in datarecord_batch])
    
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
    
