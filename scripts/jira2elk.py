# import os
# os.system("python -m pip install schedule jira elasticsearch requests")
from jira import JIRA
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import datetime
import json
import schedule
import logging
import time
import requests

class JiraToElasticsearch:

    def __init__(self, jira_token, jira_host, jira_port, jira_issue, elastic_username, elastic_password, elastic_host, elastic_port, elastic_scheme,elastic_index, updated_date):
        self.jira_token = jira_token
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
        self.updated_date = updated_date

        # Set up logging
        logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

    def authenticate(self):
        # Set up Jira
        options = {'server': '{}:{}'.format(self.jira_host, self.jira_port)}
        self.jira = JIRA(options, token_auth=self.jira_token)
        logging.info("Authenticated Jira using api token on " + self.jira_host + ":" + str(self.jira_port)) 

        # Set up Elasticsearch
        self.es = Elasticsearch(
            [{'host': self.elastic_host, 'port': self.elastic_port, 'scheme': self.elastic_scheme}],
            http_auth=(self.elastic_username, self.elastic_password),
            verify_certs=True
        )
        logging.info("Authenticated Elasticsearch with username: " + self.elastic_username + " and host: " + self.elastic_host + ":" + str(self.elastic_port))
       
    def remove_certain_fields(self, d):
        if isinstance(d, dict):
            for k, v in d.copy().items():
                if any(item in k.lower() for item in ("url", "self", "timezone")): 
                    del d[k]
                else:
                    self.remove_certain_fields(v)
        elif isinstance(d, list):
            for i in d:
                self.remove_certain_fields(i)

    def retrieve_time_in_status_from_jira(self,key):
        # Extract time in status from Jira issue
        tis_url = self.jira_host + ":" + str (self.jira_port) + "/rest/tis/report/1.0/api/issue?issueKey=" + key + "&columnsBy=statusDuration&outputType=json&calendar=normalHours&viewFormat=humanReadable"
        response = requests.get(tis_url, headers = { "Accept": "application/json", "Content-Type": "application/json", "Authorization": "Bearer " + self.jira_token })
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

    def retrieve_fields_from_jira(self, jql_query):
        # Prepare the bulk request body
        issues_dicts = []
        issues_keys = []

        # Get the issues through looping
        start_at = 0
        max_results = 20

        while True:
            results = self.jira.search_issues(jql_query, startAt=start_at, maxResults=max_results)
            if not results:
                break

            logging.info("Extracting from issue no. " + str(start_at) + " to " + str(start_at + max_results) )
            start_at += max_results
     
            # Run each document aka an issue in a loop
            for issue in results:
                issue_dict = {}

                # Extract all fields from Jira issue
                for field_name in issue.raw['fields']:
                    issue_dict['jira.' + field_name] = issue.raw['fields'][field_name]
    
                # Extract the watchers from Jira issue
                try:
                    url = ""+ self.jira_host + ":" + str (self.jira_port) + "/rest/api/2/issue/" + issue.key + "/watchers"
                    response = requests.get(url, headers = { "Accept": "application/json", "Content-Type": "application/json", "Authorization": "Bearer " + self.jira_token })
                    issue_dict['jira.watchers'] = json.loads(response.text)["watchers"]
                except:
                    issue_dict['jira.watchers'] = []
                    logging.info('No watchers found for issue with key: %s' % issue.key)

                # Append the timestamp to the issue_dict
                issue_dict['jira.timestamp']  = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

                # Append the time in status to the issue_dict
                currentState, pastState = self.retrieve_time_in_status_from_jira(issue.key)
                issue_dict['jira.currentState'] = currentState
                issue_dict['jira.pastState'] = pastState

                # Remove certain fields from the issue_dict
                self.remove_certain_fields(issue_dict)

                # Append the issue_dict and issue_key to the respective lists for bulk indexing
                issues_dicts.append(issue_dict)
                issues_keys.append(issue.key)

        return issues_keys, issues_dicts
    
    def ingest_issues_to_elasticsearch(self, is_update):
        ingest_issues_bulk = [] # List of issues to be indexed
        
        if is_update == False:
            two_months_ago = str((datetime.date.today() - datetime.timedelta(days = 60)).strftime('%Y-%m-%d'))  
            jql_query = "project = " + self.jira_issue + " AND updated >= " + two_months_ago + " AND status = DONE"
    
            # Retrieve the issues
            issues_keys, issue_dicts = self.retrieve_fields_from_jira(jql_query)
            
            # Prepare the index request body
            for i in range (len(issues_keys)):
                ingest_issues_bulk.append({
                    '_index': self.elastic_index,
                    '_id': issues_keys[i],
                    '_source': json.dumps(issue_dicts[i])
                })
            ingest_type = "Indexed"
        else:
            # Specify project id
            jql_query = "project = " + self.jira_issue + " AND updated >= " + self.updated_date + " AND status = DONE"
            
            # Retrieve the issues
            issues_keys, issue_dicts = self.retrieve_fields_from_jira(jql_query)
            
            # Prepare the index request body
            for i in range (len(issues_keys)):
                ingest_issues_bulk.append({
                      '_op_type': 'update',
                    '_index': self.elastic_index,
                    '_id': issues_keys[i],
                    'doc': issue_dicts[i]
                })
            ingest_type = "Updated"
        
        # Use `bulk` function to index the issues in Elasticsearch
        bulk(self.es, ingest_issues_bulk, index=self.elastic_index)
        logging.info(ingest_type + " the following issues keys: " + str(issues_keys) + " into  index " + self.elastic_index)
       
# Initialize JiraToElasticsearch object
jira_to_elastic = JiraToElasticsearch(
    jira_token = "",
    jira_host = "http://jira",
    jira_port = 8080,
    jira_issue = "TEST",
    elastic_username = "elastic",
    elastic_password = "P@$$w0rd",
    elastic_host = "elasticsearch", 
    elastic_port = 9200,
    elastic_scheme = "http",
    elastic_index = 'jiratestv24-' + str((datetime.date.today() - datetime.timedelta(days = 0)).strftime('%Y-%m-%d')),
    updated_date = str((datetime.date.today() - datetime.timedelta(days = 1)).strftime('%Y-%m-%d'))
)

# Start running from here
jira_to_elastic.authenticate()
jira_to_elastic.ingest_issues_to_elasticsearch(is_update = False)

# Schedule the script to run every n type of time
# schedule.every().monday.at("09:00").do(jira_to_elastic.run, is_update = True)
# schedule.every(60).seconds.do(jira_to_elastic.ingest_issues_to_elasticsearch, is_update = True)
# schedule.every(5).hours.do(jira_to_elastic.authenticate) # idle is max 5 hours

# # Keep running the scheduled job
# while True:
#     schedule.run_pending()
#     time.sleep(1)