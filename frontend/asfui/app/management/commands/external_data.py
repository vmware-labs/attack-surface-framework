#!/usr/bin/python3
from django.core.management.base import BaseCommand, CommandError
from datetime import date, datetime
from django.utils import timezone
from cProfile import label
from app.models import vdTarget, vdInTarget, vdResult, vdServices, vdInServices, vdRegExp, vdJob  

from os import path
import sys
import subprocess
import os
import re
import argparse
import csv
import json
from urllib.request import localhost
from app.tools import autodetectType, delta
from app.targets import internal_delete

#Static and Global Declarations

def parser_default(PARSER_INPUT, PARSER_OUTPUT, vdZone, tag, mode, owner):
    for DATA in PARSER_INPUT:
        debug(str(DATA))
    return

def parser_vmw_csv(PARSER_INPUT, PARSER_OUTPUT, vdZone, tag, mode, owner):
    #,Public IP,OwnerEmail,Account ID,ServiceName,Environment,RequestedBy
    CSV_READER = csv.reader(PARSER_INPUT, delimiter=',')
    IgnoreTheFirstLine = True
    for DATA in CSV_READER:
        debug(str(DATA)+"\n")
        debug("\tDomain:"+DATA[1]+"\n")
        debug("\t\tOwners:"+DATA[2]+","+DATA[6]+"\n")
        debug("\t\tEnvironment:"+DATA[5]+"\n")
        debug("\t\tDescription:"+DATA[4]+"\n")
        UNIT = {}
        UNIT['owner'] = DATA[2]+","+DATA[6]
        UNIT['accountid'] = DATA[3]
        UNIT['environment'] = DATA[5]
        UNIT['tag'] = tag
        UNIT['domain'] = DATA[1]
        UNIT['description'] = DATA[4]
        if not IgnoreTheFirstLine:
            JSON_LINE = json.dumps(UNIT)
            PARSER_OUTPUT.write(JSON_LINE+"\n")
        else:
            IgnoreTheFirstLine = False                
    return

def parser_vmw_csvfd(PARSER_INPUT, PARSER_OUTPUT, vdZone, tag, mode, owner):
    #,accountID,entityId,PublicIP,OwnerEmail,ServiceName,Environment,RequestedBy
    CSV_READER = csv.reader(PARSER_INPUT, delimiter=',')
    IgnoreTheFirstLine = True
    for DATA in CSV_READER:
        debug(str(DATA)+"\n")
        debug("\tIPAddr:"+DATA[3]+"\n")
        debug("\t\tOwners:"+DATA[4]+","+DATA[7]+"\n")
        debug("\t\tEnvironment:"+DATA[6]+"\n")
        debug("\t\tDescription:"+DATA[5]+"\n")
        UNIT = {}
        UNIT['owner'] = DATA[4]+","+DATA[7]
        UNIT['accountid'] = DATA[1]
        UNIT['environment'] = DATA[6]
        UNIT['tag'] = tag
        UNIT['domain'] = DATA[3]
        UNIT['description'] = DATA[5]
        if not IgnoreTheFirstLine:
            JSON_LINE = json.dumps(UNIT)
            PARSER_OUTPUT.write(JSON_LINE+"\n")
        else:
            IgnoreTheFirstLine = False                
    return

def parser_crt_sh(PARSER_INPUT, PARSER_OUTPUT, vdZone, tag, mode, owner):
    for DATA in PARSER_INPUT:
        DATA=DATA.rstrip()
        debug("\tDomain:"+DATA+"\n")
        debug("\t\tOwners:"+owner+"\n")
        debug("\t\tTag:"+tag+"\n")
        debug("\t\tDescription: Discovery from Crt.sh\n")
        UNIT = {}
        UNIT['owner'] = owner
        UNIT['tag'] = tag
        UNIT['domain'] = DATA
        UNIT['description'] = "Discovery from Crt.sh"
        JSON_LINE = json.dumps(UNIT)
        PARSER_OUTPUT.write(JSON_LINE+"\n")
    return

def parser_vmw_json(PARSER_INPUT, PARSER_OUTPUT, vdZone, tag, mode, owner):
    JSON_DATA = PARSER_INPUT.read()
    JSON_DATA = json.loads(JSON_DATA)
    for SECTION in JSON_DATA:
        debug(str(SECTION)+"\n")
        for DATA in JSON_DATA[SECTION]:
            debug("\t"+str(DATA)+"\n")
        debug("\t\tOwner:["+str(JSON_DATA[SECTION][1])+"]\n")
        debug("\t\tEnvironment:["+str(JSON_DATA[SECTION][2])+"]\n")        
        for DOMAIN in JSON_DATA[SECTION][0]:
            DOMAIN = DOMAIN[:-1]
            debug("\t\tDomain:["+str(DOMAIN)+"]\n")
            UNIT = {}
            UNIT['owner'] = str(JSON_DATA[SECTION][1])
            UNIT['accountid'] = str(SECTION)
            UNIT['environment'] = str(JSON_DATA[SECTION][2])
            UNIT['tag'] = tag
            #The following line, removes the special char by an asterisk, but.... needed??
            #UNIT['domain'] = DOMAIN.replace("\\052", "*")
            #Amass just requires the top domain, having a wildcard means we need to search for more findings?
            #What if the search engine finds unknown owners by removing parts of a subdomain.
            UNIT['domain'] = DOMAIN.replace("\\052.", "")
            JSON_LINE = json.dumps(UNIT)
            PARSER_OUTPUT.write(JSON_LINE+"\n")
    return

def parser_vmw_jsonl(PARSER_INPUT, PARSER_OUTPUT, vdZone, tag, mode, owner):
    vdServicesModel = vdInServices
    vdTargetModel = vdInTarget
    if vdZone == "internal" or vdZone == "external":            
        if vdZone == "external":
            vdServicesModel = vdServices
            vdTargetModel = vdTarget
    else:
        debug("Error, vdZone:'"+str(vdZone)+"' not defined, breaking\n")
        sys.exit(-1)
        
#     for line in PARSER_INPUT:
#         JSONL = json.loads(line)
#         debug("JSONL:"+str(JSONL)+"\n")
    target_manager(vdTargetModel, vdServicesModel, PARSER_INPUT, vdZone, tag, mode)
            
#Here is the global declaration of parsers, functions can be duplicated
action={'default':parser_default, 'vmw.csv':parser_vmw_csv, 'vmw.csvfd':parser_vmw_csvfd, 'vmw.json':parser_vmw_json, 'vmw.jsonl':parser_vmw_jsonl, 'crt.sh':parser_crt_sh}

def parseLines(PARSER_INPUT, PARSER_OUTPUT, vdZone, parser, tag, mode, owner):
    return action[parser](PARSER_INPUT, PARSER_OUTPUT, vdZone, tag, mode, owner)

PARSER_DEBUG=False
def debug(text):
    if PARSER_DEBUG:
        sys.stderr.write(str(text))
    return

class Command(BaseCommand):
    help = 'Processes Worker Scans'
    def add_arguments(self, parser):
        #This single module reads the input file and convert it into 
        parser.add_argument('--input', help='The input file, if not provided stdin is used', default='stdin')
        parser.add_argument('--mode', help='The action for targets/findings merge|delete|deletebytag|sync', default='merge')
        parser.add_argument('--tag', help='Assign tag for targets [EXTERNAL]', default='EXTERNAL')
        parser.add_argument('--output', help='The output File filename|stdout', default='stdout')
        parser.add_argument('--vdzone', help='The output vdZone internal|external', default='error')
        parser.add_argument('--parser', help='The parser algorithm vmw[.csv|.json]', default='default')
        parser.add_argument('--owner', help='Default email user@domain', default='user@domain')
        parser.add_argument('--debug', help='Print verbose data', action='store_true', default=False)
        
    def handle(self, *args, **kwargs):
        PARSER_INPUT = sys.stdin
        global PARSER_DEBUG
        PARSER_DEBUG = kwargs['debug']
        PARSER_OUTPUT = sys.stdout
        
        debug(str(kwargs)+"\n")
       
        if kwargs['parser'] not in action:
            PARSER_DEBUG = True
            debug("Parser:"+kwargs['parser']+" not found in action declaration:"+str(action)+"\n")
            sys.exit()

        if kwargs['input'] != "stdin":
            PARSER_INPUT = open(kwargs['input'],'r')
            debug("Input: "+kwargs['input']+"\n")
        else:
            debug("Input: STDIN \n")
        if kwargs['output'] != "stdout":
            PARSER_OUTPUT = open(kwargs['output'],'w+')
            debug("Output: "+kwargs['output']+"\n")
        else:
            debug("Output: STDOUT \n")
            
        parseLines(PARSER_INPUT, PARSER_OUTPUT, kwargs['vdzone'], kwargs['parser'], kwargs['tag'], kwargs['mode'], kwargs['owner'])
        debug("\n")

def target_manager(vdTargetModel, vdServicesModel, JSONL_FILE, vdZone, Tag, WorkMode):
    tz = timezone.get_current_timezone()
    LastDate = datetime.now().replace(tzinfo=tz)
    for JSONL_DATA in JSONL_FILE:
        data = json.loads(JSONL_DATA)
        domain = data['domain']
        Type = autodetectType(domain)
        debug("JSONL Data:"+str(data)+"\n")
        try:
            Answer = vdTargetModel.objects.update_or_create(name=domain, defaults={'type': Type, 'tag':Tag, 'lastdate': LastDate, 'owner': data['owner'], 'metadata': JSONL_DATA})
            if Answer[1]:
                debug("[Alerting about new object]")
                MSG = data
                MSG['message'] = "[NEW][OBJECT INTO "+vdZone.upper()+" TARGET DATABASE]"
                MSG['type'] = Type
                MSG['name'] = domain
                MSG['lastupdate'] = str(LastDate)
                delta(MSG)
        except Exception as e:
            sys.stderr.write(str(e)+"Error Target, Skipping:"+str(data)+"\n")
        
    sys.stderr.write("WorkMode:"+WorkMode+"\n")
    if WorkMode != 'merge':
        if WorkMode == 'sync':
            DeleteTarget = vdTargetModel.objects.filter(tag=Tag).filter(lastdate__lt=LastDate)
        if WorkMode == 'delete':
            #The equals command in filter, does not work for datetimes, so we use __gte instead
            DeleteTarget = vdTargetModel.objects.filter(tag=Tag).filter(lastdate__gte=LastDate)
        if WorkMode == 'deletebytag':
            DeleteTarget = vdTargetModel.objects.filter(tag=Tag)
        internal_delete(vdTargetModel,vdServicesModel,DeleteTarget,autodetectType,delta)
                
