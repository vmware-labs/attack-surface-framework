#!/usr/bin/python3
#Target Abstractions, to avoid copy paste on functions
# from app.tools import debug, PARSER_DEBUG, autodetectType
from datetime import date, datetime
from django.utils import timezone
from django.core.files.storage import FileSystemStorage
import sys
import json
import os.path
import subprocess
import os
from app.models import vdResult

def discovery_new(request,context,autodetectType,delta):
    if 'amass_domain' in request.POST:
        domain = request.POST['amass_domain'].strip()
        Tag = "NOTFOUND"
        tz = timezone.get_current_timezone()
        LastDate = datetime.now().replace(tzinfo=tz)
        WorkMode = "merge"
        if "tag" in request.POST:
            Tag = request.POST['tag'].strip()                
        if not domain == "":
            Type = autodetectType(domain)
            metadata = {}
            metadata['owner']="Admin from UI"
            Jmetadata = json.dumps(metadata)
            vdResult.objects.update_or_create(name=domain, defaults={'type': Type, 'tag':Tag, 'lastdate': LastDate, 'owner': metadata['owner'], 'metadata': Jmetadata})
        if 'amass_file' in request.FILES:
            amass_file = request.FILES['amass_file']
            fs = FileSystemStorage()
            filename = fs.save(amass_file.name, amass_file)
            uploaded_file_url = fs.url(filename)
            context['amass_file'] = uploaded_file_url
            addDomFiles = open(filename, "r")
            for domain in addDomFiles:
                domain = domain.strip()
                Type = autodetectType(domain)
                metadata = {}
                metadata['owner']="Admin from UI"
                metadata['bulk']=amass_file.name
                Jmetadata = json.dumps(metadata)
                try:
                    vdResult.objects.update_or_create(name=domain, defaults={'type': Type, 'tag':Tag, 'lastdate': LastDate, 'owner':metadata['owner'], 'metadata': Jmetadata})
                except:
                    sys.stderr.write("Duplicated Amass Discovery, Skipping:"+domain)
                    
        if 'mode' in request.POST:
            WorkMode = request.POST['mode'].strip()
            sys.stderr.write("WorkMode:"+WorkMode+"\n")
            if WorkMode != 'merge':
                if WorkMode == 'sync':
                    DeleteTarget = vdResult.objects.filter(tag=Tag).filter(lastdate__lt=LastDate)
                if WorkMode == 'delete':
                    #The equals command in filter, does not work for datetimes, so we use __gte instead
                    DeleteTarget = vdResult.objects.filter(tag=Tag).filter(lastdate__gte=LastDate)
                if WorkMode == 'deletebytag':
                    DeleteTarget = vdResult.objects.filter(tag=Tag)
                internal_discovery_delete(DeleteTarget,autodetectType,delta)
                
def discovery_delete(request,context,autodetectType,delta):
    if 'id' in request.POST:
        id=request.POST['id']
        DeleteTarget = vdResult.objects.filter(id=id)
        internal_discovery_delete(DeleteTarget,autodetectType,delta)
        #DeleteTarget.delete()

def internal_discovery_delete(DeleteTarget,autodetectType,delta):
    #This function is tabbed because we do not want to make it global, it is only available inside internal_delete. 
    def get_metadata_array(metadata):
        if len(metadata)>1:
            mdt = json.loads(metadata)
            if mdt is None:
                return {}
            else:
                return mdt
        else:
            return {}
        
    for obj in DeleteTarget:
        sys.stderr.write("Obj:"+str(obj)+"\n")
        #Here we really do the work, this will be hard to do, if there are many objects for deletion
        sys.stderr.write("\tSearching:"+str(obj)+" for service deletion\n")
        Name = obj.name
        DeleteFinding = vdResult.objects.filter(name=Name)
        for finding in DeleteFinding:
            sys.stderr.write("\t\tLinked for deletion Obj:"+str(finding)+"\n")
            MSG = get_metadata_array(finding.metadata)
            MSG['owner'] = finding.owner
            MSG['message'] = "[DELETE][OBJECT FROM "+vdResult._meta.object_name+" AMASS DATABASE]"
            MSG['type'] = autodetectType(finding.name)
            MSG['name'] = finding.name
            MSG['tag'] = finding.tag
            MSG['lastupdate'] = str(finding.lastdate)
            delta(MSG)
        #Bulk deletion, no loop required
        DeleteFinding.delete()                    
