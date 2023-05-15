#!/usr/bin/python3
#VER:1
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from cProfile import label
from app.models import vdTarget, vdResult, vdServices, vdInServices, vdRegExp, vdJob, vdNucleiResult

from os import path
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


def merge_csv(context={}):
    debug("Calling Join CSV\n"+str(context)+"\n")
    FILES=context['input'].split(",")
    ODESC=sys.stdout
    if 'output' in context and context['output'] != 'stdout':
        ODESC=open(context['output'],"w+")

    for FILE in FILES:
        FDESC=None
        if FILE=="stdin":
            FDESC=sys.stdin
        else:
            FDESC=open(FILE,"+r")
        DISCARD1ST = True
        for line in FDESC:
            if DISCARD1ST:
                DISCARD1ST=False                
            else:
                ODESC.write(line)
            

def merge_ip(context={}):
    debug("Calling Merge IP\n"+str(context)+"\n")
    FILES=context['input'].split(",")
    ODESC=sys.stdout
    if 'output' in context and context['output'] != 'stdout':
        ODESC=open(context['output'],"w+")

    for FILE in FILES:
        if Path(FILE).is_file():
            FDESC=None
            if FILE=="stdin":
                FDESC=sys.stdin
            else:
                FDESC=open(FILE,"+r")
            DISCARD1ST = True
            for line in FDESC:
                if DISCARD1ST:
                    DISCARD1ST=False                
                else:
                    ip=line.split(",")[3]
                    ODESC.write(ip+"\n")
    return

def slice_list(context):
    debug("Slice list\n"+str(context)+"\n")
    FILES=context['input'].split(",")
    OUTPUT_COUNTER=0
    ODESC=sys.stdout
    ODESC_IPONLY=sys.stdout
    IP_CACHE=[]
    def cycle_output(counter,context):
        if 'output' in context and context['output'] != 'stdout':
            BASE_NAME=context['output']+"."+str(counter).zfill(8)
            return open(BASE_NAME+".list","w+"), open(BASE_NAME+".ip","w+")
        else:
            return sys.stdout

    ODESC, ODESC_IPONLY=cycle_output(OUTPUT_COUNTER,context)
    PARTIAL_COUNTER=0
    MAX_COUNTER=int(context['size'])
    for FILE in FILES:
        FDESC=None
        if FILE=="stdin":
            FDESC=sys.stdin
        else:
            FDESC=open(FILE,"+r")
        
        for line in FDESC:
            PARTIAL_COUNTER+=1
            if PARTIAL_COUNTER>=MAX_COUNTER:
                ODESC.close()
                ODESC_IPONLY.close()
                OUTPUT_COUNTER+=1
                ODESC, ODESC_IPONLY=cycle_output(OUTPUT_COUNTER,context)
                PARTIAL_COUNTER=0
            IP_SEARCH = DETECTOR_IPADDRESS_IN_URI.findall(line)
            #debug("LEN="+str(len(IP_SEARCH))+str(IP_SEARCH)+"\n")
            if len(IP_SEARCH)==1:
                IP=IP_SEARCH[0]
                if IP not in IP_CACHE:
                    ODESC_IPONLY.write(IP+"\n")
                    IP_CACHE.append(IP)
            ODESC.write(line)
    
    return

def validate_list(context):
    if not context['input'].endswith(".ip"):
        debug("Error, the list for validations must end in .ip, and .list is URI list and .ip.valid the valid ip list")
        sys.exit(-1)
    BASENAME=context['input'].split(".ip")[0]
    IP_FILE_LIST=BASENAME+".ip.valid"
    IP_LIST=open(IP_FILE_LIST,"r")
    IP_CACHE=[]
    for IP in IP_LIST:
        IP_CACHE.append(IP.rstrip())
    debug(IP_CACHE)
    IP_LIST.close()
    URI_LIST_VALID=open(BASENAME+".list.valid","w+")
    URI_LIST=open(BASENAME+".list","r")
    for uri in URI_LIST:
        SEARCH_IP=DETECTOR_IPADDRESS_IN_URI.findall(uri)
        if len(SEARCH_IP)==1:
            if SEARCH_IP[0] in IP_CACHE:
                URI_LIST_VALID.write(uri)
            else:
                debug("Ignoring:"+SEARCH_IP[0]+" because is not more in use\n")
        else:
            URI_LIST_VALID.write(uri)
    return
def remove_services_by_tag(context):
    vdServicesModel = vdServices
    if 'scope' in context and context['scope']=='internal':
        vdServicesModel = vdInServices
    
    if 'tag' not in context:
        debug("Error, tag should be set")
        return
    
    OBJECTS_TO_DELETE=vdServicesModel.objects.filter(tags=context['tag'])
    for OBJECT_TO_DELETE in OBJECTS_TO_DELETE:
        debug("Preparing to delete:"+str(OBJECT_TO_DELETE))
    #OBJECTS_TO_DELETE.delete()
    return
    
#Here is the global declaration of parsers, functions can be duplicated
action={'default':merge_csv, 'merge.csv':merge_csv, 'merge.ip':merge_ip, 'slice.list':slice_list, 'validate.list':validate_list, 'remove.bytag':remove_services_by_tag}

class Command(BaseCommand):
    help = 'Processes Worker Scans'
    def add_arguments(self, parser):
        #This single module reads the input file and convert it into 
        parser.add_argument('--input', help='The input file/files, separated by commas.', default='stdin')
        parser.add_argument('--output', help='The output filename', default='stdout')
        parser.add_argument('--mode', help='The algorithm [default(merge.csv|merge.ip|slice.list|validate.list)]', default='default')
        parser.add_argument('--size', help='The size of the slice', default='200')
        parser.add_argument('--debug', help='Print verbose data', action='store_true', default=False)
        parser.add_argument('--scope', help='Scope internal or external if required by action', default='external')
        parser.add_argument('--tag', help='Tag if required by action', default='EXTERNAL')
        
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