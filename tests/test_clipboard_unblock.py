"""End-to-end tests for the editing unblock (registry flag clipboardUnblock).

The page under test is a faithful replica of the blocking mechanisms used by
sites that disable ordinary editing: an in-memory "copy guard" service that
records the last text copied/cut within the contest (window copy/cut
listeners) and a capture-phase paste interceptor on window that only accepts
text exactly matching that record (per-contest slug + normalized text),
plus document-capture copy/cut/drag-and-drop kill switches (with warning
toasts) and a context-menu blocker. The guard is armed when the contest data
loads (after page parse), which is when the paste interceptor is registered
too - the "/early" page variant registers it synchronously at parse time to
exercise the reverse registration order.

Real user input (Ctrl+C / Ctrl+V / Ctrl+X / right click) is injected through
CDP, so the browser's genuine event pipeline - and therefore the page's
interceptors and the unblock's pre-emption order - are exercised exactly as
in production. The replica is served from 127.0.0.1 with the host resolver
mapping the test hostname, so host matching is the production hostname.
"""

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

CP_HOST = "cpb.smartinterviews.in"     # clipboard-unblock host-suffix match target
CTL_HOST = "ctl.otherhost.org"         # control host: no unblock

# Faithful replica of the site's editing-block machinery (strict LIVE mode).
# The page template; /*ARM*/ is replaced by the guard's arm point. The
# default page arms when the contest data "loads" (a later task, like the
# production page); the early variant arms synchronously at parse time,
# i.e. before the unblock's own listeners are registered.
# RAW byte-string on purpose: the page's JS contains \r \n inside a regex
# literal and a string; a plain b"" would decode them into real line
# terminators, which is a JS syntax error (regex literals may not contain
# raw newlines) and silently kills the whole inline script.
_REPLICA_TEMPLATE = (rb"""<!doctype html><title>cpb</title>
<div id="host"><div id="wrap">
<textarea id="ed" rows="6" cols="40"></textarea>
<textarea id="tmp" rows="2" cols="40"></textarea>
</div></div>
<script>
(() => {
  const S = { toasts: [], armed: false, recorded: 0,
              pasteEvaluated: 0, pastePassed: 0,
              copyBlocked: 0, cutBlocked: 0, dragBlocked: 0, ctxBlocked: 0 };
  window.__cpState = S;
  const toast = (m) => {
    S.toasts.push(m);
    const d = document.createElement("div");
    d.className = "toast";
    d.textContent = m;
    document.body.appendChild(d);
  };
  const disableCopyPaste = true;
  const disableCopyEvent = () => true; // strict: LIVE + REGULAR
  const contestSlug = "rotation-of-matrix";
  const normalize = (t) => t.replace(/\r\n?/g, "\n");

  // --- copy guard service (in-memory "last copied" record, per contest) ---
  const guard = { activeContestSlug: null, lastCopied: null, listenersAdded: false };
  const getSelectedText = (target) => {
    const el = target;
    if ((el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) &&
        typeof el.selectionStart === "number") {
      return el.value.slice(el.selectionStart, el.selectionEnd ?? el.selectionStart);
    }
    return window.getSelection() ? window.getSelection().toString() : "";
  };
  const recordCopy = (e) => {
    if (!guard.activeContestSlug || !e.clipboardData) return;
    let text = e.clipboardData.getData("text/plain");
    if (!text) {
      text = getSelectedText(e.target);
      if (!text) return;
      e.clipboardData.setData("text/plain", text);
      e.preventDefault();
    }
    guard.lastCopied = { contestSlug: guard.activeContestSlug,
                         text: normalize(text) };
    S.recorded++;
  };
  const isAllowedPaste = (text, slug) =>
    !!text && !!guard.lastCopied && guard.lastCopied.contestSlug === slug &&
    guard.lastCopied.text === normalize(text);
  guard.startRecording = (slug) => {
    guard.activeContestSlug = slug;
    if (!guard.listenersAdded) {
      window.addEventListener("copy", recordCopy);
      window.addEventListener("cut", recordCopy);
      guard.listenersAdded = true;
    }
  };

  // --- paste whitelist (window capture; armed when the contest data loads) ---
  const handlePasteEvent = (e) => {
    if (disableCopyPaste) {
      const text = (e.clipboardData && e.clipboardData.getData("text/plain")) || "";
      S.pasteEvaluated++;
      if (isAllowedPaste(text, contestSlug)) { S.pastePassed++; return; } // allowed
      e.stopImmediatePropagation();
      e.preventDefault();
      toast("You can only paste the most recent data that was copied within this contest");
    }
  };
  const armPaste = () => {
    guard.startRecording(contestSlug);
    window.addEventListener("paste", handlePasteEvent, true);
    S.armed = true;
  };
  /*ARM*/

  // --- copy / cut kill switch (document capture) ---
  document.addEventListener("copy", (dn) => {
    if (disableCopyEvent()) {
      S.copyBlocked++;
      dn.preventDefault(); dn.stopImmediatePropagation(); dn.stopPropagation();
      toast("Copy event has been disabled!");
    }
  }, true);
  document.addEventListener("cut", (dn) => {
    if (disableCopyEvent()) {
      S.cutBlocked++;
      dn.preventDefault(); dn.stopImmediatePropagation(); dn.stopPropagation();
      toast("Cut event has been disabled!");
    }
  }, true);

  // --- drag and drop kill switch (document capture) ---
  const handleDrag = (dn) => {
    S.dragBlocked++;
    dn.preventDefault(); toast("Drag and drop is disabled!");
    dn.stopImmediatePropagation(); dn.stopPropagation();
  };
  document.addEventListener("dragover", handleDrag, true);
  document.addEventListener("drop", handleDrag, true);

  // --- right click blocker (bubble listener on the host element) ---
  document.getElementById("host").addEventListener("contextmenu", (y) => {
    S.ctxBlocked++;
    y.preventDefault(); toast("Right click has been disabled!");
    y.stopImmediatePropagation(); y.stopPropagation();
  }, false);

  // Probe: did the native context menu default survive? A later-registered
  // bubble listener on the same node only runs if the blocker did not.
  document.getElementById("host").addEventListener("contextmenu", () => {
    S.ctxNative = true;
  }, false);
})();
</script>""")
REPLICA_PAGE = _REPLICA_TEMPLATE.replace(
    b"/*ARM*/", b"setTimeout(armPaste, 150);")
EARLY_REPLICA_PAGE = _REPLICA_TEMPLATE.replace(b"/*ARM*/", b"armPaste();")


class _CpbHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        # "/early" serves the variant whose paste interceptor is registered
        # at parse time (before the unblock's own listeners).
        path = self.path.split("?", 1)[0].rstrip("/")
        self.wfile.write(EARLY_REPLICA_PAGE if path.endswith("/early")
                         else REPLICA_PAGE)


_TLS = {}


def _tls():
    if not _TLS:
        d = tempfile.mkdtemp(prefix="jithu-cpb-tls-")
        key, crt = os.path.join(d, "key.pem"), os.path.join(d, "cert.pem")
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", key, "-out", crt, "-days", "2",
            "-subj", "/CN=" + CP_HOST,
            "-addext", "subjectAltName=DNS:" + CP_HOST + ",DNS:" + CTL_HOST,
        ], check=True, capture_output=True)
        _TLS.update(key=key, crt=crt)
    return _TLS["key"], _TLS["crt"]


def _serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _CpbHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    key, crt = _tls()
    ctx.load_cert_chain(crt, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def _browser(extra_args, profile_dir=None):
    return RawBrowser(BROWSER, extra_args=tuple(extra_args), profile_dir=profile_dir)


def _grant_clipboard(rb, origin):
    """Allow the page origin to seed the OS clipboard for the test setup."""
    try:
        rb.browser.call("Browser.grantPermissions",
                        origin=origin,
                        permissions=["clipboardReadWrite", "clipboardSanitizedWrite"])
    except Exception:
        pass


def _ctrl_combo(tab, letter):
    """Physical Ctrl+<letter>: Ctrl down, key down, key up, Ctrl up."""
    vk = ord(letter.upper())
    tab.call("Input.dispatchKeyEvent", type="keyDown", key="Control",
             code="ControlLeft", windowsVirtualKeyCode=17, modifiers=2)
    tab.call("Input.dispatchKeyEvent", type="keyDown", key=letter,
             code="Key" + letter.upper(), windowsVirtualKeyCode=vk, modifiers=2)
    tab.call("Input.dispatchKeyEvent", type="keyUp", key=letter,
             code="Key" + letter.upper(), windowsVirtualKeyCode=vk, modifiers=2)
    tab.call("Input.dispatchKeyEvent", type="keyUp", key="Control",
             code="ControlLeft", windowsVirtualKeyCode=17, modifiers=0)


def _right_click(tab, x=200, y=120):
    tab.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y,
             button="right", clickCount=1, buttons=2)
    tab.call("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y,
             button="right", clickCount=1, buttons=0)


def _state(tab):
    return tab.ev("JSON.parse(JSON.stringify(window.__cpState || {}))")


def _wait_armed(tab, timeout=10):
    """Wait until the replica's paste guard is armed (contest data loaded),
    so the paste under test hits the page's interceptor."""
    end = time.time() + timeout
    while time.time() < end:
        if _state(tab).get("armed"):
            return
        time.sleep(0.2)
    raise AssertionError("replica paste guard did not arm in %ss" % timeout)


@needs_display
def test_paste_external_real():
    """Real Ctrl+V of text never copied in-page lands in the editor, and the
    page's own whitelist check passes (no toast, no blocked event)."""
    _require_browser()
    srv, port = _serve()
    try:
        rb = _browser(["--ignore-certificate-errors",
                       "--host-resolver-rules=MAP %s 127.0.0.1" % CP_HOST])
        try:
            tab = rb.open("https://%s:%d/" % (CP_HOST, port), spy=False)
            _wait_armed(tab)
            origin = "https://%s:%d" % (CP_HOST, port)
            _grant_clipboard(rb, origin)
            ext = "def external_helper(n):\n    return n * 2 + 1\n"
            ok = tab.ev("navigator.clipboard.writeText(%r)"
                        ".then(() => 'ok', (e) => 'err:' + e.message)" % ext)
            assert ok == "ok", ok
            tab.ev("document.getElementById('ed').focus()")
            rb.focus_os_window()
            time.sleep(0.5)
            _ctrl_combo(tab, "v")
            end = time.time() + 8
            val = ""
            while time.time() < end:
                val = tab.ev("document.getElementById('ed').value") or ""
                if ext in val:
                    break
                time.sleep(0.3)
            s = _state(tab)
            assert ext in val, {"value": val, "state": s}
            assert s.get("pasteEvaluated", 0) >= 1, s
            assert s.get("pastePassed", 0) >= 1, s
            # The page's own recorder saw the text (synthetic copy event),
            # i.e. the paste passed the page's own guard natively.
            assert s.get("recorded", 0) >= 1, s
            assert not [t for t in s.get("toasts", []) if "paste" in t.lower()], s
        finally:
            rb.quit()
    finally:
        srv.shutdown()


@needs_display
def test_paste_early_listener_still_lands():
    """When the page's paste interceptor is registered before the unblock's
    own handler (parse-time registration, e.g. SSR'd page state), the paste
    is still inserted (direct-insert fallback), even though the page's own
    check rejects it and shows its toast."""
    _require_browser()
    srv, port = _serve()
    try:
        rb = _browser(["--ignore-certificate-errors",
                       "--host-resolver-rules=MAP %s 127.0.0.1" % CP_HOST])
        try:
            tab = rb.open("https://%s:%d/early" % (CP_HOST, port), spy=False)
            _wait_armed(tab)
            origin = "https://%s:%d" % (CP_HOST, port)
            _grant_clipboard(rb, origin)
            ext = "early-listener payload 7"
            ok = tab.ev("navigator.clipboard.writeText(%r)"
                        ".then(() => 'ok', (e) => 'err:' + e.message)" % ext)
            assert ok == "ok", ok
            tab.ev("document.getElementById('ed').focus()")
            rb.focus_os_window()
            time.sleep(0.5)
            _ctrl_combo(tab, "v")
            end = time.time() + 8
            val = ""
            while time.time() < end:
                val = tab.ev("document.getElementById('ed').value") or ""
                if ext in val:
                    break
                time.sleep(0.3)
            s = _state(tab)
            assert ext in val, {"value": val, "state": s}
            # The page's interceptor ran first and rejected the text...
            assert s.get("pasteEvaluated", 0) >= 1, s
            assert not s.get("pastePassed"), s
            # ...so the unblock inserted the text itself.
            assert s.get("toasts"), s
        finally:
            rb.quit()
    finally:
        srv.shutdown()


@needs_display
def test_copy_out_roundtrip_real():
    """Real Ctrl+C on a LIVE-mode page copies the selection out (round trip
    through the OS clipboard) with no toast."""
    _require_browser()
    srv, port = _serve()
    try:
        rb = _browser(["--ignore-certificate-errors",
                       "--host-resolver-rules=MAP %s 127.0.0.1" % CP_HOST])
        try:
            tab = rb.open("https://%s:%d/" % (CP_HOST, port), spy=False)
            _wait_armed(tab)
            text = "my solution code 42"
            tab.ev("const el = document.getElementById('ed');"
                   " el.value = %r; el.setSelectionRange(0, %d);"
                   " el.focus();" % (text, len(text)))
            rb.focus_os_window()
            time.sleep(0.5)
            _ctrl_combo(tab, "c")
            time.sleep(1.0)
            # Round trip: paste from the OS clipboard into the temp field.
            tab.ev("document.getElementById('tmp').focus()")
            time.sleep(0.3)
            _ctrl_combo(tab, "v")
            end = time.time() + 8
            val = ""
            while time.time() < end:
                val = tab.ev("document.getElementById('tmp').value") or ""
                if text in val:
                    break
                time.sleep(0.3)
            s = _state(tab)
            assert text in val, {"value": val, "state": s}
            assert not s.get("copyBlocked"), s
            assert not s.get("toasts"), s
        finally:
            rb.quit()
    finally:
        srv.shutdown()


@needs_display
def test_cut_real():
    """Real Ctrl+X removes the selection (no toast) and the cut text can be
    pasted back."""
    _require_browser()
    srv, port = _serve()
    try:
        rb = _browser(["--ignore-certificate-errors",
                       "--host-resolver-rules=MAP %s 127.0.0.1" % CP_HOST])
        try:
            tab = rb.open("https://%s:%d/" % (CP_HOST, port), spy=False)
            _wait_armed(tab)
            full = "aaa-keep-bbb-mid-ccc-keep"
            tab.ev("const el = document.getElementById('ed');"
                   " el.value = %r; el.setSelectionRange(9, 16); el.focus();" % full)
            rb.focus_os_window()
            time.sleep(0.5)
            _ctrl_combo(tab, "x")
            end = time.time() + 8
            val = ""
            while time.time() < end:
                val = tab.ev("document.getElementById('ed').value") or ""
                if val == "aaa-keep--ccc-keep":
                    break
                time.sleep(0.3)
            tab.ev("document.getElementById('tmp').focus()")
            time.sleep(0.3)
            _ctrl_combo(tab, "v")
            end = time.time() + 8
            tval = ""
            while time.time() < end:
                tval = tab.ev("document.getElementById('tmp').value") or ""
                if "bbb-mid" in tval:
                    break
                time.sleep(0.3)
            s = _state(tab)
            assert val == "aaa-keep--ccc-keep", {"value": val, "state": s}
            assert "bbb-mid" in tval, {"value": tval, "state": s}
            assert not s.get("cutBlocked"), s
            assert not s.get("toasts"), s
        finally:
            rb.quit()
    finally:
        srv.shutdown()


@needs_display
def test_right_click_native():
    """A real right click produces the native context menu (no blocker toast)."""
    _require_browser()
    srv, port = _serve()
    try:
        rb = _browser(["--ignore-certificate-errors",
                       "--host-resolver-rules=MAP %s 127.0.0.1" % CP_HOST])
        try:
            tab = rb.open("https://%s:%d/" % (CP_HOST, port), spy=False)
            rb.focus_os_window()
            time.sleep(0.5)
            _right_click(tab)
            time.sleep(1.0)
            # dismiss any menu with Escape so it does not interfere
            tab.call("Input.dispatchKeyEvent", type="keyDown", key="Escape",
                     code="Escape", windowsVirtualKeyCode=27)
            tab.call("Input.dispatchKeyEvent", type="keyUp", key="Escape",
                     code="Escape", windowsVirtualKeyCode=27)
            s = _state(tab)
            # The blocker is skipped (no toast, no counter) and our handler
            # never preventDefaults, so the native context menu default
            # action proceeds (dispatch semantics).
            assert not s.get("ctxBlocked"), s
            assert not s.get("toasts"), s
        finally:
            rb.quit()
    finally:
        srv.shutdown()


@needs_display
def test_drag_drop_text():
    """Drag-and-drop of text inserts at the caret with no toast."""
    _require_browser()
    srv, port = _serve()
    try:
        rb = _browser(["--ignore-certificate-errors",
                       "--host-resolver-rules=MAP %s 127.0.0.1" % CP_HOST])
        try:
            tab = rb.open("https://%s:%d/" % (CP_HOST, port), spy=False)
            val = tab.ev(
                """(() => {
                  const el = document.getElementById('ed');
                  el.value = 'head ';
                  el.setSelectionRange(5, 5);
                  el.focus();
                  const dt = new DataTransfer();
                  dt.setData('text/plain', 'dropped-tail');
                  const do_ = new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: dt});
                  const dp = new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt});
                  el.dispatchEvent(do_);
                  el.dispatchEvent(dp);
                  return {do: do_.defaultPrevented, dp: dp.defaultPrevented, v: el.value};
                })()""")
            s = _state(tab)
            assert val["v"] == "head dropped-tail", val
            assert not s.get("dragBlocked"), s
            assert not s.get("toasts"), s
        finally:
            rb.quit()
    finally:
        srv.shutdown()


@needs_display
def test_control_host_still_blocks():
    """On an unrelated host the page's own blocks remain fully active."""
    _require_browser()
    srv, port = _serve()
    try:
        rb = _browser(["--ignore-certificate-errors",
                       "--host-resolver-rules=MAP %s 127.0.0.1, MAP %s 127.0.0.1" % (CTL_HOST, CP_HOST)])
        try:
            tab = rb.open("https://%s:%d/" % (CTL_HOST, port), spy=False)
            origin = "https://%s:%d" % (CTL_HOST, port)
            _grant_clipboard(rb, origin)
            _wait_armed(tab)
            ext = "should stay blocked 77"
            ok = tab.ev("navigator.clipboard.writeText(%r)"
                        ".then(() => 'ok', (e) => 'err:' + e.message)" % ext)
            assert ok == "ok", ok
            tab.ev("document.getElementById('ed').focus()")
            rb.focus_os_window()
            time.sleep(0.5)
            _ctrl_combo(tab, "v")
            time.sleep(1.5)
            s = _state(tab)
            val = tab.ev("document.getElementById('ed').value") or ""
            assert ext not in val, {"value": val, "state": s}
            assert s.get("pasteEvaluated", 0) >= 1 and not s.get("pastePassed"), s
            assert s.get("toasts"), s
        finally:
            rb.quit()
    finally:
        srv.shutdown()


@needs_display
def test_feature_off_still_blocks():
    _require_browser()
    srv, port = _serve()
    try:
        rb = _browser(["--ignore-certificate-errors",
                       "--host-resolver-rules=MAP %s 127.0.0.1" % CP_HOST,
                       "--disable-features=JithuBrowserEmulatedExtensions"])
        try:
            tab = rb.open("https://%s:%d/" % (CP_HOST, port), spy=False)
            origin = "https://%s:%d" % (CP_HOST, port)
            _grant_clipboard(rb, origin)
            _wait_armed(tab)
            ext = "should stay blocked 88"
            ok = tab.ev("navigator.clipboard.writeText(%r)"
                        ".then(() => 'ok', (e) => 'err:' + e.message)" % ext)
            assert ok == "ok", ok
            tab.ev("document.getElementById('ed').focus()")
            rb.focus_os_window()
            time.sleep(0.5)
            _ctrl_combo(tab, "v")
            time.sleep(1.5)
            s = _state(tab)
            val = tab.ev("document.getElementById('ed').value") or ""
            assert ext not in val, {"value": val, "state": s}
            assert s.get("toasts"), s
        finally:
            rb.quit()
    finally:
        srv.shutdown()


@needs_display
def test_per_site_off_still_blocks():
    _require_browser()
    profile = tempfile.mkdtemp(prefix="jithu-cpb-profile-")
    default = os.path.join(profile, "Default")
    os.makedirs(default)
    with open(os.path.join(default, "Preferences"), "w") as f:
        json.dump({"profile": {"exit_type": 0, "exited_cleanly": True},
                   "jithubrowser": {"unprotected_sites": ["smartinterviews.in"]}}, f)
    srv, port = _serve()
    try:
        rb = _browser(["--ignore-certificate-errors",
                       "--host-resolver-rules=MAP %s 127.0.0.1" % CP_HOST],
                      profile_dir=profile)
        try:
            tab = rb.open("https://%s:%d/" % (CP_HOST, port), spy=False)
            origin = "https://%s:%d" % (CP_HOST, port)
            _grant_clipboard(rb, origin)
            _wait_armed(tab)
            ext = "should stay blocked 99"
            ok = tab.ev("navigator.clipboard.writeText(%r)"
                        ".then(() => 'ok', (e) => 'err:' + e.message)" % ext)
            assert ok == "ok", ok
            tab.ev("document.getElementById('ed').focus()")
            rb.focus_os_window()
            time.sleep(0.5)
            _ctrl_combo(tab, "v")
            time.sleep(1.5)
            s = _state(tab)
            val = tab.ev("document.getElementById('ed').value") or ""
            assert ext not in val, {"value": val, "state": s}
            assert s.get("toasts"), s
        finally:
            rb.quit()
            shutil.rmtree(profile, ignore_errors=True)
    finally:
        srv.shutdown()
