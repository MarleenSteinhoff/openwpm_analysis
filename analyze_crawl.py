import os
import sys
import sqlite3
from time import time
from os.path import join, basename, sep, isdir
from collections import defaultdict
import util
from db_schema import (HTTP_REQUESTS_TABLE,
                       HTTP_RESPONSES_TABLE,
                       JAVASCRIPT_TABLE, OPENWPM_TABLES)
from util import dump_as_json, get_table_and_column_names, get_crawl_dir, \
    get_crawl_db_path


class CrawlDBAnalysis(object):

    def __init__(self, crawl_dir, out_dir):
        self.crawl_dir = get_crawl_dir(crawl_dir)
        self.crawl_name = basename(crawl_dir.rstrip(sep))
        self.crawl_db_path = get_crawl_db_path(self.crawl_dir)
        self.command_fail_rate = {}
        self.command_timeout_rate = {}
        self.init_db()
        self.out_dir = join(out_dir, "analysis")
        self.init_out_dir()
        self.visit_id_site_urls = self.get_visit_id_site_url_mapping()
        self.urls = self.get_urls_list()
        self.sv_num_requests = defaultdict(int)
        self.sv_num_responses = defaultdict(int)
        self.sv_num_javascript = defaultdict(int)
        self.sv_num_third_parties = defaultdict(int)
        self.num_entries_without_visit_id = defaultdict(int)
        self.num_entries = defaultdict(int)
        self.sv_third_parties = defaultdict(set)
        self.tp_to_publishers = defaultdict(set)
        self.rows_without_visit_id = 0

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

    def run_all_streaming_analysis(self):
        self.run_streaming_analysis_for_table(HTTP_REQUESTS_TABLE)
        self.run_streaming_analysis_for_table(HTTP_RESPONSES_TABLE)
        self.run_streaming_analysis_for_table(JAVASCRIPT_TABLE)

    def get_visit_id_site_url_mapping(self):
        visit_id_site_urls = {}
        for visit_id, site_url in self.db_conn.execute(
                "SELECT visit_id, site_url FROM site_visits"):
            visit_id_site_urls[visit_id] = site_url
        print(len(visit_id_site_urls), "mappings")
        print("Distinct site urls", len(set(visit_id_site_urls.values())))
        return visit_id_site_urls

    def get_visit_id_site_url_mapping_selection(self, url_list):
        visit_id_site_urls = {}
        not_in_subset = {}
        # modification: only visit_ids from sites that got crawled in all data sets
        for visit_id, site_url in self.db_conn.execute(
                "SELECT visit_id, site_url FROM site_visits"):
            if site_url in url_list:
                visit_id_site_urls[visit_id] = site_url
            else:
                not_in_subset[visit_id] = site_url
        print(len(visit_id_site_urls), "mappings")
        print("Distinct site urls in subset", len(set(visit_id_site_urls.values())))
        return visit_id_site_urls

    def get_urls_list(self):
        urls = []
        for visit_id, site_url in self.db_conn.execute(
                "SELECT visit_id, site_url FROM site_visits"):
            urls.append(site_url)
        return urls

    def run_streaming_analysis_for_table(self, table_name):
        current_visit_ids = {}
        processed = 0
        cols_to_select = ["visit_id", "crawl_id"]
        print("Will analyze %s" % table_name)
        if table_name == HTTP_REQUESTS_TABLE:
            cols_to_select.append("url")
            # check whether top_level_url is here
            # ultimately preprocesing will make sure all tables contain
            # top_level_url
            try:
                self.db_conn.execute("SELECT top_level_url FROM %s LIMIT 1" %
                                     table_name)
                cols_to_select.append("top_level_url")
            except Exception:
                pass

        query = "SELECT %s FROM %s" % (",".join(cols_to_select), table_name)
        for row in self.db_conn.execute(query):
            processed += 1
            visit_id = int(row["visit_id"])
            crawl_id = int(row["crawl_id"])
            if visit_id == -1:
                self.rows_without_visit_id += 1
                continue

            site_url = self.visit_id_site_urls[visit_id]
            if table_name == HTTP_REQUESTS_TABLE:
                # use top_level_url, otherwise fall back to top_url
                self.sv_num_requests[site_url] += 1
                top_url = None
                if "top_level_url" in row:
                    top_url = row["top_level_url"]
                if top_url is None:
                    top_url = self.visit_id_site_urls[visit_id]
                if top_url:
                    is_tp, req_ps1, _ = util.is_third_party(
                        row["url"], top_url)
                    if is_tp:
                        self.sv_third_parties[site_url].add(req_ps1)
                        self.sv_num_third_parties[site_url] = len(
                            self.sv_third_parties[site_url])
                        self.tp_to_publishers[req_ps1].add(site_url)
                else:
                    print("Warning, missing top_url", row)

            elif table_name == HTTP_RESPONSES_TABLE:
                self.sv_num_responses[site_url] += 1
            elif table_name == JAVASCRIPT_TABLE:
                self.sv_num_javascript[site_url] += 1

            if crawl_id not in current_visit_ids:
                current_visit_ids[crawl_id] = visit_id
            # end of the data from the current visit
            elif visit_id > current_visit_ids[crawl_id]:
                # self.process_visit_data(current_visit_data[crawl_id])
                # if site_url in self.sv_third_parties:
                #    del self.sv_third_parties[site_url]
                current_visit_ids[crawl_id] = visit_id
            elif visit_id < current_visit_ids[crawl_id] and visit_id > 0:
                # raise Exception(
                #    "Out of order row! Curr: %s Row: %s Crawl id: %s" %
                #    (current_visit_ids[crawl_id], visit_id, crawl_id))
                print(("Warning: Out of order row! Curr: %s Row: %s"
                       " Crawl id: %s" % (
                           current_visit_ids[crawl_id], visit_id, crawl_id)))

        self.dump_crawl_data(table_name)

    def print_num_of_rows(self):
        print("Will print the number of rows")
        db_schema_str = get_table_and_column_names(self.crawl_db_path)
        for table_name in OPENWPM_TABLES:
            # TODO: search in table names instead of the db schema
            if table_name in db_schema_str:
                try:
                    num_rows = self.db_conn.execute(
                        "SELECT MAX(id) FROM %s" % table_name).fetchone()[0]
                except sqlite3.OperationalError:
                    num_rows = self.db_conn.execute(
                        "SELECT COUNT(*) FROM %s" % table_name).fetchone()[0]
                if num_rows is None:
                    num_rows = 0
                print("Total rows", table_name, num_rows)

    def dump_urls_list(self):
        # self.dump_json(self.urls, "%s_%s" % ("urls_from", self.crawl_name))
        print()
        dump_as_json(self.urls, join(self.out_dir, "%s_%s" % (self.crawl_name, "url_list.json")))

    def dump_crawl_data(self, table_name):
        if table_name == HTTP_REQUESTS_TABLE:
            self.dump_json(self.sv_num_requests, "sv_num_requests.json")
            self.dump_json(self.sv_num_third_parties,
                           "sv_num_third_parties.json")
            # self.dump_json(self.sv_third_parties, "sv_third_parties.json")
            tp_to_publishers = {tp: "\t".join(publishers) for (tp, publishers)
                                in self.tp_to_publishers.items()}
            self.dump_json(tp_to_publishers, "tp_to_publishers.json")
        elif table_name == HTTP_RESPONSES_TABLE:
            self.dump_json(self.sv_num_responses, "sv_num_responses.json")
        elif table_name == JAVASCRIPT_TABLE:
            self.dump_json(self.sv_num_javascript, "sv_num_javascript.json")

    def dump_json(self, obj, out_file):
        dump_as_json(obj, join(self.out_dir, "%s_%s" % (self.crawl_name,
                                                        out_file)))

    def start_analysis(self):
        self.print_num_of_rows()
        self.check_crawl_history()
        self.run_all_streaming_analysis()
        self.dump_entries_without_visit_ids()

    def start_url_list(self):
        self.get_urls_list()
        self.dump_urls_list()

    def get_num_entries_without_visit_id(self, table_name):
        query = "SELECT count(*) FROM %s WHERE visit_id = -1;" % table_name
        try:
            return self.db_conn.execute(query).fetchone()[0]
        except Exception:
            return 0

    def get_num_entries(self, table_name):
        query = "SELECT count(*) FROM %s;" % table_name
        return self.db_conn.execute(query).fetchone()[0]

    def dump_entries_without_visit_ids(self):
        """All these metrics can be computed during the streaming analysis."""
        self.num_entries[HTTP_REQUESTS_TABLE] = self.get_num_entries(
            HTTP_REQUESTS_TABLE)
        self.num_entries_without_visit_id[HTTP_REQUESTS_TABLE] = \
            self.get_num_entries_without_visit_id(HTTP_REQUESTS_TABLE)

        self.num_entries[HTTP_RESPONSES_TABLE] = self.get_num_entries(
            HTTP_RESPONSES_TABLE)
        self.num_entries_without_visit_id[HTTP_RESPONSES_TABLE] = \
            self.get_num_entries_without_visit_id(HTTP_RESPONSES_TABLE)

        self.num_entries[JAVASCRIPT_TABLE] = self.get_num_entries(
            JAVASCRIPT_TABLE)
        self.num_entries_without_visit_id[JAVASCRIPT_TABLE] = \
            self.get_num_entries_without_visit_id(JAVASCRIPT_TABLE)

        self.dump_json(self.num_entries_without_visit_id,
                       "entries_without_visit_id.json")
        self.dump_json(self.num_entries, "num_entries.json")

    def check_crawl_history(self):
        """Compute failure and timeout rates for crawl_history table."""
        command_counts = {}  # num. of total commands by type
        fails = {}  # num. of failed commands grouped by cmd type
        timeouts = {}  # num. of timeouts
        for row in self.db_conn.execute(
                """SELECT command, count(*)
                FROM crawl_history
                GROUP BY command;""").fetchall():
            command_counts[row["command"]] = row["count(*)"]
            print("crawl_history Totals", row["command"], row["count(*)"])

        for row in self.db_conn.execute(
                """SELECT command, count(*)
                FROM crawl_history
                WHERE bool_success = 0
                GROUP BY command;""").fetchall():
            fails[row["command"]] = row["count(*)"]
            print("crawl_history Fails", row["command"], row["count(*)"])

        for row in self.db_conn.execute(
                """SELECT command, count(*)
                FROM crawl_history
                WHERE bool_success = -1
                GROUP BY command;""").fetchall():
            timeouts[row["command"]] = row["count(*)"]
            print("crawl_history Timeouts", row["command"], row["count(*)"])

        for command in list(command_counts.keys()):
            self.command_fail_rate[command] = (fails.get(command, 0) /
                                               command_counts[command])
            self.command_timeout_rate[command] = (timeouts.get(command, 0) /
                                                  command_counts[command])
            self.dump_json(self.command_fail_rate, "command_fail_rate.json")
            self.dump_json(self.command_timeout_rate,
                           "command_timeout_rate.json")


if __name__ == '__main__':
    t0 = time()
    # crawl_db_check = CrawlDBAnalysis(sys.argv[1], sys.argv[2])
    # crawl_db_check.start_analysis()

    crawl_db_check = CrawlDBAnalysis("/home/marleensteinhoff/UNi/Projektseminar/Datenanalyse/analysis/data",
                                     "/home/marleensteinhoff/UNi/Projektseminar/Datenanalyse/analysis/results")
    crawl_db_check.start_url_list()

    print("Analysis finished in %0.1f mins" % ((time() - t0) / 60))
