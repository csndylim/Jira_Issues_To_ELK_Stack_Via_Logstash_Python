import os
from dotenv import load_dotenv
# os.system("python -m pip install schedule jira elasticsearch requests python-dotenv")
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

    def __init__(self, jira_token, jira_host, jira_port, jira_project, jira_max_results, elastic_token_id, elastic_token_key, elastic_host, elastic_port, elastic_scheme,elastic_index, created_date, updated_date):
        self.jira_token = jira_token
        self.jira_host = jira_host
        self.jira_port = jira_port
        self.jira_project = jira_project
        self.jira_max_results = jira_max_results
        self.elastic_token_id = elastic_token_id
        self.elastic_token_key = elastic_token_key
        self.elastic_host = elastic_host
        self.elastic_port = elastic_port
        self.elastic_scheme = elastic_scheme
        self.elastic_index = elastic_index
        self.jira = None
        self.es = None
        self.created_date = created_date
        self.updated_date = updated_date

    def authenticate(self):
        # Set up Jira
        options = {'server': '{}:{}'.format(self.jira_host, self.jira_port)}
        self.jira = JIRA(options, token_auth=self.jira_token)
        logging.info("Authenticated Jira using api token on " + self.jira_host + ":" + str(self.jira_port)) 

        self.es = Elasticsearch(
            [{'host': self.elastic_host, 'port': self.elastic_port, 'scheme': self.elastic_scheme}],
            api_key=(self.elastic_token_id, self.elastic_token_key)
        )
        logging.info("Authenticated Elasticsearch using api token on  " + self.elastic_host + ":" + str(self.elastic_port))
       
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

    def retrieve_fields_from_jira(self, is_update):
        # Start the timer
        start_time_script = time.time()

        # Specify the JQL query
        if is_update == False:
            jql_query = "project = " + self.jira_project + " AND created >= " + self.created_date + " AND status = DONE"
        else:
            jql_query = "project = " + self.jira_project + " AND updated >= " + self.updated_date + " AND status = DONE"

        # Get the issues through looping
        start_at = 0
        max_results = self.jira_max_results

        while True:
            results = self.jira.search_issues(jql_query, startAt=start_at, maxResults=max_results)
            if not results:
                break
            logging.info("Extracting from issue no. " + str(start_at) + " to " + str(start_at + max_results) )
            start_at += max_results

            # Prepare the bulk request body
            issues_dicts = []
            issues_keys = []

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

            self.ingest_issues_to_elasticsearch(issues_dicts, issues_keys, is_update)
        logging.info("Time taken to run the ingestion from jira to elk: " + str(datetime.timedelta(seconds=(time.time() - start_time_script))) + "\n")
    
    def ingest_issues_to_elasticsearch(self, issues_dicts, issues_keys, is_update):
        ingest_issues_bulk = [] # List of issues to be indexed
        
        if is_update == False:
            # Prepare the index request body
            for i in range (len(issues_keys)):
                ingest_issues_bulk.append({
                    '_index': self.elastic_index,
                    '_id': issues_keys[i],
                    '_source': json.dumps(issues_dicts[i])
                })
            ingest_type = "Indexed"
        else:
            # Prepare the index request body
            for i in range (len(issues_keys)):
                ingest_issues_bulk.append({
                      '_op_type': 'update',
                    '_index': self.elastic_index,
                    '_id': issues_keys[i],
                    'doc': issues_dicts[i]
                })
            ingest_type = "Updated"
        
        # Use `bulk` function to index the issues in Elasticsearch
        bulk(self.es, ingest_issues_bulk, index=self.elastic_index)
        logging.info(ingest_type + " the following issues keys: " + str(issues_keys) + " into index " + self.elastic_index)

# Load the environment variables and set up logging
load_dotenv()
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Initialize JiraToElasticsearch object
jira_to_elastic = JiraToElasticsearch(
    jira_token = os.environ.get('JIRA_TOKEN'),
    jira_host = os.environ.get('JIRA_HOST'),
    jira_port = int(os.environ.get('JIRA_PORT')),
    jira_project = "TEST",
    jira_max_results = 3, # to increase to 20000
    elastic_token_id = os.environ.get('ELASTIC_TOKEN_ID'),
    elastic_token_key = os.environ.get('ELASTIC_TOKEN_KEY'),
    elastic_host = os.environ.get('ELASTIC_HOST'),
    elastic_port = int(os.environ.get('ELASTIC_PORT')),
    elastic_scheme = os.environ.get('ELASTIC_SCHEME'),
    elastic_index = 'jiratestv25-' + str((datetime.date.today() - datetime.timedelta(days = 0)).strftime('%Y-%m-%d')),
    created_date = str((datetime.date.today() - datetime.timedelta(days = 60)).strftime('%Y-%m-%d')),
    updated_date = str((datetime.date.today() - datetime.timedelta(days = 30)).strftime('%Y-%m-%d'))
)

# Start running from here
jira_to_elastic.authenticate()
jira_to_elastic.retrieve_fields_from_jira(is_update = False)

# Schedule the script to run every n type of time
# schedule.every().monday.at("09:00").do(jira_to_elastic.run, is_update = True)
schedule.every(20).seconds.do(jira_to_elastic.retrieve_fields_from_jira, is_update = True)
schedule.every(5).hours.do(jira_to_elastic.authenticate) # idle is max 5 hours

# # Keep running the scheduled job
while True:
    schedule.run_pending()
    time.sleep(1)