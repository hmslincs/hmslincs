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
from db.models import SmallMolecule,DataSet,Cell,Protein,Library
from db.models import get_detail_bundle, get_detail_schema

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
                logger.error(str(('DataSetDataResource', facility_id,dataset)))
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