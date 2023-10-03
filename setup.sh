#!/bin/bash
# Needs to be run in kali linux - not tested on others
# Install Graylog
apt update && apt install -y imagemagick python3-venv psmisc psutils xmlsec1 nmap curl wget tcpdump docker.io docker-compose python3-pip ca-certificates apt-transport-https
git clone https://github.com/projectdiscovery/nuclei-templates.git /home/nuclei-templates
#cp -R /opt/asf/tools/graylog /
#cd /graylog 
#docker-compose up -d
mkdir -p /opt/asf/frontend/asfui/logs # create logs directory
#Start alertmonitor for sending logs to graylog
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

#Systemd service files installation
cd /opt/asf/tools/systemd/
for file in *
do
	cp -v "$file" "/etc/systemd/system/$file" 
done

echo "Would you like to create a local MongoDB container for storing issues (y/n/d)?" 
read localdb

if [ $localdb == "y" ]
then 
	echo "This will run a local MongoDB container"
	echo "Username for MongoDB:" 
	read mdb_user
	echo "MONGO_USER=$mdb_user" | tee -a .env.prod
	echo "Password:" 
	read -s mdb_pass
	echo "MONGO_USER=$mdb_pass" | tee -a .env.prod
	sudo docker run -dp 27017:27017 -v local-mongo:/data/db --name local-mongo --restart=always -e MONGO_INITDB_ROOT_USERNAME=$mdb_user -e MONGO_INITDB_ROOT_PASSWORD=$mdb_pass mongo 



elif [ $localdb == "n" ]
then
	echo "MongoDB Host:" 
	read mdb_url
	echo "MONGO_URL=$mdb_url" | tee -a .env.prod
	echo "MongoDB Port:" 
	read mdb_port
	echo "MONGO_URL=$mdb_port" | tee -a .env.prod
	echo "Username for DB"
	read mdb_user
	echo "MONGO_USER=$mdb_user" | tee -a .env.prod
	echo "Password:" 
	read -s mdb_pass
	echo "MONGO_USER=$mdb_pass" | tee -a .env.prod

elif [ $localdb == "d" ]
then
	echo "Going with default settings make sure to enter details in the .env.prod file. If you have not done so, please exit and do before running setup again." 
fi



apt install -y nginx
rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default
cp -v /opt/asf/tools/nginx/sites-enabled/asf /etc/nginx/sites-enabled/
ln -s ../sites-enabled/asfopt/asf /etc/nginx/sites-available/asf
ln -s /opt/asf/tools/scripts/startasf.sh /bin/
systemctl daemon-reload
systemctl start asf
systemctl enable asf
systemctl enable cleanuptrash.timer
systemctl start cleanuptrash.timer
systemctl restart nginx

# Running systemctl restart ASF service to apply and reflect any changes made during the setup (via setup.sh) in the running instance.
# This step ensures that all configurations, updates, or modifications performed are loaded and utilized by ASF in real-time.
systemctl restart asf
echo "A.S.F. Running on: \
http://127.0.0.1:2021"
