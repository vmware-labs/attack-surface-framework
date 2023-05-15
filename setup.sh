#!/bin/bash
# Needs to be run in kali linux - not tested on others
# Install Graylog
apt update && apt install -y imagemagick python3-venv psmisc psutils nmap curl wget tcpdump docker.io docker-compose python3-pip golang ca-certificates apt-transport-https
git clone https://github.com/projectdiscovery/nuclei-templates.git /home/nuclei-templates
cp -R /opt/asf/tools/graylog /
cd /graylog 
docker-compose up -d
find /opt/asf/redteam /opt/asf/tools -name stop -or  -name start -or -iname '*.sh' | xargs -d$'\n'  chmod +x
#Start alertmonitor for sending logs to graylog
chmod +x /opt/asf/tools/alertmonitor/*.sh 
nohup /opt/asf/tools/alertmonitor/alertmon.sh &
cd /opt/asf/frontend/asfui
python3 -m venv ./
. bin/activate
pip3 install -r requirements.txt
python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py createsuperuser

# Kubernetes config setup
KUBE_VARS_FILE=/.kube_vars

if [ -f "$KUBE_VARS_FILE" ]
then
	# Load varibale KUBE_FLAG from kube_vars
    	. $KUBE_VARS_FILE
else
	# set default as false
	KUBE_FLAG=FALSE
	echo 'KUBE_FLAG=FALSE' > $KUBE_VARS_FILE
fi

echo "Would you like to use kubernetes cluster (y/n)?"
read kube_enable

if [ $kube_enable = "y" ]
then
	curl -fsSLo /usr/share/keyrings/kubernetes-archive-keyring.gpg https://packages.cloud.google.com/apt/doc/apt-key.gpg
	echo "deb [signed-by=/usr/share/keyrings/kubernetes-archive-keyring.gpg] https://apt.kubernetes.io/ kubernetes-xenial main" | sudo tee /etc/apt/sources.list.d/kubernetes.list
	apt-get update
	apt-get install -y kubectl
	sed -i "s/KUBE_FLAG=$KUBE_FLAG/KUBE_FLAG=TRUE/g" $KUBE_VARS_FILE
elif [ $kube_enable = "n" ]
then
	sed -i "s/KUBE_FLAG=$KUBE_FLAG/KUBE_FLAG=FALSE/g" $KUBE_VARS_FILE
fi

#Newest version of subfinder
#Other tools
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
cp -v /root/go/bin/subfinder /bin/subfinder
#Systemd service files installation
cd /opt/asf/tools/systemd/
for file in *
do
	cp -v "$file" "/etc/systemd/system/$file" 
done
apt install -y nginx
rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default
cp -v /opt/asf/tools/nginx/sites-enabled/asf /etc/nginx/sites-enabled/
ln -s ../sites-enabled/asf /etc/nginx/sites-available/asf
chmod +x /opt/asf/tools/scripts/startasf.sh
ln -s /opt/asf/tools/scripts/startasf.sh /bin/
systemctl daemon-reload
systemctl start asf
systemctl enable asf
systemctl enable projectdiscovery.timer
systemctl start projectdiscovery.timer
systemctl enable cleanuptrash.timer
systemctl start cleanuptrash.timer
systemctl restart nginx
systemctl enable nginx
echo "Try server with: \
python3 manage.py runserver 0.0.0.0:8080 \
or use nginx in port 2021"
