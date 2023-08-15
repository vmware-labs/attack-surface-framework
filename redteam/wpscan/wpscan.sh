#!/bin/bash
cat "$1" |
while read url
do 
echo "### SCANNING [$url] ###"
#docker run --rm wpscanteam/wpscan --url "$url" -f json
docker run --rm wpscanteam/wpscan --url "$url" -f json | tee $3/singlereport.json
cd /opt/asf/frontend/asfui
. bin/activate
python3 /opt/asf/frontend/asfui/manage.py remaster_output --parser=wpscan.json --debug --input="$3/singlereport.json" --output=JobID:$2
echo -e "### END SCANNING [$url] ###\n\n\n"
done