#!/usr/bin/env python3

try:
    from curl_cffi import requests
    Exc = requests.errors.RequestsError
except ImportError:
    import requests
    Exc = requests.RequestException
import urllib3
import sys

# ugh
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

failed = [ ]
for line in open("README.md"):
    if "Gone, but not" in line:
        break
    if not line.startswith("- [") or "http" not in line:
        continue
    if "heartbeat-failed" in line:
        continue
        
    name = line.strip("- [").split("]")[0]
    url = line.split("]")[1][1:].split(")")[0]
    assert url.startswith("http"), f"Line '{line}' not parsed into name and URL."

    print(f"[+] Testing {name} - {url}")
    try:
        r = requests.get(url, timeout=10, verify=False, headers={'User-agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:99.0) Gecko/20100101 Firefox/99.0'})
    except Exc as e:
        print(f"!!! Received exception {e}")
        failed.append((name, url))
        continue

    if r.status_code != 200:
        print(f"!!! Received non-200 response code {r.status_code}")
        failed.append((name, url))
        
for n,u in failed:
    print(f"FAILED: {n} - {u}")
if failed:
    sys.exit(1)
