#!/bin/bash
if test "f$1" "=" "f"
then 
    echo "Error, please specify a JobFolder"
    exit 1
fi
cd "$1"
STATIC="/home/asf/hosts"
cat app.asf | awk '{print $2}' |
while read domain
do 
	if ls results/screens/http*${domain}*.png 2>/dev/null
	then
		mkdir -p "$STATIC/$domain"
		ln -sfv  $1/results/screens/http*${domain}*.png "$STATIC/$domain/" 
	fi
done