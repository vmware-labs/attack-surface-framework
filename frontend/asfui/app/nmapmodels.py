#!/usr/bin/python3
import re
from app.views import debug, PARSER_DEBUG

PARSER_DEBUG = False
NMAP_PORTS = re.compile(".*Ports:\s")
NMAP_TAB = re.compile("\t")
NMAP_HOST = re.compile("Host:\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+\((.*?)\)")

# Parses nmap greppable format in an object
class NMService():
    def __init__(self, line = None):
        self.port = None
        self.state = None
        self.protocol = None
        self.owner = None
        self.name = None
        self.rpc_info = None
        self.version = None
        if not (line is None):
            temp_array = line.split("/")
            #debug("Service Array size:"+str(len(temp_array))+"\n")
            if len(temp_array) > 6:
                self.port = temp_array[0]
                self.state = temp_array[1]
                self.protocol = temp_array[2]
                self.owner = temp_array[3]
                self.name = temp_array[4]
                self.rpc_info = temp_array[5]
                self.version = temp_array[6]
            else:
                debug("Error parsing services in nmap Format, received:"+str(len(temp_array))+"/7 for line: "+str(line)+"\n")

    def __str__(self):
        return self.port.lower()+":"+self.protocol.lower()+":"+self.name.lower()
    
    def getList(self):
        return {'port':self.port, 'state':self.state, 'protocol':self.protocol, 'owner':self.owner, 'name':self.name, 'info':self.rpc_info, 'version':self.version}
    
    def match(self, Other):
        if Other.port != self.port:
            return False
        if Other.state != self.state:
            return False
        if Other.protocol != self.protocol:
            return False
        if Other.owner != self.owner:
            return False
        if Other.name != self.name:
            return False
        if Other.rpc_info != self.rpc_info:
            return False
        if Other.version != self.version:
            return False
        
        return True

# Similar NMService, includes multiple service objects
class NMHost:
    def __init__(self, *args):
        self.line = None
        self.name = None
        if (len(args)>=1):
            self.line = args[0]
        if (len(args)>=2):
            self.name = args[1]
        self.services = None
        self.info = ""
        self.ipv4 = ""
        self.nname = ""
        self.full_ports = "" #same as info
        if (self.line is not None):
            #First TAB contains the Hostname and IP address
            Finding = NMAP_TAB.split(self.line)
            debug(Finding)
            Host = NMAP_HOST.match(Finding[0])
            self.nname = Host.group(2).strip()
            self.ipv4 = Host.group(1)
            if self.name is None:
                if self.nname != "":
                    self.name = self.nname
                else:
                    self.name = self.ipv4
            Finding = NMAP_PORTS.split(Finding[1])
            #Ignored States have another TAB
            Finding = NMAP_TAB.split(Finding[1])
            RPorts = Finding[0].rstrip('\n')
            if len(RPorts)>1:
                self.info = RPorts
                self.full_ports = RPorts
                temp_array = self.info.split(", ")
                self.services = []
                debug("Data in temp_array:"+str(temp_array)+"\n")
                for service in temp_array:
                    SOBJ = NMService(service)
                    if SOBJ.name is not None:
                        self.services.append(SOBJ)
                    else:
                        debug("Parsing the service line returns an empty object, skipping:"+service+"\n")
        else:
            debug("In Parsing the host line, we got an empty line, skipping:"+str(self.line)+":"+str(len(args))+"\n")
            
    def __str__(self):
        return self.name+":"+self.info
    
    def getList(self):
        return {'name':self.name, 'nname':self.nname, 'ipv4':self.ipv4, 'services':self.info}
