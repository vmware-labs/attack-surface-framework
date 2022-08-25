#!/bin/bash

DSTAMP=$(date '+%Y%m%d%H%M')
IMAGE="caffix/amass"
IMAGE="m4ch1n3s/amass"
OUTPUT_DIR_PATH="/home/amass"
WDIR=`pwd`
if test -e "/home/amass/reports/amass.txt"
	then echo "Already running"
		exit 1
fi	

#docker pull $IMAGE
	mkdir -p /home/amass/reports
	#docker run -v $OUTPUT_DIR_PATH:/.config/amass/ $IMAGE enum -brute -w /wordlists/all.txt -d example.com
	echo "Executing.."

#Linking current report for partial load
	rm /home/amass/reports/amass-latest.txt
	ln -s /home/amass/reports/amass.txt /home/amass/reports/amass-latest.txt
#Lock
#echo "yahoo.com" > $OUTPUT_DIR_PATH/targets.txt
echo docker run -v $OUTPUT_DIR_PATH:/.config/amass/ $IMAGE enum -brute -ip -src -df /.config/amass/targets.txt $1 $2 $3 $4 $5
if  docker run -v $OUTPUT_DIR_PATH:/.config/amass/ $IMAGE enum -brute -ip -src -df /.config/amass/targets.txt $1 $2 $3 $4 $5 2>&1 | tee /home/amass/reports/amass.txt
	then echo done
	mv -v /home/amass/reports/amass.txt /home/amass/reports/amass-$1-$DSTAMP.txt
	rm /home/amass/reports/amass-latest.txt
	ln -s /home/amass/reports/amass-$1-$DSTAMP.txt /home/amass/reports/amass-latest.txt
	cd /opt/asf/frontend/asfui/
	. bin/activate
	python3 manage.py amassparse
else
	echo "Error running Amass from docker, please check"
	exit 1
fi
cd "$WDIR"
