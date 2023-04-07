#!/bin/bash
# Needs to be run in kali linux - not tested on others
# Install Graylog
apt update && apt install -y imagemagick python3-venv psmisc psutils nmap curl wget tcpdump docker.io docker-compose python3-pip
git clone https://github.com/projectdiscovery/nuclei-templates.git /home/nuclei-templates
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

#Systemd service files installation
cd /opt/asf/tools/systemd/
for file in *
do
	cp -v "$file" "/etc/systemd/system/$file" 
done
apt install -y nginx
rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default
cp -v /opt/asf/tools/nginx/sites-enabled/asf /etc/nginx/sites-enabled/
ln -s ../sites-enabled/asfopt/asf /etc/nginx/sites-available/asf
ln -s /opt/asf/tools/scripts/startasf.sh /bin/
#Other tools
apt install -y golang
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
if ! cp /root/go/bin/subfinder /bin/subfinder
then 
    cp -v /opt/asf/tools/subfinder/subfinder /bin/subfinder
fi

systemctl daemon-reload
systemctl start asf
systemctl enable asf
systemctl start projectdiscovery
systemctl enable projectdiscovery.timer
systemctl start projectdiscovery.timer
systemctl enable cleanuptrash.timer
systemctl start cleanuptrash.timer
systemctl restart nginx
echo "Try server with: \
python3 manage.py runserver 0.0.0.0:8080"
