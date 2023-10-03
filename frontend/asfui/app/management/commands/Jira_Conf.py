from django.core.management.base import BaseCommand
from app.models import vdInServices, vdServices
import pymongo
import urllib.parse
from django.conf import settings
from jira import JIRA
import urllib
from app.tools import *

user = settings.JIRA_USER
apikey = settings.JIRA_TOKEN
server = settings.JIRA_URL


jira = None
if settings.JIRA_ENABLED:
    jira = JIRA(server=server, basic_auth=(user,apikey))


def create_jira(finding_dict):
    severity = settings.JIRA_SEVERITY
    summary = None
    description = "*Summary:*\n"
    if "info" in finding_dict:
        if "name" in finding_dict["info"]:
            summary = "ASF Finding - "+str(finding_dict["info"]["name"] or 'None')
        if "description" in finding_dict["info"]:
            description = description + str( finding_dict["info"]["description"] or 'None')
        if "reference" in finding_dict["info"]:
            description = description + "\n*References:*\n"+ "\n".join(str(e) for e in (finding_dict["info"]["reference"] or []))
    if "host" in finding_dict:
        description = description+"\n\n*Hosts:*\n"+str(finding_dict["host"] or 'None')
    if "extracted-results" in finding_dict:
        description = description+"\n\n*Extracted Results:*\n"+"\n".join(str(e) for e in (finding_dict["extracted-results"] or []))
    new_issue = jira.create_issue(project= settings.JIRA_PROJECT, summary=summary, description=description, issuetype={'name': 'Bug'}, priority={'name':severity[finding_dict["info"]["severity"]]})
    debug(new_issue)
    return str(new_issue)
    
def jira_status(ticket_num):
    issue = jira.issue(ticket_num)
    status = issue.fields.status
    return status

def create_issue(query):
    if settings.JIRA_ENABLED:
        username = urllib.parse.quote_plus(settings.MONGO_USER)
        password = urllib.parse.quote_plus(settings.MONGO_PASSWORD)
        url = settings.MONGO_URL
        port = settings.MONGO_PORT
        client = pymongo.MongoClient(f"mongodb://{username}:{password}@{url}:{port}")
        myDB = client["Nuclei"]
        mycol = myDB["report"]
        mydoc = mycol.find(query)
        for doc in mydoc:
            ticket_num = create_jira(doc)
            id = doc['_id']
            query = {'_id': id}
            mycol.update_one(query, {"$set":{"verified":True, "ignored":False,  "jira_created":True, "jira_closed":False, "jira_ticket":ticket_num, "jira_url": settings.JIRA_URL+"/browse/"+ticket_num}})
    #if setting.EMAIL_ENABLED:
    return
        
 
def ignore_issue(query):
    username = urllib.parse.quote_plus(settings.MONGO_USER)
    password = urllib.parse.quote_plus(settings.MONGO_PASSWORD)
    url = settings.MONGO_URL
    port = settings.MONGO_PORT
    client = pymongo.MongoClient(f"mongodb://{username}:{password}@{url}:{port}")
    myDB = client["Nuclei"]
    mycol = myDB["report"]
    mycol.update_many(query, {"$set":{"verified":True, "ignored":True}})
    mycol.count_documents(query)
    debug("ignored issue", query, mycol.count_documents(query))

def main():
    create_issue()
    debug("issue created")

if __name__ == "__main__":
    main()
    
class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--ticket", type=str, required=True)

    def handle(self, *args, **kwargs):
        severity = kwargs['ticket']
        try:
            query = {"info.severity":severity}
            create_issue(query)
            debug("insert complete")
        except Exception as e:
            debug("insert failed"+ str(e))

