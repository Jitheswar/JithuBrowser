// Copyright 2026 The JithuBrowser Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// JithuBrowser Setup: a caption_font window with an animated progress display that
// carries Chromium's own mini_installer.exe as an appended payload, unpacks it
// to a temporary folder and runs it unchanged (same command line, same
// installer, same result) while it shows what is going on.
//
// Layout of the final file:  [this program][payload = mini_installer.exe]
//                            [u64 payload size]["JBPAYLD1"]
//
// Passing /silent or --silent skips the window entirely.

#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <string>
using std::max;
using std::min;
#include <objidl.h>
#include <gdiplus.h>

namespace {

using namespace Gdiplus;

constexpr wchar_t kWindowClass[] = L"JithuBrowserSetupWindow";
constexpr wchar_t kTitle[] = L"JithuBrowser Setup";
constexpr char kMagic[8] = {'J', 'B', 'P', 'A', 'Y', 'L', 'D', '1'};
constexpr UINT_PTR kTimerId = 1;
constexpr UINT kMsgFinished = WM_APP + 1;

enum Stage : int { kPreparing = 0, kInstalling = 1, kDone = 2, kFailed = 3 };

// State shared between the worker thread and the UI thread.
std::atomic<int> g_stage{kPreparing};
std::atomic<double> g_extract_fraction{0.0};   // 0..1 while unpacking
std::atomic<int> g_exit_code{0};
std::atomic<ULONGLONG> g_install_started_ms{0};
wchar_t g_error[256] = L"";

// UI-thread state.
HWND g_hwnd = nullptr;
double g_shown = 0.0;          // progress currently drawn, 0..1
double g_scale = 1.0;
ULONG_PTR g_gdiplus_token = 0;
ULONGLONG g_done_at_ms = 0;
std::wstring g_args;           // command line forwarded to the real installer

int S(double v) { return static_cast<int>(std::lround(v * g_scale)); }
float Sf(double v) { return static_cast<float>(v * g_scale); }

// ---------------------------------------------------------------------------
// Worker: unpack and run the real installer.
// ---------------------------------------------------------------------------

bool ReadPayloadLocation(HANDLE file, uint64_t* offset, uint64_t* size) {
  LARGE_INTEGER total;
  if (!GetFileSizeEx(file, &total) || total.QuadPart < 16) {
    return false;
  }
  LARGE_INTEGER pos;
  pos.QuadPart = total.QuadPart - 16;
  if (!SetFilePointerEx(file, pos, nullptr, FILE_BEGIN)) {
    return false;
  }
  unsigned char tail[16];
  DWORD got = 0;
  if (!ReadFile(file, tail, sizeof(tail), &got, nullptr) || got != sizeof(tail) ||
      std::memcmp(tail + 8, kMagic, 8) != 0) {
    return false;
  }
  uint64_t payload = 0;
  std::memcpy(&payload, tail, 8);
  if (payload == 0 || payload > static_cast<uint64_t>(total.QuadPart) - 16) {
    return false;
  }
  *size = payload;
  *offset = static_cast<uint64_t>(total.QuadPart) - 16 - payload;
  return true;
}

void Fail(const wchar_t* message) {
  lstrcpynW(g_error, message, 256);
  g_stage = kFailed;
  PostMessageW(g_hwnd, kMsgFinished, 0, 0);
}

DWORD WINAPI Worker(LPVOID) {
  wchar_t self[MAX_PATH];
  GetModuleFileNameW(nullptr, self, MAX_PATH);
  HANDLE in = CreateFileW(self, GENERIC_READ, FILE_SHARE_READ, nullptr,
                          OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
  uint64_t offset = 0, size = 0;
  if (in == INVALID_HANDLE_VALUE || !ReadPayloadLocation(in, &offset, &size)) {
    Fail(L"This setup file is damaged. Please download it again.");
    return 0;
  }

  wchar_t temp[MAX_PATH];
  GetTempPathW(MAX_PATH, temp);
  std::wstring dir = std::wstring(temp) + L"JithuBrowserSetup-" +
                     std::to_wstring(GetCurrentProcessId());
  CreateDirectoryW(dir.c_str(), nullptr);
  std::wstring installer = dir + L"\\installer.exe";

  HANDLE out = CreateFileW(installer.c_str(), GENERIC_WRITE, 0, nullptr,
                           CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (out == INVALID_HANDLE_VALUE) {
    CloseHandle(in);
    Fail(L"Could not write to the temporary folder.");
    return 0;
  }
  LARGE_INTEGER pos;
  pos.QuadPart = static_cast<LONGLONG>(offset);
  SetFilePointerEx(in, pos, nullptr, FILE_BEGIN);

  const DWORD kChunk = 1 << 20;
  char* buffer = static_cast<char*>(VirtualAlloc(nullptr, kChunk, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
  uint64_t remaining = size;
  bool ok = buffer != nullptr;
  while (ok && remaining > 0) {
    DWORD want = static_cast<DWORD>(min<uint64_t>(remaining, kChunk));
    DWORD got = 0, wrote = 0;
    ok = ReadFile(in, buffer, want, &got, nullptr) && got == want &&
         WriteFile(out, buffer, got, &wrote, nullptr) && wrote == got;
    remaining -= want;
    g_extract_fraction = 1.0 - static_cast<double>(remaining) / static_cast<double>(size);
  }
  if (buffer) {
    VirtualFree(buffer, 0, MEM_RELEASE);
  }
  CloseHandle(out);
  CloseHandle(in);
  if (!ok) {
    DeleteFileW(installer.c_str());
    RemoveDirectoryW(dir.c_str());
    Fail(L"Could not unpack the installer (is the disk full?).");
    return 0;
  }

  g_install_started_ms = GetTickCount64();
  g_stage = kInstalling;

  std::wstring cmd = L"\"" + installer + L"\"";
  if (!g_args.empty()) {
    cmd += L" " + g_args;
  }
  STARTUPINFOW si = {sizeof(si)};
  PROCESS_INFORMATION pi = {};
  if (!CreateProcessW(installer.c_str(), &cmd[0], nullptr, nullptr, FALSE, 0,
                      nullptr, dir.c_str(), &si, &pi)) {
    DeleteFileW(installer.c_str());
    RemoveDirectoryW(dir.c_str());
    Fail(L"Could not start the installer.");
    return 0;
  }
  WaitForSingleObject(pi.hProcess, INFINITE);
  DWORD code = 0;
  GetExitCodeProcess(pi.hProcess, &code);
  CloseHandle(pi.hThread);
  CloseHandle(pi.hProcess);
  DeleteFileW(installer.c_str());
  RemoveDirectoryW(dir.c_str());

  g_exit_code = static_cast<int>(code);
  if (code == 0) {
    g_stage = kDone;
  } else {
    swprintf_s(g_error, L"The installer finished with code %lu.", code);
    g_stage = kFailed;
  }
  PostMessageW(g_hwnd, kMsgFinished, 0, 0);
  return 0;
}

// ---------------------------------------------------------------------------
// Drawing
// ---------------------------------------------------------------------------

double TargetProgress() {
  switch (g_stage.load()) {
    case kPreparing:
      return 0.22 * g_extract_fraction.load();
    case kInstalling: {
      // The real installer reports no progress, so ease toward 95% over time
      // instead of pretending to know. Never reaches 100% until it is done.
      double t = static_cast<double>(GetTickCount64() - g_install_started_ms.load()) / 1000.0;
      return 0.22 + 0.73 * (1.0 - std::exp(-t / 22.0));
    }
    case kDone:
      return 1.0;
    default:
      return g_shown;
  }
}

// Segoe UI on Windows; any sans-serif face if it is missing.
const FontFamily* UiFamily() {
  static FontFamily segoe(L"Segoe UI");
  return segoe.IsAvailable() ? &segoe : FontFamily::GenericSansSerif();
}

void RoundedRect(GraphicsPath* path, float x, float y, float w, float h, float r) {
  float d = r * 2;
  path->AddArc(x, y, d, d, 180, 90);
  path->AddArc(x + w - d, y, d, d, 270, 90);
  path->AddArc(x + w - d, y + h - d, d, d, 0, 90);
  path->AddArc(x, y + h - d, d, d, 90, 90);
  path->CloseFigure();
}

void DrawCentered(Graphics& g, const wchar_t* text, const Font& font, const Brush& brush,
                  float cx, float y) {
  StringFormat fmt;
  fmt.SetAlignment(StringAlignmentCenter);
  RectF r(cx - 400, y, 800, 100);
  g.DrawString(text, -1, &font, r, &fmt, &brush);
}

void Paint(HDC dc, int width, int height) {
  const double now = static_cast<double>(GetTickCount64()) / 1000.0;
  Graphics g(dc);
  g.SetSmoothingMode(SmoothingModeAntiAlias);
  g.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);
  g.SetCompositingQuality(CompositingQualityHighQuality);

  // Background.
  LinearGradientBrush bg(Point(0, 0), Point(width, height), Color(255, 12, 18, 38),
                         Color(255, 36, 24, 84));
  g.FillRectangle(&bg, 0, 0, width, height);

  // Soft moving glow behind the logo.
  const float cx = width / 2.0f;
  const float logo_y = Sf(52);
  const float logo_d = Sf(84);
  {
    GraphicsPath glow;
    float pulse = 1.0f + 0.06f * static_cast<float>(std::sin(now * 2.2));
    float gr = Sf(120) * pulse;
    glow.AddEllipse(cx - gr, logo_y + logo_d / 2 - gr, gr * 2, gr * 2);
    PathGradientBrush pg(&glow);
    pg.SetCenterColor(Color(90, 99, 102, 241));
    Color edge(0, 99, 102, 241);
    int n = 1;
    pg.SetSurroundColors(&edge, &n);
    g.FillPath(&pg, &glow);
  }

  const int stage = g_stage.load();
  const bool failed = stage == kFailed;
  const bool done = stage == kDone;

  // Logo disc.
  Color a = failed ? Color(255, 244, 63, 94) : done ? Color(255, 16, 185, 129) : Color(255, 34, 211, 238);
  Color b = failed ? Color(255, 190, 18, 60) : done ? Color(255, 5, 150, 105) : Color(255, 139, 92, 246);
  LinearGradientBrush disc(PointF(cx - logo_d / 2, logo_y), PointF(cx + logo_d / 2, logo_y + logo_d), a, b);
  g.FillEllipse(&disc, cx - logo_d / 2, logo_y, logo_d, logo_d);

  if (done) {
    Pen check(Color(255, 255, 255, 255), Sf(6));
    check.SetStartCap(LineCapRound);
    check.SetEndCap(LineCapRound);
    check.SetLineJoin(LineJoinRound);
    PointF pts[3] = {PointF(cx - Sf(18), logo_y + logo_d / 2 + Sf(2)),
                     PointF(cx - Sf(5), logo_y + logo_d / 2 + Sf(15)),
                     PointF(cx + Sf(19), logo_y + logo_d / 2 - Sf(13))};
    g.DrawLines(&check, pts, 3);
  } else if (failed) {
    Pen x(Color(255, 255, 255, 255), Sf(6));
    x.SetStartCap(LineCapRound);
    x.SetEndCap(LineCapRound);
    float c = Sf(15);
    g.DrawLine(&x, cx - c, logo_y + logo_d / 2 - c, cx + c, logo_y + logo_d / 2 + c);
    g.DrawLine(&x, cx + c, logo_y + logo_d / 2 - c, cx - c, logo_y + logo_d / 2 + c);
  } else {
    Font jfont(UiFamily(), Sf(40), FontStyleBold, UnitPixel);
    SolidBrush white(Color(255, 255, 255, 255));
    StringFormat fmt;
    fmt.SetAlignment(StringAlignmentCenter);
    fmt.SetLineAlignment(StringAlignmentCenter);
    RectF r(cx - logo_d / 2, logo_y - Sf(2), logo_d, logo_d);
    g.DrawString(L"J", -1, &jfont, r, &fmt, &white);

    // Spinning ring.
    float ring = logo_d + Sf(22);
    float angle = static_cast<float>(std::fmod(now * 220.0, 360.0));
    Pen ring_pen(Color(255, 165, 180, 252), Sf(3.5));
    ring_pen.SetStartCap(LineCapRound);
    ring_pen.SetEndCap(LineCapRound);
    g.DrawArc(&ring_pen, cx - ring / 2, logo_y + logo_d / 2 - ring / 2, ring, ring, angle, 95.0f);
    Pen faint(Color(40, 165, 180, 252), Sf(3.5));
    g.DrawArc(&faint, cx - ring / 2, logo_y + logo_d / 2 - ring / 2, ring, ring, angle + 95.0f, 265.0f);
  }

  // Text.
  Font title(UiFamily(), Sf(26), FontStyleBold, UnitPixel);
  Font sub(UiFamily(), Sf(14), FontStyleRegular, UnitPixel);
  Font caption_font(UiFamily(), Sf(12), FontStyleRegular, UnitPixel);
  SolidBrush white(Color(255, 255, 255, 255));
  SolidBrush muted(Color(255, 160, 174, 205));
  SolidBrush faint(Color(255, 110, 124, 160));

  DrawCentered(g, L"JithuBrowser", title, white, cx, Sf(170));
  const wchar_t* status = L"Getting ready...";
  if (stage == kPreparing) status = L"Preparing files...";
  if (stage == kInstalling) status = L"Installing JithuBrowser. This can take a minute...";
  if (done) status = L"All set! JithuBrowser is installed.";
  if (failed) status = g_error;
  SolidBrush error_brush(Color(255, 253, 164, 175));
  DrawCentered(g, status, sub, failed ? static_cast<const Brush&>(error_brush) : static_cast<const Brush&>(muted), cx, Sf(212));

  // Progress bar.
  const float bx = Sf(60), bw = width - Sf(120), by = Sf(262), bh = Sf(10);
  GraphicsPath track;
  RoundedRect(&track, bx, by, bw, bh, bh / 2);
  SolidBrush track_brush(Color(70, 148, 163, 255));
  g.FillPath(&track_brush, &track);

  float fill = bw * static_cast<float>(std::clamp(g_shown, 0.0, 1.0));
  if (fill > bh && !failed) {
    GraphicsPath bar;
    RoundedRect(&bar, bx, by, fill, bh, bh / 2);
    LinearGradientBrush fillb(PointF(bx, by), PointF(bx + bw, by),
                              Color(255, 34, 211, 238), Color(255, 139, 92, 246));
    g.FillPath(&fillb, &bar);
    if (!done) {
      // Shimmer sweeping across the filled part.
      Region saved;
      g.GetClip(&saved);
      g.SetClip(&bar, CombineModeIntersect);
      float sx = bx + static_cast<float>(std::fmod(now * 0.9, 1.35)) * (fill + Sf(90)) - Sf(90);
      LinearGradientBrush shine(PointF(sx, 0), PointF(sx + Sf(90), 0), Color(0, 255, 255, 255), Color(120, 255, 255, 255));
      shine.SetWrapMode(WrapModeClamp);
      Color shine_colors[3] = {Color(0, 255, 255, 255), Color(140, 255, 255, 255), Color(0, 255, 255, 255)};
      REAL positions[3] = {0.0f, 0.5f, 1.0f};
      shine.SetInterpolationColors(shine_colors, positions, 3);
      g.FillRectangle(&shine, sx, by, Sf(90), bh);
      g.SetClip(&saved);
    }
  }

  if (!failed) {
    wchar_t pct[16];
    swprintf_s(pct, L"%d%%", static_cast<int>(std::lround(g_shown * 100)));
    StringFormat right;
    right.SetAlignment(StringAlignmentFar);
    RectF r(bx, by + Sf(16), bw, Sf(20));
    g.DrawString(pct, -1, &caption_font, r, &right, &muted);
  }
  StringFormat left;
  RectF fr(bx, by + Sf(16), bw, Sf(20));
  g.DrawString(failed ? L"Click anywhere to close." : done ? L"Closing..." : L"Privacy-first browsing, built on Chromium.",
               -1, &caption_font, fr, &left, &faint);

  // Thin border.
  Pen border(Color(60, 148, 163, 255), 1.0f);
  g.DrawRectangle(&border, 0, 0, width - 1, height - 1);
}

// ---------------------------------------------------------------------------
// Window
// ---------------------------------------------------------------------------

LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
  switch (msg) {
    case WM_CREATE:
      SetTimer(hwnd, kTimerId, 16, nullptr);
      return 0;
    case WM_TIMER: {
      double target = TargetProgress();
      // Ease toward the target; never move backwards.
      if (target > g_shown) {
        g_shown += (target - g_shown) * 0.12 + 0.0005;
        if (g_shown > target) g_shown = target;
      }
      InvalidateRect(hwnd, nullptr, FALSE);
      if (g_done_at_ms && GetTickCount64() >= g_done_at_ms) {
        DestroyWindow(hwnd);
      }
      return 0;
    }
    case kMsgFinished:
      if (g_stage.load() == kDone) {
        g_done_at_ms = GetTickCount64() + 3500;
      }
      return 0;
    case WM_ERASEBKGND:
      return 1;
    case WM_PAINT: {
      PAINTSTRUCT ps;
      HDC dc = BeginPaint(hwnd, &ps);
      RECT rc;
      GetClientRect(hwnd, &rc);
      int w = rc.right - rc.left, h = rc.bottom - rc.top;
      HDC mem = CreateCompatibleDC(dc);
      HBITMAP bmp = CreateCompatibleBitmap(dc, w, h);
      HGDIOBJ old = SelectObject(mem, bmp);
      Paint(mem, w, h);
      BitBlt(dc, 0, 0, w, h, mem, 0, 0, SRCCOPY);
      SelectObject(mem, old);
      DeleteObject(bmp);
      DeleteDC(mem);
      EndPaint(hwnd, &ps);
      return 0;
    }
    case WM_NCHITTEST: {
      // Drag the window from anywhere.
      LRESULT hit = DefWindowProcW(hwnd, msg, wp, lp);
      return hit == HTCLIENT ? HTCAPTION : hit;
    }
    case WM_NCLBUTTONUP:
    case WM_LBUTTONUP:
      if (g_stage.load() == kFailed) DestroyWindow(hwnd);
      return 0;
    case WM_CLOSE:
      // Cannot cancel half-way through; closing is allowed once finished.
      if (g_stage.load() == kDone || g_stage.load() == kFailed) DestroyWindow(hwnd);
      return 0;
    case WM_DESTROY:
      KillTimer(hwnd, kTimerId);
      PostQuitMessage(0);
      return 0;
  }
  return DefWindowProcW(hwnd, msg, wp, lp);
}

bool HasSilentFlag(const std::wstring& args) {
  std::wstring lower = args;
  for (auto& c : lower) c = static_cast<wchar_t>(towlower(c));
  return lower.find(L"--silent") != std::wstring::npos || lower.find(L"/silent") != std::wstring::npos;
}

// Arguments after the program name.
std::wstring ForwardedArguments() {
  const wchar_t* cmd = GetCommandLineW();
  if (*cmd == L'"') {
    ++cmd;
    while (*cmd && *cmd != L'"') ++cmd;
    if (*cmd) ++cmd;
  } else {
    while (*cmd && *cmd != L' ') ++cmd;
  }
  while (*cmd == L' ') ++cmd;
  return cmd;
}

}  // namespace

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int) {
  g_args = ForwardedArguments();

  // Opt in to system DPI awareness (also declared in the manifest).
  if (HMODULE user32 = GetModuleHandleW(L"user32.dll")) {
    using SetCtx = BOOL(WINAPI*)(HANDLE);
    if (auto fn = reinterpret_cast<SetCtx>(GetProcAddress(user32, "SetProcessDpiAwarenessContext"))) {
      fn(reinterpret_cast<HANDLE>(-2));  // DPI_AWARENESS_CONTEXT_SYSTEM_AWARE
    }
  }

  if (HasSilentFlag(g_args)) {
    // No window: run exactly like the plain installer.
    g_hwnd = nullptr;
    Worker(nullptr);
    return g_stage.load() == kDone ? 0 : (g_exit_code.load() ? g_exit_code.load() : 1);
  }

  HDC screen = GetDC(nullptr);
  g_scale = GetDeviceCaps(screen, LOGPIXELSX) / 96.0;
  ReleaseDC(nullptr, screen);
  if (g_scale < 1.0) g_scale = 1.0;

  GdiplusStartupInput input;
  GdiplusStartup(&g_gdiplus_token, &input, nullptr);

  WNDCLASSEXW wc = {sizeof(wc)};
  wc.style = CS_DROPSHADOW;
  wc.lpfnWndProc = WndProc;
  wc.hInstance = instance;
  wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
  wc.lpszClassName = kWindowClass;
  wc.hIcon = LoadIconW(instance, MAKEINTRESOURCEW(1));
  wc.hIconSm = wc.hIcon;
  RegisterClassExW(&wc);

  const int w = S(560), h = S(340);
  const int x = (GetSystemMetrics(SM_CXSCREEN) - w) / 2;
  const int y = (GetSystemMetrics(SM_CYSCREEN) - h) / 2;
  g_hwnd = CreateWindowExW(WS_EX_APPWINDOW, kWindowClass, kTitle, WS_POPUP | WS_MINIMIZEBOX, x, y, w, h,
                           nullptr, nullptr, instance, nullptr);

  // Rounded corners on Windows 11.
  if (HMODULE dwm = LoadLibraryW(L"dwmapi.dll")) {
    using SetAttr = HRESULT(WINAPI*)(HWND, DWORD, LPCVOID, DWORD);
    if (auto fn = reinterpret_cast<SetAttr>(GetProcAddress(dwm, "DwmSetWindowAttribute"))) {
      int round = 2;  // DWMWCP_ROUND
      fn(g_hwnd, 33 /* DWMWA_WINDOW_CORNER_PREFERENCE */, &round, sizeof(round));
    }
  }

  ShowWindow(g_hwnd, SW_SHOW);
  UpdateWindow(g_hwnd);

  HANDLE worker = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr);

  MSG msg;
  while (GetMessageW(&msg, nullptr, 0, 0) > 0) {
    TranslateMessage(&msg);
    DispatchMessageW(&msg);
  }
  // The window can only be closed once the worker has finished.
  if (worker) {
    WaitForSingleObject(worker, 5000);
    CloseHandle(worker);
  }
  GdiplusShutdown(g_gdiplus_token);
  return g_stage.load() == kDone ? 0 : 1;
}
