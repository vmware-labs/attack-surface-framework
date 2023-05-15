#!/usr/bin/python3
import csv
import sys
import ipaddress

FINPUT="input.txt"
FOUTPUT="output.txt"

if len(sys.argv) < 2:
    print("usage: "+sys.argv[0]+" input.list [output.list]")
    sys.exit()

FINPUT = open(sys.argv[1],"r")
if len(sys.argv) >= 3:
    FOUTPUT = open(sys.argv[2],"+w")
else:
    FOUTPUT = sys.stdout

for line in FINPUT:
    sys.stderr.write(line)
    CIDR=line.rstrip()
    for ip in ipaddress.IPv4Network(CIDR):
        FOUTPUT.write(str(ip)+"\n")