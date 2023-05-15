#!/bin/bash

FILEDIR="$1"
mkdir -p "$FILEDIR"
mkdir -p "$FILEDIR/subprocess_intermediate"
mkdir -p "$FILEDIR/all_status_files"

#Run this python file to get a list of tld domains and their subdomains
python3 /opt/asf/redteam/nowaf/nowaf.py --output "$1" -t
echo "Finished getting domains"

#Get http and https domains along with their status codes
cat "$FILEDIR/tld_domains.txt" | httpx-toolkit -sc -nf > "$FILEDIR/all_urls_with_status.txt"
echo "Finished running the initial httpx scan"

#Run python file to get all status code response
python3 /opt/asf/redteam/nowaf/nowaf.py --output "$1" -p
echo "Completed getting all urls along with their status codes"

#Process 200 responses
python3 /opt/asf/redteam/nowaf/nowaf.py --output "$1" -n
echo "Completed getting all 200 responses"

#Process all 300 responses
python3 /opt/asf/redteam/nowaf/nowaf.py --output "$1" -m
echo "Completed getting all 300 responses"

#Creating final file
python3 /opt/asf/redteam/nowaf/nowaf.py --output "$1" -f
echo "Completed compiling the final file"

#Filter using awk and run nuclei against the domains
awk '{ print (-z $2)?$1:$(NF) }' "$FILEDIR/final_domains.txt" | sort -u | nuclei -duc -json --no-color -t /home/nuclei-templates/technologies/waf-detect.yaml -ms | tee "$FILEDIR/app.report.txt"

##SSL Check
#Run SSL with only https domains
/opt/asf/tools/testssl/testssl.sh -S -oj "$FILEDIR/testssl_out.json" --ip=one --mode parallel --file "$FILEDIR/https_domains.txt"

#Run python to extract testssl results
python3 /opt/asf/redteam/nowaf/nowaf.py --output "$1" -s

#Cleanup
