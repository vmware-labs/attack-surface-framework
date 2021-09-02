#!/usr/bin/python3
from django.core.management.base import BaseCommand, CommandError
from app.models import vdTarget, vdInTarget, vdResult, vdServices, vdInServices, vdRegExp, vdJob  
from django.utils import timezone
import re
import sys
import os
import netaddr
from cProfile import label
from app.views import autodetectType

PARSER_DEBUG=False
def debug(text):
    if PARSER_DEBUG:
        sys.stderr.write(str(text))
    return

class Command(BaseCommand):
    def add_arguments(self, parser):
        #This single module reads the input file and converts it accordigly 
        parser.add_argument('--input', help='Input vector for nmap: amass|external|internal', default='amass')
        parser.add_argument('--output', help='The destination file', default='stderr')
        parser.add_argument('--debug', help='Print verbose data', action='store_true', default=False)

#     def add_arguments(self, parser):
#         parser.add_argument("report-file", nargs='+')
#         parser.add_argument('host', nargs='+')
    def handle(self, *args, **kwargs):

        NMAP_PORTS = re.compile(".*Ports:\s")
        NMAP_TAB = re.compile("\t")
        NMAP_HOST = re.compile("Host:\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+\((.*?)\)")

        for item in kwargs:
            print(item)
            
        PARSER_INPUT = kwargs['input']
        global PARSER_DEBUG
        PARSER_DEBUG = kwargs['debug']
        #app.views.PARSER_DEBUG = PARSER_DEBUG
        PARSER_OUTPUT = sys.stdout
        debug("Process:"+PARSER_INPUT+"\n")
        if kwargs['output'] != "stderr":
            PARSER_OUTPUT = open(kwargs['output'], "w+")
        
        Targets = []
        if PARSER_INPUT == "inservices" or PARSER_INPUT == "internal" or PARSER_INPUT == "intarget" or PARSER_INPUT == "intargets":
            Targets=vdInTarget.objects.all()
        if PARSER_INPUT == "amass":
            Targets=vdResult.objects.all()
        if PARSER_INPUT == "services" or PARSER_INPUT == "external" or PARSER_INPUT == "target" or PARSER_INPUT == "targets":
            Targets=vdTarget.objects.all()
        for target in Targets:
            TYPE = autodetectType(target.name)
            if TYPE == "CIDR":
                debug("Exploding CIDR:"+str(target)+"\n")
                for ip in netaddr.IPNetwork(target.name):
                    debug(str(ip)+" ")
                    PARSER_OUTPUT.write(str(ip)+"\n")
            else:
                debug(target.name+" ")
                PARSER_OUTPUT.write(target.name+"\n")

        debug("\nDone..\n")
        PARSER_OUTPUT.close()