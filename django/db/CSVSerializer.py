import csv
import StringIO
from tastypie.serializers import Serializer
import logging

logger = logging.getLogger(__name__)

# TODO: rough class built specifically for datasetdata - needs analysis and rework!
class CSVSerializer(Serializer):
    formats = ['json', 'jsonp', 'xml', 'yaml', 'html', 'csv']
    content_types = {
        'json': 'application/json',
        'jsonp': 'text/javascript',
        'xml': 'application/xml',
        'yaml': 'text/yaml',
        'html': 'text/html',
        'csv': 'text/csv',
    }

    def to_csv_from_queryset(self, data, options=None):
        options = options or {}
        data = self.to_simple(data, options)
        raw_data = StringIO.StringIO()
        # Untested, so this might not work exactly right.
        
        if(len(data)==0):
            return
        writer = csv.writer(raw_data)
        for i,item in enumerate(data):
            if(i==0): 
                logger.info(str(('write headers: ', item.keys() )))
                writer.writerow(item.keys())
            else:
                #logger.info(str(('write values: ', item.values())))
                writer.writerow(item.values())
        logger.info('done')
        return raw_data.getvalue()    
    
    def to_csv(self, table, options=None):
        return self.to_csv_from_tables2(table, options)
    
    def to_csv_from_tables2(self, table, options=None):
        
        raw_data = StringIO.StringIO()
        # Untested, so this might not work exactly right.
        data = table.data.list
        if(len(data)==0):
            return
        writer = csv.writer(raw_data)
        
        names = []
        for column in table.base_columns.values():
            if(column.visible): 
                names.append(column.verbose_name)
        writer.writerow(names)
        
        for item in data:
            writer.writerow(item.values())
        logger.info('done')
        return raw_data.getvalue()
    
    def to_csv_from_tables2a(self, table, options=None):
        
        raw_data = StringIO.StringIO()
        # Untested, so this might not work exactly right.
        data = table.data.list
        if(len(data)==0):
            return
        writer = csv.writer(raw_data)
        
        names = {}
        for name,column in table.base_columns.items():
            if(column.visible):
                if(column.verbose_name != None): 
                    names.append(column.verbose_name)
                else:
                    names.append(name)
        writer.writerow(names)
        
        for item in data:
            print_values = []
            for name,value in item.items():
                if(table.base_columns[name].visible):
                    print_values.append(value)
            writer.writerow(print_values)
        logger.info('done')
        return raw_data.getvalue()
    def from_csv(self, content):
        pass
        #raw_data = StringIO.StringIO(content)
        #data = []
        # Untested, so this might not work exactly right.
        #for item in csv.DictReader(raw_data):
        #    data.append(item)
        #return data