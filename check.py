#!/usr/bin/env python3

# Each site is fetched with curl and, if that fails, loaded in a real browser. It counts as up if either works.

import asyncio
import time
import sys

try:
    from curl_cffi import requests
    Exc = requests.errors.RequestsError
except ImportError:
    import requests
    import urllib3
    Exc = requests.RequestException
    # ugh
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from playwright.async_api import async_playwright, Error as PlaywrightError

CONCURRENCY = 8
LOAD_TIMEOUT = 30    # seconds for a page to load in the browser
SETTLE_TIMEOUT = 15  # further seconds for a non-200 page (e.g., a JS challenge) to navigate itself to a 200

def sites():
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
        yield name, url

def check_curl(url):
    """Fetches the URL with curl. Returns None if it is live, otherwise what went wrong."""
    try:
        r = requests.get(url, timeout=10, verify=False, headers={'User-agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:99.0) Gecko/20100101 Firefox/99.0'})
    except Exc as e:
        return f"Received exception {e}"
    if r.status_code != 200:
        return f"Received non-200 response code {r.status_code}"

async def check_browser(browser, url):
    """Loads the URL in a fresh browser profile. Returns None if it is live, otherwise what went wrong."""
    context = await browser.new_context(ignore_https_errors=True)
    try:
        page = await context.new_page()

        # every status the top-level document receives: redirects, the page itself, and any reload it triggers
        statuses = [ ]
        def on_response(response):
            try:
                if response.request.is_navigation_request() and response.frame == page.main_frame:
                    statuses.append(response.status)
            except PlaywrightError:
                pass # the request belongs to a frame that is not attached (yet), so not the top-level document
        page.on("response", on_response)

        await page.goto(url, timeout=LOAD_TIMEOUT*1000, wait_until="domcontentloaded")

        deadline = time.monotonic() + SETTLE_TIMEOUT
        while statuses and statuses[-1] != 200 and time.monotonic() < deadline:
            await page.wait_for_timeout(500)
    except PlaywrightError as e:
        # an error status with an empty body is a failed navigation to the browser: report the status instead
        if not statuses or statuses[-1] == 200:
            return f"Received exception {e.message.splitlines()[0]}"
    finally:
        await context.close()

    if not statuses:
        return "Received no response"
    if statuses[-1] != 200:
        return f"Received non-200 response code {statuses[-1]}"

async def main():
    async with async_playwright() as p:
        # headless Chromium calls itself "HeadlessChrome" and some sites 403 that, so this needs a display (e.g., xvfb-run)
        browser = await p.chromium.launch(headless=False)
        slots = asyncio.Semaphore(CONCURRENCY)

        async def test(name, url):
            async with slots:
                curl_problem = await asyncio.to_thread(check_curl, url)
                browser_problem = await check_browser(browser, url) if curl_problem else None
            if not curl_problem:
                print(f"[+] {name} - {url}", flush=True)
            elif not browser_problem:
                print(f"[+] {name} - {url} (browser only, curl: {curl_problem})", flush=True)
            else:
                print(f"!!! {name} - {url}\n      curl: {curl_problem}\n      browser: {browser_problem}", flush=True)
            return not curl_problem or not browser_problem

        todo = list(sites())
        up = await asyncio.gather(*(test(name, url) for name, url in todo))
        await browser.close()

    failed = [ site for site, ok in zip(todo, up) if not ok ]
    for n,u in failed:
        print(f"FAILED: {n} - {u}")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
