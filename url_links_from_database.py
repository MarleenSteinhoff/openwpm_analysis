import requests
from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import os

# load secrets
load_dotenv()
username = os.environ.get('WEBTAPUSER')
password = os.environ.get('PASSWORD')



BASEURL_STATEFULL = 'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateful/'
BASEURL_STATELESS = 'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/'

response = requests.get(BASEURL_STATEFULL, auth=(username, password))
soup = BeautifulSoup(response.text, 'html.parser')
all_urls = []

for link in soup.find_all('a'):
    URL = BASEURL_STATEFULL + link.get('href')
    if URL.endswith('.lz4'):
        all_urls.append(URL)



print(all_urls)

