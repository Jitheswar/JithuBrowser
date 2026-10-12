"""JithuBrowser privacy test-suite.

    tests/run-tests.sh /path/to/browser          # starts Xvfb + a window manager
    JITHU_BROWSER=/path/to/browser DISPLAY=:0 pytest tests/ -v

Run it against stock Chrome first: every test below should FAIL there (that proves
the test can detect the leak) and PASS on JithuBrowser.

Two drivers are used, each where it is accurate:

* "raw" tests drive a real browser window over the DevTools protocol without any
  automation emulation (real tabs, real second window, real minimise/fullscreen).
  Playwright is NOT used for these because it forces focus emulation on every page
  and puts each page of a context in its own window, which hides exactly the leaks
  (tab switching, focus loss) these tests exist to detect.
* Playwright tests check things that do not depend on window state: User-Agent,
  Client Hints, history, navigator.webdriver, keyboard layout and key timing.

Raw tests need a real X display and a window manager (they are skipped otherwise).
"""
import http.server
import json
import os
import re
import shutil
import socket
import statistics
import subprocess
import tempfile
import threading
import time
import urllib.request

import pytest
import websocket  # websocket-client
from playwright.sync_api import sync_playwright

BROWSER = os.environ.get("JITHU_BROWSER")
REAL_DISPLAY = bool(os.environ.get("DISPLAY"))
needs_display = pytest.mark.skipif(not REAL_DISPLAY, reason="needs a real X display + window manager (tests/run-tests.sh)")
HIGH_ENTROPY_CH = ["Sec-CH-UA-Full-Version-List", "Sec-CH-UA-Platform-Version", "Sec-CH-UA-Model",
                   "Sec-CH-UA-Arch", "Sec-CH-UA-Bitness", "Sec-CH-UA-WoW64", "Sec-CH-UA-Form-Factors"]

# What a spying page can observe. Installed before any page script runs.
SPY = """
(() => {
  const s = window.__spy = { visibilitychange: 0, hiddenSeen: false, blur: 0, focus: 0, hasFocusFalse: false,
                             freeze: 0, resume: 0, outer: new Set() };
  s.reset = () => { s.visibilitychange = 0; s.hiddenSeen = false; s.blur = 0; s.focus = 0; s.hasFocusFalse = false;
                    s.freeze = 0; s.resume = 0; s.outer = new Set(); };
  document.addEventListener('visibilitychange', () => { s.visibilitychange++; if (document.hidden) s.hiddenSeen = true; }, true);
  document.addEventListener('freeze', () => s.freeze++, true);
  document.addEventListener('resume', () => s.resume++, true);
  addEventListener('blur', e => { if (e.target === window) s.blur++; }, true);
  addEventListener('focus', e => { if (e.target === window) s.focus++; }, true);
  setInterval(() => {
    if (document.hidden || document.visibilityState !== 'visible') s.hiddenSeen = true;
    if (!document.hasFocus()) s.hasFocusFalse = true;
    s.outer.add([outerWidth - innerWidth, outerHeight - innerHeight, screenX, screenY].join(','));
  }, 50);
})();
"""

PAGE = b"<!doctype html><title>t</title><input id=i autofocus><p>spy page</p>"
SW_SCRIPT = b"self.addEventListener('message', async e => { const cs = await clients.matchAll({includeUncontrolled: true}); e.source.postMessage(JSON.stringify(cs.map(c => ({vis: c.visibilityState, focused: c.focused})))); });"


class Handler(http.server.BaseHTTPRequestHandler):
    headers_seen = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        Handler.headers_seen.append(dict(self.headers))
        if self.path.endswith("/sw.js"):
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            self.wfile.write(SW_SCRIPT)
            return
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


def _require_browser():
    if not BROWSER:
        pytest.skip("set JITHU_BROWSER to the browser binary under test")


# --------------------------------------------------------------------------------
# Raw DevTools driver (no automation emulation)
# --------------------------------------------------------------------------------

def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Cdp:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=20, suppress_origin=True)
        self.n = 0

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def ev(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


class RawBrowser:
    def __init__(self, binary, extra_args=(), profile_dir=None):
        self.port = _free_port()
        self.owns_profile = profile_dir is None
        self.profile = profile_dir or tempfile.mkdtemp(prefix="jithu-raw-")
        self.proc = subprocess.Popen(
            [binary, f"--remote-debugging-port={self.port}", f"--user-data-dir={self.profile}", "--no-first-run",
             "--no-default-browser-check", "--no-sandbox", "--disable-gpu", "--window-size=1100,800",
             "--window-position=60,60", *extra_args, "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ver = self._wait(lambda: self.http("/json/version"), 30)
        assert ver, "browser did not start"
        self.browser = Cdp(ver["webSocketDebuggerUrl"])
        self.tabs = []

    def http(self, path):
        raw = urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5).read()
        try:
            return json.loads(raw)
        except ValueError:
            return raw.decode()

    @staticmethod
    def _wait(fn, timeout):
        end = time.time() + timeout
        while time.time() < end:
            try:
                v = fn()
                if v:
                    return v
            except Exception:
                pass
            time.sleep(0.25)
        return None

    def focus_os_window(self):
        """Give the browser window OS focus like a user clicking it."""
        if shutil.which("xdotool"):
            subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(self.proc.pid), "windowactivate", "--sync"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)

    def open(self, url, new_window=False, spy=True):
        tid = self.browser.call("Target.createTarget", url="about:blank", newWindow=new_window, background=False)["targetId"]
        info = self._wait(lambda: next((t for t in self.http("/json/list") if t["id"] == tid), None), 10)
        tab = Cdp(info["webSocketDebuggerUrl"])
        tab.id = tid
        tab.call("Page.enable")
        if spy:
            tab.call("Page.addScriptToEvaluateOnNewDocument", source=SPY)
        tab.call("Page.navigate", url=url)
        self._wait(lambda: tab.ev("document.readyState") == "complete", 15)
        self.tabs.append(tab)
        return tab

    def activate(self, tab):
        self.browser.call("Target.activateTarget", targetId=tab.id)

    def close_tab(self, tab):
        self.browser.call("Target.closeTarget", targetId=tab.id)

    def window_state(self, tab, state):
        win = self.browser.call("Browser.getWindowForTarget", targetId=tab.id)["windowId"]
        self.browser.call("Browser.setWindowBounds", windowId=win, bounds={"windowState": state})

    def quit(self):
        for t in self.tabs:
            t.close()
        self.browser.close()
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        if self.owns_profile:
            shutil.rmtree(self.profile, ignore_errors=True)


@pytest.fixture
def raw(server):
    _require_browser()
    if not REAL_DISPLAY:
        pytest.skip("needs a real X display")
    rb = RawBrowser(BROWSER)
    rb.url = server + "/"
    rb.spy_tab = rb.open(rb.url)
    rb.focus_os_window()
    rb.activate(rb.spy_tab)
    time.sleep(1.5)
    rb.spy_tab.ev("__spy.reset()")  # observe only what happens from now on
    yield rb
    rb.quit()


def spy(tab):
    return tab.ev("({...__spy, outer: [...__spy.outer]})")


@needs_display
def test_tab_switch_is_invisible(raw):
    raw.open("about:blank", spy=False)              # user opens another tab in the same window
    time.sleep(2)
    raw.activate(raw.spy_tab)                       # ... and comes back
    time.sleep(1)
    s = spy(raw.spy_tab)
    assert not s["hiddenSeen"] and s["visibilitychange"] == 0, s
    assert s["freeze"] == 0 and s["resume"] == 0, s


@needs_display
def test_tab_switch_does_not_blur_window(raw):
    raw.open("about:blank", spy=False)
    time.sleep(2)
    raw.activate(raw.spy_tab)
    time.sleep(1)
    s = spy(raw.spy_tab)
    assert s["blur"] == 0 and s["focus"] == 0 and not s["hasFocusFalse"], s


@needs_display
def test_other_window_focus_is_invisible(raw):
    other = raw.open("about:blank", new_window=True, spy=False)   # user clicks into another window
    time.sleep(2)
    raw.close_tab(other)
    time.sleep(1)
    s = spy(raw.spy_tab)
    assert s["blur"] == 0 and s["focus"] == 0 and not s["hasFocusFalse"], s


@needs_display
def test_minimise_is_invisible(raw):
    raw.window_state(raw.spy_tab, "minimized")
    time.sleep(2)
    raw.window_state(raw.spy_tab, "normal")
    time.sleep(1)
    s = spy(raw.spy_tab)
    assert not s["hiddenSeen"] and s["visibilitychange"] == 0, s


@needs_display
def test_visibility_timeline_has_no_hidden_entries(raw):
    raw.open("about:blank", spy=False)
    time.sleep(2)
    raw.activate(raw.spy_tab)
    time.sleep(0.5)
    names = raw.spy_tab.ev("performance.getEntriesByType('visibility-state').map(e => e.name)")
    assert "hidden" not in names, names


@needs_display
def test_browser_fullscreen_and_window_geometry_hidden(raw):
    raw.window_state(raw.spy_tab, "fullscreen")
    time.sleep(1.5)
    fs_mq = raw.spy_tab.ev("matchMedia('(display-mode: fullscreen)').matches")
    state_mq = raw.spy_tab.ev("matchMedia('(display-state: fullscreen)').matches")
    raw.window_state(raw.spy_tab, "normal")
    time.sleep(1)
    s = spy(raw.spy_tab)
    assert not fs_mq and not state_mq
    assert len(s["outer"]) == 1, s["outer"]               # chrome size and position never change
    assert s["outer"][0].endswith(",0,0"), s["outer"]     # screenX/Y not exposed


@needs_display
def test_vibrate_does_not_reveal_hidden_tab(raw):
    raw.open("about:blank", spy=False)               # spy tab is now really hidden on stock Chrome
    time.sleep(2)
    r = raw.spy_tab.call("Runtime.evaluate", expression="navigator.vibrate(1)", userGesture=True, returnByValue=True)
    assert r["result"]["value"] is True, r


@needs_display
def test_wake_lock_does_not_reveal_hidden_tab(raw):
    raw.open("about:blank", spy=False)
    time.sleep(2)
    r = raw.spy_tab.call("Runtime.evaluate", userGesture=True, awaitPromise=True, returnByValue=True, expression="""
      navigator.wakeLock.request('screen').then(l => l.release()).then(() => 'ok', e => e.name + ': ' + e.message)""")
    assert r["result"]["value"] == "ok", r


@needs_display
def test_hidden_tab_timers_and_animation_frames_keep_running(raw):
    """A page must not be able to tell that it is in a background tab from its own clocks.

    Stock Chrome throttles timers in a hidden tab to ~1 Hz and stops requestAnimationFrame.
    """
    raw.spy_tab.ev("""window.__t = {timer: 0, raf: 0};
        setInterval(() => __t.timer++, 50);
        (function loop() { __t.raf++; requestAnimationFrame(loop); })();""")
    time.sleep(1.5)
    raw.spy_tab.ev("__t.timer = 0; __t.raf = 0")
    raw.open("about:blank", spy=False)               # spy tab is now hidden on stock Chrome
    time.sleep(4)
    t = raw.spy_tab.ev("({...__t})")
    raw.activate(raw.spy_tab)
    # Visible pages tick ~80 timers and ~240 frames in 4 s; hidden-tab throttling gives ~4 timers and 0 frames.
    assert t["timer"] >= 40, t
    assert t["raf"] >= 40, t


@needs_display
@pytest.mark.skipif(not shutil.which("xdotool"), reason="needs xdotool to press real keys")
def test_find_in_page_search_is_not_reported_to_the_page(raw):
    """Pages can hide 'canary' text in collapsed content and learn what the user searched for from the events
    a find-in-page match triggers (beforematch on hidden=until-found, toggle on <details>)."""
    raw.spy_tab.ev("""document.body.innerHTML = '<div hidden="until-found" id=d>my secret phrase</div>' +
        '<details id=det><summary>more</summary>another secret inside</details><p>visible text</p>';
        window.__f = [];
        d.addEventListener('beforematch', () => __f.push('beforematch'));
        det.addEventListener('toggle', () => __f.push('toggle'));""")
    raw.focus_os_window()
    time.sleep(0.5)
    subprocess.run(["xdotool", "key", "ctrl+f"], check=False)
    time.sleep(1.0)
    subprocess.run(["xdotool", "type", "--delay", "80", "secret"], check=False)
    time.sleep(0.5)
    subprocess.run(["xdotool", "key", "Return"], check=False)
    time.sleep(1.5)
    assert raw.spy_tab.ev("__f.slice()") == []


@needs_display
def test_hidden_tab_does_not_pause_video(raw):
    """Stock Chrome pauses a muted video the moment its tab is hidden, and the page gets a 'pause' event."""
    raw.spy_tab.ev("""document.body.innerHTML = '<video id=v muted loop playsinline width=320 src="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.webm"></video>';
        window.__ev = []; const v = document.getElementById('v');
        for (const t of ['pause']) v.addEventListener(t, () => __ev.push(t));
        v.play().catch(() => {});""", )
    for _ in range(20):
        time.sleep(1)
        if raw.spy_tab.ev("document.getElementById('v').readyState") == 4:
            break
    else:
        pytest.skip("test video could not be loaded (needs internet)")
    time.sleep(1)
    raw.spy_tab.ev("__ev.length = 0")
    raw.open("about:blank", spy=False)               # the video's tab is now hidden
    time.sleep(5)
    r = raw.spy_tab.ev("({paused: document.getElementById('v').paused, ev: __ev.slice()})")
    raw.activate(raw.spy_tab)
    assert r == {"paused": False, "ev": []}, r


@needs_display
def test_service_worker_clients_do_not_report_hidden_tab(raw):
    """clients.matchAll() reports each window's visibilityState/focused: stock Chrome says hidden/false for a background tab."""
    raw.spy_tab.ev("navigator.serviceWorker.register('/sw.js').then(() => navigator.serviceWorker.ready).then(() => 'ready')")
    raw.open("about:blank", spy=False)               # the spy tab is now hidden
    time.sleep(3)
    clients = raw.spy_tab.ev("""new Promise(res => { navigator.serviceWorker.addEventListener('message', e => res(JSON.parse(e.data)), {once: true});
        navigator.serviceWorker.ready.then(r => r.active.postMessage('q')); setTimeout(() => res('timeout'), 5000); })""")
    raw.activate(raw.spy_tab)
    assert clients != "timeout" and clients, clients
    assert all(c["vis"] == "visible" and c["focused"] for c in clients), clients


@needs_display
def test_hidden_tab_is_not_visible_to_embedded_frames(raw):
    """A frame embedded in the page must not see visibilitychange / hidden either."""
    raw.spy_tab.ev("""document.body.innerHTML = '<iframe id=f srcdoc="<script>window.log=[];document.addEventListener(\\'visibilitychange\\',()=>log.push(document.visibilityState))</script>"></iframe>'""")
    time.sleep(1)
    raw.open("about:blank", spy=False)
    time.sleep(3)
    r = raw.spy_tab.ev("(() => { const w = document.getElementById('f').contentWindow; return {log: w.log, hidden: w.document.hidden, state: w.document.visibilityState}; })()")
    raw.activate(raw.spy_tab)
    assert r == {"log": [], "hidden": False, "state": "visible"}, r


@needs_display
def test_tab_switch_while_page_is_fullscreen_is_not_reported(raw):
    """A page that is fullscreen (e.g. a video player) learns the user left the tab if the browser exits fullscreen."""
    raw.spy_tab.ev("window.__fs = []; document.addEventListener('fullscreenchange', () => __fs.push(document.fullscreenElement ? 'enter' : 'exit'));")
    raw.spy_tab.call("Runtime.evaluate", expression="document.documentElement.requestFullscreen().then(() => 'ok', e => String(e))", userGesture=True, awaitPromise=True)
    time.sleep(2)
    entered = raw.spy_tab.ev("!!document.fullscreenElement")
    raw.open("about:blank", spy=False)               # user switches to another tab
    time.sleep(3)
    r = raw.spy_tab.ev("({fs: __fs.slice(), element: !!document.fullscreenElement})")
    raw.activate(raw.spy_tab)
    assert entered, "the page could not enter fullscreen in this environment"
    assert "exit" not in r["fs"] and r["element"], r


@needs_display
def test_silent_fullscreen_exit_keeps_the_window_usable(raw):
    """The window must really leave fullscreen while the user is on another tab, restore it when they come back,
    and Esc must still exit (the page is told about a real, user-requested exit)."""
    raw.spy_tab.ev("window.__fs = []; document.addEventListener('fullscreenchange', () => __fs.push(document.fullscreenElement ? 'enter' : 'exit'));")
    raw.spy_tab.call("Runtime.evaluate", expression="document.documentElement.requestFullscreen().then(() => 'ok', e => String(e))", userGesture=True, awaitPromise=True)
    time.sleep(2)
    state = lambda: raw.browser.call("Browser.getWindowForTarget", targetId=raw.spy_tab.id)["bounds"]["windowState"]
    assert state() == "fullscreen"
    other = raw.open("about:blank", spy=False)
    time.sleep(3)
    away = state()                                    # user is looking at another tab
    raw.activate(raw.spy_tab)
    time.sleep(3)
    back = state()
    page_events = raw.spy_tab.ev("__fs.slice()")
    still_fullscreen = raw.spy_tab.ev("!!document.fullscreenElement")
    raw.focus_os_window()
    subprocess.run(["xdotool", "key", "Escape"], check=False)
    time.sleep(2)
    after_esc = raw.spy_tab.ev("({fs: __fs.slice(), element: !!document.fullscreenElement})")
    assert away != "fullscreen", f"window stayed fullscreen on the other tab: {away}"
    assert back == "fullscreen" and still_fullscreen, (back, still_fullscreen)
    assert page_events == ["enter"], page_events
    assert after_esc["element"] is False and after_esc["fs"][-1] == "exit", after_esc


# --------------------------------------------------------------------------------
# Playwright tests (independent of window state)
# --------------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def playwright_browser(pw):
    _require_browser()
    if True:
        p = pw
        if os.environ.get("JITHU_CDP_ONLY"):
            # Browsers started through a wrapper (e.g. a Windows build under Wine) cannot use
            # Playwright's pipe transport; attach over the DevTools port instead.
            rb = RawBrowser(BROWSER)
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{rb.port}")
            yield browser.contexts[0]
            browser.close()
            rb.quit()
            return
        args = ["--no-sandbox", "--disable-gpu"]
        if not REAL_DISPLAY:
            args.append("--ozone-platform=headless")
        profile = tempfile.mkdtemp(prefix="jithu-pw-")
        ctx = p.chromium.launch_persistent_context(profile, executable_path=BROWSER, headless=False, args=args,
                                                   no_viewport=True, ignore_default_args=["--enable-automation"])
        yield ctx
        ctx.close()
        shutil.rmtree(profile, ignore_errors=True)


@pytest.fixture
def page(playwright_browser, server):
    pg = playwright_browser.new_page()
    pg.goto(server + "/")
    yield pg
    pg.close()


def test_history_length_clamped(page, server):
    for i in range(5):
        page.goto(f"{server}/p{i}")
    assert page.evaluate("history.length") <= 2


def test_webdriver_false(page):
    assert page.evaluate("navigator.webdriver") is False


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


def test_worker_sees_same_user_agent(page):
    same = page.evaluate("""async () => {
      const w = new Worker(URL.createObjectURL(new Blob(['postMessage(navigator.userAgent)'])));
      const wua = await new Promise(r => { w.onmessage = e => r(e.data); });
      return wua === navigator.userAgent; }""")
    assert same


def test_keyboard_layout_is_standard_us(page):
    layout = page.evaluate("navigator.keyboard.getLayoutMap().then(m => Object.fromEntries(m))")
    assert layout.get("KeyQ") == "q" and layout.get("KeyZ") == "z" and layout.get("Semicolon") == ";", layout
    assert layout.get("KeyA") == "a" and layout.get("KeyM") == "m" and layout.get("Slash") == "/", layout


def test_typing_rhythm_is_jittered(page):
    page.evaluate("window.__keys = []; addEventListener('keydown', e => __keys.push(e.timeStamp), true)")
    page.focus("#i")
    page.keyboard.type("the quick brown fox jumps over", delay=60)
    page.wait_for_timeout(300)
    ts = page.evaluate("__keys")
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    assert all(g >= 0 for g in gaps), "timestamps must stay monotonic"
    # Robotic 60 ms typing: stock browsers reproduce it within ~1-2 ms.
    assert statistics.pstdev(gaps) > 5, (statistics.pstdev(gaps), gaps[:10])


def test_screen_avail_does_not_reveal_taskbar(page):
    # Regression guard: Xvfb has no taskbar, so this also passes on stock Chrome here.
    r = page.evaluate("({aw: screen.availWidth, ah: screen.availHeight, al: screen.availLeft, at: screen.availTop, w: screen.width, h: screen.height})")
    assert (r["aw"], r["ah"]) == (r["w"], r["h"]) and (r["al"], r["at"]) == (0, 0), r


def test_screen_is_extended_hidden(page):
    # Regression guard: Xvfb has a single screen, so this also passes on stock Chrome here.
    assert page.evaluate("screen.isExtended") is False


def test_mouse_screen_coordinates_do_not_reveal_window_position(page):
    # The window was opened at --window-position by the harness; screenX/Y of a click must be
    # derived from the viewport, not from the real window origin.
    page.evaluate("window.__m = null; addEventListener('click', e => { window.__m = [e.screenX, e.screenY, e.clientX, e.clientY]; }, true)")
    page.mouse.click(120, 140)
    sx, sy, cx, cy = page.evaluate("__m")
    assert sx == cx and sy - cy == 85, (sx, sy, cx, cy)




def test_typing_rhythm_is_blurred_even_for_performance_now(page):
    """A page timing keystrokes with performance.now() in its own handler must not see a robotic rhythm."""
    page.evaluate("window.__pn = []; addEventListener('keydown', () => __pn.push(performance.now()), true)")
    page.focus("#i")
    page.keyboard.type("the quick brown fox jumps over the lazy dog", delay=60)
    page.wait_for_timeout(500)
    ts = page.evaluate("__pn")
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    assert all(g >= 0 for g in gaps), "events must stay in order"
    assert len(ts) >= 40, len(ts)
    # Robotic 60 ms typing: stock browsers reproduce it within ~1-2 ms; the delay adds well over 5 ms of spread.
    assert statistics.pstdev(gaps) > 5, (statistics.pstdev(gaps), gaps[:8])


def test_navigation_api_does_not_reveal_history_depth(page, server):
    for i in range(6):
        page.goto(f"{server}/nav{i}")
    r = page.evaluate("({n: navigation.entries().length, idx: navigation.currentEntry.index, canBack: navigation.canGoBack})")
    assert r["n"] <= 2 and r["idx"] <= 1, r
    assert r["canBack"] is True, r          # whether there is anything to go back to is still available


def test_canvas_readback_is_not_a_pixel_exact_fingerprint(page, server):
    page.goto(f"{server}/canvas")
    r = page.evaluate("""() => {
      const c = document.createElement('canvas'); c.width = c.height = 100;
      const g = c.getContext('2d'); g.fillStyle = 'rgb(100,150,200)'; g.fillRect(0, 0, 100, 100);
      const d = g.getImageData(0, 0, 100, 100).data;
      let off = 0; for (let i = 0; i < d.length; i += 4)
        if (d[i] !== 100 || d[i+1] !== 150 || d[i+2] !== 200 || d[i+3] !== 255) off++;
      return {off, png: c.toDataURL().length};
    }""")
    assert r["off"] > 0, r                    # stock Chrome: a solid fill reads back exactly
    assert r["png"] > 2000, r                 # a solid PNG is tiny unless pixels were perturbed


def test_canvas_blob_is_perturbed_too(page, server):
    page.goto(f"{server}/canvas")
    n = page.evaluate("""async () => {
      const c = document.createElement('canvas'); c.width = c.height = 100;
      const g = c.getContext('2d'); g.fillStyle = 'rgb(100,150,200)'; g.fillRect(0, 0, 100, 100);
      return (await new Promise(r => c.toBlob(r, 'image/png'))).size;
    }""")
    assert n > 2000, n


def test_offline_audio_render_is_not_bit_exact(page, server):
    page.goto(f"{server}/audio")
    off = page.evaluate("""async () => {
      const ctx = new OfflineAudioContext(1, 4410, 44100);
      const s = ctx.createConstantSource(); s.offset.value = 1; s.connect(ctx.destination); s.start();
      const d = (await ctx.startRendering()).getChannelData(0);
      let n = 0; for (const v of d) if (v !== 1) n++;
      return n;
    }""")
    assert off > 0                            # stock Chrome renders exactly 1.0 everywhere


def test_per_site_setting_turns_protections_off_for_that_site_only(server, pw):
    # A second browser started with the unprotected-sites switch: history.length is no longer
    # clamped on that site (127.0.0.1), proving the per-site switch reaches the renderer, while
    # another host (localhost) in the same browser stays protected.
    _require_browser()
    rb = RawBrowser(BROWSER, ["--jithubrowser-unprotected-sites=127.0.0.1"])
    try:
        ctx = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{rb.port}").contexts[0]
        pg = ctx.new_page()
        for i in range(6):
            pg.goto(f"{server}/s{i}")
        unprotected = pg.evaluate("history.length")
        other = ctx.new_page()
        for i in range(6):
            other.goto(f"http://localhost:{server.rsplit(':', 1)[1]}/o{i}")
        protected = other.evaluate("history.length")
    finally:
        rb.quit()
    assert unprotected > 2, unprotected
    assert protected <= 2, protected


def test_webgl_readpixels_is_not_pixel_exact(page, server):
    page.goto(f"{server}/gl")
    r = page.evaluate("""() => {
      const c = document.createElement('canvas'); c.width = c.height = 64;
      const gl = c.getContext('webgl', {preserveDrawingBuffer: true});
      if (!gl) return {nogl: true};
      gl.clearColor(0.4, 0.5, 0.6, 1); gl.clear(gl.COLOR_BUFFER_BIT);
      const px = new Uint8Array(64 * 64 * 4);
      gl.readPixels(0, 0, 64, 64, gl.RGBA, gl.UNSIGNED_BYTE, px);
      let first = [px[0], px[1], px[2]], off = 0;
      for (let i = 0; i < px.length; i += 4)
        if (px[i] !== first[0] || px[i+1] !== first[1] || px[i+2] !== first[2]) off++;
      return {off};
    }""")
    if r.get("nogl"):
        pytest.skip("WebGL not available in this environment")
    assert r["off"] > 0, r                    # a solid clear colour reads back identically on stock Chrome


def test_audio_analyser_output_is_not_bit_exact(page, server):
    page.goto(f"{server}/analyser")
    page.mouse.click(20, 20)                  # a real gesture so the AudioContext may start
    r = page.evaluate("""async () => {
      const ctx = new AudioContext();
      await ctx.resume();
      const src = ctx.createConstantSource(); src.offset.value = 1;
      const an = ctx.createAnalyser(); src.connect(an); an.connect(ctx.destination); src.start();
      await new Promise(r => setTimeout(r, 400));
      const d = new Float32Array(an.fftSize); an.getFloatTimeDomainData(d);
      let odd = 0; for (const v of d) if (v !== 0 && v !== 1) odd++;
      await ctx.close();
      return {odd, state: 'ok'};
    }""")
    assert r["odd"] > 0, r                    # stock Chrome yields only exact 0.0 and 1.0


def test_quiet_mode_stops_background_requests_to_google(tmp_path):
    # --jithubrowser-quiet-google: no component updates, push messaging, account or time checks.
    _require_browser()
    netlog = tmp_path / "net.json"
    rb = RawBrowser(BROWSER, ["--jithubrowser-quiet-google", f"--log-net-log={netlog}"])
    try:
        time.sleep(45)
    finally:
        rb.quit()
    text = netlog.read_text(errors="replace") if netlog.exists() else ""
    assert text, "no net log written"
    # Only real request URLs count (the hostnames also appear in built-in HSTS / preconnect lists).
    bad = sorted(set(re.findall(
        r'"url":"https?://(?:update\.googleapis\.com|android\.clients\.google\.com|clients2\.google\.com/time|'
        r'accounts\.google\.com/ListAccounts)[^"]*', text)))
    assert not bad, bad
