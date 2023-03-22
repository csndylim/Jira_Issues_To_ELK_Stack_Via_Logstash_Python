# Ingestion of Jira issues from Jira Service Management into Elasticsearch via Logstash-Python

## 0. Clone this repository
FYI, these are the versions being used. Any version can work. Just change the versions inside the `docker-compose.yaml` file for containers, and `installation.py` for python
* elasticsearch's image: docker.elastic.co/elasticsearch/elasticsearch:7.16.3
* logstash's image: docker.elastic.co/logstash/logstash:7.16.3
* kibana's image: docker.elastic.co/kibana/kibana:7.16.3
* jira's image: atlassian/jira-software:8.14
* python: 2.70

## 1. Download the volume of Jira docker container (Not needed)

Go to my onedrive to download `test.tar` coz Github says the file is over 100MB, cannot upload.

You can mount the `test.tar.gz` into a Docker container using the -v flag in the docker run command. 

```bash
docker run -it -v /path/to/test.tar.gz:/test.tar.gz alpine sh
```

This will start a new container from the alpine image and mount the `test.tar.gz` at the root directory of the container as `/test.tar.gz`. The -it flag opens an interactive terminal session in the container and the sh command starts the shell.

Once you're inside the container, you can extract the contents of the tar file using the tar command:

```bash
tar -xvf /test.tar.gz
```

This will extract the contents of the test.tar.gz file to the current working directory inside the container.

In the `docker-compose.yml`, add the following `volumes` lines in the jira section.

Disclaimer: Not sure whether this part is correct coz never tried mounting the `test.tar.gz`.

``` bash
services:
   ...
   jira:
     image: atlassian/jira-software:8.14
     ports:
       - 8080:8080
     networks:
       - elk_stack
     restart: "no"
     mem_limit: 1g
    volumes:
      - 1051ede03573f84b77948bda919f034945e80aa701a181a0c2b48fe3854377b1:/var/atlassian/application-data/jira

volumes:
  1051ede03573f84b77948bda919f034945e80aa701a181a0c2b48fe3854377b1:
    external: true
    name: 1051ede03573f84b77948bda919f034945e80aa701a181a0c2b48fe3854377b1
```

## 2. Run the containers in the same directory as docker-compose.yaml, with this command on cmd
```bash
docker-compose up -d
```
The output on command line should look something like this with all 4 containers started and running.
```bash
[+] Running 4/4
 - Container elk_elasticsearch  Started                                                                            2.9s
 - Container elk_kibana         Started                                                                            4.8s
 - Container elk-docker-jira-1  Started                                                                            2.9s
 - Container elk_logstash       Started                                                                            6.4s
```

## 3. Run the first batch of jira issues from Jira Service Management to Elasticsearch in `combined_bulk_update.py`
```python
Line 201 jira_to_elastic.authenticate()
Line 202 jira_to_elastic.ingest_issues_to_elasticsearch(is_update = False)
```

## 4. Schedule to update the jira issues that are updated in Jira Service Management on Elasticsearch at every 60 seconds, and authenticate the credentials of Jira Service Management, and Elasticsearch at every 5 hours in `combined_bulk_update.py`
Feel free to change to any n type of time.
```python
Line 205 # schedule.every().monday.at("09:00").do(jira_to_elastic.run, is_update = True)
Line 206 schedule.every(60).seconds.do(jira_to_elastic.ingest_issues_to_elasticsearch, is_update = True)
Line 207 schedule.every(5).hours.do(jira_to_elastic.authenticate) # idle is max 5 hours
```

## 5. Remove or comment the first two lines of codes in `combined_bulk_update.py`.  (Optional)
Both files are located in `logstash\pipeline` folder.
```python
import os
os.system("python /usr/share/logstash/pipeline/installation.py")
```
Code explaination:
The first two lines call the script - `installation.py` which installs pip and python libraries on logstash container. I did not remove them as the logstash container might think it is not permanently installed as I am using docker containers.
