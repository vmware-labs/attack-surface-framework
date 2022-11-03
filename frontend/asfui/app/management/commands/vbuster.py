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
import httpx

from urllib.request import localhost
from app.tools import *
from app.nuclei import *
from datetime import date, datetime, timedelta

def parser_vbuster(kwargs):
    JobID=getJobID(kwargs)
    Job=getJob(JobID)
    scope=Job.input
    UINPUT=getInput(kwargs)
    DINPUT=open("/opt/asf/tools/dicts/vbuster/"+kwargs['dict']+".dict","r")
    DICT = DINPUT.read().split("\n")
    for URL in UINPUT:
        URL=URL.strip()
        debug("Testing:"+URL+"\n")
        for ITEM in DICT:
            SITE=URL+"/"+ITEM
            debug("Testing for discovery [Url:"+str(SITE)+"]\n")
            rc = 0
            r = None
            try:
                r = httpx.get(SITE)
                rc = r.status_code
                debug("Status Code:"+str(rc)+"\n")
            except Exception as e:
                debug(str(e)+"\n")
            if rc >=200 and rc < 300:
                MSG = {'message':"[wordlist-"+kwargs['dict']+"][RESPONSE]["+str(rc)+"]", 'url':SITE,
                       'dictionary':kwargs['dict']}
                MSG['datetime']=str(datetime.now())
                MSG['JobID']=JobID
                MSG['scope']=Job.input
                delta(MSG)

    return

def parser_responsecode(kwargs):
    JobID=getJobID(kwargs)
    Job=getJob(JobID)
    scope=Job.input
    UINPUT=getInput(kwargs)
    RC = kwargs['rc'].split(",")
    SINGLE_CODES=[]
    RANGE_CODES={}
    for CODE in RC:
        if CODE.endswith('xx'):
            RANGE_CODES[CODE]=int(CODE[0])*100
        else:
            SINGLE_CODES.append(int(CODE))
    
    for URL in UINPUT:
        URL=URL.strip()
        debug("Testing:"+URL+"\n")
        SITE=URL
        debug("Testing Response Code [Url:"+str(SITE)+"]\n")
        rc = 0
        r = None
        try:
            r = httpx.get(SITE)
            rc = r.status_code
            debug("Status Code:"+str(rc)+"\n")
        except Exception as e:
            debug(str(e)+"\n")
        ALERT = False
        RCODE = "NOALERT"
        for CODE in RANGE_CODES:
            if rc >= RANGE_CODES[CODE] and rc < (RANGE_CODES[CODE]+100):
                ALERT = True
                RCODE = CODE
        for CODE in SINGLE_CODES:
            if rc == CODE:
                ALERT = True
                RCODE = CODE
                
        if ALERT:
            MSG = {'message':"[STATUS][CODE]["+RCODE+"]["+str(rc)+"]", 'url':SITE,
                   'dictionary':kwargs['dict']}
            MSG['datetime']=str(datetime.now())
            MSG['JobID']=JobID
            MSG['scope']=Job.input
            delta(MSG)

    return
       
#Here is the global declaration of parsers, functions can be duplicated
action={'default':parser_vbuster,
        'vbuster':parser_vbuster,
        'responsecode':parser_responsecode}

def getJobID(kwargs):
    if "JobID:" in kwargs['output']:
        JobID = kwargs['output'].split("JobID:")[1]
        debug("Requested to parse output from JobID:"+JobID+"\n")
        return JobID
    else:
        debug("Please specify  --output JobID:Id, ID has to be valid\n")
        sys.exit()

def getJob(JobID):
    try:
        Job = vdJob.objects.filter(id = JobID)[0]
    except Exception as e:
        debug("Error looking for JobID"+JobID+"\n")
        sys.exit()
    debug("Dump:"+str(Job.input)+":Dump\n")
    return Job

def getInput(kwargs):
    PARSER_INPUT = sys.stdin
    if kwargs['input'] != "stdin":
        PARSER_INPUT = open(kwargs['input'],'r')
        debug("Input: "+kwargs['input']+"\n")
    else:
        debug("Input: STDIN \n")
    return PARSER_INPUT

def parseLines(kwargs):
    return action[kwargs['parser']](kwargs)

PARSER_DEBUG=False
def debug(text):
    if PARSER_DEBUG:
        sys.stderr.write(str(text))
    return

class Command(BaseCommand):
    help = 'Processes Worker Scans'
    def add_arguments(self, parser):
        #This single module reads the input file and convert it into 
        parser.add_argument('--input', help='The input file/folder according to parser, if not provided stdin is used', default='stdin')
        parser.add_argument('--output', help='The output JobID:ID/String according to parser', default='error')
        parser.add_argument('--parser', help='The parser algorithm [default]', default='default')
        parser.add_argument('--dict', help='The dictionary name.dict with full path', default='jira')
        parser.add_argument('--rc', help='Response Codes to Alert, 2xx, 3xx, 4xx separated by commas', default='4xx,5xx')
        parser.add_argument('--debug', help='Print verbose data', action='store_true', default=False)
        
    def handle(self, *args, **kwargs):        
        global PARSER_DEBUG
        PARSER_DEBUG = kwargs['debug']
        
        debug(str(kwargs)+"\n")
       
        if kwargs['parser'] not in action:
            PARSER_DEBUG = True
            debug("Parser:"+kwargs['parser']+" not found in action declaration:"+str(action)+"\n")
            sys.exit()
        parseLines(kwargs)
        debug("\n")
