#!/usr/bin/env python3
"""Extension compatibility check: load unpacked MV3 extensions and confirm they actually run.

  JITHU_BROWSER=/path/to/browser tests/extension_check.py <extension dir> [<extension dir> ...]

Checks per extension: a service worker starts, and for the bundled test extension (build-work/ext/mine)
the content script runs and a service-worker round trip (runtime messaging + chrome.storage + chrome.tabs)
succeeds. For Dark Reader (a real Chrome Web Store extension) it checks that it injects its stylesheet.
Needs a display (tests/run-tests.sh sets one up).
"""
import http.server
import os
import shutil
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright

browser = os.environ.get("JITHU_BROWSER") or sys.exit("set JITHU_BROWSER")
dirs = [os.path.abspath(d) for d in sys.argv[1:]] or sys.exit("give extension directories")


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<!doctype html><title>ext test</title><body style='background:#fff;color:#000'><p>hello extension</p></body>")


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/"
profile = tempfile.mkdtemp(prefix="jithu-ext-")
fails = 0
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        profile, executable_path=browser, headless=False, no_viewport=True,
        args=["--no-sandbox", "--disable-gpu", f"--disable-extensions-except={','.join(dirs)}", f"--load-extension={','.join(dirs)}"],
        ignore_default_args=["--enable-automation", "--disable-extensions"])
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_timeout(5000)
    sws = ctx.service_workers
    print(f"service workers started: {[s.url.split('/')[2][:8] + '…/' + s.url.split('/')[-1] for s in sws]}")
    if len(sws) < len(dirs):
        print("FAIL: not every extension started a service worker"); fails += 1
    ds = page.evaluate("({...document.documentElement.dataset})")
    for d in dirs:
        name = os.path.basename(d)
        if name == "mine":
            ok = ds.get("jithuExt") == "content-script-ran" and '"pong":42' in ds.get("jithuExtReply", "") and '"tab":true' in ds.get("jithuExtReply", "")
            print(f"{'PASS' if ok else 'FAIL'}: test extension content script + service worker round trip: {ds}")
            fails += not ok
        if name == "darkreader":
            n = page.evaluate("document.querySelectorAll('style.darkreader, style[class*=darkreader], meta[name=darkreader-lock]').length")
            ok = n > 0
            print(f"{'PASS' if ok else 'FAIL'}: Dark Reader injected its styles into the page ({n} elements)")
            fails += not ok
    ctx.close()
shutil.rmtree(profile, ignore_errors=True)
print("EXTENSIONS OK" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
