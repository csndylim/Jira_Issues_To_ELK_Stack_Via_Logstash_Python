# # Debugging the container
# import time
# while True:
#     print("Hello")
#     time.sleep(10)

from jira import JIRA
from elasticsearch import Elasticsearch
import datetime
import json
import schedule
import time
import logging

class JiraToElasticsearch:

    def __init__(self, jira_username, jira_password, jira_host, jira_port, jira_issue, elastic_username, elastic_password, elastic_host, elastic_port, elastic_scheme):
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
        self.jira = None
        self.es = None

        # Set up logging
        logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

    def authenticate(self):
        # Set up Jira
        options = {'server': 'http://{}:{}'.format(self.jira_host, self.jira_port)}
        self.jira = JIRA(options, basic_auth=(self.jira_username, self.jira_password))

        # Set up Elasticsearch
        self.es = Elasticsearch(
            [{'host': self.elastic_host, 'port': self.elastic_port, 'scheme': self.elastic_scheme}],
            http_auth=(self.elastic_username, self.elastic_password),
            verify_certs=True
        )

    def get_issues(self):
        # Specify project id
        jql_query = 'project = ' + self.jira_issue

        # Set the maximum number of issues to be retrieved
        max_results = 100

        # Get the issues
        start_at = 0
        issues = []
        while True:
            results = self.jira.search_issues(jql_query, startAt=start_at, maxResults=max_results)
            if not results:
                break
            issues += results
            start_at += max_results

        # Index the Jira issues in Elasticsearch
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

            issue_dict['key'] = issue.key
            # issue_dict['summary'] = issue.fields.summary
            # issue_dict['description'] = issue.fields.description
            # issue_dict['assignee'] = issue.fields.assignee.name if issue.fields.assignee else None
            # issue_dict['reporter'] = issue.fields.reporter.name if issue.fields.reporter else None
            # issue_dict['updated_date'] = issue.fields.updated if issue.fields.updated else None
            # issue_dict['created_date'] = issue.fields.created if issue.fields.created else None

            issue_dict['timestamp']  = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

            # Get the current date
            current_date = str(datetime.date.today().strftime('%Y-%m-%d'))

            # Index the Jira issues in Elasticsearch using the current date
            self.es.index(index='jiratestv14-' + current_date, body=json.dumps(issue_dict))
            
            # Log the successful upload
            logging.info('Successfully uploaded issue with key: %s' % issue.key)

    def run(self):
        self.authenticate()
        self.get_issues()

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
    elastic_scheme="http"
)

# Schedule the script
# schedule.every().monday.at("09:00").do(jira_to_elastic.run)
schedule.every(60).seconds.do(jira_to_elastic.run)

# Keep running the scheduled job
while True:
    schedule.run_pending()
    time.sleep(1)