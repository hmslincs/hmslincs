import logging
import re
import time;  

import import_utils as util
import init_utils as iu

import argparse
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction, models
import xlrd
from xlrd.biffh import XLRDError
from xlrd.book import colname

from db.models import DataSet, DataColumn, DataRecord, DataPoint, \
        LibraryMapping, AntibodyBatch, OtherReagent, SmallMoleculeBatch, \
        OtherReagentBatch, ProteinBatch, CellBatch, PrimaryCellBatch, \
        DiffCellBatch, IpscBatch, EsCellBatch, UnclassifiedBatch, DatasetProperty, \
        ReagentBatch, camel_case_dwg 


logger = logging.getLogger(__name__)

reagents_read_hash = {}
sm_reagents_hash = {}

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
        'display_name': 'Cell Line',
        'data_type': 'cell',
        'description': 'A Cell Line reagent',
        'comments': 'A Cell Line reagent'
    },
    'PrimaryCell': {
        'display_order': 2,
        'name': 'primarycell',
        'display_name': 'Primary Cell',
        'data_type': 'primary_cell',
        'description': 'A Primary Cell reagent',
        'comments': 'A Primary Cell reagent'
    },
    'IPSC': {
        'display_order': 2,
        'name': 'ipsc',
        'display_name': 'IPSC',
        'data_type': 'ipsc',
        'description': 'An induced pluripotent stem cell reagent',
        'comments': 'An induced pluripotent stem cell reagent'
    },
    'EsCell': {
        'display_order': 2,
        'name': 'escell',
        'display_name': 'Embryonic Stem Cell',
        'data_type': 'es_cell',
        'description': 'An embryonic stem cell reagent',
        'comments': 'An embryonic stem cell reagent'
    },
    'DiffCell': {
        'display_order': 2,
        'name': 'diffcell',
        'display_name': 'Differentiated Cell',
        'data_type': 'diff_cell',
        'description': 'A Differentiated Cell reagent',
        'comments': 'A Differentiated Cell reagent'
    },
    'Antibody': {
        'display_order': 3,
        'name': 'antibody',
        'display_name': 'Antibody',
        'data_type': 'antibody',
        'description': 'An Antibody reagent',
        'comments': 'An Antibody reagent'
    },
    'Protein': {
        'display_order': 5,
        'name': 'protein',
        'display_name': 'Protein',
        'data_type': 'protein',
        'description': 'A Protein reagent',
        'comments': 'A Protein reagent'
    },
    'OtherReagent': {
        'display_order': 3,
        'name': 'otherReagent',
        'display_name': 'Other Reagent',
        'data_type': 'other_reagent',
        'description': 'Other reagent',
        'comments': 'Other reagent'
    },
    'UnclassifiedPerturbagen': {
        'display_order': 3,
        'name': 'unclassifiedPerturbagen',
        'display_name': 'Unclassified Perturbagen',
        'data_type': 'unclassified',
        'description': 'Unclassified Perturbagen',
        'comments': 'Unclassified Perturbagen'
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

def read_string(cell):
    value = cell.value
    if value is None:
        return None
    elif cell.ctype == xlrd.XL_CELL_NUMBER:
        ival = int(value)
        if value == ival:
            value = ival
        return str(value)
    else:
        value = str(value).strip()
        if not value:
            return None
        return value

def main(path):
    
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
    
    read_dataset_properties(book, 'metadata', dataset)
    
    read_datacolumns_and_data(book, dataset)
    
    read_explicit_reagents(book, dataset)

    dataset.save()

def read_dataset_properties(book, sheetname, dataset):
    
    sheet = None
    for name in book.sheet_names():
        if name.lower() == sheetname.lower():
            sheet = book.sheet_by_name(name)
            break
    if sheet is None:
        logger.warn('No sheet found: %r', sheetname)
        return None
    
    properties = []
    for i in xrange(sheet.nrows):
        row = sheet.row_values(i)
        name = row[0]
        type = name.split('_')[0]
        value = row[1]
        if isinstance(value, (int, float)):
            if float(int(value)) == float(value):
                value = int(value)
        
        dsProperty = DatasetProperty.objects.create(
            dataset=dataset,
            type=type,
            name=row[0],
            value=value, 
            ordinal=i )
        dsProperty.save()
        logger.debug('created property %r', dsProperty)
    logger.info('Sheet: %r rows read: %d', sheetname, len(properties))
    return properties

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
        'Dataset Data URL':('dataset_data_url', False),
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

def read_datacolumns_and_data(book, dataset):

    logger.debug('read data columns and data...')
    try:
        data_column_sheet = book.sheet_by_name('Data Columns')
    except XLRDError, e:
        logger.info('no "Data Columns" sheet found')
        return None
    
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
    logger.info('dc_definitions: %r', dc_definitions)
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

    
    col_to_dc_map = {}
    first_small_molecule_column = None
    for i,dc_definition in enumerate(dc_definitions_found):
        dc_definition['dataset'] = dataset
        if (not 'display_order' in dc_definition 
                or dc_definition['display_order']==None): 
            dc_definition['display_order']=i
        datacolumn = DataColumn(**dc_definition)
        datacolumn.save()
        if not first_small_molecule_column and datacolumn.data_type == 'small_molecule':
            first_small_molecule_column = datacolumn
        logger.debug('datacolumn created: %r' % datacolumn)
        if datacolumn.worksheet_column:
            col_to_dc_map[int_for_col(datacolumn.worksheet_column)] = datacolumn    
    logger.debug('final data columns: %s' % col_to_dc_map)

    read_data(book, col_to_dc_map, first_small_molecule_column, dataset)

def read_explicit_reagents(book, dataset):
    
    try:
        reagents_sheet = book.sheet_by_name('Reagents')
        for row in range(1,reagents_sheet.nrows):
            facility_batch_id = read_string(reagents_sheet.cell(row,0))
            vals = [
                 util.convertdata(x,int) for x in facility_batch_id.split('-')]
            
            logger.info('facility_batch_id: %r', vals)
            
            if len(vals)>3:
                raise Exception(
                    'Reagent id has too many values: %r', facility_batch_id)
            
            if (len(vals)==3):
                smb = SmallMoleculeBatch.objects.get(
                    reagent__facility_id=vals[0],
                    reagent__salt_id=vals[1],
                    batch_id=vals[2])
                logger.info('small molecule batch found: %r', smb)
                dataset.small_molecules.add(smb)
            else:
                if len(vals)==2:
                    if len(str(vals[1]))==3:
                        smb = SmallMoleculeBatch.objects.get(
                            reagent__facility_id=vals[0],
                            reagent__salt_id=vals[1],
                            batch_id=0)
                        logger.info('small molecule batch found: %r', smb)
                        dataset.small_molecules.add(smb)
                        continue
                    
                    rb = ReagentBatch.objects.get(
                        reagent__facility_id=vals[0],
                        batch_id=vals[1])
                else:
                    rb = ReagentBatch.objects.get(
                        reagent__facility_id=vals[0],
                        batch_id=0)
                if hasattr(rb,'antibodybatch'):
                    logger.info('antibody reagent found: %r', rb)
                    dataset.antibodies.add(rb.antibodybatch)
                elif hasattr(rb, 'cellbatch'):
                    logger.info('cell reagent found: %r', rb)
                    dataset.cells.add(rb.cellbatch)
                elif hasattr(rb, 'otherreagentbatch'):
                    logger.info('other_reagent reagent found: %r', rb)
                    dataset.other_reagents.add(rb.otherreagentbatch)
                elif hasattr(rb, 'unclassifiedbatch'):
                    logger.info('unclassified reagent found: %r', rb)
                    dataset.unclassified_perturbagens.add(rb.unclassifiedbatch)
                elif hasattr(rb, 'primarycellbatch'):
                    logger.info('primary cell reagent found: %r', rb)
                    dataset.primary_cells.add(rb.primarycellbatch)
                elif hasattr(rb, 'diffcellbatch'):
                    logger.info('differentiated cell reagent found: %r', rb)
                    dataset.diff_cells.add(rb.diffcellbatch)
                elif hasattr(rb, 'ipscbatch'):
                    logger.info('ipsc reagent found: %r', rb)
                    dataset.ipscs.add(rb.ipscbatch)
                elif hasattr(rb, 'escellbatch'):
                    logger.info('embryonic stem cell reagent found: %r', rb)
                    dataset.es_cells.add(rb.escellbatch)
                elif hasattr(rb, 'proteinbatch'):
                    logger.info('protein reagent found: %r', rb)
                    dataset.proteins.add(rb.proteinbatch)
                else:
                    raise Exception('unknown reagent type: %r', rb)
        dataset.save()
    except XLRDError, e:
        logger.info('no "Reagents" sheet found')


def read_data(book, col_to_dc_map, first_small_molecule_column, dataset):

    datarecord_batch = []
    save_interval = 1000

    logger.info('read the Data sheet...')
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
    rows_created = 0
    
    # find 'small_molecule_no_salt' if any
    sm_hmsl_no_salt_col = None
    for i, dc in col_to_dc_map.items():
        if dc.data_type == 'small_molecule_no_salt':
            sm_hmsl_no_salt_col = i
            dc.data_type = 'small_molecule'
            dc.save()
            logger.info('Converting column to small_molecule (with salt) %r', dc)
            # only supports one
            break
            
    def sheet_rows(workbook_sheet):
        for row in xrange(workbook_sheet.nrows):
            yield util.make_row(workbook_sheet.row_values(row))
    
    # Create a generator to insert extra rows for all of the salt versions of the SM
    def sheet_no_salt_rows(_gen, hmsl_column):
        
        for i,row in enumerate(_gen):
            if i == 0:
                yield row
            else:
                facility_id = row[hmsl_column]
    
                if facility_id in sm_reagents_hash:
                    sm_reagents = sm_reagents_hash[facility_id]
                else:
                    query = SmallMoleculeBatch.objects.filter(
                        reagent__facility_id=facility_id, batch_id=0)
                    logger.debug('Found Small Molecules for: %r, %d', facility_id, query.count())
                    if not query.exists():
                        raise ObjectDoesNotExist('Small Molecule for %r not found' % facility_id)
                    else:
                        sm_reagents = [rb for rb in query.all()]
                        sm_reagents_hash[facility_id] = sm_reagents
                for reagentbatch in sm_reagents:
                    
                    facility_salt = facility_id + '-' + reagentbatch.reagent.salt_id
                    
                    new_row = row[:]
                    new_row[hmsl_column] = facility_salt
                    yield new_row
                
    _gen = sheet_rows(data_sheet)
    if sm_hmsl_no_salt_col is not None:
        _gen = sheet_no_salt_rows(_gen, sm_hmsl_no_salt_col)
        
    for i, r in enumerate(_gen):
        if i == 0:
            # Header row
            continue

        datarecord = DataRecord(dataset=dataset)
        
        if meta_columns['Control Type'] > -1: 
            datarecord.control_type = util.convertdata(
                r[meta_columns['Control Type']])

        datapoint_batch = []
        small_molecule_datapoint = None
        for i,dc in col_to_dc_map.items():
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
            _read_plate_well(
                meta_columns['Plate'], r, i, datarecord,
                first_small_molecule_column,small_molecule_datapoint,
                datapoint_batch)
        
        
        datarecord_batch.append((datarecord, datapoint_batch))
        rows_created += 1
        
        if (rows_created % save_interval == 0):
            bulk_create_datarecords(datarecord_batch)
            logger.debug(
                'datarecord batch created, rows_created: %d , time (s): %d'
                    % (rows_created, time.time()-loopStart ) )
            count = bulk_create_datapoints(datarecord_batch)
            datarecord_batch=[]

    bulk_create_datarecords(datarecord_batch)
    et = time.time()-loopStart
    logger.debug(
        'final datarecord batch created, rows_created: %d, time (ms): %d' 
            % (rows_created, et))

    count = bulk_create_datapoints(datarecord_batch)

    print 'Finished reading, rows created: ', rows_created, ', points Saved: ', pointsSaved
    print 'elapsed: ', et , 'avg: ', et/rows_created
    
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
        elif datacolumn.data_type == 'other_reagent':
            _read_other_reagent(dataset, datapoint)
        elif datacolumn.data_type == 'unclassified':
            _read_unclassified(dataset, datapoint)
        elif datacolumn.data_type == 'cell':
            _read_cell_batch(dataset, datapoint)
        elif datacolumn.data_type == 'primary_cell':
            _read_primary_cell_batch(dataset, datapoint)
        elif datacolumn.data_type == 'diff_cell':
            _read_diff_cell_batch(dataset, datapoint)
        elif datacolumn.data_type == 'ipsc':
            _read_ipsc_batch(dataset, datapoint)
        elif datacolumn.data_type == 'es_cell':
            _read_es_cell_batch(dataset, datapoint)
    return datapoint

def _parse_reagent_batch(text_value):
    ''' 
    Split text_value on the dash character, convert each element to an integer
    '''
    vals = [ util.convertdata(x,int) for x in text_value.split('-')]
    if len(vals) > 2:
        raise Exception(
            'invalid reagent-batch ID value, to many identifiers: %r' 
            % text_value)
    facility_id = vals[0]
    batch_id = 0
    if len(vals) == 2:
        batch_id = vals[1]
    parsed_text = '-'.join([str(x) for x in vals])
    return (facility_id,batch_id,parsed_text)
    
def _parse_reagent_salt_batch(text_value):
    ''' 
    Split text_value on the dash character, convert each element to an integer
    '''
    vals = [ util.convertdata(x,int) for x in text_value.split('-')]
    if len(vals) not in [2,3]:
        raise Exception(
            'invalid facility-salt-batch ID value, to many identifiers: %r' 
            % text_value)
    facility_id = vals[0]
    salt_id = vals[1]
    batch_id = 0
    if len(vals) == 3:
        batch_id = vals[2]
    parsed_text = '-'.join([str(x) for x in vals])
    return (facility_id,salt_id,batch_id,parsed_text)
    
def _read_protein(dataset, datapoint):

    try:
        (facility_id,batch_id,text_value) = (
            _parse_reagent_batch(datapoint.text_value))
        datapoint.text_value = text_value
        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('reagent already read: %r' % text_value)
            return
        reagentbatch = ProteinBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id = batch_id ) 
        dataset.proteins.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid Protein identifier: raw val: %r",
            datapoint.text_value)
        raise    

def _read_other_reagent(dataset, datapoint):

    try:
        (facility_id,batch_id,text_value) = (
            _parse_reagent_batch(datapoint.text_value))
        datapoint.text_value = text_value
        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('reagent already read: %r' % text_value)
            return
        reagentbatch = OtherReagentBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id=batch_id) 
        dataset.other_reagents.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid Other Reagent identifier: %r:%r, raw val: %r",
            facility_id,batch_id,text_value)
        raise    

def _read_unclassified(dataset, datapoint):

    try:
        (facility_id,batch_id,text_value) = (
            _parse_reagent_batch(datapoint.text_value))
        datapoint.text_value = text_value
        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('reagent already read: %r' % text_value)
            return
        reagentbatch = UnclassifiedBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id=batch_id) 
        dataset.unclassified_perturbagens.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid Unclassified Perturbagen identifier: %r:%r, raw val: %r",
            facility_id,batch_id,text_value)
        raise    

def _read_antibody(dataset, datapoint):

    try:
        (facility_id,batch_id,text_value) = (
            _parse_reagent_batch(datapoint.text_value))
        datapoint.text_value = text_value
        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('reagent already read: %r' % text_value)
            return
        reagentbatch = AntibodyBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id=batch_id) 
        dataset.antibodies.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid Antibody identifier: %r:%r, raw val: %r",
            facility_id,batch_id,text_value)
        raise    

def _read_cell_batch(dataset, datapoint):

    try:
        (facility_id,batch_id,text_value) = (
            _parse_reagent_batch(datapoint.text_value))
        datapoint.text_value = text_value
        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('reagent already read: %r' % text_value)
            return
        reagentbatch = CellBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id=batch_id) 
        dataset.cells.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid Cell Line identifier: %r:%r, raw val: %r",
            facility_id,batch_id,text_value)
        raise    

def _read_primary_cell_batch(dataset, datapoint):

    try:
        (facility_id,batch_id,text_value) = (
            _parse_reagent_batch(datapoint.text_value))
        datapoint.text_value = text_value
        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('reagent already read: %r' % text_value)
            return
        reagentbatch = PrimaryCellBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id=batch_id) 
        dataset.primary_cells.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid Primary Cell identifier: %r:%r, raw val: %r",
            facility_id,batch_id,text_value)
        raise    

def _read_ipsc_batch(dataset, datapoint):

    try:
        (facility_id,batch_id,text_value) = (
            _parse_reagent_batch(datapoint.text_value))
        datapoint.text_value = text_value
        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('reagent already read: %r' % text_value)
            return
        reagentbatch = IpscBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id=batch_id) 
        dataset.ipscs.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid IPSC identifier: %r:%r, raw val: %r",
            facility_id,batch_id,text_value)
        raise    

def _read_es_cell_batch(dataset, datapoint):

    try:
        (facility_id,batch_id,text_value) = (
            _parse_reagent_batch(datapoint.text_value))
        datapoint.text_value = text_value
        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('reagent already read: %r' % text_value)
            return
        reagentbatch = EsCellBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id=batch_id) 
        dataset.es_cells.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid Embryonic Cell identifier: %r:%r, raw val: %r",
            facility_id,batch_id,text_value)
        raise    

def _read_diff_cell_batch(dataset, datapoint):

    try:
        (facility_id,batch_id,text_value) = (
            _parse_reagent_batch(datapoint.text_value))
        datapoint.text_value = text_value
        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('reagent already read: %r' % text_value)
            return
        reagentbatch = DiffCellBatch.objects.get(
            reagent__facility_id=facility_id,
            batch_id=batch_id) 
        dataset.diff_cells.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        reagents_read_hash[text_value] = reagentbatch
    except Exception, e:
        logger.exception("Invalid Differentiated Cell identifier: %r:%r, raw val: %r",
            facility_id,batch_id,text_value)
        raise    

def _read_small_molecule(dataset, datapoint):
    
    try:
        (facility_id,salt_id,batch_id,text_value) = (
            _parse_reagent_salt_batch(datapoint.text_value))
        datapoint.text_value = text_value
        if text_value in reagents_read_hash:
            datapoint.reagent_batch = reagents_read_hash[text_value]
            logger.debug('reagent already read: %r' % text_value)
            return
        reagentbatch = SmallMoleculeBatch.objects.get(
            reagent__facility_id=facility_id, reagent__salt_id=salt_id, 
            batch_id=batch_id)
        dataset.small_molecules.add(reagentbatch)
        datapoint.reagent_batch = reagentbatch
        
        logger.debug('read small molecule batch %s' % reagentbatch )
        reagents_read_hash[text_value] = reagentbatch
    
    except Exception, e:
        logger.exception("Invalid Small Molecule identifier: %r:%r, raw val: %r",
            facility_id,batch_id,text_value)
        raise

def _read_plate_well(map_column, r, current_row, dr, small_molecule_column,
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
                    datapoint = DataPoint(datacolumn=small_molecule_column,
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
    
