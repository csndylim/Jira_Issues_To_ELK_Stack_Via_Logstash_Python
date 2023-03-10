from jira import JIRA
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

import datetime
import json


# =============================================================================
# # Authentication
# =============================================================================
options = {'server': 'http://localhost:8080'}
username = "admin"
password = "jira"
username_elastic = "elastic"
password_elastic = "P@$$w0rd"

# Get the current date
current_date = str(datetime.date.today().strftime('%Y-%m-%d'))

jira = JIRA(options, basic_auth=(username, password))

es = Elasticsearch(
    [{'host': 'localhost', 'port': 9200, 'scheme' : 'http'}],
    http_auth=(username_elastic, password_elastic),
    verify_certs=True
)


# =============================================================================
# Get the issues that are updated
# =============================================================================

# specify the JQL query to search for issues
jql_query = "project = TEST AND updated >= " + current_date


issues = jira.search_issues(jql_query)
issue_keys = [issue.key for issue in issues]


# =============================================================================
# Delete the issues on elasticsearch
# =============================================================================
# Define the index and type of the documents to be deleted
index = 'jiratestv14-' + current_date
doc_type = "_doc"

# get list of document ID from issue_keys on elasticseach
doc_ids = []
for issue_key in issue_keys:
    search_body = {
        "query": {
            "match": {
                "key": issue_key
            }
        }
    }

    res = es.search(index=index, body=search_body)
    doc_ids.append(res["hits"]["hits"][0]["_id"])

# Define a list of Elasticsearch delete requests for each document
delete_requests = [
    {
        "_index": index,
        "_type": doc_type,
        "_id": doc_id
    }
    for doc_id in doc_ids
]

# Use the Elasticsearch bulk() function to delete the documents in bulk
bulk(es, delete_requests)

# Delete just one document
# es.delete(index='my_index', doc_type='_doc', id='1')



# =============================================================================
# Add in the new issues on elasticsearch
# =============================================================================
# # Set the maximum number of issues to be retrieved
max_results = 100

# Define the JQL query to get the issues
jql_query = "project = TEST AND updated >= " + current_date

# Get the issues
start_at = 0
issues = []
while True:
    results = jira.search_issues(jql_query, startAt=start_at, maxResults=max_results, expand='changelog')
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
  
        # Extract changelog from Jira issue
        for field_name in issue.raw['changelog']:
            issue_dict[field_name] = issue.raw['changelog'][field_name]
  
  
        issue_dict['key'] = issue.key
        # issue_dict['summary'] = issue.fields.summary
        # issue_dict['description'] = issue.fields.description
        # issue_dict['assignee'] = issue.fields.assignee.name if issue.fields.assignee else None
        # issue_dict['reporter'] = issue.fields.reporter.name if issue.fields.reporter else None
        # issue_dict['updated_date'] = issue.fields.updated if issue.fields.updated else None
        # issue_dict['created_date'] = issue.fields.created if issue.fields.created else None
  
        issue_dict['timestamp']  = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
  
        # Get the current date
        # current_date = str(datetime.date.today().strftime('%Y-%m-%d'))
  
        # # Index the Jira issues in Elasticsearch using the current date
        # es.index(index='jiratestv14-' + current_date, body=json.dumps(issue_dict))
        
        # print (issue_dict)




last_time = None
for history in issue_dict['histories']:
    for item in history['items']:
        if 'toString' in item:
            current_time = datetime.datetime.strptime(history['created'], '%Y-%m-%dT%H:%M:%S.%f%z')
            if last_time is not None:
                time_elapsed = current_time - last_time
                days = time_elapsed.total_seconds() / (24 * 3600)
                print(f"Time elapsed: {days:.1f} days NewStatus: {item['toString']}")
            last_time = current_time