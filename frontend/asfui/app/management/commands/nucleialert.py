#!/usr/bin/python3
#VER:1
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from cProfile import label
from app.models import vdTarget, vdResult, vdServices, vdInServices, vdRegExp, vdJob, vdNucleiResult

from os import path
from pathlib import Path
import sys
import subprocess
import os
import re
import argparse
import csv
import json
from urllib.request import localhost
from app.tools import *
from app.nuclei import *


def alert_duedate(context={}):
    #TODO: filter false positives
    NOW = timezone.now()
    debug("Calling Nuclei Alert by bumpdate ["+str(NOW)+"]\n")
    ResultSet = vdNucleiResult.objects.filter(bumpdate__lt=NOW)
    for VDNF in ResultSet:
        debug("Name:"+VDNF.name+":Owner:"+VDNF.owner+":"+str(VDNF.bumpdate)+"\n")
        MSG = {'owner':VDNF.owner, 'message':"[NUCLEI][ALERT][UNATTENDED]", 'host':VDNF.name, 'level':VDNF.level, 'scope':VDNF.scope, 'vulnerability':VDNF.vulnerability, 'engine':VDNF.engine, 'detectiondate':VDNF.detectiondate, 'port':VDNF.port, 'protocol':VDNF.protocol, 'ptime':VDNF.ptime}
        delta(MSG)

def nuclei_clean(context={}):
    #30 days, 24h each
    OLD = timezone.now()-timedelta(hours=30*24)
    debug("Calling Nuclei clean by lastseen ["+str(OLD)+"]\n")
    ResultSet = vdNucleiResult.objects.filter(lastdate__lt=OLD)
    for VDNF in ResultSet:
        debug("[Delete][Unseen]Name:"+VDNF.name+":Owner:"+VDNF.owner+":"+str(VDNF.lastdate)+"\n")
        MSG = {'owner':VDNF.owner, 'message':"[NUCLEI][DELETE][UNSEEN]", 'host':VDNF.name, 'level':VDNF.level, 'scope':VDNF.scope, 'vulnerability':VDNF.vulnerability, 'engine':VDNF.engine, 'detectiondate':VDNF.detectiondate, 'port':VDNF.port, 'protocol':VDNF.protocol, 'ptime':VDNF.ptime}
        delta(MSG)
    ResultSet.delete()


def nuclei_purge(context={}):
    debug("Calling Purge action all over findings\n")
    vdNucleiResult.objects.all().delete()
    return

def nuclei_templates(context={}):
    debug("Calling nuclei templates enumerator\n")
    TEMPLATES_DIR=[context['templatesdir']]
    TEMPLATES=get_nuclei_templates(TEMPLATES_DIR)
    debug(str(TEMPLATES))
    return

def nuclei_blacklist(context={}):
    debug("Calling nuclei templates blacklist\n")
    TEMPLATES=get_nuclei_templates_4bl()
    debug(str(TEMPLATES))
    CMDLINE=""
    for template in TEMPLATES:
        CMDLINE+="-exclude-templates "+template+" "
    sys.stdout.write(CMDLINE)
    return

def nuclei_blacklist_save(context={}):
    debug("Calling nuclei templates blacklist\n")
    TEMPLATES=get_nuclei_templates_4bl()
    debug(str(TEMPLATES))
    BLF=open(context['templatesignorefile'],'w+')
    IGNORE='# ==| Nuclei Templates Ignore list |==\n'
    IGNORE+='# ====================================\n'
    IGNORE+='#\n'
    IGNORE+='# This is default list of tags and files to excluded from default nuclei scan.\n'
    IGNORE+='# More details - https://nuclei.projectdiscovery.io/nuclei/get-started/#template-exclusion\n'
    IGNORE+='# tags is a list of tags to ignore execution for\n'
    IGNORE+='# unless asked for by the user.\n'
    IGNORE+='#tags:\n'
    IGNORE+='#   - "fuzz"\n'
    IGNORE+='#  - "dos"\n'
    IGNORE+='# files is a list of files to ignore template execution\n'
    IGNORE+='# unless asked for by the user.\n'
    IGNORE+='files:\n'
    for template in TEMPLATES:
        IGNORE+='  - '+template+'\n'
    BLF.write(IGNORE)
    BLF.close()
    return

def nuclei_config_save(context={}):
    debug("Calling nuclei templates blacklist save in configuration\n")
    TEMPLATES=get_nuclei_templates_4bl()
    debug(str(TEMPLATES))
    BLF=open(context['configoutput'],'w+')
    NTMPLT=open(context['configtemplate'],'r')
    IGNORE=NTMPLT.read()
    NTMPLT.close()
    EXCLUDE_HEADER=False
    for template in TEMPLATES:
        if not EXCLUDE_HEADER:
            EXCLUDE_HEADER=True
            IGNORE+='\nexclude-templates: # Template based exclusion\n'
        IGNORE+='  - '+template+'\n'
    BLF.write(IGNORE)
    BLF.close()
    return

#Here is the global declaration of parsers, functions can be duplicated
action={'default':alert_duedate, 'alert.duedate':alert_duedate, 'clean':nuclei_clean, 'purge':nuclei_purge, 'templates':nuclei_templates, 'blacklist':nuclei_blacklist, 'blacklist.save':nuclei_blacklist_save, 'config.save':nuclei_config_save}

class Command(BaseCommand):
    help = 'Processes Worker Scans'
    def add_arguments(self, parser):
        #This single module reads the input file and convert it into 
        #parser.add_argument('--input', help='The input file, if not provided stdin is used', default='stdin')
        #parser.add_argument('--output', help='The output JobID:ID', default='error')
        parser.add_argument('--mode', help='The algorithm [default(alert.duedate)|clean, purge, templates, blacklist[.save]], config.save for reviewing the findings and alert for not attended', default='default')
        parser.add_argument('--templatesdir', help='The template directory, default /home/nuclei-templates', default="/home/nuclei-templates")
        parser.add_argument('--templatesignorefile', help='The template directory, default /home/nuclei-templates/.nuclei-ignore', default="/home/nuclei-templates/.nuclei-ignore")
        parser.add_argument('--configtemplate', help='The template for default configuration, default /opt/asf/redteam/nuclei/config.yaml', default="/opt/asf/redteam/nuclei/config.yaml")
        parser.add_argument('--configoutput', help='The file to store with the exclusions, default /home/asf/nuclei-config.yaml', default="/home/asf/nuclei-config.yaml")
        parser.add_argument('--debug', help='Print verbose data', action='store_true', default=False)
        
    def handle(self, *args, **kwargs):        
        PARSER_INPUT = sys.stdin
        global PARSER_DEBUG
        PARSER_DEBUG = kwargs['debug']
        
        debug(str(kwargs)+"\n")
       
        if kwargs['mode'] not in action:
            PARSER_DEBUG = True
            debug("Parser:"+kwargs['mode']+" not found in action declaration:"+str(action)+"\n")
            sys.exit()
        
        #Main code here
        debug("Starting operations for "+kwargs['mode']+"\n")
        action[kwargs['mode']](kwargs)