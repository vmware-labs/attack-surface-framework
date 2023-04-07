#!/bin/bash
# This script has been Replaced by cent https://github.com/xm1k3/cent  - check the systemd timer for the new command that runs
if ! test -e /opt/nuclei-templates/
    then
    git clone https://github.com/projectdiscovery/nuclei-templates.git /opt/nuclei-templates/
    
else
    cd /opt/nuclei-templates/
    git pull
fi
rsync -av --exclude .nuclei-ignore /opt/nuclei-templates/ /home/nuclei-templates/