#!/usr/bin/python3
#VER:1
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from cProfile import label
from app.models import *

from os import path
import sys
import subprocess
import os
import re
import argparse
from urllib.request import localhost
#Search function inside views.py, main search for inputs, this module needs to comply with the regexp query logic

from app.tools import *
from app.search import *
from app.nmapmodels import NMService, NMHost

#Static and Global Declarations
def parser_default(host):
    if host.name is None:
        return []
    else:
        return [str(host)]

def parser_hostname(host):
    if host.name is None:
        debug("Error, host missinterpreted\n")
        return []
    else:
        return [str(host.name)]
    
def parser_url(host):
    if host.name is None:
        return []
    else:
        service = NMService()
        URL=[]
        if not host.services is None:
            for service in host.services:
                temp = ""
                if "https" in service.name or ("http" in service.name and "ssl" in service.name):
                    if service.port == "443":
                        temp="https://"+host.name
                    else:
                        temp="https://"+host.name+":"+service.port
                    URL.append(temp)
                else:
                    if "http" in service.name or 'http-proxy' in service.name:
                        if service.port == "80":
                            temp="http://"+host.name
                        elif service.port == "443":
                            temp="https://"+host.name
                        else:
                            temp="http://"+host.name+":"+service.port
                        URL.append(temp)
                    else:
                        debug("\tSkip:"+str(service)+"\n")
        else:
            debug("This host:"+host.name+" has no services???\n"+host.info+"\n")
        return URL

def parser_ftp(host):
    if host.name is None:
        return []
    else:
        service = NMService()
        URL=[]
        if not host.services is None:
            for service in host.services:
                temp = ""
                if "ftp" in service.name:
                    if service.port == "21":
                        temp="ftp://"+host.name
                    else:
                        temp="ftp://"+host.name+":"+service.port
                    URL.append(temp)
                else:
                    debug("\tSkip:"+str(service)+"\n")
        else:
            debug("This host:"+host.name+" has no services???\n"+host.info+"\n")
        return URL

def parser_telnet(host):
    if host.name is None:
        return []
    else:
        service = NMService()
        URL=[]
        if host.services is not None:
            for service in host.services:
                temp = ""
                if "telnet" in service.name:
                    if service.port == "23":
                        temp="telnet://"+host.name
                    else:
                        temp="telnet://"+host.name+":"+service.port
                    URL.append(temp)
                else:
                    debug("\tSkip:"+str(service)+"\n")
        else:
            debug("This host:"+host.name+" has no services???\n"+host.info+"\n")
        return URL

#Here is the global declaration for parsers, functions can be duplicated
action={'default':parser_default, 'url':parser_url, 'host':parser_hostname, 'ftp':parser_ftp, 'telnet':parser_telnet}

def parseLine(line, parser):
    debug("Received Line is:"+line)
    HFL = NMHost(line)
    return action[parser](HFL)    

PARSER_DEBUG=False
def debug(text):
    if PARSER_DEBUG:
        sys.stderr.write(str(text))
    return

class Command(BaseCommand):
    help = 'Processes the input for Worker Scans'
    def add_arguments(self, parser):
        #This single module reads the input file and converts it 
        parser.add_argument('--input', help='Input file, domain\tports or JobID:ID, if not provided stdin is used', default='stdin')
        parser.add_argument('--output', help='Output file, protocol://domain|ip:port/ or STDOUT if not provided', default='stdout')
        parser.add_argument('--parser', help='Parser algorithm (embedded, hardcoded)', default='default')
        parser.add_argument('--debug', help='Print verbose data', action='store_true', default=False)
        
    def handle(self, *args, **kwargs):        
        PARSER_INPUT = sys.stdin
        PARSER_OUTPUT = sys.stdout
#        global PARSER_DEBUG
        PARSER_DEBUG = kwargs['debug']
        
        debug(str(kwargs)+"\n")
        
        if kwargs['output'] != "stdout":
            PARSER_OUTPUT = open(kwargs['output'],'w')
            debug("Output: "+kwargs['output']+"\n")
        else:
            debug("Output: STDOUT \n")
        
        if kwargs['parser'] not in action:
            PARSER_DEBUG = True
            debug("Parser:"+kwargs['parser']+" not found in action declaration:"+str(action)+"\n")
            sys.exit()
            
        if kwargs['input'] != "stdin":
            if "JobID:" in kwargs['input']:
                JobID = kwargs['input'].split("JobID:")[1]
                debug("Requested to extract data from database backend for JobID:"+JobID+"\n")
                JOB_FOLDER = "/home/asf/jobs/"+JobID+"/"
                JOB_FILENAME = JOB_FOLDER+"app.asf"
                try:
                    Job = vdJob.objects.filter(id = JobID)[0]
                    HostsFromModel = search(Job.regexp, Job.input, Job.exclude)
                    if not path.exists(JOB_FOLDER):
                        os.makedirs(JOB_FOLDER)
                    INPUT_FILE = open(JOB_FILENAME,"w+")
                    HOSTS_COUNTER=0
                    if Job.input == 'amass':
                        for Host in HostsFromModel:
                            INPUT_FILE.write("Host: " +Host.ipv4+" ("+Host.name+")\tPorts: ///////\n")
                            HOSTS_COUNTER = HOSTS_COUNTER + 1
                    else:
                        for HostWithServices in HostsFromModel:
                            INPUT_FILE.write("Host: "+HostWithServices.ipv4+" ("+HostWithServices.name+")\tPorts: "+HostWithServices.full_ports.rstrip('\n')+"\n")
                            HOSTS_COUNTER = HOSTS_COUNTER + 1 
                    debug("All hosts data ("+str(HOSTS_COUNTER)+") Written on "+JOB_FILENAME+"\n")
                    INPUT_FILE.close()
                except Exception as e:
                    debug("Error creating the input for JobID:"+str(JobID)+"\n")
                    debug(str(e)+"\n")
                    sys.exit()
                PARSER_INPUT = open(JOB_FILENAME, 'r')
                debug("Input: "+JOB_FILENAME+"\n")
            else:
                PARSER_INPUT = open(kwargs['input'],'r')
                debug("Input: "+kwargs['input']+"\n")
        else:
            debug("Input: STDIN \n")
            
        while PARSER_INPUT:
            parser_objects = []
            line = PARSER_INPUT.readline(8192)
            if not line:
                PARSER_INPUT.close()
                PARSER_OUTPUT.close()
                break
            debug(line+"\n")
            parser_objects = parseLine(line, kwargs['parser'])
            #debug("Received Line Content:"+line)
            for parser_object in parser_objects:
                debug(parser_object+"\n")
                PARSER_OUTPUT.write(parser_object+"\n")
    
