#!/usr/bin/python3
import csv
import sys

def subdomain(DARRAY, DOMAIN):
    if DOMAIN.count(".")>1:
        DPARTS = DOMAIN.split(".")
        PDOM = ""
        PC = 0
        for PART in DPARTS[::-1]:
            if PC==0:
                PC +=1
                PDOM = PART
                continue
            if PC==1:
                PC +=1
                PDOM = PART+"."+PDOM
                if PDOM not in DARRAY:
                    DARRAY.append(PDOM)
                    sys.stderr.write("Extra Domain: "+PDOM+"\n")
                continue 
            if PC>1:
                #If there are more than 3 dots, skip to the next row
                if PDOM.count(".")>2:
                    break
                PDOM = PART+"."+PDOM
                if PDOM not in DARRAY:
                    DARRAY.append(PDOM)
                    sys.stderr.write("Extra Domain: "+PDOM+"\n")
    return
File = open("./services.tsv",'r')
VDReader = csv.reader(File, delimiter="\t")
DNAME = []
IPADDR = []
SERVICES = []
NUCLEI = []
firstignore = True
for row in VDReader:
    sys.stderr.write(str(row)+"\n")
    if firstignore:
        firstignore = False
        sys.stderr.write("Ignoring First Row as being titles\n")
        continue 
    #0=Domain Requested
    if not row[0] in DNAME:
        DNAME.append(row[0])
        subdomain(DNAME,row[0])
    #1=Domain Redirected to (CNAME)
    if row[1] not in DNAME:
        DNAME.append(row[1])
        subdomain(DNAME,row[1])
    #2=IP Address
    if row[2] not in IPADDR:
        IPADDR.append(row[2])
    #5=Full List of Ports
    PSERVICES = row[5].split(", ")
    for PSERVICE in PSERVICES:
        if PSERVICE not in SERVICES:
            SERVICES.append(PSERVICE)
            sys.stderr.write("New Service Found:"+PSERVICE+"\n")
    #11=Nuclei
    if not row[11].strip() == "":
        NLINES = row[11].split("\n")
        for NLINE in NLINES:
            if NLINE not in NUCLEI:
                NUCLEI.append(NLINE)
                  
sys.stderr.write(str(DNAME)+"\n")
sys.stderr.write(str(IPADDR)+"\n")
sys.stderr.write(str(SERVICES)+"\n")
sys.stderr.write(str(NUCLEI)+"\n")

for item in DNAME:
    sys.stdout.write("CREATE (:DOMAIN {name:\""+item+"\"});\n")
for item in IPADDR:
    sys.stdout.write("CREATE (:IPADDR {ip:\""+item+"\"});\n")
for item in SERVICES:
    sys.stdout.write("CREATE (:SERVICE {psh:\""+item+"\"});\n")
for item in NUCLEI:
    sys.stdout.write("CREATE (:NUCLEI {info:\""+item+"\"});\n")

#The following line rewinds the file for the new reading
File.seek(0)
#Reopen the file to create relationships
for row in VDReader:
    sys.stderr.write(str(row)+"\n")
    if firstignore:
        firstignore = False
        sys.stderr.write("Ignoring First Row as being titles\n")
        continue
    if row[1].strip() == "":
        #1=CNAME, empty means no redirection, using only 0
        #2=Ipaddr
        sys.stdout.write("MATCH (d:DOMAIN {name:\""+row[0]+"\"}) MATCH (i:IPADDR {ip: \""+row[2]+"\"}) CREATE (d)-[:RESOLVE]->(i);\n")
    else:
        #1=CNAME, not empty means redirection, using 1 and 0->1
        #2=Ipaddr
        sys.stdout.write("MATCH (d:DOMAIN {name:\""+row[1]+"\"}) MATCH (i:IPADDR {ip: \""+row[2]+"\"}) CREATE (d)-[:RESOLVE]->(i);\n")
        sys.stdout.write("MATCH (d:DOMAIN {name:\""+row[0]+"\"}) MATCH (c:DOMAIN {name: \""+row[1]+"\"}) CREATE (d)-[:REDIRECTS]->(c);\n")
    
    #11=Nuclei
    if not row[11].strip() == "":
        NLINES = row[11].split("\n")
        for NLINE in NLINES:
            sys.stdout.write("MATCH (d:IPADDR {ip:\""+row[2]+"\"}) MATCH (n:NUCLEI {info: \""+NLINE+"\"}) CREATE (d)-[:HAS]->(n);\n")
    #5=Ipaddr
    PSERVICES = row[5].split(", ")
    for PSERVICE in PSERVICES:
        sys.stdout.write("MATCH (i:IPADDR {ip:\""+row[2]+"\"}) MATCH (s:SERVICE {psh: \""+PSERVICE+"\"}) CREATE (i)-[:PROVIDES]->(s);\n")