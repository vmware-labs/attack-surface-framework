#!/bin/bash
if test "f$1" "=" "f"
then 
    echo "Error, please specify a JobFolder"
    exit 1
fi
if test "f$2" "=" "f"
then 
    echo "Error, please specify a PidFile to monitor"
    exit 1
fi

cd "$1"
while ls "$2" > /dev/null
do
	sleep 120
	/opt/asf/redteam/eyewitness/extract_pics.sh $1
done