import os
os.system("python /usr/share/logstash/pipeline/installation.py")

from jira import JIRA
from elasticsearch import Elasticsearch
import datetime
import json
import schedule
import logging
import time
import re
import pytz
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

    def parse_datetime_with_timezone(self,dt_str):
        # Parse the datetime string and the UTC offset separately
        dt, tz_offset = re.match(r'(\d+-\d+-\d+T\d+:\d+:\d+\.\d+)(\+\d+)', dt_str).groups()
        # Parse the UTC offset into hours and minutes
        tz_hours = int(tz_offset[1:3])
        tz_minutes = int(tz_offset[3:])
        # Create the datetime object with the timezone information
        dt = datetime.datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S.%f')
        dt_tz = pytz.utc.localize(dt + datetime.timedelta(hours=tz_hours, minutes=tz_minutes))
        return dt_tz

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
            results = self.jira.search_issues(jql_query, startAt=start_at, maxResults=max_results, expand='changelog')
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
    
            # Extract time in status from Jira issue
            tis_url = "http://"+ self.jira_host + ":" + self.jira_port + "/rest/tis/report/1.0/api/issue?issueKey=" + issue.key + "&columnsBy=statusDuration&outputType=json&calendar=normalHours&viewFormat=humanReadable"
            response = requests.get(tis_url, auth=(self.jira_username, self.jira_password), headers={'Content-Type': 'application/json'})
            test = (response.content) # or do something else with the response data

            # Extract changelog from Jira issue
            for field_name in issue.raw['changelog']:
                issue_dict[field_name] = issue.raw['changelog'][field_name]

            # Extract the time elapsed for each field
            last_time = None
            last_field = None
            last_id = None
            output = []
            for history in issue_dict['histories']:
                for item in history['items']:
                    if 'toString' in item:
                        current_id = history['id']
                        current_value = item['toString']
                        current_time = self.parse_datetime_with_timezone(history['created'])
                        
                        if current_id != last_id and last_id is not None:
                            time_elapsed = current_time - last_time
                            days = time_elapsed.total_seconds() / (24 * 3600)
                            output.append((last_field, days))
            
                        last_id = current_id
                        last_field = current_value
                        last_time = current_time
            
            # print the time elapsed for the last field
            if last_field is not None:
                time_elapsed = datetime.datetime.now(pytz.utc) - last_time
                days = time_elapsed.total_seconds() / (24 * 3600)
                output.append((last_field, str(days)))

            issue_dict["elapsed_time"] = str(output)
            logging.info('time output: %s' % str(output))

            # Add the issue key and timestamp
            issue_dict['key'] = issue.key
            issue_dict['timestamp']  = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

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