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

    (r'^(?P<url>explore/pathway/)$',
     'django.contrib.flatpages.views.flatpage'),

    (r'^(?P<url>explore/trail-threshold-variability/)$',
     'django.contrib.flatpages.views.flatpage'),

    (r'^explore/responses/$', 'django.views.generic.simple.direct_to_template',
     {'template': 'responses/index.html'}),

    # Top-level index page.
    (r'^explore/10.1038-nchembio.1337/fallahi-sichani-2013/$',
     'django.views.generic.simple.direct_to_template',
     {'template': '10_1038_nchembio_1337__fallahi_sichani_2013/index.html'}),
    # Iframe content pages.
    (r'^explore/10.1038-nchembio.1337/fallahi-sichani-2013/intro_to_dose_response_curves_iframe\.html$',
     'django.views.generic.simple.direct_to_template',
     {'template': '10_1038_nchembio_1337__fallahi_sichani_2013/intro_to_dose_response_curves_iframe.html'}),
    (r'^explore/10.1038-nchembio.1337/fallahi-sichani-2013/dose_response_grid_iframe\.html$',
     'django.views.generic.simple.direct_to_template',
     {'template': '10_1038_nchembio_1337__fallahi_sichani_2013/dose_response_grid_iframe.html'}),
    (r'^explore/10.1038-nchembio.1337/fallahi-sichani-2013/scatterplot_browser_iframe\.html$',
     'django.views.generic.simple.direct_to_template',
     {'template': '10_1038_nchembio_1337__fallahi_sichani_2013/scatterplot_browser_iframe.html'}),
    # Conversion from old URL schemes.
    (r'^explore/(?:sensitivities|10.1038-nchembio.1337)/(?!fallahi-sichani-2013)(?P<suffix>.*)$',
     'django.views.generic.simple.redirect_to',
     {'url': '/explore/10.1038-nchembio.1337/fallahi-sichani-2013/%(suffix)s'}),
    # Catch-all for old deprecated pages -- redirect to index.
    (r'^explore/10.1038-nchembio.1337/fallahi-sichani-2013/',
     'django.views.generic.simple.redirect_to',
     {'url': '/explore/10.1038-nchembio.1337/fallahi-sichani-2013/'}),

    (r'^explore/adaptive-drug-resistance/$',
     'django.views.generic.simple.direct_to_template',
     {'template': 'adaptive_drug_resistance/index.html'}),

    (r'^explore/adaptive-drug-resistance/plsr-loadings/$',
     'django.views.generic.simple.direct_to_template',
     {'template': 'adaptive_drug_resistance/plsr_loadings/index.html'}),

    (r'^explore/adaptive-drug-resistance/vips/$',
     'django.views.generic.simple.direct_to_template',
     {'template': 'adaptive_drug_resistance/vips/index.html'}),

    (r'^(?P<url>explore/single-cell-dynamics/)$',
     'django.contrib.flatpages.views.flatpage'),

    (r'^(?P<url>explore/breast-cancer-signaling/.*)$',
     'django.contrib.flatpages.views.flatpage'),
)

# For DEBUG mode only (development) serving of static files
urlpatterns += staticfiles_urlpatterns()
