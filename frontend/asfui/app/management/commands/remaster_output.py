#!/usr/bin/python3
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from cProfile import label
from app.models import vdTarget, vdResult, vdServices, vdInServices, vdRegExp, vdJob  

from os import path
import sys
import subprocess
import os
import re
import argparse
import csv
import json
from urllib.request import localhost
from app.views import autodetectType, delta, get_metadata
from app.targets import get_metadata_array

#Static and Global Declarations
HYDRA = re.compile("^(\[.*\])(\[.*\])\s+host:\s+([a-z,0-9,A-Z,\.]*)\s+login:\s+(\S*)\s+password:\s+(.*)$")
#NUCLEI_HTTP = re.compile("^.*(\[http.*\]).*$")
NUCLEI_HTTP = re.compile("^.*(http.*)$")
NUCLEI_HTTP_DASH = re.compile("^.*(\:\/\/).*$")
NUCLEI_NETWORK = re.compile(".*\[network\].*")
DETECTOR_SOURCE = re.compile("^\[[A-Za-z0-9 ]+\].*")

def parser_default(PARSER_INPUT, PARSER_OUTPUT):
    return

def parser_patator_ssh(PARSER_INPUT, PARSER_OUTPUT):
    CSV_READER = csv.reader(PARSER_INPUT, delimiter=',')
    for DATA in CSV_READER:
        if DATA[2] == '0':
            debug(str(DATA)+"\n")
            candidate = DATA[5].split(':')
            debug("Searching:"+candidate[0]+":\n")
            OldData = PARSER_OUTPUT.objects.filter(name=candidate[0])
            MDT,METADATA = get_metadata(candidate[0])
            MSG = {'message':"[PATATOR][SSH BRUTEFORCE]", 'hostname':candidate[0], 'username':candidate[1], 'password':candidate[1]}
            MSG.update(MDT)
            delta(MSG)
            debug("Dump:"+str(OldData)+":Dump\n")
            if OldData.count()>1:
                debug("Warning: Found and Updating more than one:"+str(OldData[0].id)+":"+candidate[0]+":"+candidate[1]+":"+candidate[2]+"\n")
            debug("SSH BruteForce:{"+ candidate[1]+":"+candidate[2]+"}  \n")
            OLDMETADATA=OldData[0].metadata
            OLDMDT=get_metadata_array(OLDMETADATA)
            NEWMETADATA=json.dumps(OLDMDT.update(MDT))
            OldData.update(service_ssh="SSH BruteForce:{"+ candidate[1]+":"+candidate[2]+"}  ", owner=MDT['owner'], metadata=NEWMETADATA)
    return

def parser_patator_rdp(PARSER_INPUT, PARSER_OUTPUT):
    CSV_READER = csv.reader(PARSER_INPUT, delimiter=',')
    for DATA in CSV_READER:
        if DATA[2] == '0':
            debug(str(DATA)+"\n")
            candidate = DATA[5].split(':')
            debug("Searching:"+candidate[0]+"\n")
            OldData = PARSER_OUTPUT.objects.filter(name=candidate[0])
            if OldData.count()>1:
                debug("Found and Updating:"+str(OldData[0].id)+":"+candidate[0]+":"+candidate[1]+":"+candidate[2]+"\n")
            OldData.update(service_rdp="RDP BruteForce:{"+ candidate[1]+":"+candidate[2]+"}  ")
    return

def parser_patator_ftp(PARSER_INPUT, PARSER_OUTPUT):
    CSV_READER = csv.reader(PARSER_INPUT, delimiter=',')
    for DATA in CSV_READER:
        if DATA[2] == '0':
            debug(str(DATA)+"\n")
            candidate = DATA[5].split(':')
            debug("Searching:"+candidate[0]+"\n")
            OldData = PARSER_OUTPUT.objects.filter(name=candidate[0])
            if OldData.count()>1:
                debug("Found and Updating:"+str(OldData[0].id)+":"+candidate[0]+":"+candidate[1]+":"+candidate[2]+"\n")
            OldData.update(service_ftp="FTP BruteForce:{"+ candidate[1]+":"+candidate[2]+"}  ")
    return

def parser_patator_telnet(PARSER_INPUT, PARSER_OUTPUT):
    CSV_READER = csv.reader(PARSER_INPUT, delimiter=',')
    for DATA in CSV_READER:
        if DATA[2] == '0':
            debug(str(DATA)+"\n")
            candidate = DATA[5].split(':')
            debug("Searching:"+candidate[0]+"\n")
            OldData = PARSER_OUTPUT.objects.filter(name=candidate[0])
            if OldData.count()>1:
                debug("Found and Updating:"+str(OldData[0].id)+":"+candidate[0]+":"+candidate[1]+":"+candidate[2]+"\n")
            OldData.update(service_telnet="TELNET BruteForce:{"+ candidate[1]+":"+candidate[2]+"}  ")
    return

def parser_hydra_ftp(PARSER_INPUT, PARSER_OUTPUT):
    for line in PARSER_INPUT:
        if not line.startswith("#"):
            DATA = HYDRA.findall(line)[0]
            debug(str(DATA)+"\n")
            candidate = DATA[2]
            debug("Searching:"+candidate+"\n")
            OldData = PARSER_OUTPUT.objects.filter(name=candidate)
            MDT,METADATA = get_metadata(candidate)
            MSG = {'message':"[HYDRA][FTP BRUTEFORCE]", 'hostname':candidate, 'username':DATA[3], 'password':DATA[4]}
            MSG.update(MDT)
            delta(MSG)
            if OldData.count()>1:
                debug("Found and Updating:"+str(OldData[0].id)+":"+DATA[2]+":"+DATA[3]+":"+DATA[4]+"\n")
                OLDMETADATA=OldData[0].metadata
                OLDMDT=get_metadata_array(OLDMETADATA)
                NEWMETADATA=json.dumps(OLDMDT.update(MDT))
                OldData.update(service_ftp="FTP BruteForce:{"+DATA[2]+":"+DATA[3]+":"+DATA[4]+")", owner=MDT['owner'], metadata=NEWMETADATA)
    return

def parser_hydra_telnet(PARSER_INPUT, PARSER_OUTPUT):
    delta_cache = {}
    for line in PARSER_INPUT:
        if not line.startswith("#"):
            DATA = HYDRA.findall(line)[0]
            debug(str(DATA)+"\n")
            candidate = DATA[2]
            debug("Searching:"+candidate+"\n")
            OldData = PARSER_OUTPUT.objects.filter(name=candidate)
            MDT,METADATA = get_metadata(candidate)
            MSG = {'message':"[HYDRA][TELNET BRUTEFORCE]", 'hostname':candidate, 'username':DATA[3], 'password':DATA[4]}
            MSG.update(MDT)
            delta(MSG)
            if OldData.count()>1:
                debug("Found and Updating:"+str(OldData[0].id)+":"+DATA[2]+":"+DATA[3]+":"+DATA[4]+"\n")
                OLDMETADATA=OldData[0].metadata
                OLDMDT=get_metadata_array(OLDMETADATA)
                NEWMETADATA=json.dumps(OLDMDT.update(MDT))                
                OldData.update(service_telnet="Telnet BruteForce:{"+DATA[2]+":"+DATA[3]+":"+DATA[4]+")", owner=MDT['owner'], metadata=NEWMETADATA)
    return

def parser_nuclei_http(PARSER_INPUT, PARSER_OUTPUT):
    #Although you can import them from VIEWS, in this particular case, we need to match all over the string,
    #and VIEWS uses it for autodetectType with EXACT MATCH, so removing ^ and $ do the trick
    DETECTOR_IPADDRESS = re.compile("(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
    DETECTOR_DOMAIN = re.compile("(?!\-)(?:[a-zA-Z\d\-]{0,62}[a-zA-Z\d]\.){1,126}(?!\d+)[a-zA-Z\d]{1,63}")
    clear_cache = []
    delta_cache = {}
    for line in PARSER_INPUT:
        debug(line+"\n")
        if NUCLEI_HTTP.match(line) and NUCLEI_HTTP_DASH.match(line):
            DATA = line.split("://")[1]
            DATA = DATA.split("/")[0]
            debug(str(DATA)+"\n")
            DOMAIN = DETECTOR_DOMAIN.findall(DATA)
            if len(DOMAIN)==0:
                debug(str(DETECTOR_IPADDRESS)+"\n")
                DOMAIN = DETECTOR_IPADDRESS.findall(DATA)[0]
            else:
                DOMAIN=DOMAIN[0]
            debug("Searching:"+str(DOMAIN)+"\n")
            if DOMAIN in clear_cache:
                debug("Cache:Already Cleared\n")
                APPEND = True
            else:
                debug("Cache:Clearing Nuclei data\n")
                clear_cache.append(DOMAIN)
                APPEND = False
                
            OldData = PARSER_OUTPUT.objects.filter(name=DOMAIN)
            if OldData.count()==1:
                MDT,METADATA = get_metadata(DOMAIN)
                OLDMETADATA=OldData[0].metadata
                OLDMDT=get_metadata_array(OLDMETADATA)
                NEWMETADATA=json.dumps(OLDMDT.update(MDT))
                debug("Found and Updating:"+str(OldData[0].id)+":"+DOMAIN+"\n")
                if APPEND:
                    OldData.update(nuclei_http=OldData[0].nuclei_http+line)
                else:
                    delta_cache[DOMAIN]=OldData[0].nuclei_http.split("\n")
                    OldData.update(nuclei_http=line, owner=MDT['owner'], metadata=NEWMETADATA)

                if line not in delta_cache[DOMAIN]:
                    
                    MSG = {'message':"[NUCLEI][New Finding]", 'host':DOMAIN, 'finding':line}
                    MSG.update(MDT)
                    delta(MSG)
            else:
                #This line is a temporary MOD, please comment for system integrity, all objects should exist
                Result = PARSER_OUTPUT(name=DOMAIN, nname=DOMAIN, tags="[Services]", type=autodetectType(DOMAIN), nuclei_http=line)
                Result.save()
                debug("Error, not found:"+str(DATA)+"\n")
        else:
            debug("Found nothing:"+line)
    return

def parser_nuclei_network(PARSER_INPUT, PARSER_OUTPUT):
    #Although you can import them from VIEWS, in this particular case, we need to match all over the string,
    #and VIEWS uses it for autodetectType with EXACT MATCH, so removing ^ and $ do the trick
    DETECTOR_IPADDRESS = re.compile("(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
    DETECTOR_DOMAIN = re.compile("(?!\-)(?:[a-zA-Z\d\-]{0,62}[a-zA-Z\d]\.){1,126}(?!\d+)[a-zA-Z\d]{1,63}")
    clear_cache = []
    delta_cache = {}
    for line in PARSER_INPUT:
        debug(line+"\n")
        if NUCLEI_NETWORK.match(line):
            DATA = line.split(" ")[-1]
            DATA = DATA.split(":")[0]
            debug(str(DATA)+"\n")
            DOMAIN = DETECTOR_DOMAIN.findall(DATA)
            if len(DOMAIN)==0:
                debug(str(DETECTOR_IPADDRESS)+"\n")
                DOMAIN = DETECTOR_IPADDRESS.findall(DATA)[0]
            else:
                DOMAIN=DOMAIN[0]
            debug("Searching:"+str(DOMAIN)+"\n")
            if DOMAIN in clear_cache:
                debug("Cache:Already Cleared\n")
                APPEND = True
            else:
                debug("Cache:Clearing Nuclei data\n")
                clear_cache.append(DOMAIN)
                APPEND = False
                
            OldData = PARSER_OUTPUT.objects.filter(name=DOMAIN)
            if OldData.count()==1:
                MDT,METADATA = get_metadata(DOMAIN)
                OLDMETADATA=OldData[0].metadata
                OLDMDT=get_metadata_array(OLDMETADATA)
                NEWMETADATA=json.dumps(OLDMDT.update(MDT))
                debug("Found and Updating:"+str(OldData[0].id)+":"+DOMAIN+"\n")
                if APPEND:
                    OldData.update(nuclei_http=OldData[0].nuclei_http+line)
                else:
                    delta_cache[DOMAIN]=OldData[0].nuclei_http.split("\n")
                    OldData.update(nuclei_http=line, owner=MDT['owner'], metadata=NEWMETADATA)

                if ((DOMAIN in delta_cache) and (line not in delta_cache[DOMAIN])) or (DOMAIN not in delta_cache):
                    MSG = {'message':"[NUCLEI][New Finding]", 'host':DOMAIN, 'finding':line}
                    MSG.update(MDT)
                    delta(MSG)
            else:
                #This line is a temporary MOD, please comment for system integrity, all objects should exist
                Result = PARSER_OUTPUT(name=DOMAIN, nname=DOMAIN, tags="[Services]", type=autodetectType(DOMAIN), nuclei_http=line)
                Result.save()
                debug("Error, not found:"+str(DATA)+"\n")
        else:
            debug("Found nothing:"+line)
    return

def parser_nse_vsanrce(PARSER_INPUT, PARSER_OUTPUT):
    #Although you can import them from VIEWS, in this particular case, we need to match all over the string,
    #and VIEWS uses it for autodetectType with EXACT MATCH, so removing ^ and $ do the trick
    DETECTOR_IPADDRESS = re.compile("(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
    DETECTOR_DOMAIN = re.compile("(?!\-)(?:[a-zA-Z\d\-]{0,62}[a-zA-Z\d]\.){1,126}(?!\d+)[a-zA-Z\d]{1,63}")
    clear_cache = []
    delta_cache = {}
    for line in PARSER_INPUT:
        line = line.rstrip()
        debug(line+"\n")
        DATA = line.split(",")
        debug(str(DATA)+"\n")
        #52.58.57.117, VMware vCenter Server 7.0.1 build:16507313,  Vulnerable to CVE-2021-21972, Vulnerable to vSAN RCE
        if (len(DATA)>=3):
            DOMAIN = DETECTOR_DOMAIN.findall(DATA[0])
            if len(DOMAIN)==0:
                DOMAIN = DETECTOR_IPADDRESS.findall(DATA[0])[0]
            else:
                DOMAIN = DOMAIN[0]
            debug("Searching:"+str(DOMAIN)+"\n")
            OldData = PARSER_OUTPUT.objects.filter(name=DOMAIN)
            if OldData.count()==1:
                MDT,METADATA = get_metadata(DOMAIN)
                debug("Found and Updating:"+str(OldData[0].id)+":"+DOMAIN+"\n")
                OLDMETADATA=OldData[0].metadata
                OLDMDT=get_metadata_array(OLDMETADATA)
                NEWMETADATA=json.dumps(OLDMDT.update(MDT))                
                OldData.update(nse_vsanrce=line, owner=MDT['owner'], metadata=NEWMETADATA)
                MSG = {'message':"[NSE][VSANRCE]", 'host':DOMAIN, 'finding':line}
                counter = 0
                for field in DATA:
                    MSG["FIELD"+str(counter)]=field.lstrip().rstrip()
                    counter+=1
                MSG.update(MDT)
                delta(MSG)
            else:
                #This line is a temporary MOD, please comment for system integrity, all objects should exist
                Result = PARSER_OUTPUT(name=DOMAIN, nname=DOMAIN, tags="[Services]", type=autodetectType(DOMAIN), nse_vsanrce=line)
                Result.save()
                debug("Error, not found:"+str(DATA)+"\n")
        else:
            debug("Error, nonsense line:"+str(DATA)+"\n")
    return

#Here is the global declaration of parsers, functions can be duplicated
action={'default':parser_default, 'patator.ssh':parser_patator_ssh, 'patator.rdp':parser_patator_rdp, 'patator.ftp':parser_patator_ftp, 'patator.telnet':parser_patator_telnet, 'hydra.ftp':parser_hydra_ftp, 'hydra.telnet':parser_hydra_telnet, 'nuclei.http':parser_nuclei_http, 'nuclei.network':parser_nuclei_network, 'nse_vsanrce':parser_nse_vsanrce}

def parseLines(PARSER_INPUT, JobInput, parser):
    PARSER_OUTPUT = vdServices
    if JobInput == "inservices":
        PARSER_OUTPUT = vdInServices

    return action[parser](PARSER_INPUT, PARSER_OUTPUT)

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
        parser.add_argument('--output', help='The output JobID:ID', default='error')
        parser.add_argument('--parser', help='The parser algorithm [default|patator{.ssh, .ftp, .rdp, .telnet, .smb}]', default='default')
        parser.add_argument('--debug', help='Print verbose data', action='store_true', default=False)
        
    def handle(self, *args, **kwargs):        
        PARSER_INPUT = sys.stdin
        global PARSER_DEBUG
        PARSER_DEBUG = kwargs['debug']
        
        debug(str(kwargs)+"\n")
       
        if kwargs['parser'] not in action:
            PARSER_DEBUG = True
            debug("Parser:"+kwargs['parser']+" not found in action declaration:"+str(action)+"\n")
            sys.exit()
        
        if "JobID:" in kwargs['output']:
            JobID = kwargs['output'].split("JobID:")[1]
            debug("Requested to parse output from JobID:"+JobID+"\n")
        else:
            debug("You has to specify --output JobID:Id, and ID has to be valid\n")
            sys.exit()
            
        try:
            Job = vdJob.objects.filter(id = JobID)[0]
        except Exception as e:
            debug("There was an error looking for JobID"+JobID+"\n")
            sys.exit()
        debug("Dump:"+str(Job.input)+":Dump\n")
        if kwargs['input'] != "stdin":
            PARSER_INPUT = open(kwargs['input'],'r')
            debug("Input: "+kwargs['input']+"\n")
        else:
            debug("Input: STDIN \n")
        parseLines(PARSER_INPUT, Job.input, kwargs['parser'])
        debug("\n")