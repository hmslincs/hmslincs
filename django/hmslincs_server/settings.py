import socket
import os.path as op
from os import environ
_djangopath = op.abspath(op.dirname(op.dirname(__file__)))
_sqlite3dbpath = op.join(_djangopath, 'hmslincs.db')

# Django settings for hmslincs_server project.

DEBUG = not op.abspath(__file__).startswith('/www/')
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('Sean Erickson', 'sean_erickson@hms.harvard.edu'),
)

MANAGERS = ADMINS

DATABASES = {
    # defaults for local developer workstation testing
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'django',
        'USER': 'django',
    }
}

# now we'll check to see if we're running in one of a few specific contexts and
# modify the db connection settings accordingly
_dbdefault = DATABASES['default']
if 'LINCS_PGSQL_DB' in environ:
    # explicit db configuration for lincs site in environment variables
    _dbdefault['NAME'] = environ['LINCS_PGSQL_DB']
    _dbdefault['HOST'] = environ['LINCS_PGSQL_SERVER']
    _dbdefault['USER'] = environ['LINCS_PGSQL_USER']
    _dbdefault['PASSWORD'] = environ['LINCS_PGSQL_PASSWORD']
elif 'OSHERNATPROD_PGSQL_DB' in environ:
    # explicit db configuration for oshernatprod site in environment variables
    # TODO REMOVE THIS SECTION ONCE WE HAVE A DEV/STAGING environment for LINCS
    _dbdefault['NAME'] = environ['OSHERNATPROD_PGSQL_DB']
    _dbdefault['HOST'] = environ['OSHERNATPROD_PGSQL_SERVER']
    _dbdefault['USER'] = environ['OSHERNATPROD_PGSQL_USER']
    _dbdefault['PASSWORD'] = environ['OSHERNATPROD_PGSQL_PASSWORD']
elif socket.getfqdn().endswith('.orchestra'):
    # otherwise (no explicit db config in env vars), if we are running on
    # orchestra we will try and set up the db config by convention
    if op.abspath(__file__).startswith('/www/dev.lincs'):
        # running from the dev site dir, so set up for the dev db
        _dbdefault['NAME'] = 'devlincs'
        _dbdefault['HOST'] = 'dev.pgsql.orchestra'
    elif op.abspath(__file__).startswith('/www/'):
        # running from the live site dir, so set up for the live db
        _dbdefault['NAME'] = 'lincs'
        _dbdefault['HOST'] = 'pgsql.orchestra'
    else:
        raise RuntimeError("Please only run this from a website directory,"
                           "or explicitly set LINCS_PGSQL_{DB,SERVER,USER,PASSWORD}")
    # since we have a multi-user db environment on orchestra, there is no good
    # default for the username so we'll delete that setting to leave it
    # empty. if you do nothing else, your unix username will just "pass through"
    # to the db connection, which will work most of the time. if you need to set
    # a user/password explicitly, use the PGUSER/PGPASS environment variables
    # and/or ~/.pgpass.
    del _dbdefault['USER']
elif environ.get('HMSLINCS_DEV', 'false') == 'true':
    _dbdefault['ENGINE'] = 'django.db.backends.sqlite3'
    _dbdefault['NAME'] = _sqlite3dbpath

del _dbdefault

if socket.getfqdn().endswith('.orchestra'):

    # Additional locations of static files
    STATICFILES_DIRS = (
        # Put strings here, like "/home/html/static" or "C:/www/django/static".
        # Always use forward slashes, even on Windows.
        # Don't forget to use absolute paths, not relative paths.
        '/groups/lincs/data/images/',
    )   
else:

    # Additional locations of static files
    STATICFILES_DIRS = (
        # Put strings here, like "/home/html/static" or "C:/www/django/static".
        # Always use forward slashes, even on Windows.
        # Don't forget to use absolute paths, not relative paths.
        '/home/sde4/docs/work/LINCS/data/images/',
        op.join(_djangopath, '..', 'sampledata', 'images' ),
    )   

# Add the assets directory for cross-app dependancies
STATICFILES_DIRS = STATICFILES_DIRS + (
    op.normpath(op.join(_djangopath, 'static')),
)

# add our custom hmslincs project library path
import sys
sys.path.append(op.join(_djangopath, '..','src'))


# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'US/Eastern'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = op.join(_djangopath, '..', '..', '..', 'docroot', '_static')
STATIC_AUTHENTICATED_FILE_DIR= op.join(_djangopath, '..','..','authenticated_static_files')
# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/_static/'

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'l)&amp;m7^7s_j02pr-rdamd5qn#7sk_6ur8oqmk7zb!jst3$fh(wc'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    'webtemplates.loaders.Loader',
#     'django.template.loaders.eggs.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.static",
    "django.contrib.messages.context_processors.messages",
    "django.core.context_processors.request",
    "hmslincs_server.context_processors.login_url_with_redirect",
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

# uncomment to enable - this is the default, but we'll override 
# AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',) # Note, this is the default
# our custom backend checks the user table, then authenticates with ECommons
AUTHENTICATION_BACKENDS = ('db.auth.CustomAuthenticationBackend',)  
ROOT_URLCONF = 'hmslincs_server.urls'

# URL of the login page.
LOGIN_URL = '/db/login/'
LOGOUT_URL = '/db/logout/'
LOGIN_REDIRECT_URL = '/db/'


# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'hmslincs_server.wsgi.application'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    op.join(_djangopath, 'templates')
)

# For webtemplates, use the live WP instance if we are running on the live site,
# otherwise use the dev instance.
WEBTEMPLATES_HOST = (
    'lincs.hms.harvard.edu' if _djangopath.startswith('/www/lincs.') else
    'dev.lincs.hms.harvard.edu')
WEBTEMPLATES_BASE = 'http://%s/templates/' % WEBTEMPLATES_HOST
WEBTEMPLATES = [
    (WEBTEMPLATES_BASE + 'base/', 'wordpress_base.html'),
]

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.admindocs',
    'django_tables2', # for UI tabling
    'tastypie', # manual says this is "not necessary, but useful"
    'webtemplates',
    'db',
    'pathway',
    'responses',
    '10_1038_nchembio_1337__fallahi_sichani_2013',
    'breast_cancer_signaling',
    'single_cell_dynamics',
    'adaptive_drug_resistance',
    'trail_threshold_variability',
    # # 'south', #for schema migrations
    # # 'fts', # for full text search
)

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.

# NOTE: Django's default logging configuration
# By default, Django configures the django.request logger so that all messages 
# with ERROR or CRITICAL level are sent to AdminEmailHandler, as long as the DEBUG setting is set to False.
#
# All messages reaching the django catch-all logger when DEBUG is True are sent 
# to the console. They are simply discarded (sent to NullHandler) when DEBUG is False.

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s:%(lineno)d %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(asctime)s %(pathname)s:%(lineno)d:%(levelname)s: %(message)s'
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'console':{
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },  
        'console_verbose':{
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
#        'db': { 
#            'handlers': ['console'],
#            'propagate': True,
#            'level': 'WARN',
#        },
#        'hms': {
#            'handlers': ['console'],
#            'propagate': True,
#            'level': 'WARN',
#        },
#        'util': {  
#            'handlers': ['console'],
#            'propagate': True,
#            'level': 'WARN',
#        },
#        'django.db': {  # if you want to see how django makes sql, use this one
#            'handlers': ['console'],
#            'propagate': True,
#            'level': 'WARN',
#        },      
        '': {  # set a default handler
            'handlers': ['console'],
            'propagate': True,
            'level': 'INFO',
        },
    }
}
