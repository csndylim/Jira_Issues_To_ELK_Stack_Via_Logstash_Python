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

# =============================================================================
# Jira
# =============================================================================

# jira = JIRA(options, basic_auth=(username, password))

# # specify the JQL query to search for issues
# jql_query = 'project = TEST'

# # get the total number of issues
# total_issues = jira.search_issues(jql_query, maxResults=0, fields=None, expand=None, json_result=None).total


# num_issues = 50
# # Calculate the number of pages of issues to fetch
# num_pages = (total_issues + num_issues - 1) // num_issues

# # Fetch the issues from each page
# issues = []
# # Set the maximum number of issues to be retrieved
# max_results = 100

# # Get the issues
# start_at = 0
# issues = []
# while True:
#     results = jira.search_issues(jql_query, startAt=start_at, maxResults=max_results)
#     if not results:
#         break
#     issues += results
#     start_at += max_results

# # Print the issues
# for issue in issues:
#     print(issue)


# =============================================================================
# Elasticsearch
# =============================================================================
# process the issues as needed
es = Elasticsearch(
    [{'host': 'localhost', 'port': 9200, 'scheme' : 'http'}],
    http_auth=(username_elastic, password_elastic),
    verify_certs=True
)

# Get the current date
current_date = str(datetime.date.today().strftime('%Y-%m-%d'))

# Define the index and type of the documents to be deleted
index = 'jiratestv14-' + current_date
doc_type = "_doc"


issue_keys = ["TEST-1", "TEST-2", "TEST-3"]

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



