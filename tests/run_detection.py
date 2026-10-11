#!/usr/bin/env python3
"""Automated JithuBrowser detection-suite runner.

Serves tests/detection, launches a browser binary, then behaves like a user who
switches to another tab and back while the page is watching (the page should
NOT see visibility changes or blur).

The page POSTs its findings to /report. Request headers are captured too so
Client Hints leakage (Sec-CH-UA-*) is checked on the server side.

Usage: run_detection.py /path/to/chrome [--json out.json]
Exit status is non-zero if any check fails.
"""
import argparse
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import websocket  # websocket-client; browser-level session only, never the page


HERE = os.path.dirname(os.path.abspath(__file__))
SUITE = os.path.join(HERE, "detection")
HIGH_ENTROPY_CH = ["Sec-CH-UA-Full-Version-List", "Sec-CH-UA-Platform-Version",
                   "Sec-CH-UA-Model", "Sec-CH-UA-Arch", "Sec-CH-UA-Bitness",
                   "Sec-CH-UA-WoW64", "Sec-CH-UA-Form-Factors"]

state = {"report": None, "headers": []}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SUITE, **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):
        # Ask for every high-entropy hint; a private browser should not send them.
        self.send_header("Accept-CH", ", ".join(HIGH_ENTROPY_CH))
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        state["headers"].append({"path": self.path, **dict(self.headers)})
        super().do_GET()

    def do_POST(self):
        state["headers"].append({"path": self.path, **dict(self.headers)})
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        state["report"] = json.loads(body)
        self.send_response(204)
        self.end_headers()


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def tab_api(port, path, method="GET"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read() or b"null") if "json/activate" not in path else None


class BrowserSession:
    """Browser-target control channel (like a user clicking tabs/minimise)."""

    def __init__(self, port):
        url = tab_api(port, "/json/version")["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(url, timeout=10, suppress_origin=True)
        self.n = 0

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                return msg.get("result", {})


def wait_for(fn, timeout):
    end = time.time() + timeout
    while time.time() < end:
        try:
            v = fn()
            if v:
                return v
        except Exception:
            pass
        time.sleep(0.2)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("browser")
    ap.add_argument("--json")
    ap.add_argument("--headed", action="store_true", help="use the real $DISPLAY")
    args = ap.parse_args()

    http_port, cdp_port = free_port(), free_port()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", http_port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    profile = tempfile.mkdtemp(prefix="jithu-detect-")
    url = f"http://127.0.0.1:{http_port}/index.html?auto=18"
    cmd = [args.browser, f"--remote-debugging-port={cdp_port}", f"--user-data-dir={profile}",
           "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--no-sandbox", url]
    if not args.headed:
        # A real (non-headless) browser drawing to an in-memory display, so tab
        # switches really hide the page like they do on a desktop.
        cmd.insert(1, "--ozone-platform=headless")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        page = wait_for(lambda: next((t for t in tab_api(cdp_port, "/json/list")
                                      if t["type"] == "page" and "index.html" in t["url"]), None), 30)
        if not page:
            sys.exit("browser did not open the suite")

        b = BrowserSession(cdp_port)
        win = b.call("Browser.getWindowForTarget", targetId=page["id"])["windowId"]
        time.sleep(3)
        # 1) open a foreground tab in the same window, then go back
        other = b.call("Target.createTarget", url="about:blank", newWindow=False, background=False)
        time.sleep(3)
        b.call("Target.activateTarget", targetId=page["id"])
        b.call("Target.closeTarget", targetId=other["targetId"])
        time.sleep(1)
        # 2) minimise the window, then restore it
        b.call("Browser.setWindowBounds", windowId=win, bounds={"windowState": "minimized"})
        time.sleep(3)
        b.call("Browser.setWindowBounds", windowId=win, bounds={"windowState": "normal"})
        # 3) browser fullscreen (like F11), then back
        b.call("Browser.setWindowBounds", windowId=win, bounds={"windowState": "fullscreen"})
        time.sleep(2)
        b.call("Browser.setWindowBounds", windowId=win, bounds={"windowState": "normal"})

        if not wait_for(lambda: state["report"], 40):
            sys.exit("no report received")
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
        srv.shutdown()

    results = dict(state["report"]["results"])
    # High-entropy hints may be sent (Chrome-only sites ask for them) but must
    # carry no more detail than the reduced User-Agent string.
    import re
    leaks = {}
    for h in state["headers"]:
        low = {k.lower(): v for k, v in h.items()}
        fvl = low.get("sec-ch-ua-full-version-list")
        if fvl and re.search(r'v="\d+\.(?!0\.0\.0")', fvl):
            leaks["full-version-list"] = fvl
        if low.get("sec-ch-ua-model", '""') != '""':
            leaks["model"] = low["sec-ch-ua-model"]
        pv = low.get("sec-ch-ua-platform-version")
        if pv and not re.fullmatch(r'"(\d+\.0\.0)?"', pv):
            leaks["platform-version"] = pv
    results["Client Hints headers reduced"] = {"pass": not leaks, "detail": leaks}

    width = max(map(len, results))
    fails = 0
    for name, r in results.items():
        fails += not r["pass"]
        print(f"{'PASS' if r['pass'] else 'FAIL'}  {name.ljust(width)}  {json.dumps(r['detail'])[:110]}")
    print(f"\n{len(results) - fails}/{len(results)} checks passed")
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"results": results, "headers": state["headers"]}, f, indent=2)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
