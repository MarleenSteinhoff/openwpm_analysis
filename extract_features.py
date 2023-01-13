# -*- coding: utf-8 -*-
# packages changed for python 3
# pip install adblockparser

import sys
from analyze_crawl import get_crawl_db_path, get_crawl_dir
import ast
import sqlite3
from pqdm.processes import pqdm
from tqdm import tqdm
import re
import time
import json
from datetime import datetime
import pandas as pd
import pickle
from functools import reduce
from urllib.parse import urlparse
from os.path import realpath, join, basename, sep
from _collections import defaultdict

# https://github.com/scrapinghub/adblockparser
from adblockparser import AdblockRules
from util import dump_as_json, get_visit_id_http_status_mapping, get_successfull_crawled_ids, \
    get_visit_id_site_url_mapping
from analysis_utils.utils import (is_third_party, is_blocked_by_disconnect,
                                  get_disconnect_blocked_hosts, get_delta_timespan)

OUTDIR = ""
CRAWL_NAME = ""
DEBUG = False

# search for the occurences of ublock after enabling this switch
ENABLE_UBLOCK = False
# Only lookup scripts with sensor access
CHECK_ADBLOCK_STATUS_OF_ALL_JS = True  # False means we only check
# scripts with sensor access
DB = ''
NO_RANK = []
CONTAINS_NONE_RANKS = []
DB_NAME = ''
RESULTS_PATH = "/home/marleensteinhoff/UNi/Projektseminar/Datenanalyse/analysis/data/results"
# standard JavaScript, DOM events
JS_EVENTS = \
    ["DOMContentLoaded", "DOMMouseScroll", "abort", "afterprint",
     "animationend", "animationiteration", "animationstart",
     "appinstalled", "auxclick", "beforeinstallprompt",
     "beforeprint", "beforescriptexecute", "beforeunload",
     "blur", "canplay", "canplaythrough", "change",
     "chargingchange", "chargingtimechange", "click",
     "compassneedscalibration", "complete", "contextmenu",
     "copy", "cut", "dblclick", "devicechange", "devicelight",
     "devicemotion", "deviceorientation", "deviceproximity",
     "dischargingtimechange", "drag", "dragend", "dragenter",
     "dragleave", "dragover", "dragstart", "drop", "durationchange",
     "emptied", "ended", "error", "focus", "focusin", "focusout",
     "fullscreenchange", "gamepadconnected", "hashchange", "input",
     "invalid", "keydown", "keypress", "keyup", "levelchange",
     "load", "loadeddata", "loadedmetadata", "loadstart", "localized",
     "message", "mousedown", "mouseenter", "mouseleave", "mousemove",
     "mouseout", "mouseover", "mouseup", "notificationclick",
     "offline", "online", "orientationchange", "overflow", "pagehide",
     "pageshow", "paste", "pause", "play", "playing", "pointercancel",
     "pointerdown", "pointerleave", "pointermove", "pointerover",
     "pointerup", "popstate", "progress", "push", "ratechange",
     "readystatechange", "reset", "resize", "scroll", "seeked",
     "seeking", "select", "show", "stalled", "start", "statechange",
     "storage", "submit", "suspend", "timeupdate", "touchcancel",
     "touchend", "touchenter", "touchleave", "touchmove", "touchstart",
     "transitionend", "transitionstart", "unload", "userproximity",
     "visibilitychange", "volumechange", "vrdisplayactivate",
     "vrdisplaydeactivate", "vrdisplaypresentchange", "waiting", "wheel"]


class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


def get_event_feature(arguments, symbol):
    arguments_obj = json.loads(arguments)
    event_name = arguments_obj["0"]
    if event_name in JS_EVENTS:
        return "addEventListener_" + event_name
    else:  # custom event
        if DEBUG and event_name != "test":
            print("Custom Event:", event_name)
        return "addEventListener_CUSTOM_EVENT"


def get_simple_feature_from_js_info(operation, arguments, symbol):
    if symbol.endswith("addEventListener") and operation == "call":
        return get_event_feature(arguments, symbol)
    elif operation == "call":
        return "call_" + symbol
    elif operation == "get":
        return "get_" + symbol
    elif operation == "set":
        return "set_" + symbol


CANVAS_READ_FUNCS = [
    "HTMLCanvasElement.toDataURL",
    "CanvasRenderingContext2D.getImageData"
]

CANVAS_WRITE_FUNCS = [
    "CanvasRenderingContext2D.fillText",
    "CanvasRenderingContext2D.strokeText"
]

"""
Criteria 3 from Englehardt & Narayanan, 2016
"3. The script should not call the save, restore, or addEventListener
methods of the rendering context."
`addEventListener` is (can) only called for HTMLCanvasElement, so we use that.
"""
CANVAS_FP_DO_NOT_CALL_LIST = ["CanvasRenderingContext2D.save",
                              "CanvasRenderingContext2D.restore",
                              "HTMLCanvasElement.addEventListener"]
AUDIO_CONTEXT_FUNCS = [
    "OfflineAudioContext.createOscillator",
    "OfflineAudioContext.createDynamicsCompressor",
    "OfflineAudioContext.destination",
    "OfflineAudioContext.startRendering",
    "OfflineAudioContext.oncomplete"
]

WEBRTC_FP_CALLS = ["RTCPeerConnection.createDataChannel",
                   "RTCPeerConnection.createOffer"]

# Functions to get the charging time
BATTERY_CHARGING_TIME_CALLS = ["BatteryManager.chargingTime",
                               "BatteryManager.onchargingtimechange"]

# Functions to get the discharging time
BATTERY_DISCHARGING_TIME_CALLS = ["BatteryManager.dischargingTime",
                                  "BatteryManager.ondischargingtimechange"]
# cookie features
NUM_COOKIE_SETTERS = "num_cookie_setters"
NUM_COOKIE_TOTAL = "num_cookie_total"
NUM_SESSION_COOKIES = "num_session_cookies"
NUM_TRACKING_COOKIES = "num_tracking_cookies"
NUM_HTTP_COOKIES = "num_http_cookies"
NUM_VERY_LONG_COOKIE = "num_very_long_cookie"
NUM_LONG_COOKIE = "num_long_cookie"
NUM_CRAWLED_URLS = "num_crawled_urls"
COOKIE_SETTERS = "cookie_setters"

PER_JS_COOKIES = "per_js_cookies"
PER_COOKIE_TOTAL = "per_cookie_total"
PER_SESSION_COOKIES = "per_session_cookies"
PER_TRACKING_COOKIES = "per_tracking_cookies"
PER_HTTP_COOKIES = "per_http_cookies"
PER_HTTP_ONLY = "per_http_only"
PER_VERY_LONG_COOKIE = "per_very_long_cookie"
PER_LONG_COOKIE = "per_long_cookie"

TRACKING_SITE_URLS = "tracking_site_urls"
SITEURL_COOKIE_MAPPING = "siteurl_cookie_mapping"

# count high level features
NUM_CANVAS_FP = "num_canvas_fingerprinting"
NUM_CANVAS_FONT_FP = "num_canvas_font_fingerprinting"
NUM_AUDIO_CTX_FP = "num_audio_context_fingerprinting"
NUM_WEBRTC_FP = "num_webrtc_fingerprinting"
NUM_BATTERY_FP = "num_battery_fingerprinting"
NUM_TRIGGERS_REQUEST = "num_triggers_requests"
NUM_TRIGGERS_TP_REQUEST = "num_triggers_third_party_requests"
NUM_EASYLIST_BLOCKED = "num_easylist_blocked"
NUM_EASYPRIVACY_BLOCKED = "num_easyprivacy_blocked"
# NUM_UBLOCK_ORIGIN_BLOCKED = "num_ublockorigin_blocked"
NUM_DISCONNECT_BLOCKED = "num_disconnect_blocked"
NUM_THIRD_PARTY_SCRIPT = "num_third_party_script"

COUNT_FEATURES = [NUM_CANVAS_FP, NUM_CANVAS_FONT_FP, NUM_AUDIO_CTX_FP,
                  NUM_WEBRTC_FP, NUM_BATTERY_FP,
                  NUM_TRIGGERS_REQUEST, NUM_TRIGGERS_TP_REQUEST,
                  NUM_EASYLIST_BLOCKED, NUM_EASYPRIVACY_BLOCKED,
                  # UBLOCK_ORIGIN_BLOCKED,
                  NUM_DISCONNECT_BLOCKED,
                  NUM_THIRD_PARTY_SCRIPT]
# Cookie features
FB_COOKIEMONSTER_BLOCKED = "cookiemonster_blocked"
JS_COOKIES = "javascript_cookies"
TRACKING_COOKIES = "tracking_cookies"
HTTP_COOKIES = "http_cookies"
THRD_PARTY_COOKIES = "third_party_cookies"

# High level features
CANVAS_FP = "canvas_fingerprinting"
CANVAS_FONT_FP = "canvas_font_fingerprinting"
AUDIO_CTX_FP = "audio_context_fingerprinting"
WEBRTC_FP = "webrtc_fingerprinting"
BATTERY_FP = "battery_fingerprinting"
TRIGGERS_REQUEST = "triggers_requests"
TRIGGERS_TP_REQUEST = "triggers_third_party_requests"
EASYLIST_BLOCKED = "easylist_blocked"
EASYPRIVACY_BLOCKED = "easyprivacy_blocked"
UBLOCK_ORIGIN_BLOCKED = "ublockorigin_blocked"
DISCONNECT_BLOCKED = "disconnect_blocked"
THIRD_PARTY_SCRIPT = "third_party_script"

HIGH_LEVEL_FEATURES = [CANVAS_FP, CANVAS_FONT_FP, AUDIO_CTX_FP,
                       WEBRTC_FP, BATTERY_FP,
                       TRIGGERS_REQUEST, TRIGGERS_TP_REQUEST,
                       EASYLIST_BLOCKED, EASYPRIVACY_BLOCKED,
                       # UBLOCK_ORIGIN_BLOCKED,
                       DISCONNECT_BLOCKED,
                       THIRD_PARTY_SCRIPT]

MIN_CANVAS_TEXT_LEN = 10
MIN_CANVAS_IMAGE_WIDTH = 16
MIN_CANVAS_IMAGE_HEIGHT = 16


def get_canvas_text(arguments):
    if not arguments:
        return ""
    canvas_write_args = json.loads(arguments)
    try:
        # cast numbers etc. to string
        return str(canvas_write_args["0"])
    except Exception:
        try:
            # for non-ascii strings
            return str(canvas_write_args["0"].encode("utf-8"))
        except Exception:
            # if we cannot decode a call's arguments we exclude it
            # from the analysis to prevent false positives
            return ""


def safe_int(string):
    """Convert string to int, return 0 if conversion fails."""
    try:
        return int(string)
    except ValueError:
        return 0


def is_get_image_data_dimensions_too_small(arguments):
    """Check if the retrieved canvas data is greater than min dimensions."""
    # https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/getImageData#Parameters  # noqa
    get_image_data_args = json.loads(arguments)
    sw = safe_int(get_image_data_args.get("2", 0))
    sh = safe_int(get_image_data_args.get("3", 0))
    MIN_CANVAS_IMAGE_WIDTH = 16
    return (sw < MIN_CANVAS_IMAGE_WIDTH) or (sh < MIN_CANVAS_IMAGE_HEIGHT)


def get_base_script_url(script_url):
    return script_url.split("//")[1].split("/")[0]


def get_script_freqs_from_db(db_file, max_rank=None):
    """Return a frequency count for each script."""
    connection = sqlite3.connect(db_file)
    c = connection.cursor()

    query = """SELECT visit_id, script_url FROM javascript WHERE
        script_url <> ''
        """
    if max_rank is not None:
        query += " AND visit_id <= %i" % max_rank

    overall_script_ranks = defaultdict(set)
    for row in c.execute(query):
        visit_id, script_url = row[0:2]
        # Exclude scripts with visit_id = -1
        # This happens when OpenWPM doesn't know which visit a script belong to
        if visit_id == -1:
            continue
        # Exclude relative URLs, data urls, blobs
        if not (script_url.startswith("http://")
                or script_url.startswith("https://")):
            continue
        script_adress = get_base_script_url(script_url)
        overall_script_ranks[script_adress].add(visit_id)
    return overall_script_ranks


# This list is only used to decide if
# we want to check adblock status of scripts.
# We'll probably won'tuse userprosimity
# but let's save the adblocked status of the scripts accessing userproximity
SENSOR_FEATURES = [
    "addEventListener_devicelight",
    "addEventListener_deviceorientation",
    "addEventListener_deviceproximity",
    "addEventListener_devicemotion"
    # ,"addEventListener_userproximity"
]
"""
    #query = "SELECT * FROM javascript_cookies"
    js_cookies = pd.read_sql_query(query, connection)
    b = js_cookies.loc[js_cookies["is_session"] == 1]
    d = js_cookies.size
 """


def get_cookies(db_file, id_urls_map=tuple(), max_rank=None):
    print("get_cookies")
    # database conn
    db = sqlite3.connect(db_file)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    num_cookie_total = 0
    num_session_cookies = 0
    num_tracking_cookies = 0
    num_http_cookies = 0
    num_very_long_cookie = 0
    num_long_cookie = 0
    num_crawled_urls = len(id_urls_map)
    tracking_site_urls = defaultdict()
    site_url_host_mapping = defaultdict(set)
    tracker_urls = set()
    tracking_cookie_invalid_date = defaultdict(set)


    if CRAWL_NAME in ["2016-03", "2016-04", "2016-05", "2016-06", "2016-08", "2016-09", "2017-01", "2017-02",
                      "2017-03"]:
        print("old scheme")
        # no session and domain cookies
        query = f"""SELECT js.visit_id,
                       js.name, js.path, js.creationTime, js.expiry, js.value, 
                        js.host, sv.site_url FROM profile_cookies as js LEFT JOIN site_visits as sv
                                ON sv.visit_id = js.visit_id WHERE js.visit_id IN {format(id_urls_map)} ;
                                """
    else:
        print("else")
        query_session = f"""SELECT js.visit_id,  js.is_session, sv.site_url
                         FROM javascript_cookies as js LEFT JOIN site_visits as sv
                         ON sv.visit_id = js.visit_id WHERE js.visit_id IN {format(id_urls_map)} AND js.is_session = 1;
                         """

        session_df = pd.read_sql_query(query_session, db)
        num_session_cookies = session_df["visit_id"].size
        print("session_cookies calculated")

        # no session and domain cookies
        query = f"""SELECT js.visit_id, js.is_http_only, 
                js.name, js.path, js.creationTime, js.expiry, js.value, js.is_session, 
                js.policy, js.host, js.is_domain, 
                js.is_secure,  js.change, sv.site_url
                         FROM javascript_cookies as js LEFT JOIN site_visits as sv
                         ON sv.visit_id = js.visit_id WHERE js.visit_id IN {format(id_urls_map)} AND js.is_session = 0 AND js.is_domain = 0;
                         """

    if max_rank is not None:
        query += " AND visit_id <= %i" % max_rank
    print(query)
    print("Starting get_cookie analysis")
    for row in tqdm(c.execute(query).fetchall()):
        num_cookie_total += 1
        visit_id = row["visit_id"]
        is_http_only = row["is_http_only"]
        value = row["value"]
        is_session = row["is_session"]
        is_domain = row["is_domain"]
        change = row["change"]
        site_url = row["site_url"]
        creationtime = row["creationTime"]
        expiry = row["expiry"]
        host = row["host"]

        if is_domain == 0:
            # (1) the cookie has an expiration date over 90 days in the future
            if creationtime == "Invalid Date" or expiry == "Invalid Date":
                if site_url in tracking_cookie_invalid_date:
                    tracking_cookie_invalid_date[site_url] = value
                else:
                    tracking_cookie_invalid_date[site_url].add(value)

                print("invalid date")
                continue

            timespan = get_delta_timespan(creationtime, expiry)
            if timespan < 90:
                continue

            # (2) 8 ≤ length(parameter-value) ≤ 100 CHANGED
            length = len(value)
            if (length < 8) or (length > 150):
                continue

            # (3) the parametervalue remains the same throughout the measurement
            if change == "changed" or change == "deleted":
                continue

            else:
                if is_http_only == 1:
                    num_http_cookies += 1

                if timespan >= 365:
                    num_very_long_cookie += 1
                else:
                    num_long_cookie += 1

                num_tracking_cookies += 1
                tracker_urls.add(site_url)
                try:
                    tracking_site_urls[site_url] += 1
                except KeyError:
                    tracking_site_urls[site_url] = 0
                try:
                    site_url_host_mapping[site_url].add(host)
                except KeyError:
                    site_url_host_mapping[site_url] = host

    num_cookie_setters = len(tracker_urls)

    print("get_cookies done, saving results")
    cookie_feat_dict = {
        NUM_COOKIE_SETTERS: num_cookie_setters,
        NUM_COOKIE_TOTAL: num_cookie_total,
        NUM_SESSION_COOKIES: num_session_cookies,
        NUM_TRACKING_COOKIES: num_tracking_cookies,
        NUM_HTTP_COOKIES: num_http_cookies,
        NUM_VERY_LONG_COOKIE: num_very_long_cookie,
        NUM_LONG_COOKIE: num_long_cookie,
        NUM_CRAWLED_URLS: num_crawled_urls,
    }

    tracking_sites_dict = {
        COOKIE_SETTERS: tracker_urls,
        TRACKING_SITE_URLS: tracking_site_urls
    }

    with open(join(OUT_DIR, "%s_%s" % (CRAWL_NAME, "tracking_cookie_invalid_date.json")), 'w') as fp:
        json_string = json.dumps(tracking_cookie_invalid_date, indent=4, cls=SetEncoder)
        fp.write(json_string)

    with open(join(OUT_DIR, "%s_%s" % (CRAWL_NAME, "cookie_features.json")), 'w') as fp:
        json_string = json.dumps(cookie_feat_dict, indent=4, cls=SetEncoder)
        fp.write(json_string)

    with open(join(OUT_DIR, "%s_%s" % (CRAWL_NAME, "tracking_sites_dict.json")), 'w') as fp:
        json_string = json.dumps(tracking_sites_dict, indent=4, cls=SetEncoder)
        fp.write(json_string)


def extract_features(db_file, out_csv, id_urls_map=defaultdict(), max_rank=None):
    print("extract_features")
    """Extract fingerprinting related features from the javascript table
    of the crawl database.
    Although we use script_url to attribute the access or the function call,
    it may not always give the right script.
    For instance when a script uses jquery to listen to sensor events we'll
    attribute the (e.g. sensor related) event listening to jquery. The script
    that uses jquery should still be in the call_stack, but not necessarily at
    the top or bottom).
    TODO: use call_stack to get other potential scripts.
    The problem is how to do the attribution then, assign all access to all
    scripts that appear in the call_stack?"""

    # high level features
    canvas_reads = defaultdict(set)
    canvas_writes = defaultdict(set)
    canvas_texts = defaultdict(set)
    canvas_banned_calls = defaultdict(set)
    canvas_styles = defaultdict(lambda: defaultdict(set))
    battery_level_access = defaultdict(set)
    battery_charging_time_access = defaultdict(set)
    battery_discharging_time_access = defaultdict(set)
    audio_ctx_calls = defaultdict(lambda: defaultdict(set))
    webrtc_calls = defaultdict(lambda: defaultdict(set))
    canvas_used_fonts = defaultdict(lambda: defaultdict(set))
    canvas_measure_text_calls = defaultdict(int)

    # simple features
    script_ranks = defaultdict(set)  # site ranks where a script is embedded
    script_features = defaultdict(set)
    adblock_checked_scripts = set()  # to prevent repeated lookups
    third_party_scripts = set()

    overall_script_ranks = get_script_freqs_from_db(db_file)

    connection = sqlite3.connect(db_file)
    connection.row_factory = sqlite3.Row
    c = connection.cursor()

    if id_urls_map:

        query = f"""SELECT sv.site_url, sv.visit_id,
                js.script_url, js.operation, js.arguments, js.symbol, js.value
                FROM javascript as js LEFT JOIN site_visits as sv
                ON sv.visit_id = js.visit_id WHERE
                js.script_url <> '' AND js.visit_id IN {format(id_urls_map)}
                """

    else:
        query = """SELECT sv.site_url, sv.visit_id,
            js.script_url, js.operation, js.arguments, js.symbol, js.value
            FROM javascript as js LEFT JOIN site_visits as sv
            ON sv.visit_id = js.visit_id WHERE
            js.script_url <> ''
            """


    if max_rank is not None:
        query += " AND visit_id <= %i" % max_rank

    print("Starting feature extraction")
    for row in tqdm(c.execute(query).fetchall()):
        visit_id = row["visit_id"]
        site_url = row["site_url"]
        script_url = row["script_url"]
        operation = row["operation"]
        symbol = row["symbol"]
        value = row["value"]
        arguments = row["arguments"]

        # Exclude relative URLs, data urls, blobs, javascript URLs
        if not (script_url.startswith("http://")
                or script_url.startswith("https://")):
            continue

        script_adress = get_base_script_url(script_url)

        third_party_script = False
        if is_third_party(script_url, site_url):
            third_party_scripts.add(script_adress)
            third_party_script = True

        # get the simple feature for this call
        feat = get_simple_feature_from_js_info(operation, arguments, symbol)
        if feat is not None:
            script_features[script_adress].add(feat)

        script_ranks[script_adress].add(visit_id)

        """
        # Check easylist and easyprivacy blocked status
        # if we didn't do it for this script url before
        if script_url not in adblock_checked_scripts:

            if easylist_rules.should_block(
                    script_url, {'script': True,
                                 'third-party': third_party_script}):
                easylist_blocked_scripts.add(script_adress)

            if easyprivacy_rules.should_block(
                    script_url, {'script': True,
                                 'third-party': third_party_script}):
                easyprivacy_blocked_scripts.add(script_adress)

            if is_blocked_by_disconnect(script_url, disconnect_blocklist):
                disconnect_blocked_scripts.add(script_adress)
     """

        # High level features
        # Canvas fingerprinting
        if symbol in CANVAS_READ_FUNCS and operation == "call":
            if (symbol == "CanvasRenderingContext2D.getImageData" and
                    is_get_image_data_dimensions_too_small(arguments)):
                continue
            canvas_reads[script_adress].add(visit_id)
        elif symbol in CANVAS_WRITE_FUNCS:
            text = get_canvas_text(arguments)
            # Python miscalculates the length of unicode strings that contain
            # surrogate pairs such as emojis. This make the string look longer
            # it really is and cause false positives.
            # For instance "🏴​󠁧​󠁢​󠁥​󠁮​󠁧", which is written onto canvas by
            # Wordpress to check emoji support, gives a length of 13.
            # We ignore non-ascii characters to prevent these false positives.
            if len(text.encode('ascii', 'ignore')) >= MIN_CANVAS_TEXT_LEN:
                canvas_writes[script_adress].add(visit_id)
                # the following is used to debug false positives
                canvas_texts[(script_adress, visit_id)].add(text)
        elif symbol == "CanvasRenderingContext2D.fillStyle" and \
                operation == "call":
            canvas_styles[script_adress][visit_id].add(value)
        elif operation == "call" and symbol in CANVAS_FP_DO_NOT_CALL_LIST:
            canvas_banned_calls[script_adress].add(visit_id)
        # Canvas font fingerprinting
        elif symbol == "CanvasRenderingContext2D.font" and operation == "set":
            canvas_used_fonts[script_adress][visit_id].add(value)
        elif symbol == "CanvasRenderingContext2D.measureText" and \
                operation == "call":
            text = json.loads(arguments)["0"]
            canvas_measure_text_calls[(script_adress, visit_id, text)] += 1
        elif (operation == "call" and symbol in WEBRTC_FP_CALLS) or \
                (operation == "set" and
                 symbol == "RTCPeerConnection.onicecandidate"):
            webrtc_calls[script_adress][visit_id].add(symbol)

        # Battery Status API
        elif operation == "get" and symbol in "BatteryManager.level":
            battery_level_access[script_adress].add(visit_id)
        elif operation == "get" and symbol in BATTERY_CHARGING_TIME_CALLS:
            battery_charging_time_access[script_adress].add(visit_id)
        elif operation == "get" and symbol in BATTERY_DISCHARGING_TIME_CALLS:
            battery_discharging_time_access[script_adress].add(visit_id)
        elif (operation == "call"
              and symbol == "BatteryManager.addEventListener"):
            event_type = json.loads(arguments)["0"]
            if event_type == "levelchange":
                battery_level_access[script_adress].add(visit_id)
            elif event_type == "chargingtimechange":
                battery_charging_time_access[script_adress].add(visit_id)
            elif event_type == "dischargingtimechange":
                battery_discharging_time_access[script_adress].add(visit_id)

        # Audio Context API
        elif symbol in AUDIO_CONTEXT_FUNCS:
            audio_ctx_calls[script_adress][visit_id].add(symbol)

    print("Feature extraction done, saving results")
    canvas_fingerprinters = get_canvas_fingerprinters(canvas_reads,
                                                      canvas_writes,
                                                      canvas_styles,
                                                      canvas_banned_calls,
                                                      canvas_texts)
    canvas_font_fingerprinters = \
        get_canvas_font_fingerprinters(canvas_used_fonts,
                                       canvas_measure_text_calls)
    audio_ctx_fingerprinters = get_audio_ctx_fingerprinters(audio_ctx_calls)
    webrtc_fingerprinters = get_webrtc_fingerprinters(webrtc_calls)
    battery_fingerprinters = get_battery_fingerprinters(
        battery_level_access, battery_charging_time_access,
        battery_discharging_time_access)

    request_triggering_scripts, third_party_request_triggering_scripts = \
        get_request_triggering_scripts(db_file)

    if DEBUG:
        print("audio_ctx_fingerprinters", audio_ctx_fingerprinters)
        print("canvas_fingerprinters", canvas_fingerprinters)
        print("canvas_font_fingerprinters", canvas_font_fingerprinters)
        print("webrtc_fingerprinters", webrtc_fingerprinters)
        print("battery_fingerprinters", battery_fingerprinters)
        print("request_triggering_scripts", request_triggering_scripts)
        print("third_party_request_triggering_scripts", third_party_request_triggering_scripts)
        print(THIRD_PARTY_SCRIPT, third_party_scripts)
        #print(EASYLIST_BLOCKED, easylist_blocked_scripts)
        #print(EASYPRIVACY_BLOCKED, easyprivacy_blocked_scripts)
        # print UBLOCK_ORIGIN_BLOCKED, ublock_blocked_scripts
        #print(DISCONNECT_BLOCKED, disconnect_blocked_scripts)

    high_level_feat_dict = {
        CANVAS_FP: canvas_fingerprinters,
        CANVAS_FONT_FP: canvas_font_fingerprinters,
        AUDIO_CTX_FP: audio_ctx_fingerprinters,
        WEBRTC_FP: webrtc_fingerprinters,
        BATTERY_FP: battery_fingerprinters,
        TRIGGERS_REQUEST: request_triggering_scripts,
        TRIGGERS_TP_REQUEST: third_party_request_triggering_scripts,
        #EASYLIST_BLOCKED: easylist_blocked_scripts,
        #EASYPRIVACY_BLOCKED: easyprivacy_blocked_scripts,
        # UBLOCK_ORIGIN_BLOCKED: ublock_blocked_scripts,
        #DISCONNECT_BLOCKED: disconnect_blocked_scripts,
        THIRD_PARTY_SCRIPT: third_party_scripts
    }

    count_dict = {
        NUM_CANVAS_FP: len(canvas_fingerprinters),
        NUM_CANVAS_FONT_FP: len(canvas_font_fingerprinters),
        NUM_AUDIO_CTX_FP: len(audio_ctx_fingerprinters),
        NUM_WEBRTC_FP: len(webrtc_fingerprinters),
        NUM_BATTERY_FP: len(battery_fingerprinters),
        NUM_TRIGGERS_REQUEST: len(request_triggering_scripts),
        NUM_TRIGGERS_TP_REQUEST: len(third_party_request_triggering_scripts),
        #NUM_EASYLIST_BLOCKED: len(easylist_blocked_scripts),
        #NUM_EASYPRIVACY_BLOCKED: len(easyprivacy_blocked_scripts),

        # UBLOCK_ORIGIN_BLOCKED: ublock_blocked_scripts,
        #NUM_DISCONNECT_BLOCKED: len(disconnect_blocked_scripts),
        NUM_THIRD_PARTY_SCRIPT: len(third_party_scripts)
    }

    with open(join(OUT_DIR, "%s_%s" % (CRAWL_NAME, "count_features.json")), 'w') as fp:
        json_string = json.dumps(count_dict, cls=SetEncoder)
        fp.write(json_string)

    with open(join(OUT_DIR, "%s_%s" % (CRAWL_NAME, "script_features.json")), 'w') as fp:
        json_string = json.dumps(script_features, cls=SetEncoder)
        fp.write(json_string)

    with open(join(OUT_DIR, "%s_%s" % (CRAWL_NAME, "high_level_feat_dict.json")), 'w') as fp:
        json_string = json.dumps(high_level_feat_dict, cls=SetEncoder)
        fp.write(json_string)

    with open(join(OUT_DIR, "%s_%s" % (CRAWL_NAME, "script_ranks.json")), 'w') as fp:
        json_string = json.dumps(script_ranks, cls=SetEncoder)
        fp.write(json_string)

    with open(join(OUT_DIR, "%s_%s" % (CRAWL_NAME, "overall_script_ranks.json")), 'w') as fp:
        json_string = json.dumps(overall_script_ranks, cls=SetEncoder)
        fp.write(json_string)

    print("Finished feature extraction")


MIN_FONT_FP_FONT_COUNT = 50


def get_script_urls_from_req_call_stack(req_call_stack):
    """
    An example stack frame:
      udm_@https://sb.scorecardresearch.com/beacon.js:1:611;null"  # noqa

    Another example, this time with eval:
      null@http://static-alias-1.360buyimg.com/jzt/libs/behavior/v2.3/behavior.js line 1 > eval:1:619;null  # noqa
    """
    script_urls = set()
    frames = req_call_stack.split("\n")
    for frame in frames:
        script_url = frame. \
            rsplit(":", 2)[0]. \
            split("@", 1)[-1]. \
            split(" line")[0]
        if not (script_url.startswith("http://")
                or script_url.startswith("https://")):
            continue

        script_url_no_param = script_url.split("?")[0].split("&")[0]
        script_adress = script_url_no_param.split("://")[-1]
        script_urls.add(script_adress)
    return script_urls


def get_request_triggering_scripts(db_file):
    request_triggering_scripts = set()
    third_party_request_triggering_scripts = set()
    connection = sqlite3.connect(db_file)
    c = connection.cursor()
    query = """SELECT visit_id, url, is_third_party_channel, req_call_stack
                   FROM http_requests
                   WHERE req_call_stack <> ''
                   """
    for row in c.execute(query):
        _, _, is_third_party_channel, req_call_stack = row[0:4]
        script_addrs = get_script_urls_from_req_call_stack(req_call_stack)
        request_triggering_scripts.update(script_addrs)
        if is_third_party_channel == 1:
            third_party_request_triggering_scripts.update(script_addrs)
    return request_triggering_scripts, third_party_request_triggering_scripts


def get_battery_fingerprinters(battery_level_access,
                               battery_charging_time_access,
                               battery_discharging_time_access):
    """Find visits where all three battery related features are accessed.
    We require scripts to access three properties:
        battery level, charging and discharging time.
    """
    battery_fingerprinters = set()
    for script_address, visit_ids in battery_level_access.items():
        if script_address in battery_fingerprinters:
            continue
        fp_visits = visit_ids. \
            intersection(battery_charging_time_access[script_address],
                         battery_discharging_time_access[script_address])
        if not fp_visits:
            continue
        battery_fingerprinters.add(script_address)
        print(("Battery fingerprinter", script_address, "visit#",
               fp_visits))

    return battery_fingerprinters


def get_canvas_font_fingerprinters(canvas_used_fonts,
                                   canvas_measure_text_calls):
    """
    From: http://randomwalker.info/publications/OpenWPM_1_million_site_tracking_measurement.pdf  # noqa
    "the script sets the font property to at least 50 distinct, valid values and
    also calls the measureText method at least 50 times on the same text string."

    """
    canvas_font_fingerprinters = set()
    for script_adress, visit_id_calls_dict in canvas_used_fonts.items():
        for font_use_visit_id, canvas_fonts in visit_id_calls_dict.items():
            if len(canvas_fonts) < MIN_FONT_FP_FONT_COUNT:
                continue
            # check if there's 50+ measureText calls in this visit
            for (script_adress, font_measure_visit_id, arguments), call_count \
                    in canvas_measure_text_calls.items():
                if script_adress in canvas_font_fingerprinters:
                    continue
                if font_use_visit_id == font_measure_visit_id and \
                        call_count >= MIN_FONT_FP_FONT_COUNT:
                    canvas_font_fingerprinters.add(script_adress)
                    print(("Canvas font fingerprinter:", script_adress,
                           "visit#", font_use_visit_id,
                           arguments, len(canvas_fonts), canvas_fonts))
                    break
    return canvas_font_fingerprinters


def get_webrtc_fingerprinters(webrtc_calls_dict):
    webrtc_fingerprinters = set()
    for script_adress, visit_id_calls_dict in webrtc_calls_dict.items():
        if script_adress in webrtc_fingerprinters:
            continue
        for visit_id, webrtc_calls in visit_id_calls_dict.items():
            # we require the script to call all 2 webrtc functions
            # and set onicecandidate event listener
            # +1 for set onicecandidate
            if len(webrtc_calls) == len(WEBRTC_FP_CALLS) + 1:
                webrtc_fingerprinters.add(script_adress)
                # print(("WebRTC fingerprinter:", script_adress,
                #      "visit#", visit_id))
                break
    return webrtc_fingerprinters


def get_audio_ctx_fingerprinters(audio_ctx_calls_dict):
    """Return scripts who call the Audio Context API functions we monitor."""
    audio_context_fingerprinters = set()
    for script_adress, visit_id_calls_dict in audio_ctx_calls_dict.items():
        if script_adress in audio_context_fingerprinters:
            continue
        for visit_id, audio_ctx_calls in visit_id_calls_dict.items():
            # we require the script to call all five audio context functions
            if len(audio_ctx_calls) == len(AUDIO_CONTEXT_FUNCS):
                audio_context_fingerprinters.add(script_adress)
                print(("Audio context fingerprinter:", script_adress,
                       "visit#", visit_id))
                break
    return audio_context_fingerprinters


MIN_CANVAS_STYLE_CALLS = 0


def get_canvas_fingerprinters(canvas_reads, canvas_writes, canvas_styles,
                              canvas_banned_calls, canvas_texts):
    """
    We don't require text to be written to canvas with at least two color
    as done by Englehardt and Narayanan, 2016
    Our preliminary analysis showed that several canvas fingerprinting scripts
    uses a single color.
    Following are sample scripts that uses a single color:
    https://secure.bankofamerica.com/login/sign-in/entry/cc.go?_=1498293938310
    https://aug.americanexpress.com/collector/cc.js?v=4.4.3
    https://deviceinfo.capitalone.com/collector/cc.js?tid=HOME_5a9c9ed4-b977-4e85-9e6e-d7ca84983d0b
    Use the following query to find out some of the scripts we'd miss
    if we required this condition:
    SELECT *
      FROM javascript
     WHERE (symbol LIKE "%CanvasRenderingContext2D%" OR
            symbol LIKE "%HTMLCanvasElement.toDataURL%") AND
           id < 1000000 AND
           (script_url LIKE "%deviceinfo.capitalone.com%" OR
            script_url LIKE "%secure.bankofamerica.com/login/sign-in/entry/cc.go%" OR  # noqa
            script_url LIKE "%aug.americanexpress.com/collector/cc.js%");
    """
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
            if len(canvas_styles[script_address][canvas_rw_visit]) < \
                    MIN_CANVAS_STYLE_CALLS:
                continue

            # check if the script has made a call to save, restore or
            # addEventListener of the Canvas API. We exclude scripts making
            # these calls to eliminate false positives
            if canvas_rw_visit in canvas_banned_calls[script_address]:
                print(("Excluding potential canvas FP script", script_address,
                       "visit#", canvas_rw_visit,
                       canvas_texts[(script_address, canvas_rw_visit)]))
                continue
            canvas_fingerprinters.add(script_address)
            print(("Canvas fingerprinter", script_address, "visit#",
                   canvas_rw_visit,
                   canvas_texts[(script_address, canvas_rw_visit)]))
            break

    return canvas_fingerprinters


def get_sorted_feature_list(script_features):
    return sorted(list(reduce(set.union, list(script_features.values()))))


def empty_file(file_handle):
    file_handle.truncate(0)


def filter_out_non_absolute_urls(script_features):
    for script_url in script_features.keys():
        print()
        script_url, urlparse(script_url).netloc
    return script_features


def read_ab_rules_from_file(filename):
    filter_list = set()
    for l in open(filename):
        if len(l) == 0 or l[0] == '!':  # ignore these lines
            continue
        else:
            filter_list.add(l.strip())
    return filter_list


def get_cookie_rules():
    raw_cookie_rules = read_ab_rules_from_file("analysis_utils/fanboy-cookiemonster.txt")
    cookie_rules = AdblockRules(raw_cookie_rules)
    return cookie_rules


def get_adblock_rules():
    raw_easylist_rules = read_ab_rules_from_file("analysis_utils/easylist.txt")
    raw_easyprivacy_rules = read_ab_rules_from_file("analysis_utils/easyprivacy.txt")
    if ENABLE_UBLOCK:
        raw_ublock_rules = read_ab_rules_from_file("analysis_utils/adblock_blacklist_white.txt")
    else:
        raw_ublock_rules = []
    print(("Loaded %s from EasyList, %s rules from EasyPrivacy"
           " and %s rules from UBlockOrigin" %
           (len(raw_easylist_rules), len(raw_easyprivacy_rules),
            len(raw_ublock_rules))))
    easylist_rules = AdblockRules(raw_easylist_rules)
    easyprivacy_rules = AdblockRules(raw_easyprivacy_rules)
    ublock_rules = AdblockRules(raw_ublock_rules)

    return easylist_rules, easyprivacy_rules, ublock_rules


def write_feats_to_csv(script_features,
                       sorted_feature_list,
                       high_level_feat_dict,
                       script_ranks,
                       overall_script_ranks,
                       out_csv):
    with open(out_csv, "a", newline='', encoding='utf8') as f:

        empty_file(f)  # start a fresh file
        f.write("script_url\t" + "\t".join(sorted_feature_list) +
                "\t" + "\t".join(HIGH_LEVEL_FEATURES) + "\t" + "min_rank" +
                "\t" + "num_sites" + "\t" "num_sites_overall" + "\n")
        for script_url, script_features in script_features.items():

            binary_feats = []  # binary feature vector
            for feature in sorted_feature_list:  # iterate over sorted feats
                if feature in script_features:  # if this script has this feat
                    binary_feats.append("1")
                else:
                    binary_feats.append("0")

            f.write(script_url + "\t")  # write the script url
            f.write("\t".join(binary_feats) + "\t")  # write binary features

            hi_level_feats = []  # binary hi level feature vector
            no_rank = []
            for hi_level_feat in HIGH_LEVEL_FEATURES:
                if script_url in high_level_feat_dict[hi_level_feat]:
                    hi_level_feats.append("1")
                    # print "HIGH_LEVEL_FEATURES", hi_level_feat, script_url
                else:
                    hi_level_feats.append("0")

            f.write("\t".join(hi_level_feats))  # write binary features
            if not any(script_ranks[script_url]):
                global NO_RANK
                NO_RANK.append(script_url)
                rank_min = None
            else:
                if None in script_ranks[script_url]:
                    global CONTAINS_NONE_RANKS
                    CONTAINS_NONE_RANKS.append(script_url)

                rank_min = min(x for x in script_ranks[script_url] if x is not None and x >= 0)

            f.write("\t%s\t%s" % (rank_min, len(script_ranks[script_url])))

            f.write("\t%s" % len(overall_script_ranks[script_url]) + "\n")


def write_script_visit_ids(script_visit_ids, out_csv):
    with open(out_csv, "a") as f:
        empty_file(f)  # start a fresh file
        for script_url, visit_ids in script_visit_ids.items():
            visit_ids_str = ",".join(str(visit_id) for visit_id in visit_ids)
            f.write("%s\t%s\n" % (script_url.encode("utf-8"), visit_ids_str))


"""
Usage
To extract features, run:
python extract_features.py
To extract script URL, visit_ids mapping, run:
python extract_features.py extract_frequencies_only
"""
if __name__ == '__main__':
    t0 = time.time()
    crawl_dir = sys.argv[1]
    #crawl_dir = "/home/marleensteinhoff/UNi/Projektseminar/Datenanalyse/data/Samples/"
    OUT_DIR = sys.argv[2]
    #OUT_DIR = "/home/marleensteinhoff/UNi/Projektseminar/Datenanalyse/data/results/"
    out_csv = join(OUTDIR, "features.csv")

    crawl_dir = get_crawl_dir(crawl_dir)
    crawl_name = basename(crawl_dir.rstrip(sep))
    crawl_db_path = get_crawl_db_path(crawl_dir)
    CRAWL_NAME = crawl_db_path.rsplit('/', 1)[-1].split("_")[0].split(".sqlite")[0]
    if "extract_frequencies_only" in sys.argv:
        script_freqs = get_script_freqs_from_db(crawl_db_path)
        write_script_visit_ids(script_freqs, 'script_visit_ids.csv')
        sys.exit(0)
    LIMIT_SITE_RANK = False
    SELECTED_IDS_ONLY = True
    # Only to be used with the home-page only crawls
    MAX_RANK = 0  # for debugging testing

    if LIMIT_SITE_RANK:
        get_cookies(crawl_db_path, MAX_RANK)
        extract_features(crawl_db_path, out_csv, MAX_RANK)

    if SELECTED_IDS_ONLY:
        selected_ids = get_visit_id_site_url_mapping(crawl_db_path)
        selected_visit_ids = tuple(selected_ids['visit_id'].tolist())
        get_cookies(crawl_db_path, selected_visit_ids)
        print("crawlname", CRAWL_NAME)
        get_cookies(crawl_db_path, selected_visit_ids, MAX_RANK)
        extract_features(crawl_db_path, out_csv, selected_visit_ids)

    else:
        get_cookies(crawl_db_path, MAX_RANK)
        extract_features(crawl_db_path, out_csv)  # process all rows
    ########################################
    print(("Feature extraction completed in", time.time() - t0, "seconds"))
    print(("JSONs are written into: ", OUT_DIR))
    print(("Features are written into:", realpath(out_csv)))
