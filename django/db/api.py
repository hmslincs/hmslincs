# this file is for the tastypie REST api
# db/api.py - tastypie resources
import logging

from django.conf.urls.defaults import url
from tastypie.authorization import Authorization
from tastypie.resources import ModelResource
from tastypie.resources import Resource
from tastypie.bundle import Bundle

from tastypie import fields
import re
from django.http import Http404

from db import views
from db.DjangoTables2Serializer import DjangoTables2Serializer, get_visible_columns
from db.models import SmallMolecule,DataSet,Cell,Protein,Library, DataRecord
from db.models import get_detail_bundle, get_detail_schema
from django.forms.models import model_to_dict

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
        bundle.data['endpointFile'] = {'uri':'http://lincs.hms.harvard.edu/db/api/v1/datasetdata/'+ _facility_id + "/?format=csv",
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


class Http401(Exception):
    pass

import csv
import json
import StringIO
from tastypie.serializers import Serializer
from django.utils.encoding import smart_str
from django.db import connection
from django.http import HttpResponse

class SafSerializer(Serializer):
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
#        logger.info(str(('to_csv for SAF for cursor', cursor)))
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
        cols = [col[0] for col in cursor.description]
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

        # no response header needed?
        #        response = HttpResponse(mimetype='text/csv')
        #        response['Content-Disposition'] = 'attachment; filename=%s.csv' % unicode('test.output').replace('.', '_')
        #        raw_data.write(response)
        i=0
        cols = [col[0] for col in cursor.description]
        

        raw_data.write('[')
        for row in cursor.fetchall():
            if i!=0:
                raw_data.write(',\n')
            raw_data.write(json.dumps(dict(zip(cols, row))))
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
        
class DataSetData2Resource(Resource):
    """
    This class is a complete override of the read functionality of tastypie; 
    because serializing the dataset data is not possible using ORM code.
    """
    
    # TODO: version 2: use the manager, not the tables2
    class Meta:
        #queryset = DataRecord.objects.all()
        # to override: resource_name = 'sm'
        fields = []
        serializer = SafSerializer()
#        queryset = DataRecord.objects.all();

    def get_object_list(self, request):
        logger.info(str(('get_object_list', request.path, request.GET)))
        matchObject = re.match(r'.*datasetdata2/(\d+)/', request.path) # TODO: there must be a way to get the request path variable automagically
        if(matchObject):
            facility_id = matchObject.group(1)
            try:
                dataset = DataSet.objects.get(facility_id=facility_id)
                logger.info(str(('DataSetData2Resource', facility_id,dataset)))
                if(dataset.is_restricted and not request.user.is_authenticated()):
                    raise Http401
                
                sql = """select 
                    ds.facility_id as datasetFacilityId, sm.facility_id smallmoleculeFacilityId, dc.name as endpointName, 
                    coalesce(dp.int_value::TEXT, dp.float_value::TEXT, dp.text_value) as endpointValue
                    from db_dataset ds 
                    join db_datarecord dr on(dr.dataset_id=ds.id) 
                    join db_datacolumn dc on(dc.dataset_id=ds.id) 
                    join db_smallmolecule sm on (dr.smallmolecule_id=sm.id), 
                    db_datapoint dp 
                    where dp.datarecord_id=dr.id and dp.datacolumn_id=dc.id 
                    and ds.facility_id = %s 
                    order by dc.id, dr.id"""
                cursor = connection.cursor()
                cursor.execute(sql, [dataset.facility_id])
#                query = DataRecord.objects.filter(dataset_id=dataset.id)
#                logger.info(str(('query returns', query)))
                return cursor
            except DataSet.DoesNotExist, e:
                logger.error(str(('no such facility id', facility_id)))
                raise e
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

    
class DataSetDataResource(Resource):
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