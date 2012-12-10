import csv
import StringIO
from tastypie.serializers import Serializer
from django.utils.datastructures import SortedDict
import logging
import django_tables2 as tables
from django.db import connection
from db.PagedRawQuerySet import PagedRawQuerySet

logger = logging.getLogger(__name__)

# TODO: rough class built specifically for datasetdata - needs analysis and rework!
def get_visible_columns(table):
    """ return a sorted dict of the visible columns.
    """
    visibleColumns = SortedDict()
    #logger.info(str(('table.base_columns', table.base_columns))) 
    # base_columns is a map of the column *variable* name to column instance
    # note that the variable name is the key to the value in the queryset as well
    # so here build a dict of name->display_name of the columns wanted based on visibility
    for fieldName,column in table.base_columns.iteritems():
        if(column.visible): 
            #logger.error(str(('column v:',column, [getattr(column, attr) for attr in dir(column)])))
            if(column.verbose_name != None and column.verbose_name.strip() != ''): 
                visibleColumns[fieldName]=column.verbose_name
            else:
                logger.warn(str(('verbose name not set for column:', fieldName)))
                visibleColumns[fieldName]=fieldName
    return visibleColumns

class DjangoTables2Serializer(Serializer):
    """
    Here we serialize the Django tables2 that has been obtained through the query
    created from the query in the REST path.  
    The REST layer should be lower level, architecturally than the tables2 view - web UI specific code.
    However, it was constructed first, so, for now, this serializer can serialize 
    a django-tables2 table.  Advantage is that all of the columns have been defined
    for the view layer, queries have been built (to be refactored).  
    """
    formats = ['json', 'jsonp', 'xml', 'yaml', 'csv']
    content_types = {
        'json': 'application/json',
        'jsonp': 'text/javascript',
        'xml': 'application/xml',
        'yaml': 'text/yaml',
        'csv': 'text/csv',
    }

    def to_csv(self, table, options=None):
        return self.to_csv_from_tables2(table, options)
    
    def to_csv_from_tables2(self, table, options=None):
        """
        serialize the visible columns of a django tables2 table that has been initialized
        with a queryset.
        """
        logger.info('to_csv_from_tables2')
        raw_data = StringIO.StringIO()
                
        # this is an unexpected way to get this error, look into tastypie sequence calls
        if(isinstance(table,dict) and 'error_message' in table):
            raw_data.writelines(('error_message\n',table['error_message'],'\n'))
            return raw_data.getvalue() 
        

        data = table.data.data
        if(len(data)==0):
            return
        writer = csv.writer(raw_data)
        
        visibleColumns = get_visible_columns(table)
        
        writer.writerow(visibleColumns.values())

        i=0
        if(isinstance(data, PagedRawQuerySet)): # if PRQS, then bypass and just iterate over the cursor (note, this still doesn't accomplish streaming)
            cursor = connection.cursor()   
            cursor.execute(data.get_sql())
            for row in cursor:
                writer.writerow(row)
                i += 1
        else: # list of dicts - use non-paged iteration
            for i,item in enumerate(data):
                row = []
                for fieldname in visibleColumns.keys():
                    row.append(item[fieldname])
                writer.writerow(row)
                #if i == 10: break

        logger.info('done, wrote: %d' % i)
        return raw_data.getvalue()
    
    def to_json(self,table, options=None):
        return 'Sorry, not implemented yet. Please append "?format=csv" to your URL.'
        #return super.to_json(table.data.list, options)

    def to_jsonp(self, table, options=None):
        return 'Sorry, not implemented yet. Please append "?format=csv" to your URL.'
        #return super.to_jsonp(table.data.list, options)

    def to_xml(self, table, options=None):
        return 'Sorry, not implemented yet. Please append "?format=csv" to your URL.'
        #return super.to_xml(table.data.list,options)
    
    def to_yaml(self, table, options=None):
        return 'Sorry, not implemented yet. Please append "?format=csv" to your URL.'
        #return super.to_yaml(table.data.list, options)
        
    def from_csv(self, content):
        pass
        #raw_data = StringIO.StringIO(content)
        #data = []
        # Untested, so this might not work exactly right.
        #for item in csv.DictReader(raw_data):
        #    data.append(item)
        #return data