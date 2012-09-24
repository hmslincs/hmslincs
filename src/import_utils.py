import dateutil.parser
from datetime import date

def convertdata(value, t=None):
    #print 'convert: ', value, 'type: ', t
    if value == 'None':  # todo: because all values are returned as unicode, and xls2py is converting empty values to "None", we need this clause
        return None
    if t is None:
        return value
    elif t is int: # todo: this is a kludge, since we want an integer from values like "5.0"
        return int(float(value))
    elif t is date:
        return dateutil.parser.parse(value)
    else:
        return t(value)

def get_fields(model):
    return tuple(model._meta.fields)
        

def make_row(sheetRow):
    r = []
    for c in sheetRow:
        r.append(unicode(c))
    return r