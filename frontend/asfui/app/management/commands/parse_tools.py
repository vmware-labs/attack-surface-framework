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
from datetime import date, datetime, timedelta

def parser_default(PARSER_INPUT, PARSER_OUTPUT):
    return

def parser_nuclei_waf_rc(kwargs):
    JobID=getJobID(kwargs)
    Job=getJob(JobID)
    scope=Job.input
    RC_FOLDER=kwargs['input']+"/"
    for rc in [200,300,400,500]:
        rc_file=RC_FOLDER+str(rc)+"_responses.json"
        debug("Opening:"+rc_file+"\n")
        rc_json_file=open(rc_file)
        RC_JSON=json.load(rc_json_file)
        for SITE in RC_JSON:
            debug("Site:"+str(SITE)+"\n")
            MSG = {'message':"[HTTPX][RESPONSE]["+str(rc)+"]", 'url':SITE['original_url'], 'response':SITE['status_code']}
            MSG['datetime']=str(datetime.now())
            MSG['JobID']=JobID
            MSG['scope']=Job.input
            delta(MSG)

    return

def parser_wpscan_output(kwargs):
    JSON_FILE=kwargs['input']
    JSON=open(JSON_FILE)
    REPORT=json.load(JSON)
    #debug(str(REPORT))
    SECTIONS=['plugins','version','main_theme','config_backups']
    def alert(SECTION,REPORT):
        if 'vulnerabilities' not in SECTION:
            return 
        VULNS=SECTION['vulnerabilities']
        if len(VULNS)==0:
            return
        debug("Vulns:"+str(VULNS)+"\n")
        MSG = {'message':"[WPSCAN][VULNERABILITY]["+str(REPORT['target_url'])+"]", 'url':REPORT['target_url'], 'ip':REPORT['target_ip']}
        MSG['datetime']=str(datetime.now())
        MSG['vulnerabilities']=VULNS
        delta(MSG)
        for VULN in VULNS:
            create_or_update_finding(VULN,REPORT)
            
        return
    
    def create_or_update_finding(VULN,REPORT):
        vulnerability="ERROR"
        if 'cve' in VULN['references']:
            vulnerability="CVE-"+VULN['references']['cve'][0]
        else:
            vulnerability=VULN['title']
        Nfinding = vdNucleiResult(name=REPORT['target_url'], firstdate=datetime.now(), bumpdate=datetime.now(), detectiondate=datetime.now(), owner="Unknown", metadata=str(VULN['references']), info=str(VULN), vulnerability=vulnerability, engine='WPSCAN', level='medium', uri=REPORT['target_url'], full_uri=REPORT['target_url'], uriistruncated=0, nname=REPORT['target_url'], type='URL', port=443, ptime='P1E')
#        Nfinding.save()
        try:
            Nfinding.save()
        except Exception as e:
            debug(str(e)+"\nUpdating instead\n")
            Nfinding = vdNucleiResult.objects.filter(name=REPORT['target_url'], vulnerability=vulnerability)
            Nfinding[0].lastdate=datetime.now()
            Nfinding[0].save()
        return

    for section in SECTIONS:
        debug("Searching for "+section+"\n")
        if section == 'plugins' and 'plugins' in REPORT:
            for plugin in REPORT['plugins']:
                
                alert(REPORT['plugins'][plugin],REPORT)
        else:
            if section in REPORT:
                alert(REPORT[section],REPORT)
            else:
                debug("Non Existent Section "+section+"\n")
    return


def parser_subfinder_input(kwargs):
    Targets=vdTarget.objects.filter(type='DOMAIN')
    counter=0
    FileTargets=sys.stdout
    if kwargs['output']!='stdout':
        FileTargets=open(kwargs['output'],'w+')
    for domain in Targets:
        FileTargets.write(domain.name+"\n")
        counter+=1
    debug("Dumped "+str(counter)+" domains from external targets..\n")
    FileTargets.flush()
    FileTargets.close()
    
def parser_subfinder_output(kwargs):
    report=sys.stdin
    lines=0    
    if kwargs['input']!='stdin':
        report=open(kwargs['input'],'r')
    for line in report:
        debug("Process:"+line)
        Finding = json.loads(line)
        Tag = ""
        for source in Finding['sources']:
            Tag=Tag+"["+source+"]"
        MDT,MDATA=get_metadata(Finding['host'])
        Result = vdResult(name=Finding['host'], tag=Tag, info=Finding['input'], type=autodetectType(Finding['host']), owner=MDT['owner'], metadata=MDATA)
        NewData = True
        
        try:
            Result.save()
            debug("New Finding:"+Finding['host']+str(Result))
        except Exception as e:
            debug(str(e)+"\n")
            NewData = False
            debug("Finding Already exist:"+Finding['host'])
        if not NewData:
            #Think wise, do you really want to know domains who are not in the results now?
            #or do you think if a domain will appear again it will have different data?
            try:
                debug("Searching:"+Finding['host'])
                OldData = vdResult.objects.filter(name=Finding['host'])
                debug("Found and Updating:"+str(OldData[0].id)+":"+Tag+":"+Finding['input'])
                OldData.update(info = Finding['input'], tag = Tag)
            except Exception as e:
                debug(str(e)+"\n")
                NewData = False
                debug("Ignoring Atomic Async deletion from database, or another kind of exception, please verify:"+Finding['host']+"\n")
        else:
            MSG=Result.getList()
            MSG.update(MDT)
            MSG.update(Finding)
            MSG['message']="[DISCOVERY][New Domain Found]"
            debug("Finding and Called Delta:"+Finding['host']+str(MSG))
            delta(MSG)
                 
        debug(line)
        lines +=1
    debug("Done printing "+str(lines)+" lines..\n")
    return

def parser_socialsearch_output(kwargs):
    report=sys.stdin
    lines=0    
    if kwargs['input']!='stdin':
        report=open(kwargs['input'],'r')
    Finding = json.loads(report.read())
    Tag = ""
    if "meta" in Finding:
        debug(str(Finding['meta']))
    else:
        debug("Error in JSON, not meta key, ABORTING\n")
        return
    if "posts" in Finding:
        debug("\nFound ["+str(len(Finding['posts']))+"] results\n")
    else:
        debug("Error in JSON, not posts key, ABORTING\n")
        return
    for POST in Finding['posts']:
        MSG=Finding['meta']
        MSG.update(POST)
        MSG['message']="[SOCIALSEARCH][FOUND]"
        debug("Finding and Called Delta:"+str(MSG)+"\n\n")
        delta(MSG)
    return

def parser_pwndb_output(kwargs):
    #https://haveibeenpwned.com/api/v3/breach/Adobe
    report=sys.stdin
    lines=0    
    if kwargs['input']!='stdin':
        report=open(kwargs['input'],'r')
    Finding = json.loads(report.read())
    Tag = ""
    if "Name" in Finding[0]:
        debug(str(Finding[0]['Name']))
    else:
        debug("Error in JSON, not Name key, ABORTING\n"+str(Finding)+"\n")
        return
    MSG={}
    MSG.update(Finding[0])
    MSG['message']="[PWNDB][FOUND]"
    debug("Finding and Called Delta:"+str(MSG)+"\n\n")
    delta(MSG)
    return

def parser_ddosify_output(kwargs):
    #https://haveibeenpwned.com/api/v3/breach/Adobe
    report=sys.stdin
    lines=0    
    if kwargs['input']!='stdin':
        report=open(kwargs['input'],'r')
    Finding = json.loads(report.read())
    if "success_perc" in Finding:
        debug(str(Finding))
    else:
        debug("Error in JSON, not success_perc key, ABORTING\n")
        return
    MSG=geodata_qdict(kwargs['target'])
    MSG['hostname']=kwargs['target']
    MSG.update(Finding)
    FindingKeys = ["success_perc",
                "fail_perc",
                "success_count",
                "server_fail_count",
                "assertion_fail_count"]
    DDOS_SUCCESS=1
    for key in FindingKeys:
        if Finding[key]==0:
            DDOS_SUCCESS=0
    if DDOS_SUCCESS == 1:
        MSG['message']="[DDOSIFY][FOUND][SUCESS]"
        MSG['level']='critical'
        MSG['status']='success'
    else:
        MSG['message']="[DDOSIFY][FOUND][INFO]"
        MSG['level']='info'
        MSG['status']='failed'
    debug("Finding and Called Delta:"+str(MSG)+"\n\n")
    delta(MSG)
    return


def parser_list_domains(kwargs):
    if kwargs['input'] != "stdin":
        if "JobID:" in kwargs['input']:
            JobID = kwargs['input'].split("JobID:")[1]
            debug("Requested to extract data from database backend for JobID:"+JobID+"\n")
            FileTargets=sys.stdout
            if kwargs['output']!='stdout':
                    FileTargets=open(kwargs['output'],'w+')
            JOB_FOLDER = "/home/asf/jobs/"+JobID+"/"
            JOB_FILENAME = JOB_FOLDER+"app.asf"
            try:
                Job = vdJob.objects.filter(id = JobID)[0]
                HostsFromModel = search(Job.regexp, Job.input, Job.exclude)
                if not path.exists(JOB_FOLDER):
                    os.makedirs(JOB_FOLDER)
                INPUT_FILE = FileTargets
                HOSTS_COUNTER=0
                if Job.input == 'discovery':
                    for Host in HostsFromModel:
                        INPUT_FILE.write(Host.name+"\n")
                        HOSTS_COUNTER = HOSTS_COUNTER + 1
                else:
                    for HostWithServices in HostsFromModel:
                        INPUT_FILE.write(HostWithServices.name+"\n")
                        HOSTS_COUNTER = HOSTS_COUNTER + 1 
                debug("All hosts data ("+str(HOSTS_COUNTER)+") Written on "+kwargs['output']+"\n")
                INPUT_FILE.close()
            except Exception as e:
                debug("Error creating the input for JobID:"+str(JobID)+"\n")
                debug(str(e)+"\n")
                sys.exit()
    return


        
#Here is the global declaration of parsers, functions can be duplicated
action={'default':parser_default, 'nuclei.waf.rc':parser_nuclei_waf_rc, 'subfinder.input':parser_subfinder_input, 'subfinder.output':parser_subfinder_output, 'wpscan.output':parser_wpscan_output, 'socialsearch.output':parser_socialsearch_output, 'pwndb.output':parser_pwndb_output, 'ddosify.output':parser_ddosify_output, 'list.domains':parser_list_domains,}

def getJobID(kwargs):
    if "JobID:" in kwargs['output']:
        JobID = kwargs['output'].split("JobID:")[1]
        debug("Requested to parse output from JobID:"+JobID+"\n")
        return JobID
    else:
        debug("You has to specify --output JobID:Id, and ID has to be valid\n")
        sys.exit()

def getJob(JobID):
    try:
        Job = vdJob.objects.filter(id = JobID)[0]
    except Exception as e:
        debug("There was an error looking for JobID"+JobID+"\n")
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
        parser.add_argument('--parser', help='The parser algorithm [default|nuclei{.waf{.rc}}|subfinder(.input,.output)|wpscan.(output)]', default='default')
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