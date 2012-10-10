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
from db.CSVSerializer import CSVSerializer
from db.models import SmallMolecule,DataSet,Cell , DataRecord

logger = logging.getLogger(__name__)

class SmallMoleculeResource(ModelResource):
    class Meta:
        queryset = SmallMolecule.objects.all()
        # to override: resource_name = 'sm'
        excludes = ['column']

class CellResource(ModelResource):
    class Meta:
        queryset = Cell.objects.all()
        # to override: resource_name = 'sm'
        excludes = []
        
class DataSetResource(ModelResource):
    
    class Meta:
        queryset = DataSet.objects.all()
        # to override: resource_name = 'sm'
        excludes = []
    def dehydrate(self, bundle):
        bundle.data['endpointFile'] = {'uri':'http://localhost/db/api/v1/datasetdata/'+str(bundle.data['id']),
                                       'noCols':len(views.get_dataset_column_names(bundle.data['id'])),
                                       'cols':views.get_dataset_column_names(bundle.data['id'])
                                       }
        return bundle
    
class DataSetData(ModelResource):
    dataset_id=-1
    class Meta:
        queryset = DataRecord.objects.all()
        # to override: resource_name = 'sm'
        fields = []
        serializer = CSVSerializer()
    
    def apply_filters(self, request, applicable_filters):
        logger.error('apply filters!!!!')
        self.dataset_id = request.GET.get('dataset_id')
        self.queryset = views.get_dataset_result_table(self.dataset_id)
        return self.queryset
    
    def get_object_list(self, request):
        matchObject = re.match(r'.*datasetdata/(\d+)/', request.path)
        if(matchObject):
            self.dataset_id = matchObject.group(1)
            logger.info(str(('get_object_list for ', self.dataset_id)))
            return views.get_dataset_result_queryset(self.dataset_id)
            #return queryset
    
    def obj_get_list(self, request=None, **kwargs):
        # Filtering disabled for brevity...
        return self.get_object_list(request)
    
    def obj_get(self, request=None, **kwargs):
        return self.get_object_list(request)
    def get_detail(self, request, **kwargs):
        return self.create_response(request,self.get_object_list(request))
        
    def detail_uri_kwargs(self, bundle_or_obj):
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