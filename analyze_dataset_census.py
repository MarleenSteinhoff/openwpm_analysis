import os
import requests
from urllib.parse import urlparse
import pathlib
import sys
from clint.textui import progress


username = "census_user_1LyLrq"
password = "1zcZvRUfSiqKYmsd"


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


def download_and_manipulate(url, count=0):

    print(f"Downloading file {url}")

    current_folder = pathlib.Path(__file__).parent.resolve()

    #filename = os.path.join(current_folder, "datain", "file.lz4")
    #outfile = os.path.join(current_folder, "dataout", "file.sqlite")

    #print(f"file should be saved in {filename}")

    r = requests.get(url, auth=(username, password), stream=True)
    
    print(f"request resolved with code {r.status_code}")

    print(r.headers)

    filename = url.rsplit('/',1)[1]
    outfile = os.path.splitext(filename)[0]
    print(url)
    print(filename)

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

    #### DO SHIT HERE 
   
    os.system(f"lz4 -dc {filename} > {outfile}")
    os.system("python analyze_crawl.py /home/fsadmin/analysis_result/datain/ /home/fsadmin/analysis_result/dataout/")
    os.system(f"mv /home/fsadmin/analysis_result/dataout /home/fsadmin/analysis_result{filename}")

    ### END SHIT HERE

    print("finished, deleting downloaded archive and sql database...")
    os.remove(filename)
    os.remove(outfile)

if __name__ == "__main__":

    print("Starting download...")

    files = [
        "https://webtransparency.cs.princeton.edu/webcensus/samples/sample_2018-06_1m_stateless_census_crawl.sqlite.lz4"
    ]


    for i, file in enumerate(files):
        print("Downloading {file}")
        download_and_manipulate(file, count=i)


