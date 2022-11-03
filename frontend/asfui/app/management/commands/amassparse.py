#!/usr/bin/python3
from django.core.management.base import BaseCommand, CommandError
from app.models import vdResult
from django.utils import timezone
import re
from cProfile import label
from app.tools import autodetectType, delta, debug, PARSER_DEBUG, get_metadata
import traceback

class Command(BaseCommand):
    help = 'Amass interpreter'

    def handle(self, *args, **kwargs):
#         DETECTOR_IPADDRESS = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
#         DETECTOR_SHA256 = re.compile("^[A-Fa-f0-9]{64}$")
#         DETECTOR_MD5 = re.compile("^[A-Fa-f0-9]{32}$")
#         #DETECTOR_DOMAIN = re.compile("^[a-z0-9]([a-z0-9-]+\.){1,}[a-z0-9]+\Z")
#         DETECTOR_DOMAIN = re.compile("^(?!\-)(?:[a-zA-Z\d\-]{0,62}[a-zA-Z\d]\.){1,126}(?!\d+)[a-zA-Z\d]{1,63}$")
#         DETECTOR_EMAIL = re.compile("^[A-Za-z0-9\.\+-]+@[A-Za-z0-9\.-]+\.[a-zA-Z]*$")
        DETECTOR_SOURCE = re.compile("^\[[A-Za-z0-9 ]+\].*")
        AMASS_SEPARATOR_TAG = re.compile("\]\s+")
        AMASS_SEPARATOR = re.compile("\s+")
                
        last_report="/home/amass/reports/amass-latest.txt"
        report=open(last_report,'r')
        lines=0
        for line in report:
            #time = timezone.now().strftime('%X')
            #self.stdout.write("It's now %s" % time)
            if DETECTOR_SOURCE.match(line):
                self.stdout.write("Process"+line)
                Finding = AMASS_SEPARATOR_TAG.split(line)
                Tag = Finding[0] + "]"
                line = Finding[1]
                Finding = AMASS_SEPARATOR.split(line)
                MDT,MDATA=get_metadata(Finding[0])
                Result = vdResult(name=Finding[0], tag=Tag, info=Finding[1], type=autodetectType(Finding[0]), owner=MDT['owner'], metadata=MDATA)
                NewData = True
                
                try:
                    Result.save()
                    self.stdout.write("New Finding:"+Finding[0]+str(Result))
                except Exception as e:
                    debug(str(e)+"\n")
                    NewData = False
                    self.stdout.write("Finding Already exist:"+Finding[0])
                if not NewData:
                    #Think wise, do you really want to know domains who are not in the results now?
                    #or do you think if a domain will appear again it will have different data?
                    self.stdout.write("Searching:"+Finding[0])
                    OldData = vdResult.objects.filter(name=Finding[0])
                    self.stdout.write("Found and Updating:"+str(OldData[0].id)+":"+Tag+":"+Finding[1])
                    OldData.update(info = Finding[1], tag = Tag)
                else:
                    MSG=Result.getList()
                    MSG.update(MDT)
                    MSG['message']="[AMASS][New Domain Found]"
                    MSG['full_message']=line
                    self.stdout.write("Finding and Called Delta:"+Finding[0]+str(MSG))
                    delta(MSG)
                     
            self.stdout.write(line)
            lines +=1
        self.stdout.write("Done printing")