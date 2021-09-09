#!/usr/bin/python3
#Target Abstractions, to avoid copy paste on functions
# from app.views import debug, PARSER_DEBUG, autodetectType
from datetime import date, datetime
from django.utils import timezone
from django.core.files.storage import FileSystemStorage
import sys
import json
import os.path
import subprocess
import os

def target_new_model(vdTargetModel,vdServicesModel,request,context,autodetectType,delta):
    if 'target_domain' in request.POST:
        domain = request.POST['target_domain'].strip()
        Tag = "NOTFOUND"
        tz = timezone.get_current_timezone()
        LastDate = datetime.now().replace(tzinfo=tz)
        WorkMode = "merge"
        if "tag" in request.POST:
            Tag = request.POST['tag'].strip()                
        if not domain == "":
            Type = autodetectType(domain)
            vdTargetModel.objects.update_or_create(name=domain, defaults={'type': Type, 'tag':Tag, 'lastdate': LastDate})
        if 'target_file' in request.FILES:
            target_file = request.FILES['target_file']
            fs = FileSystemStorage()
            filename = fs.save(target_file.name, target_file)
            uploaded_file_url = fs.url(filename)
            context['target_file'] = uploaded_file_url
            addDomFiles = open(filename, "r")
            for domain in addDomFiles:
                domain = domain.strip()
                Type = autodetectType(domain)
                try:
                    vdTargetModel.objects.update_or_create(name=domain, defaults={'type': Type, 'tag':Tag, 'lastdate': LastDate})
                except:
                    sys.stderr.write("Duplicated Target, Skipping:"+domain)
                    
        if 'mode' in request.POST:
            WorkMode = request.POST['mode'].strip()
            sys.stderr.write("WorkMode:"+WorkMode+"\n")
            if WorkMode != 'merge':
                if WorkMode == 'sync':
                    DeleteTarget = vdTargetModel.objects.filter(tag=Tag).filter(lastdate__lt=LastDate)
                if WorkMode == 'delete':
                    #The equals command in filter, does not work for datetimes, so we use __gte instead
                    DeleteTarget = vdTargetModel.objects.filter(tag=Tag).filter(lastdate__gte=LastDate)
                if WorkMode == 'deletebytag':
                    DeleteTarget = vdTargetModel.objects.filter(tag=Tag)
                internal_delete(vdTargetModel,vdServicesModel,DeleteTarget,autodetectType,delta)
                
def target_delete_model(vdTargetModel,vdServicesModel,request,context,autodetectType,delta):
    if 'id' in request.POST:
        id=request.POST['id']
        DeleteTarget = vdTargetModel.objects.filter(id=id)
        internal_delete(vdTargetModel,vdServicesModel,DeleteTarget,autodetectType,delta)
        #DeleteTarget.delete()

def internal_delete(vdTargetModel,vdServicesModel,DeleteTarget,autodetectType,delta):
    for obj in DeleteTarget:
        sys.stderr.write("Obj:"+str(obj)+"\n")
        #Here we really do the work, this will be hard to do, if there are many objects for deletion
        sys.stderr.write("\tSearching:"+str(obj)+" for service deletion\n")
        Name = obj.name
        DeleteFinding = vdServicesModel.objects.filter(name=Name)
        for finding in DeleteFinding:
            sys.stderr.write("\t\tLinked for deletion Obj:"+str(finding)+"\n")
            MSG = {}
            MSG['message'] = "[DELETE][OBJECT FROM SERVICES DATABASE]"
            MSG['type'] = autodetectType(finding.name)
            MSG['name'] = finding.name
            MSG['lastupdate'] = str(finding.lastdate)
            delta(MSG)
        #Bulk deletion, no loop required
        DeleteFinding.delete()                    
        DeleteFinding = vdServicesModel.objects.filter(nname=Name)
        for finding in DeleteFinding:
            sys.stderr.write("\t\tLinked for deletion Obj:"+str(finding)+"\n")
            MSG = {}
            MSG['message'] = "[DELETE][OBJECT FROM SERVICES DATABASE]"
            MSG['type'] = autodetectType(finding.name)
            MSG['name'] = finding.name
            MSG['lastupdate'] = str(finding.lastdate)
            delta(MSG)
        #Bulk deletion, no loop required
        DeleteFinding.delete()
        MSG = {}
        MSG['message'] = "[DELETE][OBJECT FROM TARGET DATABASE]"
        MSG['type'] = autodetectType(obj.name)
        MSG['name'] = obj.name
        MSG['lastupdate'] = str(obj.lastdate)
        delta(MSG)
        DeleteTarget.delete()
