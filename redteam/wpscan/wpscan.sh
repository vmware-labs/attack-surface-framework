#!/bin/bash
# The main function calls all other functions of the program
function main {
    getKeys
    scanTargets $1 $2
}

# Gets the list of all the tokens to use, returns it in an array
function getKeys {
    IFS=$'\r\n' GLOBIGNORE='*' command eval  'tokens=($(cat /opt/asf/redteam/wpscan/tokens.txt))'
}

# Loops through all the target domains and scans them. Anytime one of the keys runs out of requests, it swaps to the next key
function scanTargets {
    tokenIndex=0
    urlCounter=0
    cat "$1" |
    while read url
    do
        :
        # Checks if the rate limit has been reached, and then swaps to the next token
        echo "**Checking token**"
        rateLimitCheck=$(curl -H "Authorization: Token token=${tokens[$tokenIndex]}" https://wpscan.com/api/v3/wordpresses/494 | grep -o "rate limit hit")
        if [ "$rateLimitCheck" != "" ]; then
            tokenIndex=$((tokenIndex+1))
            echo "**requests depleted, switching tokens**"
        fi
        # Runs WPscan, saves output to a file and displays it in the terminal
        echo "### SCANNING [$url] ###"
	urlCounter=$((urlCounter+1))
        #docker run --rm --tty wpscanteam/wpscan --url $url --disable-tls-checks --random-user-agent --api-token ${tokens[$tokenIndex]}
	wpscan --url $url --disable-tls-checks --random-user-agent --api-token ${tokens[$tokenIndex]} -f json -o "$2/partial.$urlCounter.json"
	. /opt/asf/frontend/asfui/bin/activate
	python3 manage.py parse_tools --parser=wpscan.output --debug --input "$2/partial.$urlCounter.json"
	cat "$2/partial.$urlCounter.json" >> "$2/report.txt"
        echo -e "### END SCANNING [$url] ###\n\n\n"
    done
}

# Initial call of the main function
main $1 $2
