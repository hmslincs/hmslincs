#from django.conf.urls import patterns, include, url
from django.conf.urls.defaults import *

from tastypie.api import Api
from example.api import SmallMoleculeResource,CellResource,DataSetResource

smallmolecule_resource = SmallMoleculeResource()
v1_api = Api(api_name='v1') 
v1_api.register(SmallMoleculeResource())
v1_api.register(CellResource())
v1_api.register(DataSetResource())

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    #url(r'^$', 'hmslincs_server.views.home', name='home'),
    # url(r'^hmslincs_server/', include('hmslincs_server.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # url(r'^???/', include('???.urls')),
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')), 
    url(r'^admin/', include(admin.site.urls)),
    url(r'^example/$', 'example.views.main', name="home"),
    url(r'^example/sm/$','example.views.smallMoleculeIndex', name="listSmallMolecules" ),
    url(r'^example/sm/(?P<sm_id>\d+)/$', 'example.views.smallMoleculeDetail', name="sm_detail"),
    url(r'^example/cells/$','example.views.cellIndex', name="listCells"),
    url(r'^example/cells/(?P<cell_id>\d+)/$', 'example.views.cellDetail', name="cell_detail"),
    url(r'^example/proteins/$','example.views.proteinIndex', name="listProteins"),
    url(r'^example/proteins/(?P<protein_id>\d+)/$', 'example.views.proteinDetail', name="protein_detail"),
    url(r'^example/libraries/$','example.views.libraryIndex', name="listLibraries"),
    url(r'^example/libraries/(?P<library_id>\d+)/$', 'example.views.libraryDetail', name="library_detail"),
    url(r'^example/screen/$','example.views.screenIndex', name="listScreens"),
    url(r'^example/screen/(?P<screen_id>\d+)/$', 'example.views.screenDetailMain', name="screen_detail"),
    url(r'^example/screen/(?P<screen_id>\d+)/main$', 'example.views.screenDetailMain', name="screen_detail_main"),
    url(r'^example/screen/(?P<screen_id>\d+)/cells$', 'example.views.screenDetailCells', name="screen_detail_cells"),
    url(r'^example/screen/(?P<screen_id>\d+)/proteins$', 'example.views.screenDetailProteins', name="screen_detail_proteins"),
    url(r'^example/screen/(?P<screen_id>\d+)/results$', 'example.views.screenDetailResults', name="screen_detail_results"),
    url(r'^example/study/$','example.views.studyIndex', name="listStudies"),
    url(r'^example/study/(?P<screen_id>\d+)/$', 'example.views.studyDetailMain', name="study_detail"),
    url(r'^example/study/(?P<screen_id>\d+)/main$', 'example.views.studyDetailMain', name="study_detail_main"),
    url(r'^example/study/(?P<screen_id>\d+)/cells$', 'example.views.studyDetailCells', name="study_detail_cells"),
    url(r'^example/study/(?P<screen_id>\d+)/proteins$', 'example.views.studyDetailProteins', name="study_detail_proteins"),
    url(r'^example/study/(?P<screen_id>\d+)/results$', 'example.views.studyDetailResults', name="study_detail_results"),
    #url(r'^example/search/', include('haystack.urls'), name="haystackSearch"),
    
    (r'^example/api/', include(v1_api.urls)),
)
