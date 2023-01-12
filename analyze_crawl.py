import os
import json
import sqlite3
from tqdm import tqdm
import re
from time import time
from os.path import join, basename, sep, isdir
from collections import defaultdict
import crawl_utils.domain_utils as du

import pandas as pd
import util
from util import get_visit_id_site_url_mapping
from db_schema import (HTTP_REQUESTS_TABLE,
                       HTTP_RESPONSES_TABLE, JAVASCRIPT_TABLE, OPENWPM_TABLES)
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
        self.out_dir = join(out_dir, self.crawl_name)
        self.init_out_dir()

        # mappings and selected ids
        self.visit_id_site_urls = get_visit_id_site_url_mapping(self.db_conn)
        self.visit_ids = self.visit_id_site_urls['visit_id'].tolist()
        self.suc_urls = defaultdict()
        self.num_suc_urls = defaultdict()

        # fingerprinting related variables
        self.num_js_calls = int
        self.most_common_canvas_API_calls = defaultdict(int)
        self.most_common_arguments_to_CanvasRenderingContext2D = defaultdict(int)
        self.canvas_fingerprinting_scripts = defaultdict

        # others

        self.sv_num_requests = defaultdict(int)
        self.sv_num_responses = defaultdict(int)
        self.sv_num_javascript = defaultdict(int)
        self.sv_num_third_parties = defaultdict(int)
        self.num_entries_without_visit_id = defaultdict(int)
        self.tracking_stats = defaultdict(int)
        self.num_entries = defaultdict(int)
        self.sv_third_parties = defaultdict(set)
        self.tp_to_publishers = defaultdict(set)
        self.rows_without_visit_id = 0

        self.no_javascript_calls = -1
        self.no_api_calls = -1
        self.no_session = -1
        self.no_canvas_fingerprinting = -1
        self.canvas_fingerprinters = defaultdict()


        self.no_canvas_fingerprinters = -1
        self.no_font_fp_firstpartysites = -1
        self.no_font_fp_thirdparties = -1
        self.font_fingerprinters = defaultdict(set)
        self.canvas_fingerprinters = defaultdict(set)
        self.canvas_fingerprinters_functions = defaultdict()

        self.http_only = -1
        self.js_session_cookies = -1

        self.no_cookies = -1
        self.no_sites_with_cookies = -1
        self.cookies_perSite = defaultdict()
        self.tracking_cookies = -1

        # fingerprinting condition variables
        self.MIN_CANVAS_TEXT_LEN = 10
        self.MIN_CANVAS_IMAGE_WIDTH = 16
        self.MIN_CANVAS_IMAGE_HEIGHT = 16
        self.CANVAS_READ_FUNCS = [
            "HTMLCanvasElement.toDataURL",
            "CanvasRenderingContext2D.getImageData"
        ]

        self.CANVAS_WRITE_FUNCS = [
            "CanvasRenderingContext2D.fillText",
            "CanvasRenderingContext2D.strokeText"
        ]

        self.CANVAS_FP_DO_NOT_CALL_LIST = ["CanvasRenderingContext2D.save",
                                           "CanvasRenderingContext2D.restore",
                                           "HTMLCanvasElement.addEventListener"]

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



    def get_url_eff(self):
        t0 = time()
        url_dict = get_visit_id_site_url_mapping(self.db_conn)
        url = pd.DataFrame(list(url_dict.items()), columns=['visit_id', "site_url"], index=url_dict.keys())

        http_dict = self.get_visit_id_http_status_mapping()
        result = url.loc[url['visit_id'].isin(http_dict.keys())]

        self.suc_urls = result['site_url'].tolist()
        self.num_suc_urls = len(result.index)

        print("Get_url_eff finished in %0.1f mins" % ((time() - t0) / 60))
        print("No urls: ", self.num_suc_urls)
        print(self.out_dir + "self.out_dir")
        print(self.crawl_name + "self.crawl_name")
        dump_as_json(self.suc_urls, join(self.out_dir, "%s_%s" % (self.crawl_name, "suc_urls.json")))
        dump_as_json(self.num_suc_urls, join(self.out_dir, "%s_%s" % (self.crawl_name, "num_suc_urls.json")))

    def run_streaming_analysis_for_table(self, table_name):
        current_visit_ids = {}
        processed = 0
        print(table_name)
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

        self.tracking_stats["javascript_calls"] = str(self.no_javascript_calls)
        self.tracking_stats["javascript_cookies_total"] = str(self.no_cookies)
        self.tracking_stats["no_sites_with_cookies"] = str(self.no_sites_with_cookies)
        self.tracking_stats["no_javascript_calls"] = str(self.no_javascript_calls)
        self.tracking_stats["no_api_calls"] = str(self.no_api_calls)
        self.tracking_stats["no_http_only"] = str(self.http_only)
        self.tracking_stats["is_session"] = str(self.js_session_cookies)
        self.tracking_stats["no_canvas_attempts"] = str(self.no_canvas_fingerprinting)
        self.tracking_stats["no_canvas_sites"] = str(self.no_canvas_fingerprinters)
        self.tracking_stats["no_font_sites"] = str(self.no_font_fp_firstpartysites)
        self.tracking_stats["no_font_3rdp"] = str(self.no_font_fp_thirdparties)

        dump_as_json(self.tracking_stats, join(self.out_dir, "%s_%s" % (self.crawl_name, "tracking_stats.json")))

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

    def start_fingerprinting_analysis(self, use_selected):
        if use_selected:
            selected_visit_ids = tuple(self.visit_ids)

            query = f'SELECT * FROM javascript WHERE visit_id IN {format(selected_visit_ids)}'
            # get selected URLs with corresponding visit_ids from database
            js = pd.read_sql_query(query, self.db_conn)

        else:
            js = pd.read_sql_query("SELECT * FROM javascript", self.db_conn)
        self.no_top_urls = len(set(js['visit_id']))
        self.get_canvas_fingerprinting(js, use_selected)
        self.get_font_fingerprinting(js)
        self.no_javascript_calls = len(js)

    def start_cookies_analysis(self):
        self.get_cookies()

    def dump_results(self):
        self.dump_urls_list()

    def list_for_query(self, list):
        return str(list)[1:-1]

    def get_font_fingerprinting(self, js):
        print("Number of javascript calls ", len(js))
        print("Distinct visit ids with javascript calls ", len(set(js['visit_id'])))

        # Helper columns with public suffix + 1
        js['script_ps1'] = js['script_url'].apply(lambda x: du.get_ps_plus_1(x) if x is not None else None)
        js['top_ps1'] = js['top_level_url'].apply(lambda x: du.get_ps_plus_1(x) if x is not None else None)
        js['document_ps1'] = js['document_url'].apply(lambda x: du.get_ps_plus_1(x) if x is not None else None)

        # Canvas function calls
        js_script_provider = js[(js.symbol == 'CanvasRenderingContext2D.measureText') & (js.script_ps1 != js.top_ps1)].groupby('script_ps1').top_ps1.count().sort_values(ascending=False)

        fp_measuretext = js[(js.symbol == 'CanvasRenderingContext2D.measureText') & (js.script_ps1 != js.top_ps1)]
        self.no_font_fp_firstpartysites = fp_measuretext['top_ps1'].nunique()
        self.no_font_fp_thirdparties = fp_measuretext['script_ps1'].nunique()
        self.font_fingerprinters = fp_measuretext.groupby('script_ps1').top_ps1.count().sort_values(ascending=False)

        font_shorthand = re.compile(
            r"^\s*(?=(?:(?:[-a-z]+\s*){0,2}(italic|oblique))?)(?=(?:(?:[-a-z]+\s*){0,2}(small-caps))?)(?=(?:(?:[-a-z]+\s*){0,2}(bold(?:er)?|lighter|[1-9]00))?)(?:(?:normal|\1|\2|\3)\s*){0,3}((?:xx?-)?(?:small|large)|medium|smaller|larger|[.\d]+(?:\%|in|[cem]m|ex|p[ctx]))(?:\s*\/\s*(normal|[.\d]+(?:\%|in|[cem]m|ex|p[ctx])))?\s*([-_\{\}\(\)\&!\',\*\.\"\sa-zA-Z0-9]+?)\s*$")
        # get fonts from 1st fingerprinting script provider
        url = js_script_provider.index[0]

        fonts = js[
            (js.symbol == 'CanvasRenderingContext2D.font') &
            (js.script_ps1 != js.top_ps1) &
            (js.script_ps1 == url)
            ].value.apply(lambda x: re.match(font_shorthand, x).group(6)).unique()

        self.fonts_first_fingerprinter = fonts


    def get_cookies(self):
        self.db_conn.row_factory = sqlite3.Row
        js = pd.read_sql_query(
            "SELECT * FROM javascript_cookies;",
            self.db_conn)

        self.no_cookies = js.size
        self.no_sites_with_cookies = js['visit_id'].size
        self.no_session = js.loc[js['is_session'] == 1]
        self.js_session_cookies = self.no_session.size
        self.http_only = js.loc[js['is_http_only'] == 1].size

        self.tracking_cookies = -1

        
        # self.cookies_perSite = self.no_session.groupby(['raw_host']).size().reset_index(name='# sites'). \
        #    sort_values(by=['# sites'], ascending=False)

    ## not implemented
    def get_redirection(self, con):
        # Load the data
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        redirects = pd.read_sql_query("SELECT old_channel_id, new_channel_id, visit_id FROM http_redirects"
                                      " WHERE old_channel_id IS NOT NULL AND is_sts_upgrade=0;", con)
        requests = pd.read_sql_query("SELECT url, channel_id FROM http_requests;", con)

        # build a map of channel_id to request url
        channel_id_to_url_map = dict(zip(requests.channel_id, requests.url))

        redirects["old_url"] = redirects["old_channel_id"].map(lambda x: channel_id_to_url_map.get(x, None))
        redirects["new_url"] = redirects["new_channel_id"].map(lambda x: channel_id_to_url_map.get(x, None))

        # Eliminate redirections that don't have a corresponding request in the http_requests table
        redirects = redirects[~redirects.new_url.isnull()]

        redirects['old_ps1'] = redirects['old_url'].apply(du.get_ps_plus_1)
        redirects['new_ps1'] = redirects['new_url'].apply(du.get_ps_plus_1)

        # only count redirections between different PS+1's
        redirects = redirects[redirects.old_ps1 != redirects.new_ps1]

        # only count a (src-dst) pair once on a website
        redirects.drop_duplicates(subset=["visit_id", "old_ps1", "new_ps1"], inplace=True)

        redirects.head()

        redirects.groupby(['old_ps1', 'new_ps1']).size().reset_index(name='# sites'). \
            sort_values(by=['# sites'], ascending=False)

    def get_canvas_fingerprinting(self, js, use_selected):
        #build query
        if use_selected:
            # use data from selected visit_ids
            selected_visit_ids = tuple(self.visit_ids)
            query = f"""SELECT sv.site_url, sv.visit_id,
                js.script_url, js.operation, js.arguments, js.symbol, js.value
                FROM javascript as js LEFT JOIN site_visits as sv
                ON sv.visit_id = js.visit_id WHERE
                js.script_url <> '' AND sv.visit_id IN {format(selected_visit_ids)}
                """

        else:
            query = """SELECT sv.site_url, sv.visit_id,
                js.script_url, js.operation, js.arguments, js.symbol, js.value
                FROM javascript as js LEFT JOIN site_visits as sv
                ON sv.visit_id = js.visit_id WHERE
                js.script_url <> ''
                """

        # test conn, all entries
        self.db_conn.row_factory = sqlite3.Row
        cur = self.db_conn.cursor()
        #

        # Add the helper column
        js['script_ps1'] = js['script_url'].apply(lambda x: du.get_ps_plus_1(x) if x is not None else None)

        # basic statistics
        self.num_js_calls = len(js)
        self.most_common_canvas_API_calls = js[js.operation == "call"].symbol.value_counts().head(20)
        self.most_common_arguments_to_CanvasRenderingContext2D = js[(js.operation == "call") &
                                                                    (js.symbol == "CanvasRenderingContext2D.fillText")
                                                                    ].arguments.value_counts().head(20)

        canvas_reads = defaultdict(set)
        canvas_writes = defaultdict(set)
        canvas_texts = defaultdict(set)
        canvas_banned_calls = defaultdict(set)
        canvas_styles = defaultdict(lambda: defaultdict(set))

        # start streaming analysis
        for row in tqdm(cur.execute(query)):
            # visit_id, script_url, operation, arguments, symbol, value = row[0:6]
            visit_id = row["visit_id"]
            site_url = row["site_url"]
            script_url = row["script_url"]
            operation = row["operation"]
            arguments = row["arguments"]
            symbol = row["symbol"]
            value = row["value"]

            # Exclude relative URLs, data urls, blobs
            if not (script_url.startswith("http://")
                    or script_url.startswith("https://")):
                continue
            if symbol in self.CANVAS_READ_FUNCS and operation == "call":
                if (symbol == "CanvasRenderingContext2D.getImageData" and
                        self.are_get_image_data_dimensions_too_small(arguments)):
                    continue
                canvas_reads[script_url].add(visit_id)
            elif symbol in self.CANVAS_WRITE_FUNCS:
                text = self.get_canvas_text(arguments)

                # Python miscalculates the length of unicode strings that contain
                # surrogate pairs such as emojis. This make strings look longer
                # than they really are, and is causing false positives.
                # For instance length of "🏴󠁧", which is written onto canvas by
                # Wordpress to check emoji support, is returned as 13.
                # We ignore non-ascii characters to prevent false positives.
                # Perhaps a good idea to log such cases to prevent real fingerprinting
                # scripts to slip in.
                if len(text.encode('ascii', 'ignore')) >= self.MIN_CANVAS_TEXT_LEN:
                    canvas_writes[script_url].add(visit_id)
                    # the following is used to debug false positives
                    canvas_texts[(script_url, visit_id)].add(text)
            elif symbol == "CanvasRenderingContext2D.fillStyle" and \
                    operation == "call":
                canvas_styles[script_url][visit_id].add(value)
            elif operation == "call" and symbol in self.CANVAS_FP_DO_NOT_CALL_LIST:
                canvas_banned_calls[script_url].add(visit_id)
        # get fingerprinting urls

        canvas_fingerprinters = self.get_canvas_fingerprinters(canvas_reads,
                                                          canvas_writes,
                                                          canvas_styles,
                                                          canvas_banned_calls,
                                                          canvas_texts)

        self.no_canvas_fingerprinters = len(canvas_fingerprinters)
        self.canvas_fingerprinters = canvas_fingerprinters

        # Mark canvas fingerprinting scripts in the dataframe
        js["canvas_fp"] = js["script_url"].map(lambda x: x in self.canvas_fingerprinters)
        # Extract first arguments of function calls as a separate column
        js["arg0"] = js["arguments"].map(lambda x: json.loads(x)["0"] if x else "")

        self.canvas_fingerprinting_scripts = js[
            js.canvas_fp & (js.operation == "call") & (js.symbol == "CanvasRenderingContext2D.fillText")
            ].rename({"arg0": "canvas_text"}, axis='columns')[["top_level_url", "script_ps1", "canvas_text"]]. \
            drop_duplicates()


    def are_get_image_data_dimensions_too_small(self, arguments):
        """Check if the retrieved pixel data is larger than min. dimensions."""
        # https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/getImageData#Parameters  # noqa
        get_image_data_args = json.loads(arguments)

        sw = int(get_image_data_args["2"])
        sh = int(get_image_data_args["3"])
        return (sw < self.MIN_CANVAS_IMAGE_WIDTH) or (sh < self.MIN_CANVAS_IMAGE_HEIGHT)

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
        try:
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
        except sqlite3.OperationalError:
            pass

    def get_canvas_fingerprinters(self, canvas_reads, canvas_writes, canvas_styles,
                                  canvas_banned_calls, canvas_texts):
        print('canvas_reads:', canvas_reads)
        print('canvas_writes:', canvas_writes)
        print('canvas_styles:', canvas_styles)
        print('canvas_banned_calls:', canvas_banned_calls)
        print('canvas_texts:', canvas_texts)

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

    def get_canvas_text(self, arguments):
        """Return the string that is written onto canvas from function arguments."""
        if not arguments:
            return ""
        canvas_write_args = json.loads(arguments)
        try:
            # cast numbers etc. to a unicode string
            unicode = str(canvas_write_args["0"])
            return unicode
        except Exception:
            return ""

    def are_get_image_data_dimensions_too_small(self, arguments):
        """Check if the retrieved pixel data is larger than min. dimensions."""
        # https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/getImageData#Parameters  # noqa
        get_image_data_args = json.loads(arguments)
        sw = int(get_image_data_args["2"])
        sh = int(get_image_data_args["3"])
        return (sw < self.MIN_CANVAS_IMAGE_WIDTH) or (sh < self.MIN_CANVAS_IMAGE_HEIGHT)


if __name__ == '__main__':
    t0 = time()
    # crawl_db_check = CrawlDBAnalysis(sys.argv[1], sys.argv[2], sys.argv[3])
    crawl_db_check = CrawlDBAnalysis('/home/marleensteinhoff/UNi/Projektseminar/Datenanalyse',
                                     '/home/marleensteinhoff/UNi/Projektseminar/Datenanalyse/data/results')
    crawl_db_check.start_fingerprinting_analysis(True)
    # crawl_db_check.get_url_eff()
    print("Analysis finished in %0.1f mins" % ((time() - t0) / 60))
