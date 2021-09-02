#!/bin/bash
# Needs to be run in kali linux - not tested on others
# Install Graylog
apt update && apt install -y imagemagick python3-venv psmisc psutils nmap curl wget tcpdump docker.io docker-compose python3-pip
cp -R /opt/asf/tools/graylog /
cd /graylog 
docker-compose up -d
#Start alertmonitor for sending logs to graylog 
nohup /opt/asf/tools/alertmonitor/alertmon.sh &
cd /opt/asf/frontend/asfui
python3 -m venv ./
. bin/activate
pip3 install -r requirements.txt
python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py createsuperuser
echo "Try server with: \
python3 manage.py runserver 0.0.0.0:8080"
