#!/usr/bin/env python3
"""Real-website compatibility sweep.

Loads a list of popular sites (including ones that insist on Chrome) and records, per site: did the
page load, the title, and whether the page says the browser is unsupported. Run it against JithuBrowser
and against stock Chrome as a control; a site that works in stock Chrome but fails here is a regression
(sites that fail in both are blocked by the network, not by the browser).

  JITHU_BROWSER=/path/to/browser tests/site_sweep.py [--json out.json]
Needs a display (see tests/run-tests.sh for Xvfb + window manager) and internet access.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

SITES = [
    ("Google Search", "https://www.google.com/search?q=chromium+browser"),
    ("YouTube", "https://www.youtube.com/"),
    ("Wikipedia", "https://en.wikipedia.org/wiki/Web_browser"),
    ("GitHub", "https://github.com/Jitheswar/JithuBrowser"),
    ("Reddit", "https://www.reddit.com/"),
    ("WhatsApp Web (Chrome-only)", "https://web.whatsapp.com/"),
    ("Google Meet (Chrome-only)", "https://meet.google.com/"),
    ("Google Docs", "https://docs.google.com/document/"),
    ("Figma", "https://www.figma.com/"),
    ("Discord web", "https://discord.com/login"),
    ("Netflix", "https://www.netflix.com/"),
    ("Spotify web", "https://open.spotify.com/"),
    ("Twitch", "https://www.twitch.tv/"),
    ("Amazon", "https://www.amazon.com/"),
    ("Hacker News", "https://news.ycombinator.com/"),
    ("Cloudflare", "https://www.cloudflare.com/"),
    ("WebGL check", "https://get.webgl.org/"),
    ("Zoom web client", "https://app.zoom.us/wc"),
    ("Microsoft Teams", "https://teams.microsoft.com/"),
    ("Google Maps", "https://www.google.com/maps"),
]
UNSUPPORTED = re.compile(r"(browser (is )?(not|no longer) supported|unsupported browser|update (your )?browser|"
                         r"use (a )?(supported|different|another) browser|works best (in|with) chrome|"
                         r"switch to chrome|upgrade your browser|your browser is out of date|get chrome)", re.I)


def run(binary, only=None):
    results = []
    profile = tempfile.mkdtemp(prefix="jithu-sweep-")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profile, executable_path=binary, headless=False, no_viewport=True,
                                                   args=["--no-sandbox", "--disable-gpu"],
                                                   ignore_default_args=["--enable-automation"])
        for name, url in SITES:
            if only and name not in only:
                continue
            page = ctx.new_page()
            r = {"site": name, "url": url, "ok": False}
            t0 = time.time()
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(int(os.environ.get("JITHU_SWEEP_SETTLE_MS", "2500")))
                r["status"] = resp.status if resp else None
                r["final_url"] = page.url[:90]
                r["title"] = (page.title() or "")[:60]
                text = page.evaluate("document.body ? document.body.innerText.slice(0, 6000) : ''")
                m = UNSUPPORTED.search(text or "")
                r["unsupported_notice"] = m.group(0) if m else None
                r["chars"] = len(text or "")
                r["ok"] = bool(resp and resp.status < 400 and r["chars"] > 50)
            except Exception as e:  # noqa: BLE001
                r["error"] = str(e).split("\n")[0][:100]
            r["secs"] = round(time.time() - t0, 1)
            results.append(r)
            print(f"{'OK ' if r['ok'] else 'ERR'} {name:28s} {r.get('status', '-')!s:>4} {r.get('title', r.get('error', ''))[:46]}"
                  + (f"  [UNSUPPORTED NOTICE: {r['unsupported_notice']}]" if r.get("unsupported_notice") else ""), flush=True)
            page.close()
        ctx.close()
    shutil.rmtree(profile, ignore_errors=True)
    return results


if __name__ == "__main__":
    binary = os.environ.get("JITHU_BROWSER") or sys.exit("set JITHU_BROWSER")
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    res = run(binary, only)
    ok = sum(r["ok"] for r in res)
    bad = sum(bool(r.get("unsupported_notice")) for r in res)
    print(f"\n{ok}/{len(res)} loaded; {bad} showed an unsupported-browser notice")
    if "--json" in sys.argv:
        json.dump(res, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
