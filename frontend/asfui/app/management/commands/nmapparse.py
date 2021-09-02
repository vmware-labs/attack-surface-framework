#!/usr/bin/python3
from django.core.management.base import BaseCommand, CommandError
from app.models import vdTarget, vdResult, vdServices, vdInServices, vdRegExp, vdJob  
from django.utils import timezone
import re
from cProfile import label
from app.views import autodetectType, delta
from app.nmapmodels import NMAP_PORTS, NMHost, NMService

class Command(BaseCommand):
    help = 'Processes the input for Worker Scans'
    def add_arguments(self, parser):
        #This single module reads the input file and converts it 
        parser.add_argument('--input', help='The input file from nmap', default='stdin')
        parser.add_argument('--host', help='Hostname from Target system')
        parser.add_argument('--destination', help='The destination algorithm (internal, external)', default='external')
        parser.add_argument('--debug', help='Print verbose data', action='store_true', default=False)

    def handle(self, *args, **kwargs):
        for item in kwargs:
            print(item)
        last_report=kwargs['input']
        host = kwargs['host']
        self.stdout.write("Process:"+last_report+":"+host)
        report=open(last_report+".nmap",'r')
        report_content = report.read()
        report.close()
        report=open(last_report+".gnmap",'r')
        lines=0
        for line in report:
            if NMAP_PORTS.match(line):
                self.stdout.write("Process REGEXP:"+line)
                Host = NMHost(line, host)
                if kwargs['destination'] == "external":
                    Result = vdServices(name=Host.name, nname=Host.nname, ipv4=Host.ipv4, tags="[Services]", info = report_content, ports = Host.full_ports, full_ports = Host.full_ports, info_gnmap = Host.line, type=autodetectType(Host.name))
                if kwargs['destination'] == "internal":
                    Result = vdInServices(name=Host.name, nname=Host.nname, ipv4=Host.ipv4, tags="[Services]", info = report_content, ports = Host.full_ports, full_ports = Host.full_ports, info_gnmap = Host.line, type=autodetectType(Host.name))
                NewData = True
                
                try:
                    Result.save()
                    self.stderr.write("New Finding:"+Host.name+":"+Host.nname+":"+Host.ipv4+":"+Host.full_ports)
                    
                except:
                    NewData = False
                    self.stderr.write("Finding Already exist:"+Host.name+":"+Host.nname+":"+Host.ipv4+":"+Host.full_ports)
                
                if NewData:
                    #At this point data is new - An alert needs to be fired
                    MSG = Host.getList()
                    MSG["message"] = "[NMAP][New Host Found]"
                    delta(MSG)
                    #One Alert for each service
                    for service in Host.services:
                        MSG = service.getList()
                        MSG['message'] = "[NMAP][New Service Found]"
                        delta(MSG)
                
                if not NewData:
                    self.stderr.write("Searching:"+Host.name)
                    if kwargs['destination'] == "external":
                        OldData = vdServices.objects.filter(name=Host.name)
                    if kwargs['destination'] == "internal":
                        OldData = vdInServices.objects.filter(name=Host.name)
                    OldHost = NMHost(OldData[0].info_gnmap, OldData[0].nname)
                    self.stderr.write("Found and Updating:"+str(OldData[0].id)+":"+Host.name+":"+Host.full_ports)
                    self.stderr.write("Old Data Get List:"+str(OldHost.getList())+"\n")
                    #Compare New with Old
                    for service in Host.services:
                        Match = False
                        for oldservice in OldHost.services:
                            if service.match(oldservice):
                                Match = True
                                break
                        if not Match:
                            MSG = service.getList()
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
                            MSG['message'] = "[NMAP][Service Closed]"
                            MSG['hostname'] = Host.name
                            MSG['hostnname'] = Host.nname
                            MSG['ipv4'] = Host.ipv4
                            delta(MSG)

                    OldData.update(info = report_content, nname=Host.nname, ipv4=Host.ipv4, ports = Host.full_ports, full_ports = Host.full_ports, info_gnmap = Host.line)
            self.stderr.write(line)
            lines +=1
        self.stderr.write("Done printing")