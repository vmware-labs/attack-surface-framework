#!/bin/bash
cd /home/asf/alerts/
mkdir -p journal logs queue trash
while sleep 2
do 
	for file in ./queue/*
	do
		if test -e "$file"
		then 
			cat "$file" >> ./logs/alerts.log
			mv -v "$file" ./trash/
		fi
	done
done