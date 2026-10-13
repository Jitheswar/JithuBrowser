"""End-to-end tests for the bundled extension-presence emulation (patch 0021).

The page under test is a faithful replica of the decision logic used by sites
that gate functionality on a required browser extension: it broadcasts a
CHECK_EXTENSIONS_REQUEST via window.postMessage and, unless an extension
bridge answers with FORBIDDEN_EXTENSIONS listing the expected extension
(within 3 s), it reports "missing"; extra extensions in the answer are
reported as "forbidden".

The replica is served from 127.0.0.1 but the browser's host resolver maps
the test hostname to 127.0.0.1, so the page's hostname - and therefore the
emulator's host matching - is the same as in production (TLS included).
"""

import base64
import http.server
import json
import os
import shutil
import ssl
import subprocess
import tempfile
import threading
import time

import pytest

from test_privacy import BROWSER, REAL_DISPLAY, RawBrowser, _require_browser

needs_display = pytest.mark.skipif(
    not REAL_DISPLAY, reason="needs a real X display (tests/run-tests.sh)")

EMU_HOST = "emu.smartinterviews.in"          # emulator host-suffix match target
EXPECTED_EXT_ID = "goknflnoeiaookhdbnldcbnodjahpgdh"
EXPECTED_EXT_NAME = "Hive - Extension Detector"
EXPECTED_EXT_VERSION = "1.2"
EMULATOR_EXT_ID = "kldblcdpmpjdagdaailehegebjogofan"   # must stay invisible (component)
WEBSTORE_EXT_ID = "nmmicjeknamkfloonkhhcjmomieiodli"   # stock component ext, also invisible

PROBE_EXT_KEY = ("MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAn6aVGkhJLBbGOA1as/pjO791C9veJpnKiY7y7ZdiRhq7eoJ67+RNi4MK0hw4sY5p+LlpQE9sND97t7Tz+vMOd3FFh8XtsJ1OYnV4BebeR8xNrV7nl6TV1mnTwscTzOB5byhABJ/qoHOt9sUTzGwtomuDke8xt6chfl099vN8GDF0jvZHeM1qfkY5gG1MQ56Lo5xJvO/IK7XLKZMrCOR4N1VfYmMm4hI0olw43XfWlx7HXv3rJ7ffYhZuKe7LD21BI+dB6QiiF3wyig6NTrXZsyb4cuYv8LYSt/cMwV7uECA1tB8fe0RmlQwAtrVfrexgL3yXwlW3drQLYhquWtnzbwIDAQAB")
PROBE_EXT_ID = "nehnmplhibdohoidllimnhfidkajahml"

# Faithful replica of the site's check logic (request -> 3 s timeout -> state).
PROTOCOL_PAGE = (b"""<!doctype html><title>emu</title><script>
(() => {
  const expectedExtId = "__EXPECTED__";
  const state = {show: true, reason: 'loading', others: [], seen: 0};
  let responded = false;
  const publish = () => { window.__emState = JSON.parse(JSON.stringify(state)); };
  window.addEventListener('message', (event) => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.type !== 'FORBIDDEN_EXTENSIONS') return;
    const list = Array.isArray(data.enabledExtensions) ? data.enabledExtensions : [];
    state.seen++;
    if (list.length) window.__lastAnswer = {id: list[0].id, name: list[0].name,
      version: list[0].version, isPermissionGiven: data.isPermissionGiven, count: list.length};
    const hasExpected = list.some((x) => x.id === expectedExtId);
    responded = true;
    const others = list.filter((x) => x.id !== expectedExtId);
    if (hasExpected) {
      state.show = others.length > 0; state.reason = others.length ? 'forbidden' : null;
      state.others = others.map((o) => o.name);
    } else {
      state.show = true; state.reason = 'missing'; state.others = [];
    }
    publish();
  });
  const check = () => {
    responded = false;
    window.postMessage({type: 'CHECK_EXTENSIONS_REQUEST'}, '*');
    setTimeout(() => {
      if (!responded) { state.show = true; state.reason = 'missing'; state.others = []; publish(); }
    }, 3000);
  };
  window.__emCheck = check;
  check();
  publish();
})();
</script>""").replace(b"__EXPECTED__", EXPECTED_EXT_ID.encode())

# MV3 forbids inline scripts on extension pages, so the probe JS lives in a file.
PROBE_PAGE = b"""<!doctype html><title>mgmt</title><script src="probe.js"></script>"""
PROBE_JS = b"""
chrome.management.getAll().then(
  (e) => { window.__mgmt = e.map((x) => ({id: x.id, name: x.name, type: x.type})); },
  (e) => { window.__mgmt = {error: String(e)}; });
"""


class _EmuHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(PROTOCOL_PAGE)


def _serve(handler_cls, tls=False, certfile=None, keyfile=None):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    if tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile, keyfile)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def _make_tls_cert(host):
    d = tempfile.mkdtemp(prefix="jithu-emu-tls-")
    cert, key = os.path.join(d, "c.pem"), os.path.join(d, "k.pem")
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-keyout", key, "-out", cert,
         "-days", "2", "-nodes", "-subj", f"/CN={host}",
         "-addext", f"subjectAltName=DNS:{host}"],
        check=True, capture_output=True)
    # SPKI of the cert public key (kept for reference; the test browser uses
    # --ignore-certificate-errors because the spki-list switch is inert in
    # this build).
    pem = subprocess.run(["openssl", "x509", "-in", cert, "-pubkey", "-noout"],
                         check=True, capture_output=True).stdout
    der = subprocess.run(["openssl", "pkey", "-pubin", "-outform", "DER"],
                         input=pem, check=True, capture_output=True).stdout
    spki = base64.b64encode(der).decode()
    return cert, key, spki


def _wait_state(tab, terminal_timeout=25, poll=0.5):
    """Poll __emState until it is no longer 'loading' (answer arrived or the
    page's own 3 s timeout fired)."""
    end = time.time() + terminal_timeout
    while time.time() < end:
        s = tab.ev("window.__emState || null")
        if s and s.get("reason") != "loading":
            return s
        time.sleep(poll)
    return tab.ev("window.__emState || null")


def _browser(extra_args, profile_dir=None):
    return RawBrowser(BROWSER, extra_args=tuple(extra_args), profile_dir=profile_dir)


@needs_display
def test_emulation_passes_site_check():
    """HTTPS page on the matching host passes the check with no extension installed."""
    _require_browser()
    cert, key, spki = _make_tls_cert(EMU_HOST)
    srv, port = _serve(_EmuHandler, tls=True, certfile=cert, keyfile=key)
    try:
        rb = _browser(["--host-resolver-rules=MAP %s 127.0.0.1" % EMU_HOST,
                       "--ignore-certificate-errors"])
        try:
            tab = rb.open("https://%s:%d/" % (EMU_HOST, port), spy=False)
            s = _wait_state(tab)
            assert s, "page never reached a terminal state"
            assert s["seen"] >= 1, s                    # at least one bridge answer arrived
            assert s["show"] is False, s                # the "missing"/"forbidden" modal is hidden
            assert s["reason"] is None and not s["others"], s
            a = tab.ev("window.__lastAnswer || null")
            assert a and a["id"] == EXPECTED_EXT_ID, a
            assert a["name"] == EXPECTED_EXT_NAME and a["version"] == EXPECTED_EXT_VERSION, a
            assert a["isPermissionGiven"] is True and a["count"] == 1, a
            # the page's re-check loop keeps passing
            tab.ev("window.__emCheck()")
            time.sleep(2)
            s2 = tab.ev("window.__emState")
            assert s2["show"] is False, s2
        finally:
            rb.quit()
    finally:
        srv.shutdown()


@needs_display
def test_feature_off_shows_missing():
    """With the feature disabled the page must fall back to its 'missing' state."""
    _require_browser()
    srv, port = _serve(_EmuHandler)
    try:
        rb = _browser(["--host-resolver-rules=MAP %s 127.0.0.1" % EMU_HOST,
                       "--disable-features=JithuBrowserEmulatedExtensions"])
        try:
            tab = rb.open("http://%s:%d/" % (EMU_HOST, port), spy=False)
            s = _wait_state(tab)
            assert s and s["seen"] == 0, s              # nobody answered
            assert s["show"] is True and s["reason"] == "missing", s
        finally:
            rb.quit()
    finally:
        srv.shutdown()


@needs_display
def test_per_site_off_shows_missing():
    """'Protect this site' off for the host suspends the emulation like other protections."""
    _require_browser()
    profile = tempfile.mkdtemp(prefix="jithu-emu-profile-")
    default = os.path.join(profile, "Default")
    os.makedirs(default)
    with open(os.path.join(default, "Preferences"), "w") as f:
        json.dump({"profile": {"exit_type": 0, "exited_cleanly": True},
                   "jithubrowser": {"unprotected_sites": ["smartinterviews.in"]}}, f)
    srv, port = _serve(_EmuHandler)
    try:
        rb = _browser(["--host-resolver-rules=MAP %s 127.0.0.1" % EMU_HOST],
                      profile_dir=profile)
        try:
            tab = rb.open("http://%s:%d/" % (EMU_HOST, port), spy=False)
            s = _wait_state(tab)
            assert s and s["seen"] == 0, s
            assert s["show"] is True and s["reason"] == "missing", s
        finally:
            rb.quit()
            shutil.rmtree(profile, ignore_errors=True)
    finally:
        srv.shutdown()


@needs_display
def test_other_origin_not_affected():
    """A page on an unrelated origin gets no answer (no false positives)."""
    _require_browser()
    srv, port = _serve(_EmuHandler)
    try:
        rb = _browser([])
        try:
            tab = rb.open("http://127.0.0.1:%d/" % port, spy=False)
            s = _wait_state(tab)
            assert s and s["seen"] == 0, s
            assert s["show"] is True and s["reason"] == "missing", s
        finally:
            rb.quit()
    finally:
        srv.shutdown()


@needs_display
def test_management_list_is_pure():
    """The bundled emulator (and all component extensions) must not appear in
    chrome.management.getAll(); a user extension still does."""
    _require_browser()
    ext_dir = tempfile.mkdtemp(prefix="jithu-mgmt-probe-")
    with open(os.path.join(ext_dir, "manifest.json"), "w") as f:
        json.dump({"name": "Mgmt Probe", "version": "1.0", "manifest_version": 3,
                   "key": PROBE_EXT_KEY, "permissions": ["management"],
                   "action": {"default_title": "probe"}}, f)
    with open(os.path.join(ext_dir, "probe.html"), "wb") as f:
        f.write(PROBE_PAGE)
    with open(os.path.join(ext_dir, "probe.js"), "wb") as f:
        f.write(PROBE_JS)
    rb = _browser(["--load-extension=%s" % ext_dir])
    try:
        tab = rb.open("chrome-extension://%s/probe.html" % PROBE_EXT_ID, spy=False)
        end = time.time() + 10
        mgmt = None
        while time.time() < end:
            mgmt = tab.ev("window.__mgmt || null")
            if mgmt:
                break
            time.sleep(0.3)
        assert mgmt is not None, "probe page never reported"
        if isinstance(mgmt, dict):
            raise AssertionError("management API error: " + str(mgmt.get("error")))
        ids = [e["id"] for e in mgmt]
        assert PROBE_EXT_ID in ids, mgmt                # API works, user ext visible
        assert EMULATOR_EXT_ID not in ids, mgmt         # emulator is a component ext
        assert WEBSTORE_EXT_ID not in ids, mgmt         # stock component exts stay hidden
    finally:
        rb.quit()
        shutil.rmtree(ext_dir, ignore_errors=True)


@needs_display
def test_remote_registry_unavailable_still_works():
    """If the remote registry refresh is unreachable, the bundled registry must
    keep the feature working (resilience, no false answers, no crash)."""
    _require_browser()
    srv, port = _serve(_EmuHandler)
    try:
        rb = _browser(["--host-resolver-rules=MAP %s 127.0.0.1, MAP raw.githubusercontent.com 127.0.0.1" % EMU_HOST])
        try:
            tab = rb.open("http://%s:%d/" % (EMU_HOST, port), spy=False)
            s = _wait_state(tab)
            assert s and s["seen"] >= 1, s
            assert s["show"] is False, s
            assert s["reason"] is None and not s["others"], s
            a = tab.ev("window.__lastAnswer || null")
            assert a and a["id"] == EXPECTED_EXT_ID, a
            assert a["count"] == 1, a
        finally:
            rb.quit()
    finally:
        srv.shutdown()
