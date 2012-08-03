from django.conf.urls import patterns, include, url

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
    url(r'^admin/', include(admin.site.urls)),
    url(r'^example/$','example.views.index' ),
    url(r'^example/sm/(?P<sm_id>\d+)/$', 'example.views.detail')
)
