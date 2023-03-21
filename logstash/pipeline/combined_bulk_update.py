import os
os.system("python /usr/share/logstash/pipeline/installation.py")

from jira import JIRA
from elasticsearch import Elasticsearch
import datetime
import json
import schedule
import logging
import time
import requests

class JiraToElasticsearch:
    
    def __init__(self, jira_username, jira_password, jira_host, jira_port, jira_issue, elastic_username, elastic_password, elastic_host, elastic_port, elastic_scheme,elastic_index):
        self.jira_username = jira_username
        self.jira_password = jira_password
        self.jira_host = jira_host
        self.jira_port = jira_port
        self.jira_issue = jira_issue
        self.elastic_username = elastic_username
        self.elastic_password = elastic_password
        self.elastic_host = elastic_host
        self.elastic_port = elastic_port
        self.elastic_scheme = elastic_scheme
        self.elastic_index = elastic_index
        self.jira = None
        self.es = None

        # Set up logging
        logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

    def authenticate(self):
        # Set up Jira
        options = {'server': 'http://{}:{}'.format(self.jira_host, self.jira_port)}
        self.jira = JIRA(options, basic_auth=(self.jira_username, self.jira_password))
        logging.info("Authenticated Jira with username: " + self.jira_username + " and host: " + self.jira_host + ":" + str(self.jira_port)) 

        # Set up Elasticsearch
        self.es = Elasticsearch(
            [{'host': self.elastic_host, 'port': self.elastic_port, 'scheme': self.elastic_scheme}],
            http_auth=(self.elastic_username, self.elastic_password),
            verify_certs=True
        )
        logging.info("Authenticated Elasticsearch with username: " + self.elastic_username + " and host: " + self.elastic_host + ":" + str(self.elastic_port))
        
    def _get_current_date(self):
        yesterday = datetime.date.today() - datetime.timedelta(days = 1)
        return str(yesterday.strftime('%Y-%m-%d'))
        # return str(datetime.date.today().strftime('%Y-%m-%d')) 

    def get_updated_issues(self):
        jql_query = "project = " + self.jira_issue + " AND updated >= " + self._get_current_date() +  " AND status = DONE"
        issues = self.jira.search_issues(jql_query)
        logging.info("Fetched " + str(len(issues)) + " issues from Jira with query: " + str(jql_query))

        issue_keys = [issue.key for issue in issues]
        logging.info("These are the updated issues keys: " + str(issue_keys))
        return issue_keys

    def delete_old_issues(self,  issue_keys):
        for issue_key in issue_keys:
            search_body = { "query": { "match": { "key": issue_key } }}
            result = self.es.search(index = self.elastic_index, body=search_body)

            doc_id = result["hits"]["hits"][0]["_id"]
            self.es.delete(index= self.elastic_index, doc_type='_doc', id= doc_id)
            logging.info("Deleted the issue key: " + issue_key + " with docid " + str(doc_id) + " from Elasticsearch index") 

    def remove_certain_fields(self, d):
        if isinstance(d, dict):
            for k, v in d.copy().items():
                if any(item in k.lower() for item in ("url", "self", "custom", ".keyword", "timezone")): #dont know why cannot remove keyword
                    del d[k]
                else:
                    self.remove_certain_fields(v)
        elif isinstance(d, list):
            for i in d:
                self.remove_certain_fields(i)

    def retrieve_time_in_status(self,key):
        # Extract time in status from Jira issue
        tis_url = "http://"+ self.jira_host + ":" + str (self.jira_port) + "/rest/tis/report/1.0/api/issue?issueKey=" + key + "&columnsBy=statusDuration&outputType=json&calendar=normalHours&viewFormat=humanReadable"
        response = requests.get(tis_url, auth=(self.jira_username, self.jira_password), headers={'Content-Type': 'application/json'})
        json1 = json.loads(response.text) # or do something else with the response data

        # Access the includedStatuses list and create a dictionary that maps id to name
        status_dict = {status['id']: status['name'] for status in json1['includedStatuses']}
        
        # Loop through the valueColumns and currentState list in the body and replace the id with the corresponding name
        for row in json1['table']['body']['rows']:
            for value_column in row['valueColumns']:
                value_column['id'] = status_dict[value_column['id']]
            for current_state in row['currentState']:
                current_state['id'] = status_dict[current_state['id']]    
        
        # Append this to issue_dict
        return json1['table']['body']['rows'][0]['currentState'], json1['table']['body']['rows'][0]['valueColumns']

    def index_issues(self, max_results, is_bulk):
        if is_bulk == True:
            jql_query = "project = " + self.jira_issue + " AND status = DONE"
        else:
            # Specify project id
            jql_query = "project = " + self.jira_issue + " AND updated >= " + self._get_current_date() + " AND status = DONE"
            
        # Get the issues
        start_at = 0
        issues = []
        while True:
            results = self.jira.search_issues(jql_query, startAt=start_at, maxResults=max_results)
            if not results:
                break
            issues += results
            start_at += max_results

        # Run each document aka an issue in a loop
        for issue in issues:
            issue_dict = {}

            # Extract all fields from Jira issue
            for field_name in issue.raw['fields']:
                issue_dict[field_name] = issue.raw['fields'][field_name]
 
            # Extract the attachments from Jira issue
            try:
                # issue_dict['attachments'] =  issue.raw['fields']['attachment']
                url = "http://"+ self.jira_host + ":" + str (self.jira_port) + "/rest/api/2/issue/" + issue.key
                response = requests.get(url, auth=(self.jira_username, self.jira_password), headers={'Content-Type': 'application/json'})
                issue_dict['attachments'] = json.loads(response.text)['fields']['attachment']
            except:
                issue_dict['attachments'] = []
                logging.info('No attachments found for issue with key: %s' % issue.key)
                 
            # Extract the comments from Jira issue
            try:
                # issue_dict['comments'] = issue.raw['fields']['comment']['comments']
                url = "http://"+ self.jira_host + ":" + str (self.jira_port) + "/rest/api/2/issue/" + issue.key + "/comment"
                response = requests.get(url, auth=(self.jira_username, self.jira_password), headers={'Content-Type': 'application/json'})
                issue_dict['comments'] = json.loads(response.text)["comments"]
            except:
                issue_dict['comments'] = []
                logging.info('No comments found for issue with key: %s' % issue.key)
                
            # Extract the watchers from Jira issue
            try:
                url = "http://"+ self.jira_host + ":" + str (self.jira_port) + "/rest/api/2/issue/" + issue.key + "/watchers"
                response = requests.get(url, auth=(self.jira_username, self.jira_password), headers={'Content-Type': 'application/json'})
                issue_dict['watchers'] = json.loads(response.text)["watchers"]
            except:
                issue_dict['watchers'] = []
                logging.info('No watchers found for issue with key: %s' % issue.key)

            # Append the issue key and timestamp to the issue_dict
            issue_dict['key'] = issue.key
            issue_dict['timestamp']  = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

            # Append the time in status to the issue_dict
            currentState, pastState = self.retrieve_time_in_status(issue.key)
            issue_dict['currentState'] = currentState
            issue_dict['pastState'] = pastState

            # Remove certain fields from the issue_dict
            self.remove_certain_fields(issue_dict)
            
            # Index the Jira issues in Elasticsearch index
            self.es.index(index= self.elastic_index , body=json.dumps(issue_dict))

            # Log the successful upload
            logging.info('Successfully uploaded issue with key: %s' % issue.key)

    def run(self, is_bulk):
        self.authenticate()
        if is_bulk == False: # If it is not a bulk upload, delete the old issues and append updated issues
            issue_keys = self.get_updated_issues()
            self.delete_old_issues(issue_keys)
        self.index_issues(max_results = 100,is_bulk = is_bulk) 

# Initialize JiraToElasticsearch object
jira_to_elastic = JiraToElasticsearch(
    jira_username="admin",
    jira_password="jira",
    jira_host="jira",
    jira_port=8080,
    jira_issue="TEST",
    elastic_username="elastic",
    elastic_password="P@$$w0rd",
    elastic_host="elasticsearch",
    elastic_port=9200,
    elastic_scheme="http",
    elastic_index ='jiratestv20-' + str(datetime.date.today().strftime('%Y-%m-%d'))
)

# Schedule the script
# schedule.every().monday.at("09:00").do(jira_to_elastic.run, is_bulk=False)
jira_to_elastic.run(is_bulk = True)

schedule.every(60).seconds.do(jira_to_elastic.run, is_bulk=False)

# Keep running the scheduled job
while True:
    schedule.run_pending()
    time.sleep(1)