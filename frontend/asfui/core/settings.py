# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
from decouple import config
from unipath import Path
import dj_database_url
import environ

root = environ.Path(__file__) - 4

APPEND_SLASH = True

env = environ.Env(
    DEBUG =(bool, False),
    DJANGO_ADMIN_ENABLED =(bool, False),
    
    LOGIN_FORM = (bool, True),
    SOCIAL_AUTH_GOOGLE_ENABLED =(bool, False),
    SOCIAL_AUTH_GITHUB_ENABLED = (bool, False),
    
    ALLOWED_HOSTS=(list, ["localhost"]),
    
    
    MONGO_USER=(str,''),
    MONGO_PASSWORD=(str, ''),
    MONGO_URL=(str, ''),
    MONGO_PORT=(str, ''),
    
    JIRA_ENABLED=(bool, False),
    JIRA_TOKEN=(str, ''),
    JIRA_URL=(str, ''),
    JIRA_USER=(str, ''),
    JIRA_SEVERITY=(str, ''),   
    JIRA_TICKET_CLOSE=(str,''),
    JIRA_PROJECT=(str,''),
    
    SOCIAL_SAML2_ENABLED = (bool, True),
    SAML2_ASF_URL=(str,''),
    SAML2_SSO_URL=(str,''),
    
    WPScan_Default_Severity=(str,'medium'),
    
)


if os.path.isfile(root('./.env.prod')):
    env.read_env(root('./' + env.str('DD_ENV_PATH', '.env.prod')))
  

  
LOGIN_FORM = env('LOGIN_FORM')
DJANGO_ADMIN_ENABLED = env('DJANGO_ADMIN_ENABLED')
DEBUG = env('DEBUG')
SOCIAL_AUTH_GOOGLE_ENABLED = env("SOCIAL_AUTH_GOOGLE_ENABLED")

SOCIAL_AUTH_GITHUB_ENABLED = env("SOCIAL_AUTH_GITHUB_ENABLED")
ALLOWED_HOSTS=env.list("ALLOWED_HOSTS")

MONGO_USER=env('MONGO_USER')
MONGO_PASSWORD=env('MONGO_PASSWORD')
MONGO_URL=env('MONGO_URL')
MONGO_PORT=env('MONGO_PORT')

JIRA_ENABLED=env('JIRA_ENABLED')
JIRA_TOKEN=env('JIRA_TOKEN')
JIRA_URL=env('JIRA_URL')
JIRA_USER=env('JIRA_USER')
JIRA_SEVERITY=env.json('JIRA_SEVERITY')
JIRA_TICKET_CLOSE=env('JIRA_TICKET_CLOSE')
JIRA_PROJECT=env('JIRA_PROJECT')

SOCIAL_SAML2_ENABLED = env("SOCIAL_SAML2_ENABLED")
SAML2_ASF_URL=env('SAML2_ASF_URL')
SAML2_SSO_URL=env('SAML2_SSO_URL')

WPScan_Default_Severity=env('WPScan_Default_Severity')

    
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = Path(__file__).parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='PutYourSecretHere')

# SECURITY WARNING: don't run with debug turned on in production!
#DEBUG = config('DEBUG', default=False)


# load production server from .env
#ALLOWED_HOSTS = ['*','localhost', '127.0.0.1', config('SERVER', default='127.0.0.1')]

# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'allauth', 
    'allauth.account', 
    'allauth.socialaccount',
    'app' , # Enable the inner app 
    
)

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'core.urls'
LOGIN_REDIRECT_URL = "home"   # Route defined in app/urls.py
LOGOUT_REDIRECT_URL = "home"  # Route defined in app/urls.py
TEMPLATE_DIR = os.path.join(BASE_DIR, "core/templates")  # ROOT dir for templates


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATE_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        # Allow some sort of concurrency to DB
        'OPTIONS': {'timeout': 60}

    }
}

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


#############################################################
# SOCIAL AUTH IMPLEMENTATION - GOOGLE
if SOCIAL_AUTH_GOOGLE_ENABLED:
    SOCIALACCOUNT_STORE_TOKENS=True
    SITE_ID = 1
    LOGIN_REDIRECT_URL ='home'
    SOCIALACCOUNT_QUERY_EMAIL = True
    ACCOUNT_LOGOUT_ON_GET= True
    ACCOUNT_UNIQUE_EMAIL = True
    ACCOUNT_EMAIL_REQUIRED = True
    INSTALLED_APPS += ('allauth.socialaccount.providers.google',)
    AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    )
    SOCIALACCOUNT_PROVIDERS = {
        'google': {
            'SCOPE': [
                'profile',
                'email',
            ],
            'AUTH_PARAMS': {
                'access_type': 'online',
            }   
        }
    }


#############################################################
# SOCIAL AUTH IMPLEMENTATION - GITHUB

if SOCIAL_AUTH_GITHUB_ENABLED:
    INSTALLED_APPS +=('allauth.socialaccount.providers.github',)
    AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
    )
    
    
    
#############################################################
# SAML2 AUTH IMPLEMENTATION - Add your SSO URL and additional Configuration details below before enabling


if SOCIAL_SAML2_ENABLED:
    import saml2
    import saml2.saml
    INSTALLED_APPS += ('djangosaml2',)
    MIDDLEWARE.append('djangosaml2.middleware.SamlSessionMiddleware')
    CSRF_COOKIE_DOMAIN = None
    SESSION_COOKIE_SAMESITE=None
    SAML_SESSION_COOKIE_NAME = 'saml_session'
    LOGIN_REDIRECT_URL = 'home'
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True
    LOGIN_URL = '/saml2/login/'
    URL_PREFIX = ''
    LOGIN_EXEMPT_URLS = (r'^%ssaml2/' % URL_PREFIX,)
    AUTHENTICATION_BACKENDS = (
        'django.contrib.auth.backends.ModelBackend',
        'djangosaml2.backends.Saml2Backend',
        )
    SAML_LOGOUT_REQUEST_PREFERRED_BINDING = saml2.BINDING_HTTP_POST
    SAML_DJANGO_USER_MAIN_ATTRIBUTE = 'username'
    #SAML_DJANGO_USER_MAIN_ATTRIBUTE_LOOKUP = '__iexact'
    SAML_USE_NAME_ID_AS_USERNAME = True
    SAML_CREATE_UNKNOWN_USER = True
    SAML_ATTRIBUTE_MAPPING = {
	    'NameID': ('username',),
        'email': ('emailAddress', ),
        'Firstname': ('Firstname', ),
        'Lastname': ('Lastname', ),
        }
    
    from os import path
    ASF_URL = SAML2_ASF_URL
    SSO_URL = SAML2_SSO_URL
    
    SAML_CONFIG =  {
        # full path to the xmlsec1 binary programm
        'xmlsec_binary': '/usr/bin/xmlsec1',

         # your entity id, usually your subdomain plus the url to the metadata view
        'entityid': '%s/saml2/metadata/' % ASF_URL,


         # directory with attribute mapping
        'attribute_map_dir': path.join(BASE_DIR, 'attribute-maps'),

         # this block states what services we provide
        'service': {
            # we are just a lonely SP
            'sp': {
                'allow_unsolicited': True,
                'name': 'Attack Surface Framework',
                "want_response_signed": True,
                "want_assertions_signed": False,
                "force_authn": True,
                'endpoints': {
                    # url and binding to the assetion consumer service view
                    # do not change the binding or service name
                    'assertion_consumer_service': [
                        ('%s/saml2/acs/' % ASF_URL,
                         saml2.BINDING_HTTP_POST),
                    ],
                    # url and binding to the single logout service view
                    # do not change the binding or service name
                    'single_logout_service': [
                        ('%s/saml2/ls/' % ASF_URL,
                         saml2.BINDING_HTTP_REDIRECT),
                        ('%s/saml2/ls/post' % ASF_URL,
                         saml2.BINDING_HTTP_POST),
                    ],
                },

                 # attributes that this project need to identify a user
                'required_attributes': ['Email', 'NameID'],

                 # attributes that may be useful to have but not required
                'optional_attributes': ['Firstname', 'Lastname'],

                 # in this section the list of IdPs we talk to are defined
                'idp': {
                    # we do not need a WAYF service since there is
                    # only an IdP defined here. This IdP should be
                    # present in our metadata

                     # the keys of this dictionary are entity ids
                        SSO_URL+'/SAAS/API/1.0/GET/metadata/idp.xml': {
                            'single_sign_on_service': {
                                saml2.BINDING_HTTP_REDIRECT: '%s/SAAS/auth/federation/sso' % SSO_URL,
                            },
                            'single_logout_service': {
                                saml2.BINDING_HTTP_REDIRECT: '%s/SAAS/auth/federation/sso' % SSO_URL,
                            },
                        },
                    },
                },
            },

         # where the remote metadata is stored
        'metadata': {
            'remote':[
                {
                    "url":'%s/SAAS/API/1.0/GET/metadata/idp.xml' % SSO_URL
                }
            ],
        },

         # set to 1 to output debugging information
        'debug': 1,

         # Signing
        #'key_file': path.join(BASEDIR, 'mycert.key'), # private part
        #'cert_file': path.join(BASEDIR, 'mycert.pem'), # public part

         # Encryption
        #'encryption_keypairs': [{
        #    'key_file': path.join(BASEDIR, 'my_encryption_key.key'), # private part
        #    'cert_file': path.join(BASEDIR, 'my_encryption_cert.pem'), # public part
        #}],

         # own metadata settings
            'contact_person': [
                {'given_name': '',
                'sur_name': '',
                'company': '',
                'email_address': '',
                'contact_type': 'technical'},
            ],
            # you can set multilanguage information here
            'organization': {
                'name': [('Information Security', 'en')],
                'display_name': [('Information Security', 'en')],
            },
            'valid_for': 24,  # how long is our metadata valid
        }








    

    


    




# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


#############################################################
# SRC: https://devcenter.heroku.com/articles/django-assets

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# Extra places for collectstatic to find static files.
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'core/static'),
)
#############################################################
#############################################################
