#!/usr/bin/env python3
"""Automated JBrowser detection-suite runner.

Serves tests/detection, launches a browser binary headless, then behaves like a
user who switches tabs and opens DevTools while the page is watching:

  * opens a second tab and activates it (page should NOT see visibility/blur)
  * attaches a DevTools client with Runtime/Debugger/Log enabled (page should
    NOT detect DevTools via console getters or `debugger` timing)

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

try:
    import websocket  # websocket-client
except ImportError:  # DevTools attach is skipped without it
    websocket = None

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


def devtools_json(port, path, method="GET"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read() or b"null") if "json/activate" not in path else None


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
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    http_port, cdp_port = free_port(), free_port()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", http_port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    profile = tempfile.mkdtemp(prefix="jb-detect-")
    url = f"http://127.0.0.1:{http_port}/index.html?auto=14"
    cmd = [args.browser, f"--remote-debugging-port={cdp_port}", f"--user-data-dir={profile}",
           "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--no-sandbox", url]
    if not args.headed:
        cmd.insert(1, "--headless=new")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        page = wait_for(lambda: next((t for t in devtools_json(cdp_port, "/json/list")
                                      if t["type"] == "page" and "index.html" in t["url"]), None), 30)
        if not page:
            sys.exit("browser did not open the suite")

        # "Open DevTools" on the page.
        if websocket:
            ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=5, suppress_origin=True)
            for i, m in enumerate(["Runtime.enable", "Debugger.enable", "Log.enable", "Profiler.enable"]):
                ws.send(json.dumps({"id": i + 1, "method": m}))
            ws.settimeout(None)

            def drain():
                try:
                    n = 100
                    while True:
                        msg = json.loads(ws.recv())
                        if msg.get("method") == "Debugger.paused":  # a human clicks "resume"
                            time.sleep(0.2)
                            n += 1
                            ws.send(json.dumps({"id": n, "method": "Debugger.resume"}))
                except Exception:
                    pass
            threading.Thread(target=drain, daemon=True).start()

        time.sleep(3)
        other = devtools_json(cdp_port, "/json/new?about:blank", method="PUT")  # switch away
        time.sleep(4)
        devtools_json(cdp_port, f"/json/activate/{page['id']}")                # switch back
        if other:
            time.sleep(1)
            try:
                devtools_json(cdp_port, f"/json/close/{other['id']}")
            except Exception:
                pass

        if not wait_for(lambda: state["report"], 40):
            sys.exit("no report received")
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
        srv.shutdown()

    results = dict(state["report"]["results"])
    sent = {k.lower() for h in state["headers"] for k in h}
    leaked = [h for h in HIGH_ENTROPY_CH if h.lower() in sent]
    results["Client Hints: no high-entropy headers sent"] = {"pass": not leaked, "detail": leaked}

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
