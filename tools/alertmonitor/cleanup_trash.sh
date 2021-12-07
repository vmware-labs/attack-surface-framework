#!/bin/bash
cd /var/log/
for logtype in daemon.log syslog
do
    rm -v $logtype.*
    > $logtype
done
cd /home/asf/alerts/trash
export FILTER=`date | awk '{print $2" "$3}'`
ls -lsh | grep -v "$FILTER" | awk '{print $10}' |
        while read hash;
        do rm -v "$hash"
        done