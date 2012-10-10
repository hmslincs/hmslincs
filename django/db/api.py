# this file is for the tastypie REST api
# db/api.py - tastypie resources
import logging

from django.conf.urls.defaults import url

from tastypie.resources import ModelResource
from tastypie.resources import Resource
from tastypie.bundle import Bundle

from tastypie import fields
import re

from db import views
from db.DjangoTables2Serializer import DjangoTables2Serializer, get_visible_columns
from db.models import SmallMolecule,DataSet,Cell

logger = logging.getLogger(__name__)

class SmallMoleculeResource(ModelResource):
    class Meta:
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        queryset = SmallMolecule.objects.all()
        # to override: resource_name = 'sm'
        excludes = ['column']

class CellResource(ModelResource):
    class Meta:
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        queryset = Cell.objects.all()
        # to override: resource_name = 'sm'
        excludes = []
        
class DataSetResource(ModelResource):
    
    class Meta:
        queryset = DataSet.objects.all()
        # TODO: authorization
        # TODO: it would be good to feed these from the view/tables2 code; or vice versa
        excludes = []
    def dehydrate(self, bundle):
        # TODO: the following call executes the query *just* to get the column names
        visibleColumns = get_visible_columns(views.get_dataset_result_table(bundle.data['id']))
        bundle.data['endpointFile'] = {'uri':'http://localhost/db/api/v1/datasetdata/'+str(bundle.data['id']),
                                       'noCols':len(visibleColumns),
                                       'cols':visibleColumns.values()
                                       }
        return bundle
    
class DataSetData(Resource):
    """
    This class is a complete override of the read functionality of tastypie; 
    because serializing the dataset data is not possible using ORM code.
    """
    
    class Meta:
        #queryset = DataRecord.objects.all()
        # to override: resource_name = 'sm'
        fields = []
        serializer = DjangoTables2Serializer()
    
    def get_object_list(self, request):
        logger.info('get_object_list')
        matchObject = re.match(r'.*datasetdata/(\d+)/', request.path) # TODO: there must be a way to get the request path variable automagically
        if(matchObject):
            dataset_id = matchObject.group(1)
            logger.info(str(('get_object_list for ', dataset_id)))
            return views.get_dataset_result_table(dataset_id)
            #return queryset
    
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
    def prepend_urls(self):
        logger.error('prepend urls!!!!')
        return [
            url(r"^(?P<resource_name>%s)/(?P<dataset_id>\d+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]
    
    def dehydrate(self, bundle):
        return bundle    