# this file is for the tastypie REST api
# db/api.py - tastypie resources
from collections import OrderedDict
from db import views
from db.DjangoTables2Serializer import DjangoTables2Serializer, \
    get_visible_columns
from db.models import SmallMolecule, DataSet, Cell, Protein, Library, DataRecord, \
    DataColumn, get_detail_bundle, get_detail_schema
from django.conf.urls.defaults import url
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.http import Http404
from django.utils.encoding import smart_str
from tastypie.authorization import Authorization
from tastypie.bundle import Bundle
from tastypie.resources import ModelResource, Resource
from tastypie.serializers import Serializer
import StringIO
import csv
import json
import logging
import re
        
logger = logging.getLogger(__name__)

class SmallMoleculeResource(ModelResource):
    class Meta:
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        queryset = SmallMolecule.objects.all()
        # to override: resource_name = 'sm'
        excludes = ['column']
        authorization= Authorization()
        
    def dehydrate(self, bundle):
        bundle.data = get_detail_bundle(bundle.obj, ['smallmolecule',''])
        return bundle

    def build_schema(self):
        schema = super(SmallMoleculeResource,self).build_schema()
        schema['fields'] = get_detail_schema(SmallMolecule(),['smallmolecule'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):

        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)\-(?P<salt_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]



class CellResource(ModelResource):
    class Meta:
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        queryset = Cell.objects.all()
        # to override: resource_name = 'sm'
        excludes = []
        
    def dehydrate(self, bundle):
        bundle.data = get_detail_bundle(bundle.obj, ['cell',''])
        return bundle

    def build_schema(self):
        schema = super(CellResource,self).build_schema()
        schema['fields'] = get_detail_schema(Cell(),['cell'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
    

class ProteinResource(ModelResource):
    class Meta:
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        queryset = Protein.objects.all()
        # to override: resource_name = 'sm'
        excludes = []
        
    def dehydrate(self, bundle):
        bundle.data = get_detail_bundle(bundle.obj, ['protein',''])
        return bundle

    def build_schema(self):
        schema = super(ProteinResource,self).build_schema()
        schema['fields'] = get_detail_schema(Protein(),['protein'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<lincs_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
    
class LibraryResource(ModelResource):
    class Meta:
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        queryset = Library.objects.all()
        # to override: resource_name = 'sm'
        excludes = []
        
    def dehydrate(self, bundle):
        bundle.data = get_detail_bundle(bundle.obj, ['library',''])
        return bundle

    def build_schema(self):
        schema = super(LibraryResource,self).build_schema()
        schema['fields'] = get_detail_schema(Library(),['library'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<lincs_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
        

class DataSetResource(ModelResource):
    """
    This version of the database export shows the DatasetData columns serially, 
    as is specified for the SAF version 0.1 data interchange format for the LIFE system.
    """
    
    class Meta:
        queryset = DataSet.objects.all() #.filter(is_restricted==False)
        # TODO: authorization
        excludes = ['lead_screener_firstname','lead_screener_lastname','lead_screener_email']
    def dehydrate(self, bundle):
        _facility_id =str(bundle.data['facility_id'])
        dataset_id = bundle.data['id']
        
        # NOTE: this executes the query on the resource *just* to get the columns
        datasetDataResource = DataSetDataResource()
        datasetDataCursor = datasetDataResource.get_datasetdata_cursor(dataset_id)

        datasetDataColumns = [camel_case(col[0]) for col in datasetDataCursor.description]
        
        bundle.data = get_detail_bundle(bundle.obj, ['dataset',''])
        # TODO: this is a kludge to deal with issue #103 db: api: URI for datasetdata is incorrect
        bundle.data['endpointFile'] = {'uri':'http://lincs.hms.harvard.edu/db/api/v1/datasetdata/'+ _facility_id + "/?format=csv",
                                       'noCols':len(datasetDataColumns),
                                       'cols':datasetDataColumns
                                       }
        return bundle

    def build_schema(self):
        #TODO: redo this for the SAF format
        schema = super(DataSetResource,self).build_schema()
        # TODO: build the schema from the fieldinformation
        schema['fields'] = get_detail_schema(DataSet(),['dataset'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]


def camel_case(string):
    field_name = re.sub(r'[_\s]+',' ',string)
    
    field_name = field_name.title()
    field_name = re.sub(r'[_\s]+','',field_name)
    temp = field_name[0].lower() + field_name[1:]
    logger.info(str(('camelcased:', string,temp)))
    return temp

class CursorSerializer(Serializer):
    """
    A simple serializer that takes a cursor, queries it for its columns, and outputs 
    this as either CSV or JSON.
    (The CSV output is used with SAF)
    """
    
    formats = ['json', 'jsonp', 'xml', 'yaml', 'csv']
    content_types = {
        'json': 'application/json',
        'jsonp': 'text/javascript',
        'xml': 'application/xml',
        'yaml': 'text/yaml',
        'csv': 'text/csv',
    }

    def get_saf_columns(self, query):
        return ['one','two', 'three']
    
    def to_csv(self, cursor, options=None):
        logger.info(str(('typeof the object sent to_csv',type(cursor))))
        raw_data = StringIO.StringIO()
                
        # this is an unexpected way to get this error, look into tastypie sequence calls
        if(isinstance(cursor,dict) and 'error_message' in cursor):
            logger.info(str(('report error', cursor)))
            raw_data.writelines(('error_message\n',cursor['error_message'],'\n'))
            return raw_data.getvalue() 

        # no response header needed?
        #        response = HttpResponse(mimetype='text/csv')
        #        response['Content-Disposition'] = 'attachment; filename=%s.csv' % unicode('test.output').replace('.', '_')
        #        raw_data.write(response)
        writer = csv.writer(raw_data)
        i=0
        cols = [camel_case(col[0]) for col in cursor.description]
        
        # TODO: grab the column names here
        writer.writerow(cols)

        for row in cursor.fetchall():
            writer.writerow([smart_str(val, 'utf-8', errors='ignore') for val in row])
            i += 1

        logger.info('done, wrote: %d' % i)
        return raw_data.getvalue()
    
    def to_json(self,cursor, options=None):
        logger.info(str(('typeof the object sent to_csv',type(cursor))))
#        logger.info(str(('to_csv for SAF for cursor', cursor)))
        raw_data = StringIO.StringIO()
                
        # this is an unexpected way to get this error, look into tastypie sequence calls
        if(isinstance(cursor,dict) and 'error_message' in cursor):
            logger.info(str(('report error', cursor)))
            raw_data.writelines(('error_message\n',cursor['error_message'],'\n'))
            return raw_data.getvalue() 

        # TODO: sort the fields?
        i=0
        cols = [camel_case(col[0]) for col in cursor.description]
        
        raw_data.write('[')
        for row in cursor.fetchall():
            if i!=0:
                raw_data.write(',\n')
            raw_data.write(json.dumps(OrderedDict(zip(cols, row)),skipkeys=False,ensure_ascii=True,check_circular=True, allow_nan=True, cls=DjangoJSONEncoder))
            #            raw_data.write(json.dumps(dict(zip(cols, row))))
            i += 1
        raw_data.write(']')

        logger.info('done, wrote: %d' % i)
        return raw_data.getvalue()
    
    
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
        


class DataSetDataResource(Resource):
    """
    This version of the database export shows the DatasetData columns serially,
    except for the timepoint columns (which are still flattened),
    as is specified for the SAF version 0.1 data interchange format for the LIFE system.
    
    This class is a complete override of the read functionality of tastypie; 
    because serializing the dataset data is not possible using ORM code.
    """
    
    # TODO: version 2: use the manager, not the tables2
    class Meta:
        #queryset = DataRecord.objects.all()
        # to override: resource_name = 'sm'
        fields = []
        serializer = CursorSerializer()
#        queryset = DataRecord.objects.all();

    
    def get_dataset_columns(self,dataset_id, unit=[]):
        datacolumns = DataColumn.objects.filter(dataset_id=dataset_id)
        
        if unit:
            datacolumns = datacolumns.filter(unit__in=unit)
            
        return datacolumns
        

    def get_object_list(self, request):
        """
        A hook to allow making returning the list of available objects.
        override tastypie.resources.Resource
        - we do this because this is a custom resource (not, for instance, a ModelResource)
        Note: this function will hand off to the Serializer.
        """
        logger.info(str(('get_object_list', request.path, request.GET)))
        matchObject = re.match(r'.*datasetdata/(\d+)/', request.path) # TODO: there must be a way to get the request path variable automagically
        if(matchObject):
            facility_id = matchObject.group(1)
            try:
                dataset = DataSet.objects.get(facility_id=facility_id)
                logger.info(str(('DataSetData2Resource', facility_id,dataset)))
                if(dataset.is_restricted and not request.user.is_authenticated()):
                    raise Http401
                
                return self.get_datasetdata_cursor(dataset.id)
            
            
            except DataSet.DoesNotExist, e:
                logger.error(str(('no such facility id', facility_id)))
                raise e
        else:
            raise Http404(str(('no facility id given',request.path)))
    
    def get_datasetdata_cursor(self,dataset_id):
        timepoint_columns = self.get_dataset_columns(dataset_id, ['day','hour','minute','second'])
        logger.info(str(('timepoint_columns', timepoint_columns)))
        endpoint_columns = self.get_dataset_columns(dataset_id)
        endpoint_columns = [col for col in endpoint_columns if col not in timepoint_columns]
        
        # pivot out the timepoint columns only
        timepoint_column_string = '';
        for i,dc in enumerate(timepoint_columns):
            alias = "dp_"+ str(i)
            columnName = "timepoint"
            if i>0: columnName += "_" + str(i)
            unitColumnName = "timepoint_unit"
            if i>0: unitColumnName += "_" + str(i)
            column_to_select = None
            if(dc.data_type == 'Numeric' or dc.data_type == 'omero_image'):
                if dc.precision == 0 or dc.data_type == 'omero_image':
                    column_to_select = "int_value"
                else:
                    column_to_select = "round( float_value::numeric, 2 )" # TODO: specify the precision in the fieldinformation for this column
            else:
                column_to_select = "text_value"
            timepoint_column_string +=  (",(SELECT " + column_to_select + " FROM db_datapoint " + alias + 
                                " where " + alias + ".datacolumn_id="+str(dc.id) + " and " + alias + ".datarecord_id=dr.id) as " + columnName )
            timepoint_column_string += ", '" + dc.unit + "' as " + unitColumnName
        
        # TODO: only include cell, protein if they are present in the dataset
        # TODO: build the aliases here from the fieldinformation table.  
        # Note, case is erased when cursor.description is filled, so use underscores, and leave the camelcasing for later
        sql = """select dr.id, 
            ds.facility_id as bioassay_id, 
            sm.facility_id sm_center_compound_id, 
            sm.name as sm_name,
            cell.name as cl_name, 
            cell.facility_id as cl_center_specific_id,
            protein.name as pp_name,
            protein.lincs_id as pp_lincs_id,
            dr.plate,
            dr.well,
            dr.control_type as control_type,
            dc.name as endpoint_name, 
            dc.unit as endpoint_unit,
            coalesce(dp.int_value::TEXT, dp.float_value::TEXT, dp.text_value) as endpoint_value
            """
            
        sql += timepoint_column_string
        
        sql += """
            from db_dataset ds 
            join db_datarecord dr on(dr.dataset_id=ds.id) 
            join db_datacolumn dc on(dc.dataset_id=ds.id) 
            left join db_smallmolecule sm on (dr.smallmolecule_id=sm.id) 
            left join db_cell cell on (dr.cell_id=cell.id)
            left join db_protein protein on (dr.protein_id=protein.id)
            , db_datapoint dp 
            where dp.datarecord_id=dr.id and dp.datacolumn_id=dc.id 
            and ds.id = %s 
            """
        if len(timepoint_columns) > 0: 
            sql += " and dc.id not in (" + ','.join([str(col.id) for col in timepoint_columns]) + ") "    
        sql += " order by dr.id, dc.id "
        cursor = connection.cursor()
        cursor.execute(sql, [dataset_id])
        #                query = DataRecord.objects.filter(dataset_id=dataset_id)
        #                logger.info(str(('query returns', query)))
        return cursor

    
    def obj_get_list(self, request=None, **kwargs):
        logger.info('obj_get_list')
        # Filtering disabled for brevity...
        return self.get_object_list(request)
    
    def obj_get(self, request=None, **kwargs):
        logger.info('obj_get')
        return self.get_object_list(request)
    
    def get_detail(self, request, **kwargs):
        logger.info('get_detail')
        return self.create_response(request,self.get_object_list(request))
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def build_schema(self):
        #TODO: redo this for the SAF format
        
        schema = super(DataSetResource,self).build_schema()
        # TODO: build the schema from the fieldinformation
        schema['fields'] = get_detail_schema(DataSet(),['dataset'])
        return schema 
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
    
    def dehydrate(self, bundle):
        # TODO: for datasetdata, show the column information that was entered
        return bundle            

class DataSetFlattenedResource(ModelResource):
    """
    This version of the database export shows the DatasetData columns in a pivoted, flattened table,
    in the same form as the web UI
    """
    
    class Meta:
        queryset = DataSet.objects.all() #.filter(is_restricted==False)
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        excludes = ['lead_screener_firstname','lead_screener_lastname','lead_screener_email']
    def dehydrate(self, bundle):
        # TODO: the following call executes the query *just* to get the column names
        _facility_id =str(bundle.data['facility_id'])
        visibleColumns = get_visible_columns(views.DataSetManager(bundle.obj).get_table())
        bundle.data = get_detail_bundle(bundle.obj, ['dataset',''])
        # TODO: this is a kludge to deal with issue #103 db: api: URI for datasetdata is incorrect
        bundle.data['endpointFile'] = {'uri':'http://lincs.hms.harvard.edu/db/api/v1/datasetdataflattened/'+ _facility_id + "/?format=csv",
                                       'noCols':len(visibleColumns),
                                       'cols':visibleColumns.values()
                                       }
        return bundle

    def build_schema(self):
        schema = super(DataSetResource,self).build_schema()
        # TODO: build the schema from the fieldinformation
        schema['fields'] = get_detail_schema(DataSet(),['dataset'])
        return schema 
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]

    
class DataSetDataFlattenedResource(Resource):
    """
    This class is a complete override of the read functionality of tastypie; 
    because serializing the dataset data is not possible using ORM code.
    """
    
    # TODO: version 2: use the manager, not the tables2
    class Meta:
        #queryset = DataRecord.objects.all()
        # to override: resource_name = 'sm'
        fields = []
        serializer = DjangoTables2Serializer()
    
    def get_object_list(self, request):
        matchObject = re.match(r'.*datasetdata/(\d+)/', request.path) # TODO: there must be a way to get the request path variable automagically
        if(matchObject):
            facility_id = matchObject.group(1)
            try:
                dataset = DataSet.objects.get(facility_id=facility_id)
                logger.info(str(('DataSetDataResource', facility_id,dataset)))
                if(dataset.is_restricted and not request.user.is_authenticated()):
                    raise Http401
                manager = views.DataSetManager(dataset)
                return manager.get_table()
            except DataSet.DoesNotExist, e:
                logger.error(str(('no such facility id', facility_id)))
                raise
        else:
            raise Http404(str(('no facility id given',request.path)))
    
    def obj_get_list(self, request=None, **kwargs):
        logger.info('obj_get_list')
        # Filtering disabled for brevity...
        return self.get_object_list(request)
    
    def obj_get(self, request=None, **kwargs):
        logger.info('obj_get')
        return self.get_object_list(request)
    
    def get_detail(self, request, **kwargs):
        logger.info('get_detail')
        return self.create_response(request,self.get_object_list(request))
        
    def detail_uri_kwargs(self, bundle_or_obj):
        logger.info(str(('detail_uri_kwargs', bundle_or_obj)))
        kwargs = {}

        if isinstance(bundle_or_obj, Bundle):
            kwargs['pk'] = bundle_or_obj.obj.uuid
        else:
            kwargs['pk'] = bundle_or_obj.uuid

        return kwargs    
    
    def override_urls(self):
        """ Note, will be deprecated in >0.9.12; delegate to new method, prepend_urls
        """
        return self.prepend_urls();
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<facility_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
    
    def dehydrate(self, bundle):
        # TODO: for datasetdata, show the column information that was entered
        return bundle    

class Http401(Exception):
    pass


