#from django.conf.urls import patterns, include, url
from django.conf.urls.defaults import *
from django.views.generic import TemplateView
from settings import _djangopath
import os.path as op
from tastypie.api import Api
from db.api import SmallMoleculeResource,CellResource,DataSetResource,DataSetDataResource,DataSetData2Resource,ProteinResource,LibraryResource
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

smallmolecule_resource = SmallMoleculeResource()
v1_api = Api(api_name='v1') 
v1_api.register(SmallMoleculeResource())
v1_api.register(CellResource())
v1_api.register(DataSetResource())
v1_api.register(DataSetDataResource())
v1_api.register(DataSetData2Resource())
v1_api.register(ProteinResource())
v1_api.register(LibraryResource())

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

from hmslincs_server.views import *

urlpatterns = patterns('',

    # Login / logout.
    # Note: the name "login_url" name is set to the request by the registered hmslincs.context_procesor.login_url_with_redirect
    (r'^db/login/$', 'django.contrib.auth.views.login', {'template_name': 'db/login.html'}),
    url(r'^db/logout/$', logout_page, name='logout'),

    url(r'^db/admin/doc/', include('django.contrib.admindocs.urls')), 
    url(r'^db/admin/', include(admin.site.urls)),
    url(r'^db/$', 'db.views.main', name="home"),
    url(r'^db/sm/$','db.views.smallMoleculeIndex', name="listSmallMolecules" ),
    url(r'^db/sm/facility_ids/(?P<facility_ids>.*)$','db.views.smallMoleculeIndexList', name="small_molecule_listing" ),
    url(r'^db/structuresearch/$','db.views.structure_search', name="structureSearch" ),
    url(r'^db/test/$','db.views.test', name="test" ),
    url(r'^db/cached_structure_search/$','db.views.get_cached_structure_search', name="cached_structure_search_blank" ),
    url(r'^db/cached_structure_search/(?P<search_request_id>\d+)/$','db.views.get_cached_structure_search', name="cached_structure_search" ),
    url(r'^db/sm_molfile/(?P<facility_salt_id>[0-9\-]+)$','db.views.smallMoleculeMolfile', name="smallMoleculeMolfile" ),
    url(r'^db/sm/(?P<facility_salt_id>[0-9\-]+)/$', 'db.views.smallMoleculeDetail', name="sm_detail"),
    url(r'^db/cells/$','db.views.cellIndex', name="listCells"),
    url(r'^db/cells/(?P<facility_id>\d+)/$', 'db.views.cellDetail', name="cell_detail"),
    url(r'^db/proteins/$','db.views.proteinIndex', name="listProteins"),
    url(r'^db/proteins/(?P<lincs_id>\d+)/$', 'db.views.proteinDetail', name="protein_detail"),
    url(r'^db/libraries/$','db.views.libraryIndex', name="listLibraries"),
    url(r'^db/libraries/(?P<short_name>[^/]+)/$', 'db.views.libraryDetail', name="library_detail"),
    url(r'^db/datasets/$','db.views.datasetIndex', name="listDatasets"),
    url(r'^db/datasets/(?P<facility_id>\d+)/$', 'db.views.datasetDetailMain', name="dataset_detail"),
    url(r'^db/datasets/(?P<facility_id>\d+)/main$', 'db.views.datasetDetailMain', name="dataset_detail_main"),
    url(r'^db/datasets/(?P<facility_id>\d+)/cells$', 'db.views.datasetDetailCells', name="dataset_detail_cells"),
    url(r'^db/datasets/(?P<facility_id>\d+)/proteins$', 'db.views.datasetDetailProteins', name="dataset_detail_proteins"),
    url(r'^db/datasets/(?P<facility_id>\d+)/smallmolecules$', 'db.views.datasetDetailSmallMolecules', name="dataset_detail_small_molecules"),
    url(r'^db/datasets/(?P<facility_id>\d+)/results$', 'db.views.datasetDetailResults', name="dataset_detail_results"),
    # TODO: if we install x-sendfile on the apache server, we can serve these files with an x-sendfile redirect
    url(r'^db/downloadattached/(?P<id>\d+)/$', 'db.views.download_attached_file', name='download_attached_file'),
    # TODO: if we install x-sendfile on the apache server, we can serve these files with an x-sendfile redirect
     url(r'^db/restrictedimage/(?P<filepath>\S+)$', 'db.views.restricted_image', name="restricted_image"),
    
    # this method uses the x-sendfile header to apache to serve files, see views.py
    # url(r'^db/retrievefile/(?P<path>.*)/$', 'db.views.retrieve_file', name='retrieve_file'),

    
    (r'^db/api/', include(v1_api.urls)),

    (r'^explore/pathway/$', 'django.views.static.serve',
     {'path': 'index.html',
      'document_root': op.join(_djangopath, 'pathway', 'static', 'pathway')}),

    (r'^explore/responses/$', 'django.views.generic.simple.direct_to_template',
     {'template': 'responses/index.html'}),

    (r'^explore/sensitivities/$', 'django.views.generic.simple.direct_to_template',
     {'template': 'sensitivities/index.html'}),
)

# For DEBUG mode only (development) serving of static files
urlpatterns += staticfiles_urlpatterns()
