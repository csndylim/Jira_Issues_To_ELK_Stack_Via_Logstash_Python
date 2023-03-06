# Ingestion of Jira issues from Jira Service Management into Elasticsearch-Logstash-Kibana (ELK) Stack via Logstash-Python

## 0. Clone this repository
FYI
elasticsearch's image: docker.elastic.co/elasticsearch/elasticsearch:7.16.3
logstash's image: docker.elastic.co/logstash/logstash:7.16.3
kibana's image: docker.elastic.co/kibana/kibana:7.16.3
jira's image: atlassian/jira-software:8.14

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

In the `docker-compose.yml`, add the following `volumes` lines in the jira section

I'm not sure whether this part is correct coz I never tried mounting the `test.tar.gz`

```
services:
  elasticsearch:
  logstash:
  kibana:
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
      - test:/var/atlassian/application-data/jira

volumes:
  1051ede03573f84b77948bda919f034945e80aa701a181a0c2b48fe3854377b1:
    external: true
    name: test
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

## 3. Run the first batch of jira issues from Jira Service Management to ELK
In `docker-compose.yaml`, comment line 51 and uncomment 50
```bash
Line 50  command: ["/usr/bin/python", "/usr/share/logstash/pipeline/initial_commit.py"]
Line 51 # command: ["/usr/bin/python", "/usr/share/logstash/pipeline/delete_update.py"]
```

## 4. Update the jira issues that are updated in Jira Service Management on ELK
In `docker-compose.yaml`, comment line 50 and uncomment 51
```bash
Line 50 # command: ["/usr/bin/python", "/usr/share/logstash/pipeline/initial_commit.py"]
Line 51  command: ["/usr/bin/python", "/usr/share/logstash/pipeline/delete_update.py"]
```

## 5. Remove the first two lines of codes in `initial_commit.py` and `delete_update.py` (Optional)
```python
import os
os.system("python /usr/share/logstash/pipeline/installation.py")
```
Code explaination:
The first two lines call the script - `installation.py` which installs pip and python libraries on logstash container. I did not remove them as the logstash container might think it is not permanently installed as I am using docker containers.
