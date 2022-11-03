# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path, re_path
from app import views

urlpatterns = [
    #External
    path('vd-targets',views.targets),
    path('vd-amass', views.amass),
    path('vd-portscan', views.portscan),
    path('vd-redteam', views.redteam),
    path('vd-nuclei', views.nuclei),
    path('vd-nuclei-templates', views.nucleitemplates),
#    path('vd-dashboard', views.dashboard),
    
    #Internal
    path('vd-in-targets',views.intargets),
    path('vd-in-portscan',views.inportscan),
#    path('vd-in-dashboard', views.indashboard),
    #Generic
    path('vd-export', views.export),
    
    # The home page
    path('', views.targets, name='home'),
#    path('', views.dashboard, name='dashboard'),
    
    # Matches any html file
    re_path(r'^.*\.*', views.pages, name='pages'),

]
