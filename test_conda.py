import os
import subprocess


bashCommand1 = "source /crawler/miniconda3/etc/profile.d/conda.sh"
bashCommand2 = "conda activate openwpm"

process1 = subprocess.Popen(bashCommand1.split(), stdout=subprocess.PIPE)
output, error = process1.communicate()

process2 = subprocess.Popen(bashCommand2.split(), stdout=subprocess.PIPE)
output, error = process2.communicate()

print(os.environ.get('CONDA_PREFIX'))