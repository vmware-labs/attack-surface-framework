#!/usr/bin/python3
from django.core.management.base import BaseCommand, CommandError
from app.models import *
from django.utils import timezone
import re
from cProfile import label
from app.tools import autodetectType, delta, debug, PARSER_DEBUG, get_metadata
import traceback

class Command(BaseCommand):
    help = 'Amass interpreter'

    def handle(self, *args, **kwargs):
        #Targets=vdTarget.objects.all()
        Targets=vdTarget.objects.filter(type='DOMAIN')
        FileTargets=open("/home/amass/targets.txt",'w+')
        for domain in Targets:
            FileTargets.write(domain.name+"\n")
        sys.stdout.write("Starting Amass")
        FileTargets.close()