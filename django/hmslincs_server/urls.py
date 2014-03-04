#from django.conf.urls import patterns, include, url

from django.conf.urls.defaults import *
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic import TemplateView
from hmslincs_server.views import *
from settings import _djangopath
import os.path as op


urlpatterns = patterns('',

    # Login / logout.
    # Note: the name "login_url" name is set to the request by the registered hmslincs.context_procesor.login_url_with_redirect
    (r'^db/login/$', 'django.contrib.auth.views.login', {'template_name': 'db/login.html'}),
    url(r'^db/logout/$', logout_page, name='logout'),
    url(r'^db/', include('db.urls')),
    
    (r'^explore/pathway/$', 'django.views.static.serve',
     {'path': 'index.html',
      'document_root': op.join(_djangopath, 'pathway', 'static', 'pathway')}),

    (r'^explore/responses/$', 'django.views.generic.simple.direct_to_template',
     {'template': 'responses/index.html'}),

    (r'^explore/(?:sensitivities|10.1038-nchembio.1337)/(?!fallahi-sichani-2013)(?P<suffix>.*)$',
     'django.views.generic.simple.redirect_to',
     {'url': '/explore/10.1038-nchembio.1337/fallahi-sichani-2013/%(suffix)s'}),

    (r'^explore/10.1038-nchembio.1337/fallahi-sichani-2013/$',
     'django.views.generic.simple.direct_to_template',
     {'template': '10_1038_nchembio_1337__fallahi_sichani_2013/index.html'}),

    (r'^explore/10.1038-nchembio.1337/fallahi-sichani-2013/tools_table\.html$',
     'django.views.generic.simple.direct_to_template',
     {'template': '10_1038_nchembio_1337__fallahi_sichani_2013/tools_table.html'}),

    (r'^explore/10.1038-nchembio.1337/fallahi-sichani-2013/intro_to_dose_response_curves\.html$',
     'django.views.generic.simple.direct_to_template',
     {'template': '10_1038_nchembio_1337__fallahi_sichani_2013/intro_to_dose_response_curves.html'}),

    (r'^explore/10.1038-nchembio.1337/fallahi-sichani-2013/dose_response_grid\.html$',
     'django.views.generic.simple.direct_to_template',
     {'template': '10_1038_nchembio_1337__fallahi_sichani_2013/dose_response_grid.html'}),

    (r'^explore/10.1038-nchembio.1337/fallahi-sichani-2013/scatterplot_browser\.html$',
     'django.views.generic.simple.direct_to_template',
     {'template': '10_1038_nchembio_1337__fallahi_sichani_2013/scatterplot_browser.html'}),

    # breast_cancer_signaling is currently served by apache directly from
    # STATIC_ROOT, so no url patterns are listed here.
)

# For DEBUG mode only (development) serving of static files
urlpatterns += staticfiles_urlpatterns()
