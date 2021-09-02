#!/bin/bash
OUTPUT_FOLDER="/home/nmap.int/reports"
INPUT_FOLDER="/home/nmap.int"
cd /opt/asf/frontend/asfui
. bin/activate
python3 manage.py nmap_input --input intargets --output "$INPUT_FOLDER/targets.txt"
if ! test -e "$INPUT_FOLDER/targets.txt"
then 
	echo "No input bro"
	exit 1
fi
mkdir -p "$OUTPUT_FOLDER"
> "$OUTPUT_FOLDER/nmap.lock"

#This line is for override and debug
#echo yahoo.com > "$INPUT_FOLDER/targets.txt"
#echo scanme.nmap.org > "$INPUT_FOLDER/targets.txt"
#echo 192.168.11.102 >> "$INPUT_FOLDER/targets.txt"
#echo 192.168.11.77 >> "$INPUT_FOLDER/targets.txt"
#echo 192.168.11.116 >> "$INPUT_FOLDER/targets.txt"
#echo 192.168.1.254 >> "$INPUT_FOLDER/targets.txt"
#echo 127.0.0.1 >> "$INPUT_FOLDER/targets.txt"

SNGHOSTS="127.0.0.1"
BLACKLST="10.206.96.68"
LOGDIR="/netlog/var/log/madnmap.int/"
WORKERS="64"
TIMEOUT="360s"
ABORTTM="480s"
WPIDS=""
DELTAD=`date +%Y%m%d%H%M%S`

mkdir -p "$LOGDIR/$DELTAD"
mkdir -p "/tmp/$DELTAD.madnmap.int"
mkdir -p "$OUTPUT_FOLDER/$DELTAD"
#Worker provisioning
for WORKER in `seq 1 $WORKERS`
    do
    WFILE="/tmp/$DELTAD.madnmap.int/worker_$WORKER.sh"
    echo "#!/bin/bash">$WFILE
    chmod +x $WFILE
done
WORKER=1
JOBID=1
sort -u "$INPUT_FOLDER/targets.txt" -o "$INPUT_FOLDER/targets.txt.unique"
cat "$INPUT_FOLDER/targets.txt.unique" | while read H
    do 
    WFILE="/tmp/$DELTAD.madnmap.int/worker_$WORKER.sh"
    #echo "echo Scanning host $H Thread:$WORKER; timeout -k $ABORTTM $TIMEOUT nmap -p- -Pn -T4 --open --reason -oA $OUTPUT_FOLDER/$DELTAD/Worker_$WORKER.$JOBID.txt -sC $H >> $OUTPUT_FOLDER/$DELTAD/Worker_$WORKER.log" >> "$WFILE"
    echo "echo Scanning host $H Thread:$WORKER; timeout -k $ABORTTM $TIMEOUT nmap --top-ports 200 -sC -sV -Pn -T4 --open --reason -oA $OUTPUT_FOLDER/$DELTAD/Worker_$WORKER.$JOBID.txt -sC $H >> $OUTPUT_FOLDER/$DELTAD/Worker_$WORKER.log" >> "$WFILE"
    echo "cd /opt/asf/frontend/asfui" >> "$WFILE"
    echo ". bin/activate" >> "$WFILE"
	echo "python3 manage.py nmapparse --input $OUTPUT_FOLDER/$DELTAD/Worker_$WORKER.$JOBID.txt --host $H --destination internal" >> "$WFILE"
    if test "$WORKER" -ge "$WORKERS"
	then WORKER=1
	else WORKER=$[$WORKER+1]
    fi
    JOBID=$[$JOBID+1]
done
#Lanzando workers
for WORKER in `seq 1 $WORKERS`
    do
    WFILE="/tmp/$DELTAD.madnmap.int/worker_$WORKER.sh"
    $WFILE &
    #Collect PIDs of Nmap process
    WPID="$WPID $!"
done
#In case we cancel or terminate, this process kills all subprocess before exit
	#Warning: Do not use variables with rm, in case of a mistake it could lead into a fatal deletion - hardcode paths.
trap "kill -SIGTERM $WPID" SIGTERM
while sleep 60 
    do 
    WLEFT=`ps -Af | grep -v grep | grep "/tmp/$DELTAD.madnmap.int/worker" | wc -l`
	echo "Launched $WORKERS Threads, awaiting to finish $WLEFT";
    if test "$WLEFT" "=" "0"
	then
		echo "No more Hosts, Finished"
		rm -fv "/home/nmap.int/reports/nmap.lock"
		break
	else sleep 60
    fi
    sleep 60
done
echo "Finished"
#rm -fv "/home/nmap.int/reports/nmap.lock"
#exit 0
#UnComment for production
#trap
#rm -rf "/tmp/$DELTAD.madnmap.int/"
