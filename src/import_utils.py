import dateutil.parser
from datetime import date
import logging

logger = logging.getLogger(__name__)

bool_converter = lambda x: convertdata(x,bool)
int_converter = lambda x: convertdata(x,int)
date_converter = lambda x: convertdata(x,date)

def fill_in_column_definitions(properties, column_definitions):
    """
    Utility to lowercase and to make sure every column_definition has a mapping for each property, 
    (the set of dict values assigned to it), or set to None
    """
    column_definitions_to_lower = {}
    for key,value in column_definitions.items():
        key = key.lower()
        if(isinstance(value, basestring)): value = (value,) # convert to a tuple
        #column_definitions[key]=dict(zip(properties,value))
        column_definitions_to_lower[key] = dict(zip(properties,value))
        # make all default to None
        for prop in properties:
            if(prop == 'converter'):
                column_definitions_to_lower[key].setdefault(prop,lambda x:convertdata(x))
            column_definitions_to_lower[key].setdefault(prop,None)
    return column_definitions_to_lower
    
def find_columns(column_definitions, sheet_labels, all_column_definitions_required=True, all_sheet_columns_required=True):
    """
    return a dict mapping the column ordinal to the proper column definition dict
    - all matches are done after lowercasing the sheet labels.
    """
    logger.debug(str(('sheet_labels:', sheet_labels)))
    cols = {}
    sheet_labels_cleaned = []
    for label in sheet_labels:
        label = label.strip()
        if label == None or label == '' or label == 'None': continue
        sheet_labels_cleaned.append(label.lower())
    # first put the label row in (it contains the worksheet column, and its unique)
    for i,label in enumerate(sheet_labels_cleaned):
        label = label.strip()
        if label in column_definitions:
            cols[i] = column_definitions[label]
            cols[i]['column_label']=label
        elif(all_sheet_columns_required):
            raise Exception('sheet column label not defined: "' + label + '"')
    if(all_column_definitions_required):
        for key in column_definitions:
            if(key not in sheet_labels_cleaned):
                raise Exception(str(('required column not found:"' + key + '"',sheet_labels_cleaned)))
    logger.debug(str(('cols:', cols)))
    return cols


def convertdata(value, t=None):
    """
    All values are read as strings from the input files, so this function converts them as directed.
    """
    #print 'convert: ', value, 'type: ', t
    # todo: because all values are returned as unicode, and xls2py is converting empty values to "None", we need this clause
    # also, by convention, empty values in the sdf file can be indicated as 'n/a'
    try:
        if value == None or value== '' or value == 'None' or value == u'None' or value == u'n/a':  
            return None
        if t is None:
            return value
        elif t is int: # todo: this is a kludge, since we want an integer from values like "5.0"
            return int(float(value))
        elif t is date:
            return dateutil.parser.parse(value)
        elif t is bool:
            if(value.lower() == 'true' or value.lower() == 't'): return True
            return False
        else:
            return t(value)
    except Exception, e:
        logger.error(str(('value', value)))
        raise
def get_fields(model):
    return tuple(model._meta.fields)
        

def make_row(sheetRow):
    r = []
    for c in sheetRow:
        r.append(unicode(c))
    return r