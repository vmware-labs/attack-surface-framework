# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.contrib import admin

# Register your models here.
from .models import vdTarget, vdInTarget, vdResult, vdServices, vdInServices, vdRegExp, vdJob
admin.site.register(vdTarget)
admin.site.register(vdInTarget)
admin.site.register(vdResult)
admin.site.register(vdServices)
admin.site.register(vdInServices)
admin.site.register(vdRegExp)
admin.site.register(vdJob)