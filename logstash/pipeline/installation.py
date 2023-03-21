import time
import os
os.system("curl https://bootstrap.pypa.io/pip/2.7/get-pip.py | python") 
# os.system("curl https://bootstrap.pypa.io/get-pip.py | python") # python 3 version
os.system("python -m pip --version")
os.system("export PATH=$PATH:/usr/share/logstash/.local/bin")
os.system("which python")
os.system("python -m pip install schedule jira elasticsearch requests logging")
print("Installation complete")
