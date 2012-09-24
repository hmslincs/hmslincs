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
    url(r'^example/libraries/$','example.views.libraryIndex', name="listLibraries"),
    url(r'^example/libraries/(?P<library_id>\d+)/$', 'example.views.libraryDetail', name="library_detail"),
    url(r'^example/screens/$','example.views.screenIndex', name="listScreens"),
    url(r'^example/screens/(?P<screen_id>\d+)/$', 'example.views.screenDetailMain', name="screen_detail"),
    url(r'^example/screens/(?P<screen_id>\d+)/main$', 'example.views.screenDetailMain', name="screen_detail_main"),
    url(r'^example/screens/(?P<screen_id>\d+)/cells$', 'example.views.screenDetailCells', name="screen_detail_cells"),
    url(r'^example/screens/(?P<screen_id>\d+)/results$', 'example.views.screenDetailResults', name="screen_detail_results"),
    #url(r'^example/search/', include('haystack.urls'), name="haystackSearch"),
    
    (r'^example/api/', include(v1_api.urls)),
)
