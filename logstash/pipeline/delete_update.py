import os
os.system("python /usr/share/logstash/pipeline/installation.py")

from jira import JIRA
from elasticsearch import Elasticsearch
import datetime
import json
import schedule
import logging
import time

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
        return str(datetime.date.today().strftime('%Y-%m-%d'))

    def get_issues(self):
        jql_query = "project = " + self.jira_issue + " AND updated >= " + self._get_current_date()
        issues = self.jira.search_issues(jql_query)
        logging.info("Fetched " + str(len(issues)) + " issues from Jira with query: " + str(jql_query))

        issue_keys = [issue.key for issue in issues]
        logging.info("These are the updated issues keys: " + str(issue_keys))
        return issue_keys

    def delete_issues(self,  issue_keys):
        for issue_key in issue_keys:
            search_body = { "query": { "match": { "key": issue_key } }}
            result = self.es.search(index = self.elastic_index, body=search_body)

            doc_id = result["hits"]["hits"][0]["_id"]
            self.es.delete(index= self.elastic_index, doc_type='_doc', id= doc_id)
            logging.info("Deleted the issue key: " + issue_key + " with docid " + str(doc_id) + " from Elasticsearch index") 

    def index_issues(self, max_results):
        # Specify project id
        jql_query = "project = " + self.jira_issue + " AND updated >= " + self._get_current_date() #same as authentication code coz same issues keys
        
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

            # Extract comments
            try:
                comments = []
                for comment in issue.fields.comment.comments:
                    comments.append(comment.body)
                issue_dict['comments'] = comments
            except AttributeError:
                issue_dict['comments'] = []

            # Extract worklogs
            try:
                worklogs = []
                for worklog in issue.fields.worklog.worklogs:
                    worklogs.append({
                        'author': worklog.author.displayName,
                        'timeSpent': worklog.timeSpent,
                        'created': worklog.created
                    })
                issue_dict['worklogs'] = worklogs
            except AttributeError:
                issue_dict['worklogs'] = []

            # Extract attachments
            try:
                attachments = []
                for attachment in issue.fields.attachment:
                    attachments.append(attachment.filename)
                issue_dict['attachments'] = attachments
            except AttributeError:
                issue_dict['attachments'] = []
            
            # Add the issue key and timestamp
            issue_dict['key'] = issue.key
            issue_dict['timestamp']  = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

            # Index the Jira issues in Elasticsearch index
            self.es.index(index= self.elastic_index , body=json.dumps(issue_dict))

            # Log the successful upload
            logging.info('Successfully uploaded issue with key: %s' % issue.key)

    def run(self):
        self.authenticate()
        issue_keys = self.get_issues()
        self.delete_issues(issue_keys)
        self.index_issues(max_results = 100)

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
    elastic_index ='jiratestv16-' + str(datetime.date.today().strftime('%Y-%m-%d'))
)

# Schedule the script
# schedule.every().monday.at("09:00").do(jira_to_elastic.run)
schedule.every(60).seconds.do(jira_to_elastic.run)

# Keep running the scheduled job
while True:
    schedule.run_pending()
    time.sleep(1)