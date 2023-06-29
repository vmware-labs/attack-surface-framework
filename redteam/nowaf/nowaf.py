#!/usr/bin/python3
import requests
import re
import argparse
import json
import logging
import subprocess
import os, os.path
import sys


parent_directory = "/tmp"

TLD_REGEX = re.compile(r'(vmware)|(vmworld)|(workspace)|(ws1)|(wsone)|(air-watch)|(airwatch)|(awmdm)|(salt)|(avinetworks)|(bitnami)|(carbonblack)|(lastline)|(rabbitmq)|(mesh)|(tanzu)|(velocloud)|(wavefront)|(octarine)')
final_chain_name = "subprocess_intermediate/final_chain.txt"

#Update the final file with the data
def update_file(data):
    with open(f"{parent_directory}/{final_chain_name}", 'w') as f:
        f.write("\n".join(str(item) for item in data))

#Search for all TLD Domains
def get_tld_domains(domain):
    result = TLD_REGEX.search(domain)
    return True if result else False

#Process the domains.txt file
def process_tld_domains():
    with open(f'{parent_directory}/app.input') as f:
        domains = f.readlines()
    
    tld_domain_file = open(f"{parent_directory}/tld_domains.txt", "w")

    for domain in domains:
        if get_tld_domains(domain):
            tld_domain_file.write(domain)

    tld_domain_file.close() 

def get_ssl_safe():
    ssl_out = open(f"{parent_directory}/testssl_out_200.json")
    ssl_data = json.load(ssl_out)
    final = open(f"{parent_directory}/ssl_okay.txt","w")
    res = [ {"finding":val['finding'],"host":val["ip"].split("/")[0]} for val in ssl_data if val['id'] == "cert_trust"]
    with open(f"{parent_directory}/missing_ssl.txt","w") as miss:
        for value in res:
            if "Ok via" in value['finding']:
                final.write("https://"+value["host"]+"\n")
                # ssl_okay.append("https://"+value["host"])
            else:
                miss.write("https://"+value["host"]+"\n")
    final.close()
    return True

#Extract 200 responses
def extract_200_responses():
    final = open(f"{parent_directory}/final_domains.txt","w")
    f = open(f"{parent_directory}/all_status_files/200_responses.json")
    data = json.load(f)
    
    for domain in data:
        if "http://" in domain["original_url"]:
            logging.warning(domain["original_url"] + " is unsafe")
        else:
            #Append to the same final file for nuclei
            final.write(domain["original_url"]+"\n")
            # print(domain.strip() + " is safe")
    final.close()

def extract_301_responses():
    file_name = "x_1.txt"
    i = 1
    flag = 0
    count = 0
    source_file = "300_status.txt"

    while True:
        if not os.path.exists(f"{parent_directory}/{final_chain_name}"):
            cmd = f"cat {parent_directory}/{source_file} | /bin/httpx-toolkit -location -sc -maxr 3 -o {parent_directory}/subprocess_intermediate/{file_name}"
            initial_iter = []
        else:
            final_chain_file = open(f"{parent_directory}/{final_chain_name}","r")
            final_chain_data = final_chain_file.read().split("\n")
            final_chain_file.close()
            flag = 1
            cmd = f"cat {parent_directory}/{source_file} | /bin/httpx-toolkit -location -sc -nf > {parent_directory}/subprocess_intermediate/{file_name}"
        result = subprocess.Popen(cmd, shell = True, stdout=subprocess.DEVNULL, stderr = subprocess.DEVNULL)
        x = result.wait()
        if x == 0:
            #If the above command executes succesfully
            with open(f"{parent_directory}/subprocess_intermediate/{file_name}") as f:
                domains = f.readlines()

            i = i+1
            file_name = "x_" + str(i) + ".txt" 
            source_file = f"{parent_directory}/subprocess_intermediate/intermediate.txt"
            intermediate_file = open(f"{source_file}","w")
            for idx, domain in enumerate(domains):
                line = domain.strip().split(" ")
                og = line[0]
                status_code = status_code = line[1].replace("[","").replace("0m]","").replace("\u001b","").replace("31m","").replace("33m","").replace("35m","").replace("32m","")
                inter = line[len(line)-1].replace("[","").replace("0m]","").replace("\u001b","").replace("35m","").replace("33m","").replace("32m","").replace("31m","")
                if "http://" not in inter and "https://" not in inter:
                    inter = line[0] + inter
                
                #Source file exists
                if flag:
                    #Redirection occurs
                    if inter != "":
                        #Final chain file exists
                        for idx in range(len(final_chain_data)):
                            if og in final_chain_data[idx] and inter not in final_chain_data[idx] :
                                temp = final_chain_data[idx] + " " + inter
                                final_chain_data[idx] = temp
                        intermediate_file.write(inter + "\n")
                    #No redirection   
                    else:
                        count += 1
                        intermediate_file.write(og + "\n") 
                #Source File does not exist
                else:
                    #Redirection occurs
                    if inter != "":
                        temp = og + " " + inter
                        initial_iter.append(temp)
                        intermediate_file.write(inter + "\n")
                    #No redirection   
                    else:
                        count += 1
                        initial_iter.append(og)
                        intermediate_file.write(og + "\n")
            
            if not flag:
                update_file(initial_iter)
            else:
                update_file(final_chain_data)

            intermediate_file.close()
            
            #Stop operation if all redirection stops or after specified iterations
            if count == len(domains) or i == 4:
                break 

def process_httpx():
    dict_200 = []
    dict_300 = []
    dict_400 = []
    dict_500 = []
    final_file = open(f"{parent_directory}/final_domains.txt","w")
    https_domains = open(f"{parent_directory}/https_domains.txt","w")
    with open(f"{parent_directory}/all_urls_with_status.txt") as t:
        domains = t.readlines()

    file_300 = open(f"{parent_directory}/300_status.txt","w")
    #Extract status codes and store them in their respective files
    for domain in domains:
        full_url_with_status = domain.strip().split(" ")
        original_url = full_url_with_status[0]
        status_code = full_url_with_status[len(full_url_with_status)-1].replace("[","").replace("0m]","").replace("\u001b","").replace("33m","").replace("32m","").replace("31m","").replace("1;","")
        temp_dict = {
            "original_url" : original_url,
            "status_code" : status_code 
        }
        if "https://" in original_url:
            https_domains.write(original_url + "\n")
        if status_code.startswith("2"):
            final_file.write(original_url + "\n")
            dict_200.append(temp_dict)
        if status_code.startswith("3"):
            dict_300.append(temp_dict)
            file_300.write(original_url + "\n")
        if status_code.startswith("4"):
            dict_400.append(temp_dict)
        if status_code.startswith("5"):
            dict_500.append(temp_dict)

    with open(f"{parent_directory}/all_status_files/200_responses.json", "w") as outfile:
        json.dump(dict_200, outfile, indent=4)
    with open(f"{parent_directory}/all_status_files/300_responses.json", "w") as outfile:
        json.dump(dict_300, outfile, indent=4)
    with open(f"{parent_directory}/all_status_files/400_responses.json", "w") as outfile:
        json.dump(dict_400, outfile, indent=4)
    with open(f"{parent_directory}/all_status_files/500_responses.json", "w") as outfile:
        json.dump(dict_500, outfile, indent=4)

    final_file.close()
    file_300.close()
    https_domains.close()

def final_file():
    final = open(f"{parent_directory}/final_domains.txt","a")
    
    with open(f"{parent_directory}/{final_chain_name}","r") as chain:
        data = chain.readlines()
    
    for domain in data:
        final.write(domain)
    
    final.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='No waf module')
    parser.add_argument('--output', help='The output Directory', default='/tmp')
    parser.add_argument('-t',action='store_true',help='Set this argument to extract tld domains')
    parser.add_argument('-f',action='store_true',help='Set this argument to compile the final file')
    parser.add_argument('-s',action='store_true',help='Set this argument to extract safe websites from the ssltest.sh')
    parser.add_argument('-n',action='store_true',help='Set this argument to extract 200 responses')
    parser.add_argument('-m',action='store_true',help='Set this argument to extract 301 responses')
    parser.add_argument('-p',action='store_true',help='Set this argument to process httpx results')
    args = parser.parse_args()
    parent_directory = args.output
    if args.t:
        process_tld_domains()
    if args.f:
        final_file()
    if args.s:
        get_ssl_safe()
    if args.n:
        extract_200_responses()
    if args.m:
        extract_301_responses()
    if args.p:
        process_httpx()
    
        
