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

    (r'^explore/sensitivities/$', 'django.views.generic.simple.direct_to_template',
     {'template': 'sensitivities/index.html'}),

    (r'^explore/sensitivities/dose_response_grid.html$',
     'django.views.generic.simple.direct_to_template',
     {'template': 'sensitivities/dose_response_grid.html'}),
)

# For DEBUG mode only (development) serving of static files
urlpatterns += staticfiles_urlpatterns()
