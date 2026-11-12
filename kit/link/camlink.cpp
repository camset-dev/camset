// camlink: one long-lived connection to a Sony camera through the Camera Remote SDK.
//
// Commands arrive on stdin, one per line. Every command gets exactly one JSON reply line on stdout. A line may start
// with "@N" (the kit sends one with every command), which the reply echoes as "id": N: the kit matches each reply to
// its command by it, so a stray line on stdout (from the SDK or a library) cannot shift every later reply.
// SDK events (disconnects, warnings, errors) are JSON lines on stderr, so replies never interleave
// with them. camlink holds no menu knowledge: the Python side decides what to press and when.
//
//   camlink [--usb] [--ip A.B.C.D] [--model ILCE-1M2]
//                                         LAN by default (CAMSET_IP or --ip); credentials come from
//                                         ~/.config/camset/network.json (%USERPROFILE% on Windows), below.
//                                         --model (or CAMSET_MODEL) names the body for a LAN camera the SDK
//                                         did not find by itself, CAMSET_MAC its MAC address when known. The
//                                         bodies it takes are camera_net.h's list (lanModel); a missing or
//                                         unknown one is said in a "note" event, and camlink asks as for the
//                                         list's first body.
//
// The credentials file, written by the person (or the editor's Save), mode 600; camlink only reads it, and refuses one
// other users of the computer can read (Windows: not checked):
//   {"user": "...", "password": "...",                                      the default pair
//    "cameras": {"AA:BB:CC:DD:EE:FF": {"name": "...", "user": "...", "password": "..."}}}   one camera's own pair
// The first camera entry found wins, looked up (case does not matter) by the MAC address the SDK names for the camera
// it finds at the address, then by the MAC address this computer's own network neighbour table (ARP) holds for the
// address, then by CAMSET_MAC; else the default pair, else none. One camera can carry two MAC addresses, since the
// SDK names its wired or its wireless LAN card's by model and not by the connection in use (Sony's API reference),
// while the neighbour table holds the card that answered at the address. The lookup and the MAC address reading are
// shared with the editor's camera helper (kit/common/camera_net.h), so both pick the same login.
//
// The login goes only to the camera it was saved for: before Connect, the fingerprint the camera at the address shows
// is compared with the one kept for it in ~/.config/camset/known_cameras.json (camera_net.h); one that differs refuses
// the connection and nothing is sent. A camera met for the first time is trusted, and kept there once connected.
//
// The first reply names the camera, never its serial number (the kit does not show it); a failure is
// {"ok": false, "error": <why>, "cause": <token>}, with the tokens camset_probe's cause line uses: "bad_address" (the
// address is not four numbers 0-255), "credentials_file_open" (the credentials file can be read by other users),
// "camera_changed" (the camera at the address shows another fingerprint than the one kept for it), "no_usb_camera",
// "no_answer" (its fingerprint could not be read at all, as from a camera restarting after an upload, or Connect
// started and no connection came), else
// "connect_failed" (the camera object or the Connect call failed, or no cause more precise is known). A command's
// failure carries a cause too where one is known: "refused" (below), "button_held", "download_refused" (the camera
// would not save its settings: no card, a menu open), "not_a_settings_file" (an upload that is no settings file,
// kit/common/settings_file.h: never sent), "hash_mismatch" (an upload whose bytes are not the ones the SHA-256 on its
// line names: never sent) and "upload_refused" (the camera would not take the file). Once connected:
//   {"ok": true, "ready": <model>, "connection": "lan A.B.C.D" or "usb", "mac", "neighbour_mac", "login", "login_under",
//    "upload_sha256": true}
//   upload_sha256  always true: upload takes the SHA-256 the kit checked the file by (below). The kit refuses to open a
//                  link to a camlink whose ready line lacks it (an older build: python3 kit/setup.py rebuilds it), as
//                  that one would refuse every upload, the run's put-back of its start file included
//   mac            the camera's MAC address, when known: the one the SDK names for the camera object; for an object
//                  made from the address without one, the one the neighbour table holds for the address (the card
//                  that answered), else CAMSET_MAC
//   neighbour_mac  the MAC address the neighbour table holds for the address, only when it is not the one in "mac"
//                  (the SDK may name the camera's other network card)
//   login          which pair was used: "camera", "default" or "none"
//   login_under    only for "camera": the MAC address its entry was found under, "sdk_mac", "neighbour_mac" or
//                  "CAMSET_MAC"
//
// Builds on macOS, Windows and Linux. On Windows the SDK is built with UNICODE, as Sony's samples are,
// so its strings are wchar_t there; kit/common/sdk_session.h converts (narrow, in camera_net.h, for the MAC address's
// ASCII text), and everything else here is UTF-8. What camlink does the same way as the editor's camera helper (the
// connection's steps, a press, the OSD, a download) is in kit/common/sdk_session.h; the words here are camlink's own.
// Commands (kit/link/protocol.h: a trailing "\r" is dropped; a PATH, DIR, NAME or TEXT may be "quoted" with \" and
// \\ inside, which is how the kit sends them, so spaces and Windows backslashes arrive whole; a number is decimal or
// 0x hex, and one with anything after it is refused, as "bad arguments"):
//   hello                                 model, connection, mac (when known)
//   props                                 every property: code, name, type, writable, current, values|range, text
//   get NAME|0xCODE                       one property
//   set NAME|0xCODE VALUE                 set and wait until the camera reports it
//   setstr NAME|0xCODE TEXT...            ASCII string property (other text is refused)
//   press BUTTON [HOLD_MS] [allowed]      button down, hold (default 60 ms, 20-2000), up; no redraw wait
//
// What camlink never sends, whoever asks (kit/common/never_touch.h, written from kit/camkit/safety.py, whose guards the
// kit's own link applies first): a never button (C1-C3, C5-C7, Movie, AF-On, AEL, Mode, Home, Thumbnail); a guarded
// one (C4, Delete, Playback, Fn, Display, Back) unless the line ends "allowed", which the kit adds only where its
// screen check allowed it; a button or dial no list names (kit/common/remote.h); a property set or setstr whose name,
// as the SDK's table spells it for the code asked for, makes sound, light or motion, holds credentials or
// identity, acts, or is a button, dial or lever (those go through press and dial), nor one the SDK's table does not
// name. Such a line gets {"ok": false, "error": ..., "cause": "refused"}. A press holds its button at most 2 s, and
// its release is tried three times: one refused every time gets "cause": "button_held".
//   dial DIAL STEPS                       turn a dial (negative = the other way)
//   osd PATH                              save the camera's OSD image (PNG)
//   download DIR NAME                     settings file -> DIR/NAME.DAT (DIR quoted when it holds a space; an
//                                         existing NAME.DAT is never replaced: refused before the camera is asked)
//   upload PATH [SHA256]                  send a settings file (the camera restarts; the link drops). The file is read
//                                         once, and those bytes are checked and sent: a settings file, and when SHA256
//                                         is given (the kit gives the hash of the camera download it checked) bytes
//                                         with that SHA-256, else "hash_mismatch" and nothing is sent. The SDK uploads
//                                         from a path: a copy of those bytes camlink writes beside the file (0600,
//                                         _camlink_upload_<pid>.DAT), removed however the command ends (the kit's
//                                         download pickers skip the name, should a crash leave one). The reply
//                                         carries their sha256.
//   ping                                  connection state
//   quit
//
// Signals: a SIGINT, SIGTERM or SIGHUP (Ctrl-C, Ctrl-Break on Windows) never cuts a command short, since a dropped
// session applies the dialog on screen (docs/decisions/0015). The command in progress finishes and replies; then
// camlink answers {"ok": false, "error": ..., "cause": "signal"} (the reply the caller's next command reads), says so
// on stderr ({"event": "signal"}), disconnects and exits with 128 + the signal's number. The Python side starts
// camlink in a process group of its own, so a terminal's Ctrl-C reaches only Python, which stops the run cleanly
// and then sends quit.

#include <algorithm>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <thread>
#include <vector>

// kit/common: camera_net.h first (the MAC address, the login, the trusted cameras; on Windows winsock2.h must come
// before the SDK's headers), sdk_session.h (the SDK's steps both helpers share, with the SDK's headers),
// callback_wait.h (the wait on the SDK's thread), never_touch.h (written from kit/camkit/safety.py: the buttons and
// properties never sent) and remote.h (the button and dial codes and their rule), sdk_values.h (a property's value
// as its type reads it, and a number as a command gives it), settings_file.h (the check before an upload: the file
// read once, a settings file, its SHA-256 (sha256.h) the one the kit checked, and the copy the SDK is given)
#include "camera_net.h"
#include "sdk_session.h"
#include "callback_wait.h"
#include "never_touch.h"
#include "remote.h"
#include "sdk_values.h"
#include "settings_file.h"
#include "protocol.h"     // the command lines: quoting, "\r\n", the request's id

#ifndef _WIN32
#include <pthread.h>
#include <signal.h>
#endif

namespace fs = std::filesystem;
using namespace std::chrono_literals;
using Clock = std::chrono::steady_clock;

// ---------------------------------------------------------------- JSON output

struct Obj {   // tiny ordered JSON object builder
    std::string body;
    Obj& raw(const std::string& k, const std::string& v) { body += (body.empty() ? "" : ",") + jsonText(k) + ":" + v; return *this; }
    Obj& s(const std::string& k, const std::string& v) { return raw(k, jsonText(v)); }
    Obj& i(const std::string& k, long long v) { return raw(k, std::to_string(v)); }
    Obj& b(const std::string& k, bool v) { return raw(k, v ? "true" : "false"); }
    Obj& list(const std::string& k, const std::vector<long long>& v) {
        std::string a = "[";
        for (size_t n = 0; n < v.size(); ++n) a += (n ? "," : "") + std::to_string(v[n]);
        return raw(k, a + "]");
    }
    std::string str() const { return "{" + body + "}"; }
};

// One lock for each stream: replies (stdout, the main thread) and events (stderr, the SDK's thread too) each come out
// whole, and a reader of stderr that stops can block only the events, never a reply.
static std::mutex g_replyLock, g_eventLock;
static std::string g_id;   // the id of the command being answered (protocol::command), echoed in its reply
static void reply(Obj o) {
    if (!g_id.empty()) o.raw("id", g_id);
    std::lock_guard<std::mutex> l(g_replyLock);
    std::cout << o.str() << std::endl;
}
static void replyError(const std::string& why) { reply(Obj().b("ok", false).s("error", why)); }
static void replyCause(const std::string& why, const std::string& cause) { reply(Obj().b("ok", false).s("error", why).s("cause", cause)); }
static void replyRefused(const std::string& why) { replyCause(why, "refused"); }
static void event(Obj o) { std::lock_guard<std::mutex> l(g_eventLock); std::cerr << o.str() << std::endl; }
static void note(const std::string& text) { event(Obj().s("event", "note").s("text", text)); }

static std::string errorText(CrInt32u code) { return CrErrorString(static_cast<SCRSDK::CrError>(code)); }

// ---------------------------------------------------------------- SDK callbacks

// One outstanding wait at a time (commands are sequential); the callback thread ends it (kit/common/callback_wait.h).
static CallbackWait g_wait;
static std::atomic<bool> g_connected{false};

class Callback final : public SCRSDK::IDeviceCallback {   // static, never deleted through the SDK's base, which has no virtual destructor
public:
    void OnConnected(SCRSDK::DeviceConnectionVersioin) override {
        g_connected = true;
        g_wait.finish("connect", true);
    }
    void OnDisconnected(CrInt32u e) override {
        g_connected = false;
        event(Obj().s("event", "disconnected").i("code", e).s("text", errorText(e)));
        g_wait.failAny("disconnected");
    }
    void OnError(CrInt32u e) override {
        event(Obj().s("event", "error").i("code", e).s("text", errorText(e)));
        g_wait.finish("connect", false, errorText(e));
    }
    void OnCompleteDownload(CrChar* filename, CrInt32u) override {
        g_wait.finish("download", true, sdk_session::fromCr(filename));
    }
    void OnWarning(CrInt32u w) override {
        switch (w) {
            case SCRSDK::CrWarning_Connect_Reconnecting: return;
            case SCRSDK::CrWarning_CameraSettings_Read_Result_OK: g_wait.finish("upload", true, "read ok"); return;
            case SCRSDK::CrWarning_CameraSettings_Read_Result_NG:
            case SCRSDK::CrWarning_CameraSettings_Read_Result_Invalid:
                g_wait.finish("upload", false, errorText(w)); return;
            case SCRSDK::CrWarning_CameraSettings_Save_Result_NG:
                g_wait.finish("download", false, errorText(w)); return;
        }
        event(Obj().s("event", "warning").i("code", w).s("text", errorText(w)));
    }
    void OnPropertyChangedCodes(CrInt32u num, CrInt32u* codes) override { g_wait.changed(num, codes); }
};

static Callback g_cb;
static SCRSDK::CrDeviceHandle g_dev = 0;
static SCRSDK::ICrEnumCameraObjectInfo* g_enum = nullptr;
static SCRSDK::ICrCameraObjectInfo* g_made = nullptr;   // camera object we created (LAN without discovery)
static std::string g_model, g_connection, g_mac, g_neighbourMac, g_login = "none", g_loginUnder;
static std::string g_cause;   // why the connection was refused, as a token (the header), when known

// ---------------------------------------------------------------- properties

// The name a reply shows for a property: the SDK table's spelling ("unknown(0x5021)" for a code it does not name).
static std::string propName(uint32_t code) {
    return CrDevicePropertyString(static_cast<SCRSDK::CrDevicePropertyCode>(code));
}

static Obj describe(const SCRSDK::CrDeviceProperty& p) {
    const auto t = p.GetValueType();
    Obj o;
    o.i("code", p.GetCode()).s("name", propName(p.GetCode())).i("type", t)
     .i("enable", p.GetPropertyEnableFlag()).b("writable", p.IsSetEnableCurrentValue());
    if (t == SCRSDK::CrDataType_STR) return o.s("text", sdk_session::text(p));
    o.i("current", sdk_values::current(p));
    const std::vector<long long> vals = sdk_session::packedValues(p);
    if ((t & SCRSDK::CrDataType_RangeBit) && vals.size() >= 3) o.list("range", {vals[0], vals[1], vals[2]});
    else o.list("values", vals);
    return o;
}

// NAME (with or without the CrDeviceProperty_ prefix) or a 0x code (up to 32 bits, all of it hex digits); 0 for none.
static uint32_t resolve(const std::string& key) {
    if (key.rfind("0x", 0) == 0) {
        long long v = 0;
        return sdk_values::parse(key, &v) && v > 0 && v <= 0xFFFFFFFFLL ? static_cast<uint32_t>(v) : 0;
    }
    const std::string bare = key.rfind("CrDeviceProperty_", 0) == 0 ? key.substr(17) : key;
    const auto code = static_cast<CrInt32>(CrDevicePropertyCode(bare));   // the SDK's name table answers -1 for unknown names
    return code > 0 ? static_cast<uint32_t>(code) : 0;
}

// ---------------------------------------------------------------- connection

static int propertyCount() {
    CrInt32 n = 0;
    SCRSDK::CrDeviceProperty* list = nullptr;
    const bool ok = SCRSDK::GetDeviceProperties(g_dev, &list, &n) == SCRSDK::CrError_None && list;
    if (list) SCRSDK::ReleaseDeviceProperties(g_dev, list);
    return ok ? n : 0;
}

// Connected is not ready: right after OnConnected the camera offers only a handful of properties.
// Wait 1 s, then until the property count stops changing.
static bool waitConnected(std::string* why) {
    if (!g_wait.until(20s, why)) return false;
    std::this_thread::sleep_for(1s);
    const auto end = Clock::now() + 10s;
    int last = -1, steady = 0;
    while (Clock::now() < end) {
        const int n = propertyCount();
        steady = (n > 0 && n == last) ? steady + 1 : 0;
        if (steady >= 2) return true;
        last = n;
        std::this_thread::sleep_for(300ms);
    }
    *why = "connected, but the camera's property list never settled";
    return false;
}

static bool connectLan(const std::string& ip, const std::string& modelName, std::string* why) {
    unsigned b[4];
    if (!ipv4Bytes(ip, b)) {         // camera_net.h: four numbers 0-255, nothing else (300.1.1.1 and 1.2.3.4.5 are not)
        g_cause = "bad_address";
        *why = "not an IPv4 address: " + ip;
        return false;
    }
    // a login file other users can read is not used (the header)
    const fs::path dir = camsetDir();
    const Credentials creds = readCredentials(dir);
    if (creds.open) {
        g_cause = "credentials_file_open";
        *why = openToOthersText(creds.file);
        return false;
    }
    SCRSDK::ICrCameraObjectInfo* info = sdk_session::searchAt(&g_enum, 3, ip, [](const SCRSDK::ICrCameraObjectInfo*) {});
    // the login (the header): the entry for the MAC address the SDK names for the camera it found at the address, else
    // for the one this computer's neighbour table holds for the address, else for CAMSET_MAC, else the default pair
    const std::string envMac = macKey(envText("CAMSET_MAC"));
    const std::string sdkMac = macKey(sdkMacText(info)), seenMac = neighbourMac(ip);
    const Login login = chooseLogin(creds.text, sdkMac, seenMac, envMac);
    g_login = login.from.empty() ? "none" : login.from;
    g_loginUnder = login.under;
    const bool ssh = !login.user.empty();
    if (!info) {
        // made from the address: the body named by --model or CAMSET_MODEL (the header)
        SCRSDK::CrError err = SCRSDK::CrError_None;
        g_made = sdk_session::makeAt(b, ip, modelName, envMac, ssh, note, &err);
        if (!g_made) { g_cause = "connect_failed"; *why = "camera object: " + CrErrorString(err); return false; }
        info = g_made;
    }
    // the login goes only to the camera it was saved for (the header): its fingerprint against the one kept for it,
    // under every MAC address it carries now (the neighbour table is read again: the camera has just answered)
    const fs::path trustedFile = dir / "known_cameras.json";
    sdk_session::Fingerprint fp;
    if (ssh) {
        if (const SCRSDK::CrError err = sdk_session::readFingerprint(info, &fp)) {
            g_cause = "no_answer";              // nothing answered (a restart): no trust was checked
            *why = "fingerprint: " + CrErrorString(err);
            return false;
        }
        const TrustCheck trust = checkTrust(readTrusted(fileText(trustedFile)), fp.text(), {sdkMac, seenMac, neighbourMac(ip), envMac}, ip);
        if (trust.verdict == "changed") {
            g_cause = "camera_changed";
            *why = cameraChangedText(ip, trustedFile);
            return false;
        }
    }
    g_wait.arm("connect");
    if (const SCRSDK::CrError err = sdk_session::connectTo(info, &g_cb, &g_dev, login, fp)) {
        g_cause = "connect_failed";
        *why = "connect: " + CrErrorString(err);
        return false;
    }
    if (!waitConnected(why)) { g_cause = "no_answer"; return false; }
    g_model = sdk_session::fromCr(info->GetModel());
    g_connection = "lan " + ip;
    // the camera's MAC address (the header); the neighbour table is read again, now that the camera has answered
    const std::string seen = neighbourMac(ip);
    g_mac = macKey(sdkMacText(info));
    if (g_mac.empty() && info == g_made) g_mac = seen;
    if (g_mac.empty()) g_mac = envMac;
    if (!seen.empty() && seen != g_mac) g_neighbourMac = seen;
    // connected: the camera's fingerprint is kept (again) under its MAC addresses and its address
    if (ssh && !dir.empty() && !keepTrusted(trustedFile, fp.text(), {sdkMac, seen}, ip))
        note("the camera's fingerprint could not be kept in " + trustedFile.u8string());
    return true;
}

static bool connectUsb(std::string* why) {
    for (int attempt = 1; attempt <= 5; ++attempt) {
        sdk_session::releaseFromMacCameraService(300ms);
        if (g_enum) { g_enum->Release(); g_enum = nullptr; }
        if (SCRSDK::EnumCameraObjects(&g_enum, 3) != SCRSDK::CrError_None || !g_enum || !g_enum->GetCount()) {
            g_cause = "no_usb_camera";
            *why = "no USB camera found";
            continue;
        }
        auto* info = const_cast<SCRSDK::ICrCameraObjectInfo*>(g_enum->GetCameraObjectInfo(0));
        g_wait.arm("connect");
        if (sdk_session::connectTo(info, &g_cb, &g_dev, Login{}, sdk_session::Fingerprint{}) != SCRSDK::CrError_None) {
            g_cause = "connect_failed";
            *why = "connect call failed";
            sdk_session::closeDevice(&g_dev, g_wait, false);
            continue;
        }
        if (waitConnected(why)) {
            g_cause.clear();
            g_model = sdk_session::fromCr(info->GetModel());
            g_mac = macKey(sdkMacText(info));
            g_connection = "usb";
            return true;
        }
        g_cause = "no_answer";
        sdk_session::closeDevice(&g_dev, g_wait, g_connected);   // connected but never settled: disconnected first
    }
    return false;
}

static void disconnect() {
    sdk_session::closeDevice(&g_dev, g_wait, g_connected);
    if (g_enum) g_enum->Release();
    if (g_made) g_made->Release();
    g_enum = nullptr;
    g_made = nullptr;
    SCRSDK::Release();
}

// ---------------------------------------------------------------- commands

static long long msSince(Clock::time_point t) {
    return std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - t).count();
}

static void cmdProps() {
    CrInt32 n = 0;
    SCRSDK::CrDeviceProperty* list = nullptr;
    if (SCRSDK::GetDeviceProperties(g_dev, &list, &n) != SCRSDK::CrError_None || !list) {
        if (list) SCRSDK::ReleaseDeviceProperties(g_dev, list);
        return replyError("GetDeviceProperties failed");
    }
    std::string arr = "[";
    for (CrInt32 k = 0; k < n; ++k) arr += (k ? "," : "") + describe(list[k]).str();
    SCRSDK::ReleaseDeviceProperties(g_dev, list);
    reply(Obj().b("ok", true).i("count", n).raw("props", arr + "]"));
}

static void cmdGet(const std::string& key) {
    const uint32_t code = resolve(key);
    SCRSDK::CrDeviceProperty p;
    if (!code || !sdk_session::fetch(g_dev, code, &p)) return replyError("unknown property " + key);
    reply(describe(p).b("ok", true));
}

static void cmdSet(const std::string& key, const std::string& valueText) {
    const uint32_t code = resolve(key);
    if (code)
        if (const std::string why = sdk_session::neverSet(code); !why.empty()) return replyRefused("property " + key + " is never set: " + why);
    long long value = 0;
    if (!sdk_values::parse(valueText, &value)) return replyError("bad arguments: VALUE is not a number: " + valueText);
    if (!code) return replyError("unknown property " + key);
    SCRSDK::CrDeviceProperty p;
    std::string why;
    switch (sdk_session::setValue(g_dev, g_wait, code, value, true, &p, &why)) {
        case sdk_session::Set::held: return reply(describe(p).b("ok", true));
        case sdk_session::Set::unknown: return replyError("unknown property " + key);
        case sdk_session::Set::notWritable: return replyError("not writable now");
        case sdk_session::Set::refused: return replyError(why);
        case sdk_session::Set::kept: return reply(describe(p).b("ok", false).s("error", "camera kept another value"));
    }
}

static void cmdSetStr(const std::string& key, const std::string& value) {
    const uint32_t code = resolve(key);
    if (code)
        if (const std::string why = sdk_session::neverSet(code); !why.empty()) return replyRefused("property " + key + " is never set: " + why);
    SCRSDK::CrDeviceProperty p;
    if (!code || !sdk_session::fetch(g_dev, code, &p)) return replyError("unknown property " + key);
    if (const std::string why = sdk_session::sendText(g_dev, &p, value); !why.empty()) return replyError(why);
    if (sdk_session::holdsText(g_dev, code, value, &p)) return reply(describe(p).b("ok", true));
    reply(describe(p).b("ok", false).s("error", "camera kept another value"));
}

// The guards camlink keeps itself (the header): a never button is never pressed, a guarded one only when the caller
// says it allows it, one no list names never, and the hold is capped; the Up is tried three times, so a button is not
// left held.
static void cmdPress(const std::string& name, const std::string& holdText, bool allowed) {
    const uint32_t button = remote::buttonCode(name);
    if (!button) return replyError("unknown button " + name);
    switch (remote::pressRule(name, allowed)) {
        case remote::Press::allowed: break;
        case remote::Press::never:
            return replyRefused("button " + name + " is never pressed (docs/decisions/0002 and 0007)");
        case remote::Press::guarded:
            return replyRefused("button " + name + " is pressed only where the caller allows it: press " + name + " HOLD_MS allowed");
        case remote::Press::unlisted:
            return replyRefused("button " + name + " is on none of kit/common/never_touch.h's lists, so it is never pressed");
    }
    long long hold = 60;
    if (!holdText.empty() && !sdk_values::parse(holdText, &hold)) return replyError("bad arguments: HOLD_MS is not a number: " + holdText);
    const int holdMs = static_cast<int>(std::max<long long>(never_touch::kMinHoldMs, std::min<long long>(hold, never_touch::kMaxHoldMs)));
    const auto t0 = Clock::now();
    const sdk_session::Pressed r = sdk_session::press(g_dev, button, std::chrono::milliseconds(holdMs));
    if (!r.up)
        return reply(Obj().b("ok", false).s("error", "button " + name + " not accepted: its release was refused three times, "
                                                     "so it may still be held").s("cause", "button_held"));
    if (!r.down) return replyError("button not accepted");
    reply(Obj().b("ok", true).b("was_idle", r.idle).i("hold_ms", holdMs).i("ms", msSince(t0)));
}

static void cmdDial(const std::string& name, const std::string& stepsText) {
    const uint32_t dial = remote::dialCode(name);
    if (!dial) return replyError("unknown dial " + name);
    if (remote::pressRule(name, false) != remote::Press::allowed)
        return replyRefused("dial " + name + " is on none of kit/common/never_touch.h's lists of inputs turned, so it is never turned");
    long long steps = 0;
    if (!sdk_values::parse(stepsText, &steps) || steps == 0 || steps < -32768 || steps > 32767) return replyError("steps out of range");
    const auto t0 = Clock::now();
    sdk_session::buttonsIdle(g_dev, 2s);
    if (!sdk_session::turn(g_dev, dial, static_cast<int>(steps))) return replyError("dial not accepted");
    reply(Obj().b("ok", true).i("ms", msSince(t0)));
}

static void cmdOsd(const std::string& path) {
    if (path.empty()) return replyError("bad arguments: osd PATH");   // else the camera is asked and ./.part written
    const auto t0 = Clock::now();
    long long bytes = 0;
    if (const std::string why = sdk_session::saveOsd(g_dev, fs::u8path(path), &bytes); !why.empty()) return replyError(why);
    reply(Obj().b("ok", true).s("path", path).i("bytes", bytes).i("ms", msSince(t0)));
}

static void cmdDownload(const std::string& dir, const std::string& name) {
    const auto t0 = Clock::now();
    // the camera must allow the save (else download_refused), and an existing file is never replaced
    const sdk_session::Download d = sdk_session::downloadSettings(g_dev, g_wait, fs::u8path(dir), name, {"_camlink_tmp", true, false});
    if (!d.error.empty()) return d.refused ? replyCause(d.error, "download_refused") : replyError(d.error);
    std::error_code ec;
    const auto bytes = fs::file_size(d.path, ec);
    reply(Obj().b("ok", true).s("path", d.path.u8string()).i("bytes", ec ? 0 : static_cast<long long>(bytes)).i("ms", msSince(t0)));
}

// The copy the SDK is given, removed however cmdUpload ends, an exception included (a "note" event when it cannot be).
struct UploadCopy {
    fs::path path;
    void remove() {
        if (path.empty()) return;
        std::error_code ec;
        if (!fs::remove(path, ec) || ec)
            note("the copy sent to the camera, " + path.u8string() + ", could not be removed" + (ec ? ": " + ec.message() : "") +
                 "; delete it by hand");
        path.clear();
    }
    UploadCopy() = default;
    UploadCopy(const UploadCopy&) = delete;
    UploadCopy& operator=(const UploadCopy&) = delete;
    ~UploadCopy() {
        try { remove(); } catch (...) {}           // a destructor must not throw: the note is only words
    }
};

// The file is read once (kit/common/settings_file.h toSend): the bytes checked are the bytes sent. Only a settings file
// goes to the camera, and with `expected` (the SHA-256 of the camera download the kit checked, Link.upload) only those
// very bytes, so a file swapped in after the kit's check is not sent. The SDK is given a copy camlink wrote itself.
static void cmdUpload(const std::string& path, const std::string& expected) {
    const fs::path file = fs::u8path(path);
    std::error_code ec;
    if (!fs::exists(file, ec)) return replyError("no such file " + path);
    const settings_file::ToSend s = settings_file::toSend(file, expected);
    if (!s.problem.empty()) return s.cause.empty() ? replyError(s.problem) : replyCause(s.problem, s.cause);
    SCRSDK::CrDeviceProperty st;
    if (sdk_session::fetch(g_dev, SCRSDK::CrDeviceProperty_CameraSetting_ReadOperationEnableStatus, &st) &&
        st.GetCurrentValue() != SCRSDK::CrCameraSettingReadOperation_Enable)
        return replyCause("camera does not allow a settings upload now", "upload_refused");
    UploadCopy copy;
    if (const std::string why = settings_file::writeCopy(file, s.bytes, "_camlink_upload", &copy.path); !why.empty())
        return replyError("not sent: " + why + " (camlink sends a copy it writes beside the file: free space there, or "
                          "upload the file from a folder you can write to)");
    const auto t0 = Clock::now();
    const sdk_session::Upload u = sdk_session::uploadSettings(g_dev, g_wait, copy.path);
    copy.remove();                                          // before the reply: the caller may list the folder next
    if (!u.called) return replyCause(u.detail, "upload_refused");
    const bool ok = u.ended == CallbackWait::Ended::ok;
    Obj done = Obj().b("ok", ok).s(ok ? "result" : "error", u.detail).s("sha256", s.sha256).i("ms", msSince(t0));
    reply(ok ? done : done.s("cause", "upload_refused"));
}

// One command line's command, its arguments still in `in` (kit/link/protocol.h). A malformed argument throws, and
// the caller answers "bad arguments".
static void runCommand(const std::string& cmd, std::istringstream& in) {
    auto rest = [&]() { return protocol::rest(in); };
    auto word = [&]() { std::string w; protocol::word(in, w); return w; };
    if (cmd == "hello") {
        Obj o = Obj().b("ok", true).s("model", g_model).s("connection", g_connection);
        reply(g_mac.empty() ? o : o.s("mac", g_mac));
    }
    else if (cmd == "ping") reply(Obj().b("ok", true).b("connected", g_connected));
    else if (cmd == "props") cmdProps();
    else if (cmd == "get") cmdGet(word());
    else if (cmd == "set") { const std::string k = word(); const std::string v = word(); cmdSet(k, v); }
    else if (cmd == "setstr") { const std::string k = word(); cmdSetStr(k, rest()); }
    else if (cmd == "press") {
        const std::string b = word(), h = word(), mark = word();
        if (!mark.empty() && mark != "allowed") throw std::runtime_error("press BUTTON [HOLD_MS] [allowed]");
        cmdPress(b, h, mark == "allowed");
    }
    else if (cmd == "dial") { const std::string d = word(); cmdDial(d, word()); }
    else if (cmd == "osd") cmdOsd(rest());
    else if (cmd == "download") { const std::string d = word(); cmdDownload(d, rest()); }
    else if (cmd == "upload") { std::string hash; const std::string p = protocol::pathAndHash(in, hash); cmdUpload(p, hash); }
    else replyError("unknown command " + cmd);
}

// ---------------------------------------------------------------- signals (see the header)

static volatile std::sig_atomic_t g_signal = 0;

extern "C" void onSignal(int sig) {
    g_signal = sig;
#ifdef _WIN32
    std::signal(sig, onSignal);           // the Windows runtime puts the default back before calling a handler
#endif
}

static void catchSignals() {
#ifdef _WIN32
    for (int sig : {SIGINT, SIGTERM, SIGBREAK}) std::signal(sig, onSignal);
#else
    struct sigaction sa;
    std::memset(&sa, 0, sizeof sa);
    sa.sa_handler = onSignal;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;                      // no SA_RESTART: a read waiting for the next command returns at once
    for (int sig : {SIGINT, SIGTERM, SIGHUP}) sigaction(sig, &sa, nullptr);
#endif
}

// The SDK's own threads must not take a signal, so that it wakes the thread reading commands: the signals are held
// while the SDK starts and connects (its threads keep that mask), then let through for this thread alone.
static void holdSignals(bool hold) {
#ifdef _WIN32
    (void)hold;
#else
    sigset_t set;
    sigemptyset(&set);
    for (int sig : {SIGINT, SIGTERM, SIGHUP}) sigaddset(&set, sig);
    pthread_sigmask(hold ? SIG_BLOCK : SIG_UNBLOCK, &set, nullptr);
#endif
}

static std::string signalName(int sig) {
    switch (sig) {
        case SIGINT: return "SIGINT";
        case SIGTERM: return "SIGTERM";
#ifdef _WIN32
        case SIGBREAK: return "SIGBREAK";
#else
        case SIGHUP: return "SIGHUP";
#endif
        default: return "signal " + std::to_string(sig);
    }
}

// ---------------------------------------------------------------- main

// The commands, one line each, until quit, the end of input or a signal (then answered with "cause": "signal").
static void serve() {
    std::string line;
    while (!g_signal && protocol::readLine(std::cin, line)) {
        std::istringstream in(line);
        std::string cmd;
        g_id = protocol::command(in, cmd);   // "@N" first: the reply echoes it as "id"
        if (g_signal) break;              // a command read as the signal came: it is answered below, with its id, not run
        if (cmd.empty()) {
            if (!g_id.empty()) replyError("no command after the request's id");   // every request gets its one reply
            continue;
        }
        if (cmd == "quit") break;
        if (!g_connected && cmd != "ping") { replyError("disconnected"); continue; }
        try {
            runCommand(cmd, in);
        } catch (const std::exception& e) {
            replyError(std::string("bad arguments: ") + e.what());
        }
    }
    if (const int sig = g_signal) {
        event(Obj().s("event", "signal").s("signal", signalName(sig)));
        reply(Obj().b("ok", false).s("cause", "signal")
                  .s("error", "camlink stopped on " + signalName(sig) + " after the command in progress finished; "
                              "the session is closed cleanly"));
    }
}

int main(int argc, char** argv) {
    catchSignals();
    holdSignals(true);
    std::string ip = envText("CAMSET_IP");
    // the body a LAN camera is, used when the search does not find it: camera_net.h's list (lanModel)
    std::string modelName = envText("CAMSET_MODEL");
    bool usb = false;
    for (int k = 1; k < argc; ++k) {
        const std::string a = argv[k];
        if (a == "--usb") usb = true;
        else if (a == "--ip" && k + 1 < argc) ip = argv[++k];
        else if (a == "--model" && k + 1 < argc) modelName = argv[++k];
        else { std::cerr << "usage: camlink [--usb] [--ip A.B.C.D] [--model ILCE-1M2]\n"; return 2; }
    }
    if (!usb && ip.empty()) { std::cerr << "camlink: give --ip (or CAMSET_IP) or --usb\n"; return 2; }
    if (!SCRSDK::Init()) { reply(Obj().b("ok", false).s("error", "SDK init failed").s("cause", "connect_failed")); return 1; }

    std::string why;
    const bool up = usb ? connectUsb(&why) : connectLan(ip, trimmed(modelName), &why);
    if (!up) {
        Obj failed = Obj().b("ok", false).s("error", why);
        reply(failed.s("cause", g_cause.empty() ? "connect_failed" : g_cause));   // connect_failed: no cause more precise
        disconnect();
        return 1;
    }
    Obj ready = Obj().b("ok", true).s("ready", g_model).s("connection", g_connection);
    if (!g_mac.empty()) ready.s("mac", g_mac);
    if (!g_neighbourMac.empty()) ready.s("neighbour_mac", g_neighbourMac);
    ready.s("login", g_login);
    if (!g_loginUnder.empty()) ready.s("login_under", g_loginUnder);
    ready.b("upload_sha256", true);                     // upload takes the SHA-256 the kit checked (the header)
    reply(ready);

    holdSignals(false);
    serve();
    const int sig = g_signal;
    disconnect();
    return sig ? 128 + sig : 0;
}
