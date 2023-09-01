#!/bin/zsh
function debugsub {
    DATESTAMP=$(date '+%Y%m%d%H%M%S')
    echo -e "${DATESTAMP}\t $1 $2 $3 $4 $5" >> /var/log/subfinder.log
}

DSTAMP=$(date '+%Y%m%d%H%M')
IMAGE="projectdiscovery/subfinder"
OUTPUT_DIR_PATH="/home/discovery"
WDIR=`pwd`
mkdir -p "${OUTPUT_DIR_PATH}/reports"
mkdir -p "${OUTPUT_DIR_PATH}/history"
debugsub "Created folders and Time Stamp"
if test -e "${OUTPUT_DIR_PATH}/.lock"
	then echo "Already running"
		debugsub "Quitting because already running"
		exit 1
fi
debugsub "Creating lock file"
echo > "${OUTPUT_DIR_PATH}/.lock"
debugsub "Extracting from system app.input using parse_tools"
cd /opt/asf/frontend/asfui/
. bin/activate
python3 manage.py parse_tools --parser=subfinder.input --output="${OUTPUT_DIR_PATH}/history/${DSTAMP}_targets.txt"
rm -v "${OUTPUT_DIR_PATH}/targets.txt"
ln -s "${OUTPUT_DIR_PATH}/history/${DSTAMP}_targets.txt" "${OUTPUT_DIR_PATH}/targets.txt"
docker pull $IMAGE:latest
echo "Executing.."
#Lock
debugsub "Running subfinder"
#echo "subfinder -dL ${OUTPUT_DIR_PATH}/targets.txt -all -cs -oJ -o ${OUTPUT_DIR_PATH}/report.txt 2>&1 | tee -a ${OUTPUT_DIR_PATH}/history/${DSTAMP}_discovery.log | grep -e \"^{\" | python3 manage.py parse_tools --parser=subfinder.output --input=stdin 2>&1 | tee -a ${OUTPUT_DIR_PATH}/history/${DSTAMP}_run.log"
#if HOME=/root subfinder -dL ${OUTPUT_DIR_PATH}/targets.txt -all -cs -oJ -o ${OUTPUT_DIR_PATH}/report.txt 2>&1 | tee -a ${OUTPUT_DIR_PATH}/history/${DSTAMP}_discovery.log | grep -e "^{" | python3 manage.py parse_tools --parser=subfinder.output --input=stdin 2>&1 | tee -a ${OUTPUT_DIR_PATH}/history/${DSTAMP}_run.log
# runnning subfinder through docker now instead of standalone
echo "docker run -v ${OUTPUT_DIR_PATH}/:/${OUTPUT_DIR_PATH}/ -t projectdiscovery/subfinder -dL ${OUTPUT_DIR_PATH}/targets.txt -all -cs -oJ -o ${OUTPUT_DIR_PATH}/report.txt 2>&1 | tee -a ${OUTPUT_DIR_PATH}/history/${DSTAMP}_discovery.log | grep -e \"^{\" | python3 manage.py parse_tools --parser=subfinder.output --input=stdin 2>&1 | tee -a ${OUTPUT_DIR_PATH}/history/${DSTAMP}_run.log"
if HOME=/root docker run -v ${OUTPUT_DIR_PATH}/:/${OUTPUT_DIR_PATH}/ -t projectdiscovery/subfinder -dL ${OUTPUT_DIR_PATH}/targets.txt -all -cs -oJ -o ${OUTPUT_DIR_PATH}/report.txt 2>&1| tee -a ${OUTPUT_DIR_PATH}/history/${DSTAMP}_discovery.log | grep -e "^{" | python3 manage.py parse_tools --parser=subfinder.output --input=stdin 2>&1 | tee -a ${OUTPUT_DIR_PATH}/history/${DSTAMP}_run.log
then 
	echo "done"
	debugsub "Success running"
	rm -v "${OUTPUT_DIR_PATH}/.lock"
else
	echo "Error running subfinder from docker, please check"
	debugsub "Subfinder error while running"
	rm -v "${OUTPUT_DIR_PATH}/.lock"
	exit 1
fi
cd "$WDIR"