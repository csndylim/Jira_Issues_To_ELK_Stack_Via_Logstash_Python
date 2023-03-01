# =============================================================================
# Import libraries
# =============================================================================
from jira import JIRA
from elasticsearch import Elasticsearch
import datetime
import pytz
import json

# =============================================================================
# Authentication
# =============================================================================
jira_username = "admin"
jira_password = "jira"
jira_host = "localhost"
jira_port = 8080
jira_issue = "TEST"

elastic_username = "elastic"
elastic_password = "P@$$w0rd"
elastic_host = "localhost"
elastic_port = 9200
elastic_scheme = "http"

# Set up Jira 
options = {'server': f'http://{jira_host}:{jira_port}'}
jira = JIRA(options, basic_auth=(jira_username, jira_password))

# Set up Elasticsearch
es = Elasticsearch(
    [{'host': elastic_host, 'port': elastic_port, 'scheme' : elastic_scheme}],
    http_auth=(elastic_username, elastic_password),
    verify_certs=True
)

# =============================================================================
# Jira
# =============================================================================

# Specify project id
jql_query = f'project = {jira_issue}'

# Set the maximum number of issues to be retrieved
max_results = 100

# Get the issues
start_at = 0
issues = []
while True:
    results = jira.search_issues(jql_query, startAt=start_at, maxResults=max_results)
    if not results:
        break
    issues += results
    start_at += max_results

# =============================================================================
# Elasticsearch
# =============================================================================

# Index the Jira issues in Elasticsearch
for issue in issues:
    issue_dict = {}
    
    # Extract all fields from Jira issue
    for field_name in issue.raw['fields']:
        issue_dict[field_name] = issue.raw['fields'][field_name]

    # Extract comments from Jira issue
    comments = []
    for comment in issue.fields.comment.comments:
        comment_dict = {
            'author': comment.author.displayName,
            'created': comment.created,
            'body': comment.body
        }
        comments.append(comment_dict)
    issue_dict['comments'] = comments

    # Extract worklog from Jira issue
    worklogs = []
    for worklog in issue.fields.worklog.worklogs:
        worklog_dict = {
            'author': worklog.author.displayName,
            'created': worklog.created,
            'time_spent': worklog.timeSpentSeconds
        }
        worklogs.append(worklog_dict)
    issue_dict['worklog'] = worklogs

    # issue_dict['key'] = issue.key
    # issue_dict['summary'] = issue.fields.summary
    # issue_dict['description'] = issue.fields.description
    # issue_dict['assignee'] = issue.fields.assignee.name if issue.fields.assignee else None
    # issue_dict['reporter'] = issue.fields.reporter.name if issue.fields.reporter else None
    # issue_dict['updated_date'] = issue.fields.updated if issue.fields.updated else None
    # issue_dict['created_date'] = issue.fields.created if issue.fields.created else None
    
    # Index the issue in Elasticsearch
    es.index(index='jiratestv2-2023-03-01', body=json.dumps(issue_dict))
