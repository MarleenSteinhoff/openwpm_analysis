import requests as re
from time import time
import requests
import os
from urllib.parse import urlparse
import sys
from dotenv import load_dotenv 





if __name__ == '__main__':
    t0 = time()
    url = sys.argv[1]
    extraction_dir = sys.argv[2]
    print("url " + url)
    print("directory " + extraction_dir)
    
    #load secrets
    load_dotenv()
    username = os.environ.get('WEBTAPUSER')
    password = os.environ.get('PASSWORD')

    print(f"Downloading file {url}")

    r = requests.get(url, auth=(username, password), stream=True)
    
    print(f"request resolved with code {r.status_code}")

    print(r.headers)

    filename = url.rsplit('/',1)[1]
    
  
    if r.status_code == 200:
        with open(filename, "wb") as out:
            total_length = int(r.headers.get("content-length"))
            
            print(f"expected file size: {total_length}b")

            for chunk in progress.bar(r.iter_content(chunk_size=1024), expected_size=(total_length / 1024) + 1):
                if chunk:
                    out.write(chunk)
                    out.flush()
        
    else:
        print("error downloading file")





    print("Analysis finished in %0.1f mins" % ((time() - t0) / 60))
