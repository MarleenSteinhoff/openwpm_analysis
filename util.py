import sqlite3
import json
import pandas as pd
from time import time
from multiprocessing import Process

import pandas
from tld import get_tld
import ipaddress
from os.path import join, isfile,  isdir, dirname
import glob
from shutil import copyfile
try:
    from urllib.parse import urlparse
except ImportError:
    from urllib.parse import urlparse


CRAWL_DB_EXT = ".sqlite"
DB_SCHEMA_SUFFIX = "_db_schema.txt"
# print progress every million rows
PRINT_PROGRESS_EVERY = 10**6


def load_alexa_ranks(alexa_csv_path):
    site_ranks = dict()
    for line in open(alexa_csv_path):
        parts = line.strip().split(',')
        site_ranks[parts[1]] = int(parts[0])
    return site_ranks


def get_column_names(table_name, cursor):
    """Return the column names for a table.

    Modified from https://stackoverflow.com/a/38854129
    """
    cursor.execute("SELECT * FROM %s" % table_name)
    return " ".join([member[0] for member in cursor.description])


def get_table_and_column_names(db_path):
    """Return the table and column names for a database.

    Modified from: https://stackoverflow.com/a/33100538
    """
    db_schema_str = ""
    db = sqlite3.connect(db_path)
    cursor = db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    for table_name in cursor.fetchall():
        table_name = table_name[0]
        db_schema_str += "%s %s\n" % (table_name, get_column_names(table_name,
                                                                   cursor))
    return db_schema_str


def start_worker_processes(worker_function, queue, num_workers=1):
    workers = []
    for _ in range(num_workers):
        worker_proc = Process(target=worker_function, args=(queue,))
        worker_proc.start()
        workers.append(worker_proc)
    return workers


def get_tld_or_host(url):
    try:
        return get_tld(url, fail_silently=False)
    except Exception:
        hostname = urlparse(url).hostname
        try:
            ipaddress.ip_address(hostname)
            return hostname
        except Exception:
            return None


def is_third_party(req_url, top_level_url):
    # TODO: when we have missing information we return False
    # meaning we think this is a first-party
    # let's make sure this doesn't have any strange side effects
    # We can also try returning `unknown`.
    if not top_level_url:
        return (None, "", "")

    site_ps1 = get_tld_or_host(top_level_url)
    if site_ps1 is None:
        return (None, "", "")

    req_ps1 = get_tld_or_host(req_url)
    if req_ps1 is None:
        # print url
        return (None, "", site_ps1)
    if (req_ps1 == site_ps1):
        return (False, req_ps1, site_ps1)

    return (True, req_ps1, site_ps1)

def get_successfull_crawled_ids(db):
    suc_visit_ids = set()
    for visit_id, response_status in db.execute(
        "SELECT visit_id, response_status FROM http_responses"):
        if response_status == 200:
            suc_visit_ids.add(visit_id)
        else:
            continue
    return suc_visit_ids
def get_visit_id_http_status_mapping(db):
    visit_id_http_status = {}
    for visit_id, response_status in db.execute(
        "SELECT visit_id, response_status FROM http_responses"):
        if response_status == 200:
            visit_id_http_status[visit_id] = response_status
        else:
            continue

        print(len(visit_id_http_status), "mappings")
        print("Distinct site urls", len(set(visit_id_http_status.values())))
    return visit_id_http_status, len(visit_id_http_status)


def copy_if_not_exists(src, dst):
    if not isfile(dst):
        print("Copying %s to %s" % (src, dst))
        copyfile(src, dst)


def read_json(json_path):
    return json.load(open(json_path))


def dump_as_json(obj, json_path):
    with open(json_path, 'w') as f:
        json.dump(obj, f)


def get_crawl_db_path(crawl_dir):
    sqlite_files = glob.glob(join(crawl_dir, "*" + CRAWL_DB_EXT))
    assert len(sqlite_files) == 1
    return sqlite_files[0]


def get_crawl_dir(crawl_dir):
    if isdir(crawl_dir):
        return crawl_dir
    else:
        print("Missing crawl dir (archive name mismatch)", crawl_dir)
        crawl_dir_pattern = join(dirname(crawl_dir), "*201*")
        crawl_dir = glob.glob(crawl_dir_pattern)
        print(len(crawl_dir))
        assert len(crawl_dir) == 1
        return crawl_dir[0]


def print_progress(t0, processed, num_rows):
    if processed % PRINT_PROGRESS_EVERY == 0:
        elapsed = time() - t0
        speed = processed / elapsed
        progress = 100 * processed / num_rows
        remaining = (num_rows - processed) / speed
        print("Processed: %iK (%0.2f%%) Speed: %d rows/s | Elapsed %0.2f"\
            " | Remaining %d mins" % (
                processed/1000, progress, speed, elapsed, remaining / 60))

    # run get_url_visit_id_mapping for a subset of given urls
    # analysis will be performed with the given URLs only
def get_visit_id_site_url_mapping(db_file):
    db_conn = sqlite3.connect(db_file)
    cur = db_conn.cursor()
    # TODO: set json file as varibale
    visit_ids = pd.read_json('suc_urls_24.json')
    visit_ids.columns = ['url']

    data = tuple(visit_ids)
    with open('suc_urls_24.json') as json_file:
        data = json.load(json_file)
    # selected URLs
    site_urls = tuple(data)

    query = f'SELECT visit_id, site_url FROM site_visits WHERE site_url IN {format(site_urls)}'
    # get selected URLs with corresponding visit_ids from database
    visit_id_site_urls = pd.read_sql_query(query, db_conn)
    print(len(data), "URLs in the given URL list")
    print(len(visit_id_site_urls), "visit_id-mappings found to the given list")

    return visit_id_site_urls