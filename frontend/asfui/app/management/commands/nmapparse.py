#!/usr/bin/python3
from django.core.management.base import BaseCommand, CommandError
from app.models import vdTarget, vdResult, vdServices, vdInServices, vdRegExp, vdJob  
from django.utils import timezone
import re, json
from cProfile import label
from app.views import autodetectType, delta, debug, get_metadata, PARSER_DEBUG
from app.nmapmodels import NMAP_PORTS, NMHost, NMService

class Command(BaseCommand):
    help = 'Processes the input for Worker Scans'
    def add_arguments(self, parser):
        #This single module reads the input file and convert it into 
        parser.add_argument('--input', help='The input file from nmap', default='stdin')
        parser.add_argument('--host', help='Hostname from Target system')
        parser.add_argument('--destination', help='The destination algorithm (internal, external)', default='external')
        parser.add_argument('--debug', help='Print verbose data', action='store_true', default=False)

    def handle(self, *args, **kwargs):
        for item in kwargs:
            print(item)
        last_report=kwargs['input']
        host = kwargs['host']
        PARSER_DEBUG = kwargs['debug']
        debug("Process:"+last_report+":"+host)
        report=open(last_report+".nmap",'r')
        report_content = report.read()
        report.close()
        report=open(last_report+".gnmap",'r')
        lines=0
        for line in report:
            if NMAP_PORTS.match(line):
                debug("Process REGEXP:"+line)
                Host = NMHost(line, host)
                MDT,MDATA = get_metadata(Host.name,kwargs['destination'])
                if kwargs['destination'] == "external":
                    Result = vdServices(name=Host.name, nname=Host.nname, ipv4=Host.ipv4, tags="[Services]", info = report_content, ports = Host.full_ports, full_ports = Host.full_ports, info_gnmap = Host.line, type=autodetectType(Host.name), metadata = MDATA, owner = MDT['owner'])
                if kwargs['destination'] == "internal":
                    Result = vdInServices(name=Host.name, nname=Host.nname, ipv4=Host.ipv4, tags="[Services]", info = report_content, ports = Host.full_ports, full_ports = Host.full_ports, info_gnmap = Host.line, type=autodetectType(Host.name), metadata = MDATA, owner = MDT['owner'])
                NewData = True
                
                try:
                    Result.save()
                    debug("New Finding Saved:"+Host.name+":"+Host.nname+":"+Host.ipv4+":"+MDT['owner']+":"+Host.full_ports+"\n")
                    
                except:
                    NewData = False
                    debug("Finding Already exist:"+Host.name+":"+Host.nname+":"+Host.ipv4+":"+MDT['owner']+":"+Host.full_ports+"\n")
                
                if NewData:
                    #At this point data is new and has to be fired an alert
                    MSG = Host.getList()
                    MSG.update(MDT)
                    MSG["message"] = "[NMAP][New Host Found]"
                    delta(MSG)
                    #One Alert for each service
                    for service in Host.services:
                        MSG = service.getList()
                        MSG.update(MDT)
                        MSG['message'] = "[NMAP][New Service Found]"
                        delta(MSG)
                
                if not NewData:
                    debug("Searching:"+Host.name)
                    if kwargs['destination'] == "external":
                        OldData = vdServices.objects.filter(name=Host.name)
                    if kwargs['destination'] == "internal":
                        OldData = vdInServices.objects.filter(name=Host.name)
                    OldHost = NMHost(OldData[0].info_gnmap, OldData[0].nname)
                    debug("Found and Updating:"+str(OldData[0].id)+":"+Host.name+":"+Host.full_ports)
                    debug("Old Data Get List:"+str(OldHost.getList())+"\n")
                    #Compare New with Old
                    for service in Host.services:
                        Match = False
                        for oldservice in OldHost.services:
                            if service.match(oldservice):
                                Match = True
                                break
                        if not Match:
                            MSG = service.getList()
                            MSG.update(MDT)
                            MSG['message'] = "[NMAP][New Service Found]"
                            MSG['hostname'] = Host.name
                            MSG['hostnname'] = Host.nname
                            MSG['ipv4'] = Host.ipv4
                            delta(MSG)
                    #Compare Old data with New
                    for service in OldHost.services:
                        Match = False
                        for newservice in Host.services:
                            if service.match(newservice):
                                Match = True
                                break
                        if not Match:
                            MSG = service.getList()
                            MSG.update(MDT)
                            MSG['message'] = "[NMAP][Service Closed]"
                            MSG['hostname'] = Host.name
                            MSG['hostnname'] = Host.nname
                            MSG['ipv4'] = Host.ipv4
                            delta(MSG)

                    OldData.update(info = report_content, nname=Host.nname, ipv4=Host.ipv4, ports = Host.full_ports, full_ports = Host.full_ports, info_gnmap = Host.line, owner = MDT['owner'], metadata = MDATA)
                    debug("\n\n#########Updating....#################\n")
            debug(line)
            lines +=1
        debug("Done printing")
    