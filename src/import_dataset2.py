import argparse
import import_utils as util
import init_utils as iu
import logging
import re
import time;  
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction, models
import xlrd
from xlrd.book import colname

from db.models import DataSet, DataColumn, DataRecord, DataPoint, \
        LibraryMapping, AntibodyBatch, OtherReagent, SmallMoleculeBatch, \
        OtherReagentBatch, ProteinBatch, CellBatch, camel_case_dwg
import time;  

logger = logging.getLogger(__name__)

reagents_read_hash = {}

default_reagent_columns = {
    'Small Molecule Batch': {
        'display_order': 1,
        'name': 'smallMolecule',
        'display_name': 'Small Molecule',
        'data_type': 'small_molecule',
        'description': 'A Small Molecule reagent',
        'comments': 'A Small Molecule reagent'
    },
    'Cell': {
        'display_order': 2,
        'name': 'cell',
        'display_name': 'Cell',
        'data_type': 'cell',
        'description': 'A Cell reagent',
        'comments': 'A Cell reagent'
    },
    'Protein': {
        'display_order': 3,
        'name': 'protein',
        'display_name': 'Protein',
        'data_type': 'protein',
        'description': 'A Protein reagent',
        'comments': 'A Protein reagent'
    },
    'Antibody': {
        'display_order': 3,
        'name': 'antibody',
        'display_name': 'Antibody',
        'data_type': 'antibody',
        'description': 'An Antibody reagent',
        'comments': 'An Antibody reagent'
    },
    'OtherReagent': {
        'display_order': 3,
        'name': 'otherReagent',
        'display_name': 'Other Reagent',
        'data_type': 'otherreagent',
        'description': 'Other reagent',
        'comments': 'Other reagent'
    }
}

meta_columns = {'Control Type':-1, 'Plate': -1, 'Well': -1} 

DEFAULT_CONVERTER=re.compile(r'[\W]+')
def default_converter(original_text, sep='_'):
    temp = DEFAULT_CONVERTER.sub(' ', original_text)
    return sep.join(temp.lower().split())      

def int_for_col(name, i=0):
    name = name.upper()
    val = ord(name[-1])-ord('A')
    if i > 0:
        val = (val+1) * 26**i
    if len(name) > 1:
        val += int_for_col(name[:-1],i+1)
    return val

def col_for_int(i):
    # note use equivalent xlrd.book.colname
    exp = i/26
    val = i%26
    letter = chr(ord('A')+val)
    if exp > 0:
        letter = col_for_int(exp-1) + letter
    return letter
 
def read_metadata(meta_sheet):

    properties = ('model_field', 'required', 'default', 'converter')
    field_definitions = {
        'Lead Screener First': 'lead_screener_firstname',
        'Lead Screener Last': 'lead_screener_lastname',
        'Lead Screener Email': 'lead_screener_email',
        'Lab Head First': 'lab_head_firstname',
        'Lab Head Last': 'lab_head_lastname',
        'Lab Head Email': 'lab_head_email',
        'Title': 'title',
        'Facility ID': (
            'facility_id', True, None, lambda x: util.convertdata(x, int)),
        'Summary': 'summary',
        'Protocol': 'protocol',
        'References': 'protocol_references',
        'Date Data Received':(
            'date_data_received', False, None, util.date_converter),
        'Date Loaded': ('date_loaded', False, None, util.date_converter),
        'Date Publicly Available': (
            'date_publicly_available', False, None, util.date_converter),
        'Most Recent Update': (
            'date_updated', False, None, util.date_converter),
        'Is Restricted':('is_restricted', False, False, util.bool_converter),
        'Dataset Type':('dataset_type', False),
        'Bioassay':('bioassay', False),
        'Dataset Keywords':('dataset_keywords', False),
        'Usage Message':('usage_message', False),
        'Associated Publication': ('associated_publication', False),
        'Associated Project Summary': ('associated_project_summary', False),
    }
    
    sheet_labels = []
    for i in xrange(meta_sheet.nrows-1):
        row = meta_sheet.row_values(i+1)
        sheet_labels.append(row[0])

    field_definitions = util.fill_in_column_definitions(
        properties, field_definitions)

    cols = util.find_columns(field_definitions, sheet_labels,
        all_column_definitions_required=False)
    
    initializer = {}
    for i in xrange(meta_sheet.nrows-1):
        row = meta_sheet.row_values(i+1)
        
        properties = cols[i]
        value = row[1]
        logger.debug('Metadata raw value %r' % value)

        required = properties['required']
        default = properties['default']
        converter = properties['converter']
        model_field = properties['model_field']

        if converter:
            value = converter(value)
        if not value and default != None:
            value = default
        if not value and required:
            raise Exception(
                'Field is required: %s, record: %d' 
                    % (properties['column_label'], row))
        logger.debug('model_field: %s, value: %r' % ( model_field, value ) )
        initializer[model_field] = value

    return initializer 

def read_datacolumns(book):
    '''
    @return an array of data column definition dicts 
    '''
    
    data_column_sheet = book.sheet_by_name('Data Columns')
    
    labels = {
        'Worksheet Column':'worksheet_column',
        '"Data" Worksheet Column':'worksheet_column',
        'Display Order':'display_order',
        'Display Name':'display_name',
        'Name':'name',
        'Data Type':'data_type',
        'Decimal Places':'precision',
        'Description':'description',
        'Replicate Number':'replicate',
        'Unit':'unit', 
        'Assay readout type':'readout_type',
        'Comments':'comments',
    }

    dc_definitions = []
    datacolumn_fields = util.get_fields(DataColumn)
    type_lookup = dict((f.name, iu.totype(f)) for f in datacolumn_fields)
    logger.debug('datacolumn type lookups: %s' % type_lookup)
    required_labels = ['name', 'data_type']

    logger.info('read the data column definitions...')
    for i in xrange(data_column_sheet.nrows):
        row_values = data_column_sheet.row_values(i)
        
        if i == 0:
            for val in row_values[1:]:
                dc_definitions.append({})
        
        label_read = row_values[0]
        
        recognized_label = next(
            (field_name for label, field_name in labels.items() 
                if label_read and label.lower() == label_read.lower() ), None)
        
        if recognized_label:
            
            logger.debug(
                'label: %r, recognized_label: %r' % (label_read, recognized_label))
            
            for j,val in enumerate(row_values[1:]):
                dc_dict = dc_definitions[j]

                logger.debug('data column %s:%d:%d:%r' 
                    % ( recognized_label, i, j, val))
                
                final_val = util.convertdata(
                    val,type_lookup.get(recognized_label, None)) 
                
                if final_val != None:
                    dc_dict[recognized_label] = final_val
                    if recognized_label == 'display_order':
                        # add 10 to the order, so default reagent cols can go first
                        dc_dict['display_order'] = (
                            dc_dict['display_order'] + 10)
                    if recognized_label == 'name':
                        # split on non-alphanumeric chars
                        temp = re.split(r'[^a-zA-Z0-9]+',dc_dict['name'])
                        # convert, if needed
                        if len(temp) > 1:
                            dc_dict['name'] = camel_case_dwg(dc_dict['name'])
                else:
                    if recognized_label in required_labels:
                        raise Exception(
                            'Error, data column field is required: %s, col: %r'
                                % ( recognized_label, colname(j+1) ) )
        else:
            logger.debug(
                'unrecognized label in "Data Columns" sheet %r' % label_read)
    
    for dc_dict in dc_definitions:
        for label in required_labels:
            if label not in dc_dict:
                raise Exception(
                    'required "Data Column" label not defined %r' % label)

    logger.info('find the data columns on the "Data" sheet...')           

    data_sheet = book.sheet_by_name('Data')
    data_sheet_labels = data_sheet.row_values(0)
    dc_definitions_found = []
    data_labels_found = []
    for i,data_label in enumerate(data_sheet_labels):
        
        if not data_label or not data_label.strip():
            logger.info('break on data sheet col %d, blank' % i)
            break
        
        data_label = data_label.upper()
        col_letter = colname(i)
        
        for dc_dict in dc_definitions:
            _dict = None
            if 'worksheet_column' in dc_dict:
                
                v = dc_dict['worksheet_column']
                if v.upper() == col_letter:
                    data_labels_found.append(i)
                    dc_definitions_found.append(dc_dict)
                    _dict = dc_dict
                    
            elif 'name' in dc_dict or 'display_name' in dc_dict:
            
                if ( dc_dict.get('name', '').upper() == data_label
                    or dc_dict.get('display_name', '').upper() == data_label):
                    
                    dc_dict['worksheet_column'] = col_letter
                    data_labels_found.append(i)
                    dc_definitions_found.append(dc_dict)
                    _dict = dc_dict
                    
            if _dict and 'display_order' not in _dict:
            
                _dict['display_order'] = i+10
                logger.warn(
                    'auto assigning "display_order" for col %r as %d' 
                        % (_dict['name'], i+10))

        if i not in data_labels_found:
        
            logger.debug( ( 
                'Data sheet label not found %r,'
                ' looking in default reagent definitions %s' )
                     % ( data_label, default_reagent_columns.keys() ) )
            
            for key,dc_dict in default_reagent_columns.items():
                if (key.upper() == data_label 
                    or dc_dict.get('name', '').upper() == data_label
                    or dc_dict.get('display_name', '').upper() == data_label):
                    
                    dc_dict['worksheet_column'] = col_letter
                    data_labels_found.append(i)
                    dc_definitions_found.append(dc_dict)
    
    data_labels_not_found = [ 
        data_label for i,data_label in enumerate(data_sheet_labels) 
            if data_label and data_label.strip() 
            and i not in data_labels_found and data_label not in meta_columns ]
    if data_labels_not_found:
        logger.warn(
            'data sheet labels not recognized %s' % data_labels_not_found )

    # for legacy datasets: make sure the small molecule column 1 is always created
    small_mol_col = None
    for dc_dict in dc_definitions_found:
        if dc_dict['data_type'] == 'small_molecule':
            small_mol_col = dc_dict
            break
    if not small_mol_col:
        dc_definitions_found.append(default_reagent_columns['Small Molecule Batch'])
        
    logger.info('data column definitions found: %s' 
        % [x['display_name'] for x in dc_definitions_found])

    return dc_definitions_found


def main(path):
    
    datarecord_batch = []
    save_interval = 1000

    logger.debug('read metadata...')
    book = xlrd.open_workbook(path)

    dataset = None

    metadata = read_metadata(book.sheet_by_name('Meta'))
    try:
        extant_dataset = DataSet.objects.get( facility_id=metadata['facility_id'] )
        if(extant_dataset):
            logger.warn(
                'deleting extant dataset for facility id: %r' 
                    % metadata['facility_id'] )
            extant_dataset.delete()
    except ObjectDoesNotExist, e:
        pass
    except Exception,e:
        logger.exception(
            'on delete of extant dataset: %r' % metadata['facility_id'])
        raise

    dataset = DataSet(**metadata)
    logger.info('dataset to save %s' % dataset)
    dataset.save()
    
    logger.debug('read data columns...')
    col_to_definitions = read_datacolumns(book)

    small_molecule_col = None
    col_to_dc_map = {}
    for i,dc_definition in enumerate(col_to_definitions):
        dc_definition['dataset'] = dataset
        if (not 'display_order' in dc_definition 
                or dc_definition['display_order']==None): 
            dc_definition['display_order']=i
        datacolumn = DataColumn(**dc_definition)
        datacolumn.save()
        if not small_molecule_col and datacolumn.data_type == 'small_molecule':
            small_molecule_col = datacolumn
        logger.debug('datacolumn created: %r' % datacolumn)
        if datacolumn.worksheet_column:
            col_to_dc_map[int_for_col(datacolumn.worksheet_column)] = datacolumn    
    logger.debug('final data columns: %s' % col_to_dc_map)

    logger.debug('read the Data sheet')
    data_sheet = book.sheet_by_name('Data')
    
    for i,label in enumerate(data_sheet.row_values(0)):
        logger.debug('find datasheet label %r:%r' % (colname(i), label))
        if label in meta_columns: 
            meta_columns[label] = i
            continue
    
    logger.debug('meta_columns: %s, datacolumnList: %s' 
        % (meta_columns, col_to_dc_map) )
    
    logger.debug('read the data sheet, save_interval: %d' % save_interval)
    loopStart = time.time()
    pointsSaved = 0
    rows_read = 0
    col_to_dc_items = col_to_dc_map.items()

    for i in xrange(data_sheet.nrows-1):
        current_row = i + 2
        row = data_sheet.row_values(i+1)    

        r = util.make_row(row)
        datarecord = DataRecord(dataset=dataset)
        
        if meta_columns['Control Type'] > -1: 
            datarecord.control_type = util.convertdata(
                r[meta_columns['Control Type']])

        datapoint_batch = []
        small_molecule_datapoint = None 
        for i,dc in col_to_dc_items:
            value = r[i]
            logger.debug(
                'reading column %r, %s, val: %r' % (colname(i), dc, value))
            value = value.strip()
            value = util.convertdata(value)
            if not value: 
                continue
            datapoint = _create_datapoint(dc, dataset, datarecord, value)
            datapoint_batch.append(datapoint)
            pointsSaved += 1
            if not small_molecule_datapoint and dc.data_type == 'small_molecule':
                small_molecule_datapoint = datapoint
                
        if meta_columns['Plate'] > -1:
            _read_plate_well(meta_columns['Plate'], r, current_row, 
                datarecord,small_molecule_col,small_molecule_datapoint,datapoint_batch)
        
        
        datarecord_batch.append((datarecord, datapoint_batch))
        rows_read += 1
        
        if (rows_read % save_interval == 0):
            bulk_create_datarecords(datarecord_batch)
            logger.debug(
                'datarecord batch created, rows_read: %d , time (ms): %d'
                    % (rows_read, time.time()-loopStart ) )
            count = bulk_create_datapoints(datarecord_batch)
            logger.debug('datapoints created in batch: %d ' % count)
            datarecord_batch=[]

    bulk_create_datarecords(datarecord_batch)
    et = time.time()-loopStart
    logger.debug(
        'final datarecord batch created, rows_read: %d, time (ms): %d' 
            % (rows_read, et))

    count = bulk_create_datapoints(datarecord_batch)
    logger.debug('created dps %d' % count )

    print 'Finished reading, rows_read: ', rows_read, ', points Saved: ', pointsSaved
    print 'elapsed: ', et , 'avg: ', et/rows_read
    
    cleanup_unused_datacolumns(dataset)

def cleanup_unused_datacolumns(dataset):
    for dc in DataColumn.objects.all().filter(dataset=dataset):
        if not dc.datapoint_set.all().exists():
            print 'removing unused datacolumn (no values stored): %r' % dc
            dc.delete()


def _create_datapoint(datacolumn, dataset, datarecord, value):
    
    datapoint = None
    
    if datacolumn.data_type == 'Numeric': 
        if datacolumn.precision != 0: 
            datapoint = DataPoint(datacolumn = datacolumn,
                                  dataset = dataset,
                                  datarecord = datarecord,
                                  float_value=util.convertdata(value, float))
        else:
            datapoint = DataPoint(datacolumn=datacolumn,
                                  dataset = dataset,
                                  datarecord = datarecord,
                                  int_value=util.convertdata(value, int))
    elif datacolumn.data_type == 'omero_image': 
        datapoint = DataPoint(datacolumn=datacolumn,
                              dataset = dataset,
                              datarecord = datarecord,
                              int_value=util.convertdata(value, int))
    else: 
        logger.debug(
            'create datapoint for %r, datarecord: %s' % (value, datarecord))
        datapoint = DataPoint(datacolumn=datacolumn,
                              dataset = dataset,
                              datarecord = datarecord,
                              text_value=util.convertdata(value))
        if datacolumn.data_type == 'small_molecule':
            _read_small_molecule(dataset, datapoint)
        elif datacolumn.data_type == 'protein':
            _read_protein(dataset, datapoint)
        elif datacolumn.data_type == 'antibody':
            _read_antibody(dataset, datapoint)
        elif datacolumn.data_type == 'otherreagent':
            _read_other_reagent(dataset, datapoint)
        elif datacolumn.data_type == 'cell':
            _read_cell_batch(dataset, datapoint)

    return datapoint

def _read_protein(dataset, datapoint):

    try:
        text_value = datapoint.text_value
        if '-' not in text_value:
            # TODO: convert ID to "HMSL####", this int conversion unneeded then 
            text_value = str(util.convertdata(text_value, int))
            datapoint.text_value = text_value

        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('already read in the reagent %r' % text_value)
            return
        value = text_value.split("-")
        facility_id = util.convertdata(value[0], int) 
        batch_id = 0
        if len(value)>1:
            batch_id = util.convertdata(value[1], int)
        reagentbatch = ProteinBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id = batch_id ) 
        dataset.proteins.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid Protein identifiers: %r" % text_value)
        raise    

def _read_other_reagent(dataset, datapoint):

    try:
        text_value = datapoint.text_value
        if '-' not in text_value:
            # TODO: convert ID to "HMSL####", this int conversion unneeded then 
            text_value = str(util.convertdata(text_value, int))
            datapoint.text_value = text_value

        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('already read in the reagent %r' % text_value)
            return
        value = text_value.split("-")
        facility_id = util.convertdata(value[0], int) 
        batch_id = 0
        if len(value)>1:
            batch_id = util.convertdata(value[1], int)
        reagentbatch = OtherReagentBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id=batch_id) 
        dataset.other_reagents.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid OtherReagent identifiers: %r" % text_value)
        raise    

def _read_antibody(dataset, datapoint):

    try:
        text_value = datapoint.text_value
        if '-' not in text_value:
            # TODO: convert ID to "HMSL####", this int conversion unneeded then 
            text_value = str(util.convertdata(text_value, int))
            datapoint.text_value = text_value

        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('already read in the reagent %r' % text_value)
            return
        value = text_value.split("-")
        facility_id = util.convertdata(value[0], int) 
        batch_id = 0
        if len(value)>1:
            batch_id = util.convertdata(value[1], int)
        reagentbatch = AntibodyBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id=batch_id) 
        dataset.antibodies.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid Antibody identifiers: %r" % text_value)
        raise    

def _read_cell_batch(dataset, datapoint):

    try:
        text_value = datapoint.text_value
        if '-' not in text_value:
            # TODO: convert ID to "HMSL####", this int conversion unneeded then 
            text_value = str(util.convertdata(text_value, int))
            datapoint.text_value = text_value

        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('already read in the reagent %r' % text_value)
            return
        value = text_value.split("-")
        facility_id = util.convertdata(value[0], int) 
        batch_id = 0
        if len(value)>1:
            batch_id = util.convertdata(value[1], int)
            # TODO: validate that the batch exists? 
        reagentbatch = CellBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id=batch_id) 
        dataset.cells.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid Cell identifiers: %r" % text_value)
        raise    
    
def _read_small_molecule(dataset, datapoint):
    
    text_value = datapoint.text_value

    if text_value in reagents_read_hash:
        datapoint.reagent_batch = reagents_read_hash[text_value]
        logger.debug('smb reagent already read in: %r' % text_value)
        return
    
    value = text_value.split("-")
    if len(value) < 2: 
        raise Exception( (
            'Invalid value: %r, '
            'Small Molecule (Batch) format is '
            '#####-###(-#) **Note that (batch) is optional')
            % text_value )
        
    facility = util.convertdata(value[0], int) 
    salt = util.convertdata(value[1], int)
    batch_id = 0
    if len(value)>2:
        batch_id = util.convertdata(value[2], int)
    
    try:
        reagentbatch = SmallMoleculeBatch.objects.get(
            reagent__facility_id=facility, reagent__salt_id=salt, 
            batch_id=batch_id)
        dataset.small_molecules.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        
        logger.debug('read small molecule batch %s' % reagentbatch )
        reagents_read_hash[text_value] = reagentbatch
    
    except Exception, e:
        logger.exception(
            'could not locate small molecule batch for %r' % text_value)
        raise

def _read_plate_well(map_column, r, current_row, dr, small_mol_col,
        small_molecule_datapoint,datapoint_batch):

    plate_id=None
    well_id=None
    try:
        value = util.convertdata(r[map_column].strip())
        if (value != None and value != ''):
            plate_id = util.convertdata(value, int)
         
            value = util.convertdata(r[map_column+1].strip())
            if (value != None and value != '' ):
                well_id = value 
            else:
                raise Exception(
                    'Must define both plate and well (not just plate), row: %d' 
                        % current_row)
                
            dr.plate = plate_id
            dr.well = well_id
            dr.library_mapping = LibraryMapping.objects.get(
                plate=plate_id, well=well_id)
            
            # Legacy loading use-case:
            # - if small molecule already specified, check that it is the same
            # - if no small molecule specified yet, associate the plate:well
            # small molecule with a datapoint and the dataset
            if(dr.library_mapping.smallmolecule_batch != None):
                if small_molecule_datapoint and small_molecule_datapoint.reagent_batch:
                    if small_molecule_datapoint.reagent_batch != dr.library_mapping.smallmolecule_batch:
                        raise Exception((
                            'plate:well entry %s '
                            'does not match small molecule %r, row: %s')
                            % (well_id, dr.library_mapping.smallmolecule_batch, current_row))
                else:
                    dr.dataset.small_molecules.add(dr.library_mapping.smallmolecule_batch)
                    text_value = dr.library_mapping.smallmolecule_batch.reagent.facility_id
                    text_value += '-%s' % dr.library_mapping.smallmolecule_batch.reagent.salt_id
                    if dr.library_mapping.smallmolecule_batch.batch_id != 0:
                        text_value += '-%s' % dr.library_mapping.smallmolecule_batch.batch_id
                    datapoint = DataPoint(datacolumn=small_mol_col,
                                      dataset = dr.dataset,
                                      datarecord = dr,
                                      reagent_batch=dr.library_mapping.smallmolecule_batch,
                                      text_value=text_value)
                    datapoint_batch.append(datapoint)
    except Exception, e:
        logger.exception(
            ('Invalid plate/row information, '
            'plate: %r, well: %r, data: %s, row_number: %d')
            % ( plate_id,well_id, r, current_row ))
        raise e
    
@transaction.commit_on_success
def bulk_create_datapoints(datarecord_batch):

    datapoint_id_start = DataPoint.objects.all().aggregate(
        models.Max('id'))['id__max']
    
    if not isinstance(datapoint_id_start , int): 
        datapoint_id_start = 0
    
    datapoint_id_start +=1
    datapoint_list = []
    for j,(datarecord,datapoints) in enumerate(datarecord_batch):
        for i, datapoint in enumerate(datapoints): 
            datapoint.datarecord = datarecord
        datapoint_id_start += len(datapoints)
        datapoint_list.extend(datapoints)
    
    DataPoint.objects.bulk_create(datapoint_list)
    
    return len(datapoint_list)

@transaction.commit_on_success
def bulk_create_datarecords(datarecord_batch):

    datarecord_id_start = (
        DataRecord.objects.all()
            .aggregate(models.Max('id'))['id__max'])
    
    if not isinstance(datarecord_id_start , int): 
        datarecord_id_start = 0
    
    datarecord_id_start +=1
    for j,(datarecord,datapoints) in enumerate(datarecord_batch):
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
    if args.inputFile is None:
        parser.print_help();
        parser.exit(0, "\nMust define the FILE param.\n")

    log_level = logging.WARNING 
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
    
