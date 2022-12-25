import os
import json
import sys
import sqlite3
import traceback
from sqlite3 import OperationalError
import unicodedata as unicode
from tqdm import tqdm
import re
from time import time
from os.path import join, basename, sep, isdir
from collections import defaultdict
import crawl_utils.domain_utils as du
import pandas as pd

import util
from db_schema import (HTTP_REQUESTS_TABLE,
                       HTTP_RESPONSES_TABLE, SITE_VISITS_TABLE,
                       JAVASCRIPT_TABLE, OPENWPM_TABLES)
from util import dump_as_json, get_table_and_column_names, get_crawl_dir, \
    get_crawl_db_path

MIN_CANVAS_TEXT_LEN = 10
MIN_CANVAS_IMAGE_WIDTH = 16
MIN_CANVAS_IMAGE_HEIGHT = 16
CANVAS_READ_FUNCS = [
    "HTMLCanvasElement.toDataURL",
    "CanvasRenderingContext2D.getImageData"
]

CANVAS_WRITE_FUNCS = [
    "CanvasRenderingContext2D.fillText",
    "CanvasRenderingContext2D.strokeText"
]

CANVAS_FP_DO_NOT_CALL_LIST = ["CanvasRenderingContext2D.save",
                              "CanvasRenderingContext2D.restore",
                              "HTMLCanvasElement.addEventListener"]


def get_canvas_text(arguments):
    """Return the string that is written onto canvas from function arguments."""
    if not arguments:
        return ""
    canvas_write_args = json.loads(arguments)
    try:
        # cast numbers etc. to a unicode string
        return unicode(canvas_write_args["0"])
    except Exception:
        return ""


def are_get_image_data_dimensions_too_small(arguments):
    """Check if the retrieved pixel data is larger than min. dimensions."""
    # https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/getImageData#Parameters  # noqa
    get_image_data_args = json.loads(arguments)
    sw = int(get_image_data_args["2"])
    sh = int(get_image_data_args["3"])
    return (sw < MIN_CANVAS_IMAGE_WIDTH) or (sh < MIN_CANVAS_IMAGE_HEIGHT)


def get_canvas_fingerprinters(canvas_reads, canvas_writes, canvas_styles,
                              canvas_banned_calls, canvas_texts):
    canvas_fingerprinters = set()
    for script_address, visit_ids in canvas_reads.items():
        if script_address in canvas_fingerprinters:
            continue
        canvas_rw_visits = visit_ids. \
            intersection(canvas_writes[script_address])
        if not canvas_rw_visits:
            continue
        # we can remove the following, we don't use the style/color condition
        for canvas_rw_visit in canvas_rw_visits:
            # check if the script has made a call to save, restore or
            # addEventListener of the Canvas API. We exclude scripts making
            # these calls to eliminate false positives
            if canvas_rw_visit in canvas_banned_calls[script_address]:
                print("Excluding potential canvas FP script", script_address,
                      "visit#", canvas_rw_visit,
                      canvas_texts[(script_address, canvas_rw_visit)])
                continue
            canvas_fingerprinters.add(script_address)
            # print ("Canvas fingerprinter", script_address, "visit#",
            #       canvas_rw_visit,
            #       canvas_texts[(script_address, canvas_rw_visit)])
            break

    return canvas_fingerprinters


class CrawlDBAnalysis(object):

    def __init__(self, crawl_dir, out_dir):
        print("init")
        print("crawl dir")
        self.crawl_dir = get_crawl_dir(crawl_dir)
        print("crawl name")
        self.crawl_name = basename(crawl_dir.rstrip(sep))
        print("crawl path")
        self.crawl_db_path = get_crawl_db_path(self.crawl_dir)
        print("init db")
        self.init_db()
        print("out dir")
        self.out_dir = join(out_dir, "analysis")
        print("init out dir")
        self.init_out_dir()
        print("urls")
        self.suc_urls = defaultdict()
        self.num_suc_urls = defaultdict()


    def init_db(self):
        self.db_conn = sqlite3.connect(self.crawl_db_path)
        self.db_conn.row_factory = sqlite3.Row
        self.optimize_db()

    def init_out_dir(self):
        if not isdir(self.out_dir):
            os.makedirs(self.out_dir)

    def optimize_db(self, size_in_gb=20):
        """ Runs PRAGMA queries to make sqlite better """
        self.db_conn.execute("PRAGMA cache_size = -%i" % (size_in_gb * 10 ** 6))
        # Store temp tables, indices in memory
        self.db_conn.execute("PRAGMA temp_store = 2")
        # self.db_conn.execute("PRAGMA synchronous = NORMAL;")
        self.db_conn.execute("PRAGMA synchronous = OFF;")
        # self.db_conn.execute("PRAGMA journal_mode = WAL;")
        self.db_conn.execute("PRAGMA journal_mode = OFF;")
        self.db_conn.execute("PRAGMA page_size = 32768;")

    def get_visit_id_http_status_mapping(self):
        visit_id_http_status = {}
        for visit_id, response_status in self.db_conn.execute(
                "SELECT visit_id, response_status FROM http_responses"):
            if response_status == 200:
                visit_id_http_status[visit_id] = response_status
            else:
                continue

        print(len(visit_id_http_status), "mappings")
        print("Distinct site urls", len(set(visit_id_http_status.values())))
        return visit_id_http_status

    def get_visit_id_site_url_mapping(self):
        visit_id_site_urls = {}
        for visit_id, site_url in self.db_conn.execute(
                "SELECT visit_id, site_url FROM site_visits"):
            visit_id_site_urls[visit_id] = site_url
        print(len(visit_id_site_urls), "mappings")
        print("Distinct site urls", len(set(visit_id_site_urls.values())))
        return visit_id_site_urls


    def get_url_eff(self):
        t0 = time()
        url_dict = self.get_visit_id_site_url_mapping()
        url = pd.DataFrame(list(url_dict.items()), columns=['visit_id', "site_url"], index=url_dict.keys())

        http_dict = self.get_visit_id_http_status_mapping()
        result = url.loc[url['visit_id'].isin(http_dict.keys())]

        self.suc_urls = result['site_url'].tolist()
        self.num_suc_urls = len(result.index)

        print("Get_url_eff finished in %0.1f mins" % ((time() - t0) / 60))
        print("No urls: ", self.num_suc_urls)
        dump_as_json(self.suc_urls, join(self.out_dir, "%s_%s" % (self.crawl_name, "suc_urls.json")))
        dump_as_json(self.num_suc_urls, join(self.out_dir, "%s_%s" % (self.crawl_name, "num_suc_urls.json")))



if __name__ == '__main__':
    t0 = time()
    crawl_db_check = CrawlDBAnalysis("/crawler/url/2015-12_1m_stateless/", "/crawler/results")
    crawl_db_check.get_url_eff()
    print("Analysis finished in %0.1f mins" % ((time() - t0) / 60))
