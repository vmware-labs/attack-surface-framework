#!/usr/bin/python3
import sys
import json
import os.path
import subprocess
import os

#from app.views import debug

DaysOfWeek = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
MainDictionaries = ['Unit', 'Timer', 'Service', 'Install']
class sdService():
    def __init__(self, setup = {}):
        global MainDictionaries
        self.config = {}
        
        if type(setup) is not dict:
            sys.stderr.write("Error, received non dictionary variable:"+str(setup))
        else:
            self.config = setup
            
        for Dictionary in MainDictionaries:
            if Dictionary not in self.config:
                self.config[Dictionary] = {} 

        if 'name' not in self.config:
            self.config['name'] = "vddefault"

    def __str__(self):
        return str(self.config)

    def readTimerFromRequest(self, request):
        global DaysOfWeek
        Days = ""
        Hour = "00"
        Minute = "00"
        Repeat = "00"
        FirstDay = True
        ADays = []
        for Day in DaysOfWeek:
            if Day in request.POST:
                ADays.append(Day)
                if FirstDay:
                    Days = Day
                    FirstDay = False
                else:
                    Days = Days+","+Day
        if 'Disabled' in request.POST:
            #String true
            self.config['Disabled'] = 'true'
        else:
            #string false, not boolean
            self.config['Disabled'] = 'false'
            
        if 'hour' in request.POST:
            Hour = request.POST['hour']
            if len(Hour) < 2:
                Hour = '0'+Hour
            
        if 'minute' in request.POST:
            Minute = request.POST['minute']
            if len(Minute) < 2:
                Minute = '0'+Minute

        if 'repeat' in request.POST:
            Repeat = request.POST['repeat']
            if len(Repeat) < 2:
                Repeat = '0'+Repeat
        OnCalendarRepeat=""
        if Repeat != "00":
            OnCalendarRepeat="/"+Repeat+":00"
        
        self.config['Hour'] = Hour
        self.config['Minute'] = Minute
        self.config['Repeat'] = Repeat
        self.config['Days'] = ADays
        self.config['Timer']['OnCalendar'] = Days+" "+Hour+":"+Minute+OnCalendarRepeat

    def write(self):
        global MainDictionaries
        if "Unit" not in self.config['Timer']:
            self.config['Timer']['Unit']=self.config['name']+".service"
        if "WantedBy" not in self.config['Install']:
            self.config['Install']['WantedBy'] = "multi-user.target"
        #Writing the Service File, we ignore Timer, because of the scope, and Install, because the Timer will be installable.
        ServiceFile=open("/etc/systemd/system/"+self.config['name']+".service",'w+')
        for Section in MainDictionaries:
            if Section != 'Timer' and Section != 'Install':
                ServiceFile.write("["+Section+"]\n")
                for Param in self.config[Section]:
                    ServiceFile.write(Param+"="+self.config[Section][Param]+"\n")
                ServiceFile.write("\n")
        ServiceFile.close()
        
        #Writing the Timer Service Unit File, does not require Service Section
        ServiceFile=open("/etc/systemd/system/"+self.config['name']+".timer",'w+')
        for Section in MainDictionaries:
            if Section != 'Service':
                ServiceFile.write("["+Section+"]\n")
                for Param in self.config[Section]:
                    ServiceFile.write(Param+"="+self.config[Section][Param]+"\n")
                ServiceFile.write("\n")

        #Write the whole configuration for further usage
        ServiceFile=open("/etc/systemd/system/"+self.config['name']+".asfui",'w+')
        json_info = json.dumps(self.config)
        ServiceFile.write(json_info)
        ServiceFile.close()
        if self.config['Disabled'] == 'true':
            sys.stderr.write("Disabling the system service timer")
            self.disable()
            self.stop()
        else:
            self.reload()

    def read(self):
        FileName = "/etc/systemd/system/"+self.config['name']+".asfui"
        if os.path.isfile(FileName):
            ServiceFile=open(FileName,'r')
            json_info = ServiceFile.read()
            self.config = json.loads(json_info)
            ServiceFile.close()
            #The following Fix is only for upgrade from older systemd timers.
            if 'Repeat' not in self.config:
                self.config['Repeat'] = '00'
            return True
        self.config['Hour'] = '00'
        self.config['Minute'] = '00'
        self.config['Repeat'] = '00'
        self.config['Days'] = []
        self.config['Disabled'] = 'true'
        return False
    
    def remove(self):
        FileName = "/etc/systemd/system/"+self.config['name']
        Extensions = ['asfui', 'service', 'timer']
        for Extension in Extensions:
            FN = FileName+"."+Extension
            if os.path.isfile(FN):
                os.remove(FN)

    def execute(self, cmdarray):
        sys.stderr.write("\nExcecuting command"+str(cmdarray)+"\n")
        subprocess.Popen(cmdarray)
        
    def enable(self):
        self.execute(["systemctl", "stop", self.config['name']+".timer"])

    def disable(self):
        self.execute(["systemctl", "disable", self.config['name']+".timer"])

    def start(self):
        self.execute(["systemctl", "start", self.config['name']+".timer"])

    def stop(self):
        self.execute(["systemctl", "stop", self.config['name']+".timer"])
        
    def reload(self):
        self.stop()
        self.execute(["systemctl", "daemon-reload"])
        self.start()
        
    def setContext(self, context):
        #Django Template compares integers, because of the for counter, it has to be converted (hour, minute) to int
        context['Hour'] = int(self.config['Hour'])
        context['Minute'] = int(self.config['Minute'])
        context['Repeat'] = int(self.config['Repeat'])
        context['Days'] = self.config['Days']
        context['DaysOfWeek'] = DaysOfWeek
        context['Disabled'] = self.config['Disabled']