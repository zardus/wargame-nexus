#!/usr/bin/env python3

try:
    from curl_cffi import requests
    Exc = requests.errors.RequestsError
except ImportError:
    import requests
    Exc = requests.RequestException
import urllib3
import sys
import time

# ugh
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TIMEOUT_SECONDS = 15
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1

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
    ok = False
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = requests.get(
                url,
                timeout=TIMEOUT_SECONDS,
                verify=False,
                stream=True,
                headers={"User-agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:99.0) Gecko/20100101 Firefox/99.0"},
            )
            if 200 <= r.status_code < 300:
                ok = True
                break
            print(f"!!! Attempt {attempt}/{MAX_ATTEMPTS}: received non-2xx response code {r.status_code}")
        except Exc as e:
            print(f"!!! Attempt {attempt}/{MAX_ATTEMPTS}: received exception {e}")

        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_DELAY_SECONDS)

    if not ok:
        failed.append((name, url))
        
for n,u in failed:
    print(f"FAILED: {n} - {u}")
if failed:
    sys.exit(1)
