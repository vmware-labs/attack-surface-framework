# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.contrib import admin
from django.urls import path, include, re_path # add this
from django.conf import settings
from django.views.generic import RedirectView

urlpatterns = []

if hasattr(settings, 'DJANGO_ADMIN_ENABLED'):
    if settings.DJANGO_ADMIN_ENABLED:
        urlpatterns += [    
                path("admin/" , admin.site.urls),          # Django admin route 
                re_path(r'^admin$', RedirectView.as_view(url = '/admin/')),
        ]

urlpatterns +=[
    #path('admin/', admin.site.urls),          # Django admin route
    path("", include("authentication.urls")),
    ]
if hasattr(settings, 'SOCIAL_AUTH_GOOGLE_ENABLED'):
    if settings.SOCIAL_AUTH_GOOGLE_ENABLED:
        urlpatterns += [
        path("accounts/", include("allauth.urls")),
   
]

if hasattr(settings, 'SOCIAL_SAML2_ENABLED'):
    if settings.SOCIAL_SAML2_ENABLED:
        urlpatterns += [
            re_path(r'^saml2/', include('djangosaml2.urls')),
            re_path(r'^sso/',include('djangosaml2.urls')),
        ]

urlpatterns += [
    path("", include("app.urls")), 
]

