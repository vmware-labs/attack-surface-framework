#!/usr/bin/python3
#VER:1
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from cProfile import label
from app.models import vdTarget, vdResult, vdServices, vdInServices, vdRegExp, vdJob, vdNucleiResult
from django.conf import settings
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
import pymongo
import urllib
from datetime import datetime

#Static and Global Declarations
HYDRA = re.compile("^(\[.*\])(\[.*\])\s+host:\s+([a-z,0-9,A-Z,\.]*)\s+login:\s+(\S*)\s+password:\s+(.*)$")
#NUCLEI_HTTP = re.compile("^.*(\[http.*\]).*$")
NUCLEI_HTTP = re.compile("^.*(http.*)$")
NUCLEI_HTTP_DASH = re.compile("^.*(\:\/\/).*$")
NUCLEI_NETWORK = re.compile(".*\[network\].*")
NUCLEI_CRITICAL = re.compile(".*\[critical\].*")
NUCLEI_HIGH = re.compile(".*\[high\].*")
NUCLEI_MEDIUM = re.compile(".*\[medium\].*")
NUCLEI_INFO = re.compile(".*\[info\].*")
NUCLEI_FINDING = re.compile("^\[[A-Za-z0-9 \-:]*\] \[.*")
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
                    OWN="Unknown"
                    if 'owner' in MDT:
                        OWN = MDT['owner']
                    OldData.update(nuclei_http=line, owner=OWN, metadata=NEWMETADATA)

                if line not in delta_cache[DOMAIN]:
                    
                    MSG = {'message':"[NUCLEI][New Finding]", 'host':DOMAIN, 'finding':line}
                    MSG.update(MDT)
                    delta(MSG)
            else:
                #This line is a temporary MOD, please comment for system integrity, all objects should exist
                Result = PARSER_OUTPUT(name=DOMAIN, nname=DOMAIN, tag="[Services]", type=autodetectType(DOMAIN), nuclei_http=line)
                Result.save()
                debug("Error, not found:"+str(DATA)+"\n")
        else:
            debug("Found nothing:"+line)
    return


def parser_wpscan_json(PARSER_INPUT, PARSER_OUTPUT):
    print("Sending to parser for WPScan")
    #ParseWPscanData(PARSER_INPUT)
    username = urllib.parse.quote_plus(settings.MONGO_USER)
    password = urllib.parse.quote_plus(settings.MONGO_PASSWORD)
    url = settings.MONGO_URL
    port = settings.MONGO_PORT
    myclient = pymongo.MongoClient(f"mongodb://{username}:{password}@{url}:{port}")
    db = myclient["Nuclei"]
    Collection = db["report"]
    file_data = json.load(PARSER_INPUT)
    primaryBulkArr = []
    result_list =[]
    severity = 'medium'
    try:
        host = file_data['target_url']
        start_time = file_data['start_time']
        timestamp = (datetime.fromtimestamp(start_time)).strftime("%Y-%m-%dT%H:%M:%S")
        if "vulnerabilities" in file_data['version']:
            for i in file_data['version']['vulnerabilities']:
                #print(i["title"], data["target_url"])   
                row = {'host': host, 'jira_created': False, 'verified':False, "ignored":False, 'info':{'name':i['title'], 'description': i['title'], 'severity': severity}, 'matched-at':file_data['target_url'], 'template-id': i['title'], 'timestamp':timestamp }
                result_list.append(row)
        if "vulnerabilities" in file_data["main_theme"]:
            for i in file_data["main_theme"]["vulnerabilities"]:
                row = {'host': host, 'jira_created': False, 'verified':False, "ignored":False, 'info':{'name':i['title'], 'description': i['title'], 'severity': severity}, 'matched-at':file_data['main_theme']['location'], 'template-id': i['title'], 'timestamp':timestamp }
                result_list.append(row) 
        for i in file_data["plugins"]:
            if "vulnerabilities" in file_data["plugins"][i]:
                    for j in file_data["plugins"][i]["vulnerabilities"]:
                        if "title" in j:
                            row = {'host': host, 'jira_created': False, 'verified':False, "ignored":False, 'info':{'name':j['title'], 'description': j['title'], 'severity': severity}, 'matched-at':file_data["plugins"][i]['location'], 'template-id': j['title'], 'timestamp':timestamp }
                            result_list.append(row) 
    except Exception as e:
        print("error in parsing WPscan report:", str(e))
        pass
        
    for x in result_list:
        primaryBulkArr.append(pymongo.UpdateOne({"template-id": x['template-id'], 'host':x['host'], 'matched-at':x['matched-at']}, {'$set':x, '$inc':{'counter':1}}, upsert=True))
    if len(primaryBulkArr)> 0:
        Collection.bulk_write(primaryBulkArr)
    else:
        print("nothing to insert")
    
    return 
    


def parser_nuclei_json(PARSER_INPUT, PARSER_OUTPUT):
    username = urllib.parse.quote_plus(settings.MONGO_USER)
    password = urllib.parse.quote_plus(settings.MONGO_PASSWORD)
    url = settings.MONGO_URL
    port = settings.MONGO_PORT
    myclient = pymongo.MongoClient(f"mongodb://{username}:{password}@{url}:{port}")
    db = myclient["Nuclei"]
    Collection = db["report"]
    file_data = json.load(PARSER_INPUT)
    primaryBulkArr = []
    
    for index,x in enumerate(file_data):
        if Collection.count_documents({"template-id": x['template-id'], 'host': x['host'], 'matched-at':x['matched-at']}) < 1:
            x.update({'jira_created':False, 'verified':False, 'ignored':False})
            primaryBulkArr.append(pymongo.UpdateOne({"template-id": x['template-id'], 'host':x['host'], 'matched-at':x['matched-at']}, {'$set':x, '$inc':{'counter':1}}, upsert=True))
        else:
            primaryBulkArr.append(pymongo.UpdateOne({"template-id": x['template-id'], 'host':x['host'], 'matched-at':x['matched-at']}, {'$set':x, '$inc':{'counter':1}}, upsert=True))
    if len(primaryBulkArr)> 0:
        Collection.bulk_write(primaryBulkArr)
    else:
        print("nothing to insert")
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
                Result = PARSER_OUTPUT(name=DOMAIN, nname=DOMAIN, tag="[Services]", type=autodetectType(DOMAIN), nuclei_http=line)
                Result.save()
                debug("Error, not found:"+str(DATA)+"\n")
        else:
            debug("Found nothing:"+line)
    return

def master_parser_nuclei(PARSER_INPUT, PARSER_OUTPUT, FILTER):
    clear_cache = []
    delta_cache = {}
    vulnerability_cache = []
    scope="E"
    if PARSER_OUTPUT.__name__=='vdInServices':
        scope="I"
    for line in PARSER_INPUT:
        debug(line+"\n")
        if NUCLEI_FINDING.match(line):
            debug("Line contains the FINDING regular expression\n")
            DATA = NFinding(line,scope)
            if FILTER is not None:
                DATA=FILTER(DATA)
            debug(str(DATA)+"\n")
            if DATA is not None:
                if DATA.full_uri is not None:
                    #NFinding class now does all the job parsing Nuclei findings, even domain or IP address.
                    UNIQUE_KEY = str(DATA.name)+"|"+str(DATA.vulnerability)
                    debug("Searching:"+str(UNIQUE_KEY)+"\n")
                    #The main purpose of the cache, is to set up the finding just once and avoid too many excecution resources.
                    if DATA.name in clear_cache:
                        debug("Cache:Already managed\n")
                        APPEND = True
                    else:
                        debug("Cache:Seting up new finding in cache\n")
                        clear_cache.append(DATA.name)
                        APPEND = False
                    #Here we work in the main data information, grouping the findings all together.
                    OldData = PARSER_OUTPUT.objects.filter(name=DATA.name)
                    NEWMETADATA=""
                    MDT={'owner':'Unknown'}
                    if OldData.count()==1:
                        MDT,METADATA = get_metadata(DATA.name)
                        OLDMETADATA=OldData[0].metadata
                        OLDMDT=get_metadata_array(OLDMETADATA)
                        NEWMETADATA=json.dumps(OLDMDT.update(MDT))
                        debug("Found and Updating:"+str(OldData[0].id)+":"+DATA.name+"\n")
                        if APPEND:
                            OldData.update(nuclei_http=OldData[0].nuclei_http+line)
                        else:
                            delta_cache[DATA.name]=OldData[0].nuclei_http.split("\n")
                            OldData.update(nuclei_http=line, owner=MDT['owner'], metadata=NEWMETADATA)
                
                        if ((DATA.name in delta_cache) and (line not in delta_cache[DATA.name])) or (DATA.name not in delta_cache):
                            MSG = {'message':"[NUCLEI][New Finding]", 'host':DATA.name, 'finding':line}
                            MSG.update(MDT)
                            delta(MSG)
                    else:
                        #This line is a temporary MOD, please comment for system integrity, all objects should exist
                        Result = PARSER_OUTPUT(name=DATA.name, nname=DATA.name, tag="[Services]", type=autodetectType(DATA.name), nuclei_http=line)
                        Result.save()
                        debug("Error, not found:"+str(DATA)+"\n")
                    #In this point we fill the new table for the dashboard
                    DATA.metadata=NEWMETADATA
                    DATA.owner=MDT['owner']
                    if UNIQUE_KEY not in vulnerability_cache:
                        #Search for the existence of unique VT
                        VT = vdNucleiResult.objects.filter(name=DATA.name, vulnerability=DATA.vulnerability)
                        if VT.count()==1:
                            debug("Found and Updating:"+UNIQUE_KEY+"\n")
                            update_nuclei_finding(VT,DATA)
                        else:
                            debug("Not Found and Creating:"+UNIQUE_KEY+"\n")
                            create_nuclei_finding(DATA)
            else:
                pass
        else:
            debug("Found nothing:"+line)
    return

def parser_nuclei(PARSER_INPUT, PARSER_OUTPUT):
    return master_parser_nuclei(PARSER_INPUT, PARSER_OUTPUT, None)

def parser_nuclei_waf(PARSER_INPUT, PARSER_OUTPUT):
    return master_parser_nuclei(PARSER_INPUT, PARSER_OUTPUT, filter_nuclei_waf)

def filter_nuclei_waf(DATA):
    if DATA.temp_array[2]=='failed':
        DATA.level="medium"
        DATA.vulnerability="MISSING-WAF"
        return DATA
    else:
        return None


def parser_nuclei_onlyalert(PARSER_INPUT, PARSER_OUTPUT):
    #Line example: [2022-09-01 22:19:31] [waf-detect:apachegeneric] [matched] [http] [info] https://ywd-fgkjhfgh.co.kr/
    #Line example: [2022-09-05 07:17:51] [CVE-2021-40438] [http] [critical] http://3.
    clear_cache = []
    delta_cache = {}
    vulnerability_cache = []
    scope="E"
    if PARSER_OUTPUT.__name__=='vdInServices':
        scope="I"
    for line in PARSER_INPUT:
        debug(line+"\n")
        if NUCLEI_FINDING.match(line):
            debug("Line contains the FINDING regular expression\n")
            DATA = NFinding(line,scope)
            debug(str(DATA)+"\n")
            if DATA.full_uri is not None:
                #NFinding class now does all the job parsing Nuclei findings, even domain or IP address.
                UNIQUE_KEY = str(DATA.name)+"|"+str(DATA.vulnerability)
                debug("Searching:"+str(UNIQUE_KEY)+"\n")
                debug("Values:"+str(DATA.temp_array)+"\n")
                MSG = {'message':"[NUCLEI][New Finding]", 'host':DATA.name, 'finding':line}
                MSG['datetime']=str(DATA.detectiondate)
                MSG['url']=DATA.full_uri
                MSG['waf']=DATA.temp_array[1]
                MSG['status']=DATA.temp_array[2]
                MSG['protocol']=DATA.temp_array[3]
                #Level is always 'info'
                MSG['level']=DATA.temp_array[4]
                delta(MSG)

    return


#Here is the global declaration of parsers, functions can be duplicated
action={'default':parser_default, 'patator.ssh':parser_patator_ssh, 'patator.rdp':parser_patator_rdp, 'patator.ftp':parser_patator_ftp, 'patator.telnet':parser_patator_telnet, 'hydra.ftp':parser_hydra_ftp, 'hydra.telnet':parser_hydra_telnet, 'nuclei.http':parser_nuclei_http, 'nuclei.network':parser_nuclei_network, 'nuclei':parser_nuclei, 'nuclei.onlyalert':parser_nuclei_onlyalert, 'nuclei.waf':parser_nuclei_waf, 'nuclei.json':parser_nuclei_json, 'wpscan.json':parser_wpscan_json}

def parseLines(PARSER_INPUT, JobInput, parser):
    if JobInput == "inservices":
        PARSER_OUTPUT = vdInServices
    if JobInput == "services":
        PARSER_OUTPUT = vdServices
#     if JobInput == 'nucleiresult':
#         PARSER_OUTPUT = vdNucleiResult
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
        parser.add_argument('--parser', help='The parser algorithm [default|nuclei|patator{.ssh, .ftp, .rdp, .telnet, .smb}]', default='default')
        parser.add_argument('--debug', help='Print verbose data', action='store_true', default=False)
        
    def handle(self, *args, **kwargs):        
        PARSER_INPUT = sys.stdin
        global PARSER_DEBUG
        PARSER_DEBUG = kwargs['debug']
        
        debug(str(kwargs)+"\n")
        print((str(kwargs)+"\n"))
       
        if kwargs['parser'] not in action:
            PARSER_DEBUG = True
            debug("Parser:"+kwargs['parser']+" not found in action declaration:"+str(action)+"\n")
            sys.exit()
        
        if "JobID:" in kwargs['output']:
            JobID = kwargs['output'].split("JobID:")[1]
            print("Requested to parse output from JobID:"+JobID+"\n")
            debug("Requested to parse output from JobID:"+JobID+"\n")
        else:
            debug("You has to specify --output JobID:Id, and ID has to be valid\n")
            sys.exit()
            
        try:
            Job = vdJob.objects.filter(id = JobID)[0]
        except Exception as e:
            debug("There was an error looking for JobID:"+JobID+"\n")
            sys.exit()
        debug("Dump:"+str(Job.input)+":Dump\n")
        if kwargs['input'] != "stdin":
            PARSER_INPUT = open(kwargs['input'],'r')
            debug("Input: "+kwargs['input']+"\n")
        else:
            debug("Input: STDIN \n")
        parseLines(PARSER_INPUT, Job.input, kwargs['parser'])
        debug("\n")