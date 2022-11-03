#!/usr/bin/python3
#Nuclei Abstractions and tools, to avoid copy paste on functions
from app.tools import debug, PARSER_DEBUG, autodetectType, delta, get_metadata
from app.search import *
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.core.files.storage import FileSystemStorage
import sys
import json
import os.path
from pathlib import Path
import subprocess
import os
import re
from app.models import vdNucleiResult

NUCLEI_SEPARATOR = re.compile("[\[\]\n ]{2,}")
NUCLEI_IP_PORT = re.compile("\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\:\d+")
NUCLEI_IP = re.compile("(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
NUCLEI_PORT = re.compile("\:(\d+)")
NUCLEI_DOUBLE_PORT = re.compile("\:\d+\:(\d+)")
NUCLEI_DOMAIN_PORT = re.compile("(?!\-)(?:[a-zA-Z\d\-]{0,62}[a-zA-Z\d]\.){1,126}(?!\d+)[a-zA-Z\d]{1,63}\:(\d+)")
NUCLEI_DOMAIN = re.compile("(?!\-)(?:[a-zA-Z\d\-]{0,62}[a-zA-Z\d]\.){1,126}(?!\d+)[a-zA-Z\d]{1,63}")
NUCLEI_TEMPLATE_EXTENSIONS_PATTERNS = ['**/*.[yY][aA][mM][lL]']
NUCLEI_BLACKLIST_FILE = "/etc/vdnuclei.bl"
#DEFAULT VALUES, can be tweaked if required
NUCLEI_DEFAULT_SCOPE='E'
NUCLEI_DEFAULT_LEVEL='medium'

NUCLEI_PTIME = {
                'S':{'P0E':72, 'P1I':336, 'P1E':336, 'P2I':720, 'P2E': 720, 'P3I': 1440, 'P4E':2160, 'P4I':2160},
                'I':{'critical':'P1I', 'high':'P2I', 'medium':'P3I', 'low':'P4I'},
                'E':{'critical':'P0E', 'high':'P1E', 'medium':'P2E', 'low':'P4E'}
                }
class NFinding:
    def __init__(self, line=None, scope='E'):
        self.name = None
        self.tfp = None
        self.type = None
        self.source = None
        self.ipv4 = None
        self.ipv6 = None
        self.lastdate = datetime.now()
        self.firstdate = datetime.now()
        self.bumpdate = None
        self.port = None
        self.protocol = None
        self.detectiondate = None
        self.vulnerability = None
        self.engine = None
        self.level = None
        self.scope = scope
        self.ptime = None
        self.uri = None
        self.uriistruncated = 0
        self.full_uri = None
        self.nname = None
        self.itemcount = None
        self.tag = None
        self.info = None
        self.line = line
        self.owner = None
        self.metadata = None
        self.temp_array = None
        if (self.line is not None):
            self.temp_array = NUCLEI_SEPARATOR.split(self.line)
            #debug("Nuclei Array size:"+str(len(self.temp_array))+"\n")
            if len(self.temp_array) >= 5:
                self.detectiondate = self.temp_array[0][1:]
                debug("DateOnFile:"+self.temp_array[0]+":")
                self.detectiondate = datetime.strptime(self.detectiondate, "%Y-%m-%d %H:%M:%S")
                self.temp_array[0]=self.detectiondate
                debug("DateAsObject:"+str(self.detectiondate)+"\n")
                self.vulnerability = self.temp_array[1]
                self.engine = self.temp_array[2]
                #self.level = self.temp_array[3].lower()
                self.level = self.temp_array[-2].lower()
                #self.full_uri = self.temp_array[4]
                self.full_uri = self.temp_array[-1]
                self.uri = self.full_uri
                if len(self.full_uri) > vdNucleiResult._meta.get_field('uri').max_length:
                    self.uriistruncated = 1
                if len(self.temp_array) >= 6:
                    self.info = self.temp_array[5]
                else:
                    self.info = ""
                self.setPortandName()
                debug("Port detection debug:"+self.name+":"+str(self.port)+"\n")
                self.type=autodetectType(self.name)
                self.ptime,hours=nuclei_ptime(self.level, self.scope)
                self.bumpdate=self.detectiondate+timedelta(hours=hours)
                debug("Delta date:"+str(self.bumpdate)+":"+self.ptime+":"+self.level+":"+str(self.detectiondate)+"\n")
            else:
                debug("Error parsing finding in Nuclei Format, received:"+str(len(self.temp_array))+"/6 for line: "+str(line)+"\n")
        else:
            debug("Error parsing Line in Nuclei Format, received:"+str(line)+":Broken or empty\n")
            
    def __str__(self):
        return "Name["+str(self.name)+"]:["+str(self.port)+"]:~:"+str(self.detectiondate)+":~:"+str(self.vulnerability)+":~:"+str(self.engine)+":~:"+str(self.level)+":~:"+str(self.uri)+":~:Truncated:~:"+str(self.uriistruncated)+":~:"+str(self.info)
    
    def setPortandName(self):
        #I don't know why NUCLEI_DOMAIN_PORT.match does not work, but with findall and len>0 we were able to detect the host part
        PORT="443"
        if len(NUCLEI_DOMAIN_PORT.findall(self.full_uri))>0:
            debug("Matching DP\n")
            self.name = NUCLEI_DOMAIN.findall(self.full_uri)[0]
            if len(NUCLEI_DOUBLE_PORT.findall(self.full_uri))>0:
                PORT=NUCLEI_DOUBLE_PORT.findall(self.full_uri)[0]
            else:
                PORT = NUCLEI_PORT.findall(self.full_uri)[0]
        else:
            debug("NOT Matching DP\n")
            if len(NUCLEI_IP_PORT.findall(self.full_uri))>0:
                debug("Matching IP\n")
                self.name = NUCLEI_IP.findall(self.full_uri)[0]
                if len(NUCLEI_DOUBLE_PORT.findall(self.full_uri))>0:
                    PORT = NUCLEI_DOUBLE_PORT.findall(self.full_uri)[0]
                else:
                    PORT = NUCLEI_PORT.findall(self.full_uri)[0]
            else:
                debug("NOT Matching IP\n")
                if len(NUCLEI_DOMAIN.findall(self.full_uri))>0:
                    debug("Matching D\n")
                    self.name = NUCLEI_DOMAIN.findall(self.full_uri)[0]
                else:
                    debug("NOT Matching D\n")
                    if len(NUCLEI_IP.findall(self.full_uri))>0:
                        debug("Matching I\n")
                        self.name = NUCLEI_IP.findall(self.full_uri)[0]
                    else:
                        debug("NOT Matching I\n")
                if self.full_uri.startswith("https"):
                    PORT="443"
                else:
                    if self.full_uri.startswith("http"):
                        PORT="80"
        self.port=int(PORT)
        self.nname=self.name
                
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
    
    def update(self):
        debug("Updating"+self.__str__())
        
    def create(self):
        debug("Creating"+self.__str__())

#Usable functions non part of the class.
def nuclei_delete_model(context):
    MSG={}
    NF = vdNucleiResult.objects.none()
    if 'name' in context:
        MSG['name']=context['name']
        if 'vulnerability' in context:
            MSG['message']="[NUCLEI][DELETE]"
            MSG['vulnerability']=context['vulnerability']
            NF = vdNucleiResult.objects.filter(name=MSG['name'], vulnerability=MSG['vulnerability'])
        else:
            MSG['message']="[NUCLEI][DELETE][ALL]"
            NF = vdNucleiResult.objects.filter(name=MSG['name'])
    else:
        if 'domain_search' in context:
            MSG['message']="[NUCLEI][DELETE][SEARCH]"
            MSG['search']=context['domain_search']
            NF = search(context['domain_search'],'nuclei')
            IGNORE_NEWCONTEXT,NF = nuclei_filter(context, NF)
        else:
            MSG['message']="[NUCLEI][DELETE][ERROR]"
            MSG['name']='None'
            
    if NF.count()>=1:
        NF.delete()
    else:
        debug("Objects not found:"+str(NF)+":"+str(MSG))    
    delta(MSG)
    debug(str(MSG))

def nuclei_tfp_model(context):
    MSG={}
    NF = vdNucleiResult.objects.none()
    MSG['message']="[NUCLEI]["+context['nuclei_action'].upper()+"]"
    if 'name' in context:
        MSG['name']=context['name']
        if 'vulnerability' in context:
            MSG['vulnerability']=context['vulnerability']
            NF = vdNucleiResult.objects.filter(name=MSG['name'], vulnerability=MSG['vulnerability'])
        else:
            MSG['message']=MSG['message']+"[ALL]"
            NF = vdNucleiResult.objects.filter(name=MSG['name'])
    else:
        if 'domain_search' in context:
            MSG['search']=context['domain_search']
            MSG['message']=MSG['message']+"[BySEARCH]"
            NF = search(MSG['search'],'nuclei')
    debug("\n[Updating]:"+str(NF)+":[FROM][CONTEXT]:"+str(context)+"\n")
    #Other status different than true or false makes STATUS = -1    
    STATUS = -1
    if 'nuclei_action' in context:
        if context['nuclei_action'] == "true":
            STATUS=1
        if context['nuclei_action'] == "false":
            STATUS=0
    IGNORE_ANSWER,NF = nuclei_filter(context, NF)
    if NF.count()>=1:
        NF.update(tfp=STATUS)
    delta(MSG)
    debug(str(MSG))

def nuclei_filter(POST,subset):
    context = {}
    def merge_results(partial, results):
        results = results | partial
        return results
    
    def nuclei_filter_true(context,objects):
        subset = objects.filter(tfp=1)
        return subset
    
    def nuclei_filter_false(context,objects):
        subset = objects.filter(tfp=0)
        return subset
    
    def nuclei_filter_bump(context,objects):
        subset = objects.filter(tfp=-1)
        return subset
    
    def nuclei_filter_new(context,objects):
        dt = datetime.today() - timedelta(days=7)
        subset = objects.filter(tfp=-1, detectiondate__gte=dt)
        return subset

    def nuclei_filter_old(context,objects):
        dt = datetime.today() - timedelta(days=7)
        subset = objects.filter(tfp=-1, detectiondate__lt=dt)
        return subset
    
    def is_filter_enabled(context,filter):
        if filter in context:
            if context[filter] == "on" or context[filter] == "checked":
                return True
        return False
    
    #Special context filter variables
    FILTERS = {'nuclei_filter_true':nuclei_filter_true, 'nuclei_filter_false':nuclei_filter_false, 'nuclei_filter_bump':nuclei_filter_bump, 'nuclei_filter_new':nuclei_filter_new, 'nuclei_filter_old':nuclei_filter_old}
    NOFILTERS = True
    CHECKEDCOUNT = 0
    for filter in FILTERS:
        if is_filter_enabled(POST, filter):
            context[filter]="checked"
            NOFILTERS = False
            CHECKEDCOUNT +=1
            debug("Filter["+filter+"]="+POST[filter]+"\n")

    filtered=vdNucleiResult.objects.none()
    if NOFILTERS or CHECKEDCOUNT==len(FILTERS):
        filtered=subset
        debug("All selectors = All objects\n")
    else:
        for filter in FILTERS:
            if is_filter_enabled(context,filter):
                fobjects=FILTERS[filter](context,subset)
                debug("Filtered to include:["+filter+"]="+str(fobjects)+"\n")
                filtered=merge_results(fobjects, filtered)
    return context,filtered

def nuclei_ptime(level,scope):
    if scope not in ['E','I']:
        scope=NUCLEI_DEFAULT_SCOPE
    if level not in ['critical', 'high', 'medium', 'low']:
        level=NUCLEI_DEFAULT_LEVEL
    return NUCLEI_PTIME[scope][level], NUCLEI_PTIME['S'][NUCLEI_PTIME[scope][level]]

def get_nuclei_ptime_selector(context):
    SELECTOR="<select name='nuclei_ptime'>\n"
    DEFAULT='P0E'
    if 'nuclei_ptime' in context:
        if  context['nuclei_ptime'] in NUCLEI_PTIME['S']:
            DEFAULT=context['nuclei_ptime']
    for option in NUCLEI_PTIME['S']:
        SELECTED=""
        if option==DEFAULT:
            SELECTED="selected"
        SELECTOR+="<option value='"+option+"' "+SELECTED+">"+option+"</option>\n"
    SELECTOR+="</select>\n"
    return SELECTOR

def get_nuclei_filter_hidden(context):
#    FILTER="<input type=\"hidden\" name='domain_search' value=\""+get_default(context,'domain_search')+"\">"
    FILTER="<input type=\"hidden\" name='nuclei_filter_true' value=\""+get_default(context,'nuclei_filter_true')+"\">"
    FILTER+="<input type=\"hidden\" name='nuclei_filter_false' value=\""+get_default(context,'nuclei_filter_false')+"\">"
    FILTER+="<input type=\"hidden\" name='nuclei_filter_bump' value=\""+get_default(context,'nuclei_filter_bump')+"\">"
    FILTER+="<input type=\"hidden\" name='nuclei_filter_new' value=\""+get_default(context,'nuclei_filter_new')+"\">"
    FILTER+="<input type=\"hidden\" name='nuclei_filter_old' value=\""+get_default(context,'nuclei_filter_old')+"\">"
    return FILTER

def get_default(context,keyword,default=""):
    if keyword in context:
        return context[keyword]
    else:
        return default

def set_nuclei_ptime(context):
    MSG={}
    NEW_PTIME='P0E'
    if 'nuclei_ptime' in context:
        if context['nuclei_ptime'] in NUCLEI_PTIME['S']:
            NEW_PTIME=context['nuclei_ptime']
    NF = vdNucleiResult.objects.none()
    MSG['message']="[NUCLEI]["+context['nuclei_action'].upper()+"]"
    if 'name' in context:
        MSG['name']=context['name']
        if 'vulnerability' in context:
            MSG['vulnerability']=context['vulnerability']
            NF = vdNucleiResult.objects.filter(name=MSG['name'], vulnerability=MSG['vulnerability'])
        else:
            MSG['message']=MSG['message']+"[ALL]"
            NF = vdNucleiResult.objects.filter(name=MSG['name'])
    else:
        if 'domain_search' in context:
            MSG['search']=context['domain_search']
            MSG['message']=MSG['message']+"[BySEARCH]"
            NF = search(MSG['search'],'nuclei')
    debug("\n[Updating]:"+str(NF)+":[FROM][CONTEXT]:"+str(context)+"\n")
    #Other status different than true or false makes STATUS = -1    
    IGNORE_ANSWER,NF = nuclei_filter(context, NF)
    if NF.count()>=1:
        NF.update(ptime=NEW_PTIME)
    delta(MSG)
    debug(str(MSG))

def update_nuclei_finding(ResultSet, DATA, Optional=False):
    #Missing calculations for bumptime, we can not update bumptime, because it has to be from the very beginning of the first discovery. 
    #ResultSet.update(name=DATA.name, owner=DATA.owner, metadata=DATA.metadata, info=DATA.info, vulnerability=DATA.vulnerability, detectiondate=DATA.detectiondate, engine=DATA.engine, level=DATA.level, uri=DATA.uri, full_uri=DATA.full_uri, uriistruncated=DATA.uriistruncated, nname=DATA.nname, port=DATA.port, lastdate=datetime.now())
    #Missing not updated fields below are on purpose, because in a bulk update you shuld not update with an unique name all objects, some others like vulnerability will not change, and so on.
    for VDNR in ResultSet:
        VDNR.owner=DATA.owner
        VDNR.metadata=DATA.metadata
        VDNR.info=DATA.info
        #Not sure if has to be updated, using Optional Feature
        if Optional:
            #VDNR.detectiondate=DATA.detectiondate
            VDNR.uri=DATA.uri
            VDNR.full_uri=DATA.full_uri
            VDNR.uriistruncated=DATA.uriistruncated
            VDNR.nname=DATA.nname
            VDNR.port=DATA.port
            VDNR.engine=DATA.engine
        VDNR.level=DATA.level
        VDNR.lastdate=datetime.now()
        VDNR.ptime,hours=nuclei_ptime(DATA.level, DATA.scope)
        VDNR.bumpdate=VDNR.detectiondate+timedelta(hours=hours)
        VDNR.save()
    return
        
def create_nuclei_finding(DATA):
    Nfinding = vdNucleiResult(name=DATA.name, owner=DATA.owner, metadata=DATA.metadata, info=DATA.info, vulnerability=DATA.vulnerability, detectiondate=DATA.detectiondate, engine=DATA.engine, level=DATA.level, uri=DATA.uri, full_uri=DATA.full_uri, uriistruncated=DATA.uriistruncated, nname=DATA.nname, port=DATA.port, bumpdate=DATA.bumpdate, firstdate=DATA.firstdate, ptime=DATA.ptime)
    Nfinding.save()
    return

def get_nuclei_templates(folders=['/home/nuclei-templates/']):
    FILES = []
    for folder in folders:
        debug(folder+"\n")
#         if os.path.isfile(folder):
#             FILES.append(folder)
        if os.path.isdir(folder):
            for p in NUCLEI_TEMPLATE_EXTENSIONS_PATTERNS:
                pathlist = Path(folder).glob(p)
                for path in pathlist:
                    filename = str(path)
                    #debug(filename+"\n")
                    nucleifn=filename.replace(folder, "")
                    FILES.append(nucleifn)
    return FILES

def get_nuclei_templates_4view(templates):
    TEMPLATES=[]
    ID=0
    BL=get_nuclei_templates_4bl()
    for template in templates:
        enabled=""
        if template in BL:
            enabled="checked"
        TEMPLATES.append({'id':ID, 'template':template, 'enabled':enabled})
        ID+=1
    return TEMPLATES
    
def set_nuclei_templates_4bl(context,FILES=[]):
    BL=[]
    for file in FILES:
        #debug("Is file in context:"+file+"?\n")
        if file in context:
            BL.append(file)
    debug(BL)
    JFC=open(NUCLEI_BLACKLIST_FILE,"w+")
    json_info=json.dumps(BL)
    JFC.write(json_info)
    return

def get_nuclei_templates_4bl(FILES=[]):
    BL=[]
    if Path(NUCLEI_BLACKLIST_FILE).is_file():
        JFC=open(NUCLEI_BLACKLIST_FILE,"r")
        json_info=JFC.read()
        BL=json.loads(json_info)
    return BL