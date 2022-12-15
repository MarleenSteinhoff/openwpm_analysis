import os
import requests
from urllib.parse import urlparse
import pathlib
import argparse
import sys
from clint.textui import progress
from dotenv import load_dotenv 


current_folder = pathlib.Path(__file__).parent.resolve()

crawl_dir = os.path.join(current_folder, "datain")
out_dir = os.path.join(current_folder, "dataout")



def get_filename_from_cd(cd):
    """
    Get filename from content-disposition
    """
    if not cd:
        return None
    fname = re.findall('filename=(.+)', cd)
    if len(fname) == 0:
        return None
    return fname[0]

def download(url, count=0):

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
            manipulate(filename)
        
    else:
        print("error downloading file")


def manipulate(filename):
    #### DO SHIT HERE 
    outfile = os.path.splitext(filename)[0]
    os.system(f"lz4 -dc {crawl_dir}/{filename} > {crawl_dir}/{outfile}")
    os.system(f"python analyze_crawl.py {crawl_dir} {out_dir}")
    # remove all files from current crawl
    os.system(f"rm -f {crawl_dir}/*")


    ### END SHIT HERE

    print("finished, deleting downloaded archive and sql database...")
    # os.remove(filename)
    # os.remove(outfile)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--test",action='store_true', default=False),
    args = parser.parse_args()

    os.system(f"mkdir {crawl_dir}")
    os.system(f"mkdir {out_dir}")



    if args.test:
        print("Running analysis with sample DB...")
        path = './samples/sample.sqlite'

        filename = 'sample.sqlite'  

        os.system(f"cp {path} {crawl_dir}")
        os

        manipulate(filename)


    

    else:

        load_dotenv()
        username = os.environ.get('WEBTAPUSER')
        password = os.environ.get('PASSWORD')
        print(username)
        print(password)
        print("Starting download...")
        

        download_links = [
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2015-12_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-03_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-04_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-05_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-06_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-07_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-08_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-09_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-01_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-02_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-03_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-04_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-05_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-06_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-07_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-09_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-10_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-12_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-01_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-02_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-03_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-06_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-11_1m_stateless.tar.lz4",
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2019-06_1m_stateless.tar.lz4"

        ]


        print("Downloading file by file...")

        for i, file in enumerate(download_links):
            print("Downloading {file}")
            download(file)









