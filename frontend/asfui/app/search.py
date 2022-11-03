#!/usr/bin/python
import re
from app.models import *
from app.tools import *

def search(RegExp, Model_NAME, ExcludeRegExp = ""):
    sys.stderr.write("Starting search function for module:"+Model_NAME+" with Regexp:"+RegExp+" Excluding:"+ExcludeRegExp+"\n")
    def merge_results(partial, results):
        #sys.stderr.write("[SEARCH]: merging hosts from query\n")
#         partial = partial.values_list()
#         results.append(partial)
#        results.union(partial)
        results = results | partial
        #sys.stderr.write("[APPEND]:"+str(results)+"\n")
#         for host in partial:
#             if host not in results:
#                 sys.stderr.write("[APPEND]:"+str(host)+"\n")
#                 results.append(host)
        return results
    
    def search_services(RegExp, ExcludeRegExp):
        sys.stderr.write("[SEARCH]: Searching in any host services\n")
        results = vdServices.objects.none()
        partial = vdServices.objects.filter(info__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(info__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdServices.objects.filter(service_ssh__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(service_ssh__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdServices.objects.filter(service_rdp__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(service_rdp__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdServices.objects.filter(service_ftp__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(service_ftp__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdServices.objects.filter(service_smb__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(service_smb__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdServices.objects.filter(service_telnet__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(service_telnet__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdServices.objects.filter(nuclei_http__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(nuclei_http__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdServices.objects.filter(owner=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(owner=ExcludeRegExp)
        results = merge_results(partial, results)
        return results

    def search_inservices(RegExp, ExcludeRegExp):
        sys.stderr.write("[SEARCH]: Searching in any host services\n")
        results = vdInServices.objects.none()
        partial = vdInServices.objects.filter(info__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(info__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdInServices.objects.filter(service_ssh__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(service_ssh__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdInServices.objects.filter(service_rdp__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(service_rdp__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdInServices.objects.filter(service_ftp__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(service_ftp__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdInServices.objects.filter(service_smb__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(service_smb__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdInServices.objects.filter(service_telnet__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(service_telnet__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdInServices.objects.filter(nuclei_http__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(nuclei_http__regex=ExcludeRegExp)
        results = merge_results(partial, results)
        partial = vdInServices.objects.filter(owner=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(owner=ExcludeRegExp)
        results = merge_results(partial, results)        
        return results

    def search_amass(RegExp, ExcludeRegExp):
        sys.stderr.write("[SEARCH]: Searching in any host from amass\n")
        results = vdResult.objects.none()
        partial = vdResult.objects.filter(name__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(name__regex=RegExp)
        results = merge_results(partial, results)
        partial = vdResult.objects.filter(metadata__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(metadata__regex=RegExp)
        results = merge_results(partial, results)        
        return results
    
    def search_targets(RegExp, ExcludeRegExp):
        return search_targets_by_model(RegExp, ExcludeRegExp, vdTarget)

    def search_intargets(RegExp, ExcludeRegExp):
        return search_targets_by_model(RegExp, ExcludeRegExp, vdInTarget)

#Master Search for Targets
    def search_targets_by_model(RegExp, ExcludeRegExp, vdTargetModel):
        sys.stderr.write("[SEARCH]: Searching in any host from "+vdTargetModel._meta.object_name+"\n")
        results = vdTargetModel.objects.none()
        partial = vdTargetModel.objects.filter(name__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(name__regex=RegExp)
        results = merge_results(partial, results)
        partial = vdTargetModel.objects.filter(metadata__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(metadata__regex=RegExp)
        results = merge_results(partial, results)
        return results
    
    def search_nuclei(RegExp, ExcludeRegExp):
        sys.stderr.write("[SEARCH]: Searching in any host from Nuclei Findings\n")
        results = vdNucleiResult.objects.none()
        partial = vdNucleiResult.objects.filter(full_uri__regex=RegExp)
        partial = merge_results(partial, vdNucleiResult.objects.filter(vulnerability__regex=RegExp))
        if ExcludeRegExp != "":
            partial = partial.exclude(full_uri__regex=RegExp)
        results = merge_results(partial, results)
        partial = vdNucleiResult.objects.filter(metadata__regex=RegExp)
        if ExcludeRegExp != "":
            partial = partial.exclude(metadata__regex=RegExp)
        results = merge_results(partial, results)        
        return results

    action={'services':search_services, 'amass':search_amass, 'service':search_services, 'inservices':search_inservices, 'targets':search_targets, 'intargets':search_intargets, 'nuclei':search_nuclei}
    if Model_NAME in action:
        return action[Model_NAME](RegExp, ExcludeRegExp)
    
#Special Filtering functions