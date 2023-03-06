# Ingestion of Jira issues from Jira Service Management into Elasticsearch-Logstash-Kibana (ELK) Stack via Logstash-Python

## 0. Clone this repository

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

## 2. Install python on logstash
Remotely access `elk_logstash` on cmd with root privileges
```bash
docker exec -u root -it --workdir / elk_logstash bash
```

Install pip - I think python is already installed but is 2.7 version
```bash
curl https://bootstrap.pypa.io/pip/2.7/get-pip.py | python
```

Install the libraries
```bash
pip install schedule jira elasticsearch requests logging
```

3. Run the first batch of jira issues from Jira Service Management to ELK
In `docker-compose.yaml`, comment line 51 and uncomment 52
```bash
Line 51 # command: ["/usr/bin/python", "/usr/share/logstash/pipeline/installation.py"]
Line 52  command: ["/usr/bin/python", "/usr/share/logstash/pipeline/initial_commit.py"]
Line 53 # command: ["/usr/bin/python", "/usr/share/logstash/pipeline/delete_update.py"]
```

4. Update the jira issues that are updated in Jira Service Management on ELK
In `docker-compose.yaml`, comment line 52 and uncomment 53
```bash
Line 51 # command: ["/usr/bin/python", "/usr/share/logstash/pipeline/installation.py"]
Line 52 # command: ["/usr/bin/python", "/usr/share/logstash/pipeline/initial_commit.py"]
Line 53  command: ["/usr/bin/python", "/usr/share/logstash/pipeline/delete_update.py"]
```
