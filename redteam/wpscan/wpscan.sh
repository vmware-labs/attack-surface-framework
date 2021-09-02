#!/bin/bash
cat "$1" |
while read url
do 
echo "### SCANNING [$url] ###"
docker run --rm --tty wpscanteam/wpscan --url "$url"
echo -e "### END SCANNING [$url] ###\n\n\n"
done