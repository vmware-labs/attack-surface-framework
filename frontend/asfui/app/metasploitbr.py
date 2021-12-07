#!/usr/bin/python3
from pymetasploit3.msfrpc import *
import sys
import os
import psutil
import subprocess
import json
import time
from app.models import vdJob 
#Warning: You need to ignore some keywords in order to set all arguments, 'payloads', 'payload', 'exploit'
#these keywords are not part of the exploit configuration includded to pass information to Web Browser

def get_client_object():
    #Hardcoded password?, don't worry the server only works on localhost
    client = MsfRpcClient('changeme', host="127.0.0.1", ssl=True)
    return client

def get_msfconfig_by_module(module_name, module_type = 'exploit'):
    msf_check_services()
    client = get_client_object()
    Manager = MsfManager(client)
    MManager = ModuleManager(Manager)
    config_array = {}
    
    if module_name.startswith('auxiliary'):
        module_type = 'auxiliary'
    
    msfmodule = client.modules.use(module_type, module_name)
        
    for eopt in msfmodule.missing_required:
        config_array[eopt] = ""

    for eopt in msfmodule.runoptions:
        #sys.stderr.write(str(eopt)+"\n")
        config_array[eopt] = msfmodule.runoptions[eopt]
    
    config_array['payloads'] = ['none']
    if module_type == 'exploit':
        payloads = msfmodule.targetpayloads()
        config_array['payloads'] = payloads
    config_array['payload'] = ""

    print(config_array)
    return config_array

def msf_read_args(Job):
    job_id = Job.id
    JOB_FOLDER = "/home/asf/jobs/"+str(job_id)+"/"
    FileName = JOB_FOLDER+"msf.asfui"
    config = {}
    if os.path.isfile(FileName):
        MSFF=open(FileName,'r')
        json_info = MSFF.read()
        config = json.loads(json_info)
        MSFF.close()

    if 'exploit' in config:
        msfdefault = get_msfconfig_by_module(config['exploit'])
        for dkey in msfdefault:
            if dkey not in config:
                config[dkey] = msfdefault[dkey]
    
    if "payload" not in config:
        config['payload']=""
        
    return config

def msf_save_args(request):
    if 'job_id' in request.POST:
        MSFC = {}
        job_id = request.POST['job_id']
        Job = vdJob.objects.filter(id = job_id)[0]
        JOB_FOLDER = "/home/asf/jobs/"+str(job_id)+"/"
        FileName = JOB_FOLDER+"msf.asfui"
        if 'exploit' in request.POST:
            MSFC['exploit'] = request.POST['exploit']
            econfig = get_msfconfig_by_module(MSFC['exploit'])
            for ekey in econfig:
                if ekey in request.POST:
                    MSFC[ekey] = request.POST[ekey]
                else:
                    MSFC[ekey] = econfig[ekey]
                        
            json_data = json.dumps(MSFC) 
            MSFF = open(FileName, 'w+')
            MSFF.write(json_data)
            return True
    return False

def msf_execute(cmdarray):
        sys.stderr.write("\nExcecuting command"+str(cmdarray)+"\n")
        subprocess.Popen(cmdarray)
        
def msf_check_services():
    PMSFD = False
    PMSFRPCD = False
    for process in psutil.process_iter():
        #For now, we are going to assume a unique process with that name is running, in the future it should be checked the port number too, but it could be in a container, so is the same problem.
        #sys.stderr.write("Process name:"+str(process)+str(process.cmdline())+"\n")
        if process.name == "msfd" or process.name == "msfrpcd":
            PMSFD = True
    if not PMSFRPCD:
        CMDARGS = ['nohup',  '/usr/bin/msfrpcd', '-P', 'changeme', '-f']
        msf_execute(CMDARGS)
    if not PMSFD:
        CMDARGS = ['nohup', '/usr/bin/msfd', '-f', '-a', '127.0.0.1', '-p', '5554']
        msf_execute(CMDARGS)
    time.sleep(10)