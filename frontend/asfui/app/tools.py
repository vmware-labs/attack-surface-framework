#!/usr/bin/python3
import sys
import os
import re
import shutil
from datetime import date, datetime, timedelta
import time
import json
import hashlib
from app.models import vdTarget, vdInTarget


# This classes and functions are meant to be exported, to avoid duplicates between modules, commands or else.
PARSER_DEBUG=True
DETECTOR_IPADDRESS = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
DETECTOR_IPADDRESS_IN_URI = re.compile("\:\/\/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*")
DETECTOR_CIDR = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\/\d{1,2}$")
DETECTOR_SHA256 = re.compile("^[A-Fa-f0-9]{64}$")
DETECTOR_MD5 = re.compile("^[A-Fa-f0-9]{32}$")
#DETECTOR_DOMAIN = re.compile("^[a-z0-9]([a-z0-9-]+\.){1,}[a-z0-9]+\Z")
DETECTOR_DOMAIN = re.compile("^(?!\-)(?:[a-zA-Z\d\-]{0,62}[a-zA-Z\d]\.){1,126}(?!\d+)[a-zA-Z\d]{1,63}$")
DETECTOR_EMAIL = re.compile("^[A-Za-z0-9\.\+-]+@[A-Za-z0-9\.-]+\.[a-zA-Z]*$")
DETECTOR_SOURCE = re.compile("^\[[A-Za-z0-9 ]+\].*")

def debug(text):
    global PARSER_DEBUG
    if PARSER_DEBUG:
        sys.stderr.write(str(text))
    return

def autodetectType(IOC):
    global DETECTOR_IPADDRESS
    global DETECTOR_CIDR
    global DETECTOR_SHA256
    global DETECTOR_MD5
    global DETECTOR_DOMAIN
    global DETECTOR_EMAIL
    global DETECTOR_SOURCE
    
    if DETECTOR_IPADDRESS.match(IOC):
        return "ADDR"
    if DETECTOR_CIDR.match(IOC):
        return "CIDR"
    if IOC.lower().startswith("http"):
        return "URL"
    if DETECTOR_DOMAIN.match(IOC):
        return "DOMAIN"
    if DETECTOR_SHA256.match(IOC):
        return "FILE_HASH"
    if DETECTOR_MD5.match(IOC):
        return "FILE_HASH"
    if DETECTOR_EMAIL.match(IOC):
        return "EMAIL"
    return "Unknown"

def get_metadata(id,scope='internal'):
    TargetModel = vdInTarget
    if scope=='external':
        TargetModel = vdTarget
    Query = TargetModel.objects.filter(name=id)
    if Query.exists():
        debug("Found:"+str(Query[0].metadata)+"\n\n")
        return get_metadata_array(Query[0].metadata,scope),Query[0].metadata
    else:
        if scope=='internal':
            return get_metadata(id, 'external')
        METADATA = {'scope':scope, 'owner':'Unknown', 'tag':'new'}
        return METADATA, json.dumps(METADATA)

def delta(info):
    JOURNAL_DIR = "/home/asf/alerts/journal/"
    QUEUE_DIR = "/home/asf/alerts/queue/"
    LOGS_DIR = "/home/asf/alerts/logs/"
    DIRS = [JOURNAL_DIR, QUEUE_DIR, LOGS_DIR]
    ensure_dirs(DIRS)
    #Adding timestamp
    dt = datetime.now()
    info['timestamp']=str(dt.timestamp())
    info['datestamp']=str(dt)
    info['year'] = str(dt.year)
    info['month'] = str(dt.month)
    info['day'] = str(dt.day)
    info['hour'] = str(dt.hour)
    info['minute'] = str(dt.minute)
    info['second'] = str(dt.second)
    #Creating a Hash fom info, this will be the file name in the Journal while it's weitten
    INFO_HASH = hashlib.sha256(str(info).encode('utf-8')).hexdigest()
    FILE_IN_JOURNAL = JOURNAL_DIR+INFO_HASH
    FIN = open(FILE_IN_JOURNAL, "w+")
    json_info=json.dumps(info)
    FIN.write(json_info)
    #Required new line for using basic shell monitor (CAT does not print new lines if not exist)
    FIN.write("\n")
    FIN.close()
    #File is written, now will be moved to queue
    shutil.move(FILE_IN_JOURNAL, QUEUE_DIR+INFO_HASH)
    debug("Created new alert in queue:"+INFO_HASH+":"+str(info)+":"+json_info+"\n")
    return True

def ensure_dirs(DIR_PATHS):
    if type(DIR_PATHS) is not list:
        PATHS = [DIR_PATHS]
    else:
        PATHS = DIR_PATHS
        
    for DIR in PATHS:
        #debug("Ensure existence of this directory: "+str(DIR)+"\n")
        if not os.path.isdir(DIR):
            os.makedirs(DIR)
            
def get_metadata_array(metadata,scope='Untracked'):
    mdt = {}
    if len(metadata)>1:
        mdt = json.loads(metadata)
        if mdt is None:
            mdt = {'owner':'Unknown', 'scope':scope}
    if 'owner' not in mdt:
        mdt['owner']='Unknown'
    if 'scope' not in mdt:
        mdt['scope']=scope
    if 'tag' not in mdt:
        mdt['tag']='new'
    return mdt
