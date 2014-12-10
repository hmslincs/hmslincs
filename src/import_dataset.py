import argparse
import import_utils as util
import init_utils as iu
import logging
import re
import time;  
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction, models

from db.models import DataSet, DataColumn, DataRecord, DataPoint, \
        SmallMolecule, Cell, Protein, LibraryMapping,\
        Antibody, OtherReagent


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
    Read in the DataSets, Datacolumns, and Data sheets.  In the Data sheet, rows
    are DataRecords, and columns are DataPoints
    """
    # Read in the DataSet
    sheetname = 'Meta'
    # Note, skipping the header row by default
    metaSheet = iu.readtable([path, sheetname]) 

    # Define the Column Names -> model fields mapping
    properties = ('model_field','required','default','converter')
    field_definitions = {'Lead Screener First': 'lead_screener_firstname',
              'Lead Screener Last': 'lead_screener_lastname',
              'Lead Screener Email': 'lead_screener_email',
              'Lab Head First': 'lab_head_firstname',
              'Lab Head Last': 'lab_head_lastname',
              'Lab Head Email': 'lab_head_email',
              'Title': 'title',
              'Facility ID': ('facility_id',True,None, 
                              lambda x: util.convertdata(x,int)),
              'Summary': 'summary',
              'Protocol': 'protocol',
              'References': 'protocol_references',
              'Date Data Received':('date_data_received',False,None,
                                    util.date_converter),
              'Date Loaded': ('date_loaded',False,None,util.date_converter),
              'Date Publicly Available': ('date_publicly_available',False,None,
                                          util.date_converter),
              'Most Recent Update': ('date_updated',False,None,
                                      util.date_converter),
              'Is Restricted':('is_restricted',False,False,util.bool_converter),
              'Dataset Type':('dataset_type',False),
              'Bioassay':('bioassay',False),
              'Dataset Keywords':('dataset_keywords',False),
              'Usage Message':('usage_message',False),
              }
    
    sheet_labels = []
    for row in metaSheet:
        rowAsUnicode = util.make_row(row)
        sheet_labels.append(rowAsUnicode[0])

    # convert the definitions to fleshed out dict's, with strategies for 
    # optional, default and converter
    field_definitions = \
        util.fill_in_column_definitions(properties,field_definitions)
    # create a dict mapping the column/row ordinal to the proper definition dict
    cols = util.find_columns(field_definitions, sheet_labels,
                             all_column_definitions_required=False)

    
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
            raise Exception('Field is required: %s, record: %d' % 
                            (properties['column_label'],row))
        logger.debug(str(('model_field: ' , model_field, ', value: ', value)))
        initializer[model_field] = value

    return initializer 

def readDataColumns(path):
    # Read in the DataColumn Sheet
    sheetname = 'Data Columns'
    dataColumnSheet = iu.readtable([path, sheetname])

    # Lookup all of the field types of the Datacolumn table.  
    # These will be used to validate input type by converting on read
    _fields = util.get_fields(DataColumn)
    _typelookup = dict((f.name, iu.totype(f)) for f in _fields)
    
    # TODO: Use the import_utils methods here
    # TODO: compare and combine this with the fieldinformation entity
    labels = {'Worksheet Column':'worksheet_column',
              'Display Order':'display_order',
              'Name':'name',
              'Display Name':'display_name',
              'Data Type':'data_type',
              'Decimal Places':'precision',
              'Description':'description',
              'Replicate Number':'replicate',
              'Unit':'unit', 
              'Assay readout type':'readout_type',
              'Comments':'comments',
              'Protein HMS LINCS ID': 'protein', 
              'Cell HMS LINCS ID': 'cell'}

    # create an array of dict's, each dict defines a DataColumn    
    dataColumnDefinitions = []
    #Note we also allow a list of pro
    # first the label row (it contains the worksheet column, it is unique)
    for v in dataColumnSheet.labels[1:]:
        dataColumnDefinitions.append({labels['Worksheet Column']:v})
        
    logger.debug(str(('========== datacolumns:',dataColumnDefinitions)))
    # for each row, create the dictionary entry in the dataColumnDefinitions
    for row in dataColumnSheet:
        rowAsUnicode = util.make_row(row)
        keyRead = rowAsUnicode[0]
        for i,cellText in enumerate(rowAsUnicode[1:]):
            try:
                for key,fieldName in labels.items():
                    # if one of the DataColumn fields, add it to the dict
                    if re.match(key,keyRead,re.M|re.I): 
                        if re.match('Protein HMS LINCS ID', keyRead, re.M|re.I):
                            facility_id = util.convertdata(cellText, int);
                            if facility_id:
                                dataColumnDefinitions[i][fieldName] = \
                                    Protein.objects.get(lincs_id=facility_id) 
                        elif re.match('Cell HMS LINCS ID', keyRead, re.M|re.I):
                            facility_id = util.convertdata(cellText, int);
                            if facility_id:
                                dataColumnDefinitions[i][fieldName] = \
                                    Cell.objects.get(facility_id=facility_id) 
                        else:
                            # Use the type from the fieldinformation table 
                            # to read in the data for each DC field
                            dataColumnDefinitions[i][fieldName] = \
                                util.convertdata(cellText,
                                                 _typelookup.get(fieldName, None)) 
                    else:
                        logger.debug(str((
                            '"Data Column definition not used: ', cellText)) ) 
                        pass
            except Exception, e:
                logger.error(str(('Exception reading data for cell', i, cellText, e)))
                raise e
        logger.debug(str(("definitions: ", dataColumnDefinitions)) )
    
    return dataColumnDefinitions

def colForInt(i):
    j = i/26
    rem = i%26
    baseColName = ''
    if j > 0:
        baseColName = colForInt(j-1)
    return  baseColName + chr(ord('A') + rem)


def main(path):
    datarecord_batch = []
    save_interval = 1000
    # read in the two columns of the meta sheet to a dict that defines a DataSet
    # TODO: Need a transaction, in case loading fails!
    logger.debug('read metadata...')

    metadata = read_metadata(path)
    dataset = None
    try:
        metadata = read_metadata(path)
        try:
            extant_dataset = DataSet.objects.get(
                facility_id=metadata['facility_id'])
            logger.debug(str(('extent_dataset',extant_dataset)))
            if(extant_dataset):
                logger.warn(str(('deleting extant dataset for facility id: ', 
                                 metadata['facility_id'])))
                extant_dataset.delete()
        except Exception,e:
            logger.debug(str(('on trying to delete',e)))
        dataset = DataSet(**metadata)
        dataset.save()
        logger.debug(str(('dataset created: ', dataset)))
    except Exception, e:
        logger.error(str(('Exception reading metadata or saving the dataset', 
                          metadata, e)))
        raise e
    
    # Read in the data columns sheet to an array of dict's, 
    # each dict defines a DataColumn.    
    logger.debug('read data columns...')
    dataColumnDefinitions = readDataColumns(path)
    
    # Now that the array of DataColumn dicts is created, 
    # use them to create the DataColumn instances.
    dataColumns = {}
    for i,dc in enumerate(dataColumnDefinitions):
        dc['dataset'] = dataset
        if(not 'display_order' in dc or dc['display_order']==None): 
            dc['display_order']=i
        dataColumn = DataColumn(**dc)
        dataColumn.save()
        logger.debug(str(('====datacolumn created:', dataColumn)))
        dataColumns[dataColumn.name] = dataColumn    

    logger.debug('read the Data sheet')
    sheetname = 'Data'
    dataSheet = iu.readtable([path, sheetname])
    
    # First, map the sheet column indices to the DataColumns that were created.
    dataColumnList = {}
    # Follows are optional columns
    # Meta columns contain forensic information, all are optional
    metaColumnDict = {'Control Type':-1, 'batch_id':-1} 
    # What is being studied - at least one is required
    mappingColumnDict = {
        'Small Molecule Batch':-1, 'Plate':-1, 'Well':-1, 
        'Cell':-1, 'Protein':-1, 'Antibody': -1, 'OtherReagent': -1} 
    # NOTE: this scheme is matching based on the labels between the 
    # "Data Column" sheet and the "Data" sheet.
    for i,label in enumerate(dataSheet.labels):
        if(label == 'None' or  label.strip()=='' or label == 'Exclude' ): 
            continue  
        if label in metaColumnDict: 
            metaColumnDict[label] = i
            continue
        if label in mappingColumnDict: 
            mappingColumnDict[label] = i
            continue
        if label in dataColumns:
            dataColumnList[i] = dataColumns[label] 
            
        else:
            #raise Exception("no datacolumn for the label: " + label)
            columnName = colForInt(i)
            findError = True
            for column in dataColumns.values():
                if(column.worksheet_column == columnName):
                    dataColumnList[i] = column
                    findError = False
                    break
            if findError:    
                logger.warn(str(( 
                    "Warn: ignoring undefined column: ", label, 
                    " (not found in the datacolumns sheet), columns: ", 
                    dataColumns.values(), metaColumnDict.keys(),
                    metaColumnDict.keys())))
    
    found=False
    for key,value in mappingColumnDict.items():
        if(value != -1): 
            found=True
    if(not found):
        raise Exception('at least one of: ' + str(mappingColumnDict.keys()) + 
                        ' must be defined and used in the Data sheet.')
    
    # Read the Datasheet, create DataPoint values for mapped column in each row
    logger.debug(str(('now read rows, save_interval:', save_interval)))
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
            _read_small_molecule_batch(map_column,r,current_row,dataRecord)
        map_column = mappingColumnDict['Plate']
        if(map_column > -1):
            _read_plate_well(map_column,r,current_row, dataRecord)
        map_column = mappingColumnDict['Cell']
        if(map_column > -1):
            _read_cell(map_column,r,current_row,dataRecord)
        map_column = mappingColumnDict['Antibody']
        if(map_column > -1):
            _read_antibody(map_column,r,current_row,dataRecord)
        map_column = mappingColumnDict['OtherReagent']
        if(map_column > -1):
            _read_other_reagent(map_column,r,current_row,dataRecord)
        map_column = mappingColumnDict['Protein']
        if(map_column > -1):
            _read_protein(map_column,r,current_row,dataRecord)
                            
        if metaColumnDict['Control Type'] > -1: 
            dataRecord.control_type = util.convertdata(
                r[metaColumnDict['Control Type']])
            if(dataRecord.control_type is not None and 
                    dataRecord.smallmolecule is not None):
                raise Exception(str((
                    'Cannot define a control type for a non-control well '
                    '(well mapped to a small molecule batch)',
                    dataRecord.smallmolecule,dataRecord.control_type, 
                    'row',current_row)))
        if metaColumnDict['batch_id'] > -1: 
            temp = util.convertdata(r[metaColumnDict['batch_id']], int)
            if(temp != None):
                if(dataRecord.sm_batch_id is not None and 
                        temp is not None and dataRecord.sm_batch_id != temp):
                    raise Exception(str((
                        'batch id field(1) does not match batch id set with '
                        'entity(2):',temp,dataRecord.sm_batch_id)))
                dataRecord.sm_batch_id = temp
        
        #dataRecord.save()
        logger.debug(str(('datarecord created:', dataRecord)))
        datapoint_batch = [] 
        for i,value in enumerate(r):
            # NOTE: shall there be an "empty" datapoint? 
            # No, since non-existance of data in the worksheet does not mean
            # "null" will mean "no value entered"
            # TODO: verify/read existing code, ask Dave
            if(value.strip()==''): continue  
            if i in dataColumnList:
                dataColumn = dataColumnList[i]
                dataPoint = _create_datapoint(dataColumn, dataset, dataRecord, value)
                #dataPoint.save()
                datapoint_batch.append(dataPoint)
                pointsSaved += 1
        datarecord_batch.append((dataRecord,datapoint_batch))
        rowsRead += 1
        
        if(rowsRead % save_interval == 0 ):
            bulk_create_datarecords(datarecord_batch)
            logger.debug(str((
                "created datarecord_batch, rowsRead", rowsRead, "time:", 
                time.time() - loopStart )))
            count = bulk_create_datapoints(datarecord_batch)
            logger.debug(str(('createded dps',count)))
            datarecord_batch=[]

    bulk_create_datarecords(datarecord_batch)
    logger.debug(str((
        "created datarecord_batch, rowsRead", rowsRead, "time:", 
        time.time() - loopStart )))

    count = bulk_create_datapoints(datarecord_batch)
    logger.debug(str(('createded dps',count)))

    print 'Finished reading, rowsRead: ', rowsRead, ', points Saved: ', pointsSaved
    et = time.time()-loopStart
    print'elapsed: ',et , 'avg: ', et/rowsRead

def _create_datapoint(dataColumn, dataset, dataRecord, value):
    dataPoint = None
    # TODO: define allowed "types" for the input sheet 
    # (this is listed in current SS code, but we may want to rework)
    if (dataColumn.data_type == 'Numeric'): 
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
    elif (dataColumn.data_type == 'omero_image'): 
        dataPoint = DataPoint(datacolumn=dataColumn,
                              dataset = dataset,
                              datarecord = dataRecord,
                              int_value=util.convertdata(value,int))
    else: # ONLY text, for now, we'll need to define the allowed types, next!
        dataPoint = DataPoint(datacolumn=dataColumn,
                              dataset = dataset,
                              datarecord = dataRecord,
                              text_value=util.convertdata(value))
    return dataPoint

def _read_protein(map_column,r,current_row, dr):
    '''
    @param r row
    @param dr dataRecord
    '''
    try:
        value = util.convertdata(r[map_column].strip())
        if(value != None and value != '' ):
            facility_id = r[map_column]
            facility_id = util.convertdata(facility_id,int) 
            dr.protein = Protein.objects.get(lincs_id=facility_id) 
    except Exception, e:
        logger.error(str((
            "Invalid Protein facility id: ", value,'row',current_row, e)))
        raise


def _read_other_reagent(map_column,r,current_row, dr):
    '''
    @param r row
    @param dr dataRecord
    '''

    try:
        value = util.convertdata(r[map_column].strip())
        facility_id = None
        if(value != None and value != '' ):
            facility_id = util.convertdata(value,int) 
            dr.otherreagent = OtherReagent.objects.get(facility_id=facility_id) 
    except Exception, e:
        logger.error(str((
            "Invalid OtherReagent facility id: ", facility_id,'row',current_row, e)))
        raise    

def _read_antibody(map_column,r,current_row, dr):
    '''
    @param r row
    @param dr dataRecord
    '''

    try:
        value = util.convertdata(r[map_column].strip())
        facility_id = None
        if(value != None and value != '' ):
            facility_id = util.convertdata(value,int) 
            dr.antibody = Antibody.objects.get(facility_id=facility_id) 
    except Exception, e:
        logger.error(str((
            "Invalid Antibody facility id: ", facility_id,'row',current_row, e)))
        raise    

def _read_cell(map_column,r,current_row, dr):
    '''
    @param r row
    @param dr dataRecord
    '''
    try:
        value = util.convertdata(r[map_column].strip())
        facility_id = None
        if(value != None and value != '' ):
            value = value.split("-")
            facility_id = util.convertdata(value[0],int) 
            dr.cell = Cell.objects.get(facility_id=facility_id) 
            if(len(value)>1):
                dr.cell_batch_id = util.convertdata(value[1],int)
                # TODO: validate that the batch exists? 
    except Exception, e:
        logger.error(str(("Invalid Cell facility id: ", facility_id,
                          'row',current_row, e)))
        raise    
    

def _read_small_molecule_batch(map_column,r,current_row, dr):
    '''
    @param r row
    @param dr dataRecord
    '''
    try:
        value = util.convertdata(r[map_column].strip())
        if(value != None and value != '' ):
            value = value.split("-")
            if len(value) < 2: 
                raise Exception('Small Molecule (Batch) format is '
                                '#####-###(-#) **Note that (batch) is optional')
            x = value[0]
            facility = util.convertdata(x,int) 
            salt = value[1]
            try:
                dr.smallmolecule = SmallMolecule.objects.get(
                    facility_id=facility, salt_id=salt)
            except Exception, e:
                logger.error(str(('could not locate small molecule:', 
                                  facility,e)))
                raise
            if(len(value)>2):
                dr.sm_batch_id = util.convertdata(value[2],int)
                # TODO: validate that the batch exists?  (would need to
                # do for all types, not just Small Molecule
    except Exception, e:
        logger.error(str((
            "Invalid Small Molecule (or batch) identifiers: ", value, 
            'row',current_row,e)))
        raise    
    

def _read_plate_well(map_column,r,current_row, dr):
    '''
    @param r row
    @param dr dataRecord
    '''
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
                raise Exception(str((
                    'Must define both plate and well (not just plate), row', 
                    current_row)))
                
            dr.plate = plate_id
            dr.well = well_id
            try:
                # TODO: 
                # What if the plate/well does not correlate to a 
                # librarymapping?  
                # i.e. if this is the plate/well for a cell/protein study?
                # For now, the effect of the following logic is that 
                # plate/well either maps a librarymapping, or is a an 
                # arbitrary plate/well.
                dr.library_mapping = \
                    LibraryMapping.objects.get(plate=plate_id,well=well_id)
                if(dr.smallmolecule != None):
                    if(dr.smallmolecule != None and 
                       dr.library_mapping.smallmolecule_batch != None and 
                       (dr.smallmolecule != 
                           dr.library_mapping.smallmolecule_batch.smallmolecule)):
                        raise Exception(str((
                            'SmallMolecule does not match the '
                            'libraryMapping.smallmolecule_batch.smallmolecule '
                            'pointed to by the plate/well:'
                            ,plate_id,well_id,
                            dr.smallmolecule,
                            dr.library_mapping.smallmolecule_batch.smallmolecule,
                            r,'row',current_row)))
                elif(dr.library_mapping.smallmolecule_batch != None):
                    dr.smallmolecule = \
                        dr.library_mapping.smallmolecule_batch.smallmolecule
            except ObjectDoesNotExist, e:
                logger.warn(str((
                    'No librarymapping defined (plate/well do not point to a '
                    'librarymapping), row', current_row))) 
    except Exception, e:
        logger.error(str(("Invalid plate/well identifiers",plate_id,well_id,r,
            e,'row',current_row,e)))
        raise e
        
    
@transaction.commit_on_success
def bulk_create_datapoints(datarecord_batch):
    datapoint_id_start = DataPoint.objects.all().aggregate(
        models.Max('id'))['id__max']
    if(not isinstance(datapoint_id_start ,int)): datapoint_id_start = 0
    datapoint_id_start +=1
    datapoint_list = []
    for j, (datarecord,datapoints) in enumerate(datarecord_batch):
        for i,datapoint in enumerate(datapoints): 
            datapoint.datarecord = datarecord
        datapoint_id_start += len(datapoints)
        datapoint_list.extend(datapoints)
    DataPoint.objects.bulk_create(datapoint_list)
    return len(datapoint_list)

@transaction.commit_on_success
def bulk_create_datarecords(datarecord_batch):
    datarecord_id_start = DataRecord.objects.all().aggregate(
        models.Max('id'))['id__max']
    if(not isinstance(datarecord_id_start ,int)): datarecord_id_start = 0
    datarecord_id_start +=1
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
    if args.verbose:
        # NOTE: when running with the django settings file, the logging 
        # configured there will augment this, and 
        # cause double logging. So this will manually override that.
        # Probably a better solution would be to configure this utility as a
        # "management command"
        logging.basicConfig(level=log_level, 
            format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')   
        logger.setLevel(log_level)

    print 'importing ', args.inputFile
    main(args.inputFile)
    
