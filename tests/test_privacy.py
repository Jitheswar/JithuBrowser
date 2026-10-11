"""JithuBrowser privacy test-suite (pytest + Playwright).

Run against any Chromium-based binary:

    JITHU_BROWSER=/opt/jithubrowser/jithubrowser pytest tests/ -v
    JITHU_BROWSER=/path/to/stock/chrome pytest tests/ -v   # baseline: should fail

The browser runs non-headless on an in-memory display (--ozone-platform=headless)
so tab switches, minimising and fullscreen behave like on a desktop.
"""
import http.server
import json
import os
import re
import statistics
import threading

import pytest
from playwright.sync_api import sync_playwright

BROWSER = os.environ.get("JITHU_BROWSER")
HIGH_ENTROPY_CH = ["Sec-CH-UA-Full-Version-List", "Sec-CH-UA-Platform-Version", "Sec-CH-UA-Model",
                   "Sec-CH-UA-Arch", "Sec-CH-UA-Bitness", "Sec-CH-UA-WoW64", "Sec-CH-UA-Form-Factors"]

# Records what a spying page can observe. Installed before any page script runs.
SPY = """
window.__spy = { visibilitychange: 0, hiddenSeen: false, blur: 0, focus: 0, hasFocusFalse: false,
                 freeze: 0, resume: 0, keydowns: [], outer: new Set() };
document.addEventListener('visibilitychange', () => { __spy.visibilitychange++; if (document.hidden) __spy.hiddenSeen = true; }, true);
document.addEventListener('freeze', () => __spy.freeze++, true);
document.addEventListener('resume', () => __spy.resume++, true);
addEventListener('blur', e => { if (e.target === window) __spy.blur++; }, true);
addEventListener('focus', e => { if (e.target === window) __spy.focus++; }, true);
addEventListener('keydown', e => __spy.keydowns.push(e.timeStamp), true);
setInterval(() => {
  if (document.hidden || document.visibilityState !== 'visible') __spy.hiddenSeen = true;
  if (!document.hasFocus()) __spy.hasFocusFalse = true;
  __spy.outer.add([outerWidth - innerWidth, outerHeight - innerHeight, screenX, screenY].join(','));
}, 50);
"""

PAGE = b"<!doctype html><title>t</title><input id=i autofocus>"


class Handler(http.server.BaseHTTPRequestHandler):
    headers_seen = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        Handler.headers_seen.append(dict(self.headers))
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Accept-CH", ", ".join(HIGH_ENTROPY_CH))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(PAGE)


@pytest.fixture(scope="session")
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="session")
def browser():
    if not BROWSER:
        pytest.skip("set JITHU_BROWSER to the browser binary under test")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=BROWSER, headless=False,
                              args=["--ozone-platform=headless", "--no-sandbox", "--disable-gpu"])
        yield b
        b.close()


@pytest.fixture
def page(browser, server):
    ctx = browser.new_context(no_viewport=True)
    ctx.add_init_script(SPY)
    pg = ctx.new_page()
    pg.goto(server + "/")
    pg.wait_for_timeout(500)
    yield pg
    ctx.close()


def spy(pg):
    return pg.evaluate("({...__spy, outer: [...__spy.outer]})")


def window_state(pg, state):
    cdp = pg.context.browser.new_browser_cdp_session()
    win = cdp.send("Browser.getWindowForTarget", {"targetId": pg.context.new_cdp_session(pg).send("Target.getTargetInfo")["targetInfo"]["targetId"]})["windowId"]
    cdp.send("Browser.setWindowBounds", {"windowId": win, "bounds": {"windowState": state}})


# --- Page Visibility / focus ---------------------------------------------------

def test_tab_switch_is_invisible(page):
    other = page.context.new_page()
    other.bring_to_front()
    page.wait_for_timeout(1500)
    page.bring_to_front()
    page.wait_for_timeout(500)
    s = spy(page)
    assert not s["hiddenSeen"] and s["visibilitychange"] == 0, s
    assert s["blur"] == 0 and s["focus"] == 0 and not s["hasFocusFalse"], s


def test_minimise_is_invisible(page):
    window_state(page, "minimized")
    page.wait_for_timeout(1500)
    window_state(page, "normal")
    page.wait_for_timeout(500)
    s = spy(page)
    assert not s["hiddenSeen"] and s["visibilitychange"] == 0 and s["blur"] == 0, s


def test_visibility_timeline_has_no_hidden_entries(page):
    other = page.context.new_page()
    other.bring_to_front()
    page.wait_for_timeout(1000)
    page.bring_to_front()
    names = page.evaluate("performance.getEntriesByType('visibility-state').map(e => e.name)")
    assert "hidden" not in names, names


# --- Window geometry / fullscreen ----------------------------------------------

def test_browser_fullscreen_and_window_size_hidden(page):
    window_state(page, "fullscreen")
    page.wait_for_timeout(1000)
    fs_mq = page.evaluate("matchMedia('(display-mode: fullscreen)').matches")
    window_state(page, "normal")
    page.wait_for_timeout(800)
    s = spy(page)
    assert not fs_mq
    assert len(set(s["outer"])) == 1, s["outer"]          # chrome size & position never change
    assert s["outer"][0].endswith(",0,0"), s["outer"]     # screenX/Y not exposed


# --- History / automation --------------------------------------------------------

def test_history_length_clamped(page, server):
    for i in range(5):
        page.goto(f"{server}/p{i}")
    assert page.evaluate("history.length") <= 2


def test_webdriver_false(page):
    # Playwright launches with automation enabled, stock Chrome reports true here.
    assert page.evaluate("navigator.webdriver") is False


# --- User-Agent / Client Hints ---------------------------------------------------

def test_user_agent_is_plain_chrome(page):
    ua = page.evaluate("navigator.userAgent")
    brands = page.evaluate("navigator.userAgentData.brands.map(b => b.brand)")
    assert re.search(r"Chrome/\d+\.0\.0\.0 Safari/537\.36$", ua) and "Headless" not in ua, ua
    assert "Google Chrome" in brands, brands


def test_high_entropy_hints_reduced(page):
    he = page.evaluate("navigator.userAgentData.getHighEntropyValues(['model','platformVersion','fullVersionList','uaFullVersion','wow64'])")
    assert he["model"] == "" and he["wow64"] is False, he
    assert re.fullmatch(r"(\d+\.0\.0)?", he["platformVersion"]), he
    assert all(re.fullmatch(r"\d+\.0\.0\.0", v["version"]) for v in he["fullVersionList"]), he


def test_client_hint_headers_reduced(page, server):
    Handler.headers_seen.clear()
    page.goto(server + "/again")
    h = {k.lower(): v for k, v in Handler.headers_seen[-1].items()}
    fvl = h.get("sec-ch-ua-full-version-list", "")
    assert not re.search(r'v="\d+\.(?!0\.0\.0")', fvl), fvl
    assert h.get("sec-ch-ua-model", '""') == '""', h
    assert "Google Chrome" in h.get("sec-ch-ua", ""), h


# --- Keyboard --------------------------------------------------------------------

def test_keyboard_layout_is_standard_us(page):
    layout = page.evaluate("navigator.keyboard.getLayoutMap().then(m => Object.fromEntries(m))")
    assert layout.get("KeyQ") == "q" and layout.get("KeyZ") == "z" and layout.get("Semicolon") == ";", layout


def test_typing_rhythm_is_jittered(page):
    page.focus("#i")
    page.keyboard.type("the quick brown fox jumps over", delay=60)
    page.wait_for_timeout(300)
    ts = spy(page)["keydowns"]
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    # Robotic 60 ms typing: stock browsers reproduce it within ~1-2 ms.
    assert statistics.pstdev(gaps) > 5, (statistics.pstdev(gaps), gaps[:10])
