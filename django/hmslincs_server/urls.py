#from django.conf.urls import patterns, include, url
from django.conf.urls.defaults import *
from django.views.generic import TemplateView
from settings import _djangopath
import os.path as op
from tastypie.api import Api
from db.api import SmallMoleculeResource,CellResource,DataSetResource,DataSetDataResource,ProteinResource,LibraryResource
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

smallmolecule_resource = SmallMoleculeResource()
v1_api = Api(api_name='v1') 
v1_api.register(SmallMoleculeResource())
v1_api.register(CellResource())
v1_api.register(DataSetResource())
v1_api.register(DataSetDataResource())
v1_api.register(ProteinResource())
v1_api.register(LibraryResource())

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

from hmslincs_server.views import *

urlpatterns = patterns('',

    # Login / logout.
    # Note: the name "login_url" name is set to the request by the registered hmslincs.context_procesor.login_url_with_redirect
    (r'^login/$', 'django.contrib.auth.views.login', {'template_name': 'db/login.html'}),
    url(r'^logout/$', logout_page, name='logout'),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # url(r'^???/', include('???.urls')),
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')), 
    url(r'^admin/', include(admin.site.urls)),
    url(r'^db/$', 'db.views.main', name="home"),
    url(r'^db/sm/$','db.views.smallMoleculeIndex', name="listSmallMolecules" ),
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
    url(r'^db/datasets/(?P<facility_id>\d+)/results$', 'db.views.datasetDetailResults', name="dataset_detail_results"),
    #url(r'^db/study/$','db.views.studyIndex', name="listStudies"),
    url(r'^db/downloadattached/(?P<path>.*)/$', 'db.views.download_attached_file', name='download_attached_file'),
    #url(r'^db/search/', include('haystack.urls'), name="haystackSearch"),

# TODO: override 
#    url(r'^db/screentest/(?P<facility_id>\d+)/$', 'db.views.screenTest', name="screentest"),
    
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
