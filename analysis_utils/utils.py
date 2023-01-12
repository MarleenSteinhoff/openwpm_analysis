from tld import get_fld
from urllib.parse import urlparse
import ipaddress
import json
import os
from datetime import datetime


def get_ps1_or_host(url):
    if not url.startswith("http"):
        url = 'http://' + url

    try:
        return get_fld(url, fail_silently=False)
    except Exception:
        hostname = urlparse(url).hostname
        try:
            ipaddress.ip_address(hostname)
            return hostname
        except Exception:
            return None


def is_third_party(url, site_url):
    # !!!: We return False when we have missing information
    if not site_url:
        return False

    site_ps1 = get_ps1_or_host(site_url)
    if site_ps1 is None:
        return False

    req_ps1 = get_ps1_or_host(url)
    if req_ps1 is None:
        # print url
        return False
    if req_ps1 == site_ps1:
        return False

    return True

def get_disconnect_blocked_hosts():
    blocked_hosts = set()
    __location__ = os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__)))

    with open(os.path.join(__location__, 'bundled-resource.jpg'), 'r') as j:
        disconnect = json.loads(j.read())

    #disconnect = json.loads(open(disconnect_json).read())
    categories = disconnect["categories"]
    for _, entries in list(categories.items()):
        for entry in entries:
            adresses = list(entry.values())
            for address in adresses:
                address.pop("dnt", None)  # there's one such entry
                # and it's not a domain/host
                hosts_list = list(address.values())
                blocked_hosts.update(hosts_list[0])

    print((len(blocked_hosts), "blocked hosts"))
    # note that disconnect keep a list of blocked hosts, not PS+1s
    assert "adwords.google.com" in blocked_hosts
    assert "facebook.com" in blocked_hosts
    return list(blocked_hosts)


def is_blocked_by_disconnect_old(url, disconnect_blocked_hosts):
    return urlparse(url).hostname in disconnect_blocked_hosts

def get_delta_timespan(creationtime, expiry):
    date_format = "%Y-%m-%d %H:%M:%S"

    try:
        a = datetime.strptime(creationtime, date_format)
        b = datetime.strptime(expiry, date_format)
        delta = b - a
        return delta.days
    except ValueError:
        a = creationtime.split("-")[0]
        b = expiry.split("-")[0]
        delta = int(b) - int(a)

        if delta >= 1:
            return delta*365
        else:
            return 0

def is_blocked_by_disconnect(url, disconnect_blocked_hosts):
    host = urlparse(url).hostname
    if host in disconnect_blocked_hosts:
        return True
    while True:
        # strip one subdomain at a time
        host = host.split(".", 1)[-1]  # take foo.com from bar.foo.com
        if "." not in host:
            return False
        if host in disconnect_blocked_hosts:
            return True
        return False  # this shouldn't happen unless we are provided a corrupt hostname


if __name__ == '__main__':
    # Test for the is_blocked_by_disconnect
    # TODO: move to a separate file
    assert is_blocked_by_disconnect("http://adwords.google.com", ["facebook.com", "adwords.google.com"])
    assert not is_blocked_by_disconnect("http://example.com", ["facebook.com", "google.com"])
    assert not is_blocked_by_disconnect("http://8.8.8.8", ["facebook.com", "google.com"])
    disconnect_blocked_hosts = get_disconnect_blocked_hosts()
    assert is_blocked_by_disconnect("https://tps40.doubleverify.com/visit.js",
                                    disconnect_blocked_hosts)
    assert is_blocked_by_disconnect("https://pagead2.googlesyndication.com/bg/CI_hqThbQjBwoUSK10cIsovHByRI4InaU0wolTzGCLU.js",
                                    disconnect_blocked_hosts)
    assert not is_blocked_by_disconnect("http://bar-foo.com", ["foo.com"])
    assert not is_blocked_by_disconnect("http://oo.com", ["foo.com"])
    assert is_blocked_by_disconnect("http://bar.foo.com", ["foo.com"])
    assert is_blocked_by_disconnect("http://sub.bar.foo.com", ["foo.com"])
