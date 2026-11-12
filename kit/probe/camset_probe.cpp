// camset_probe: map Sony camera properties to CAMSET.DAT records automatically.
//
// For each settable property it: changes the value, downloads the camera
// settings file over USB, restores the original value. A Python script then
// diffs every downloaded file against the baseline.
//
// It never uploads a settings file unless you run the explicit `upload`
// command (upload makes the camera reboot).
//
// Usage (the editor uses discover, list, download and upload):
//   camset_probe discover                             list cameras the SDK sees (USB and network), one JSON line each
//   camset_probe list     [--out DIR]                 write DIR/properties.json
//   camset_probe download NAME [--out DIR]            download one settings file (DIR/NAME.DAT, replaced if there)
//   camset_probe sweep    [--out DIR] [--include RE] [--exclude RE]
//                         [--values one|all] [--max-values N] [--max N] [--dry-run]
//   camset_probe upload   FILE.DAT                    restore a settings file (camera reboots)
//   camset_probe watch | osd [FILE] | press BTN.. | set NAME VALUE | setstr NAME TEXT
//   camset_probe serve    [--max-seconds N]           commands on stdin, one reply line each; ends after N s (600)
// DIR is probe_out in the current folder unless given; only the commands that write into it make it (list,
// download, sweep, watch, serve, osd without FILE), so discover and upload write nothing beside the program. VALUE
// and N are decimal or 0x hex. An option this program does not know, a number that is not one, or a regular
// expression that does not compile is refused before any connection. kit/probe/values_include.txt holds an --include
// list for a sweep of the settings that hold a value: --include "$(cat kit/probe/values_include.txt)".
// On Windows the arguments are read as UTF-16 and every path goes to the SDK whole, so a folder name outside the
// ANSI code page (the editor's camera folder is under the user's own) arrives as it is.
//
// What it never sends, whoever asks (kit/common, shared with the camera link): a button other than the menus' own
// (the arrows, Enter, Menu, the multi-selector and the dials: never_touch.h, by the rule in remote.h), since it reads
// no screen first: `press` naming one is refused before any connection, and none of its buttons is pressed; C4 and
// the other guarded buttons only the kit presses, once it has read the screen; a property never_touch.h names (sound,
// light, motion, credentials, identity, actions, the buttons and dials themselves): a set or setstr naming one is
// refused before any connection, as is a set whose VALUE is no number, and every set, the sweep's included, is judged
// again by the SDK's name for the code it would set (setAndConfirm), so the sweep leaves those properties out; an
// upload of a file that is not a settings file (settings_file.h: its records must frame up to a checksum that holds),
// refused before any connection with cause not_a_settings_file. serve ends after --max-seconds whatever arrives, as a
// run's STOP file would, and burst presses at most 64 times. An error in a command once connected (a serve line whose
// value is no number) is said and the session closed cleanly, never cut off by an exception.
//
// Network: CAMSET_IP=A.B.C.D (and CAMSET_MAC=AA:BB:CC:DD:EE:FF, the camera's MAC address, when known). The access-
// authentication user name and password come from ~/.config/camset/network.json (%USERPROFILE% on Windows, mode 600),
// written by the person or the editor's Save, never from the command line:
//   {"user": "...", "password": "...",                                      the default pair
//    "cameras": {"AA:BB:CC:DD:EE:FF": {"name": "...", "user": "...", "password": "..."}}}   one camera's own pair
// The first camera entry found wins, looked up (case does not matter) by the MAC address the SDK names for the camera
// it finds at CAMSET_IP, then by the MAC address this computer's own network neighbour table (ARP) holds for
// CAMSET_IP, then by CAMSET_MAC; else the default pair, else none. One camera can carry two MAC addresses, since the
// SDK names its wired or its wireless LAN card's by model and not by the connection in use (Sony's API reference),
// while the neighbour table holds the card that answered at the address. The lookup and the MAC address reading are
// shared with the camera link (kit/common/camera_net.h), so both pick the same login. The file must be private: one
// that other users of this computer can read is refused (cause credentials_file_open; Windows: not checked).
//
// The login goes only to the camera it was saved for: before Connect, the fingerprint the camera at CAMSET_IP shows
// (GetFingerprint) is compared with the one kept for it in ~/.config/camset/known_cameras.json (its shape and how a
// camera is looked up: kit/common/camera_net.h); one that differs refuses the connection (cause camera_changed) and
// nothing is sent. A camera met for the first time is trusted, and kept there after the connection succeeds.
//
// CAMSET_MODEL=ILCE-1M2: the camera's model, which the editor passes from the known camera when it has one. It is used
// only when the SDK's search does not list a camera at CAMSET_IP and the camera object is made from the address; a
// missing or unknown model gives a `note:` line, and the helper asks as for the first body of camera_net.h's list.
//
// discover prints one JSON object per camera, with "found" saying how: "search" (the SDK's search listed it) or
// "address" (CAMSET_IP is set, two searches did not list a camera there, and one answered when asked at that
// address; its "mac" is then the neighbour table's, empty when the table holds none, its "model" CAMSET_MODEL's when
// that is a body camera_net.h knows, else empty, and its "id" is empty).
// "id" is the SDK's id for the camera as text when it is text (every byte printable ASCII or NUL, one at least
// printable: a USB camera's body serial number), whatever "id_type" says, and empty otherwise (the network id is a
// binary record); "id_hex" is the raw id (GetId, GetIdSize bytes, at most 64) as lower-case hex in every case, the
// evidence when "id" comes out empty; "id_type" is the SDK's id type, as information.
//
// After every connection (download, upload and every other command but discover), up to three lines name the camera,
// each only when known, so the editor recognises the same body over USB and over the network:
//   serial: <text>      the body's serial number (CrDeviceProperty_BodySerialNumber; else the SDK's id when it is text)
//   mac: <AA:BB:...>    the connected camera object's MAC address (a network camera); for an object made from the
//                       address without one, the MAC address the neighbour table holds for the address
//   model: <ILCE-...>   the model
// Before them, one `note:` line each when the serial number did not come from the property:
//   note: the camera did not list its serial number property
//   note: the camera listed its serial number property with no text
//   note: serial taken from the camera object's id      after either, when the id's text (as "id" in discover)
//                                                       gave the serial: line
//
// When a connection fails, one machine-readable line `cause: <token>` goes to stdout, at most once per
// run (the first cause found), before the human-readable messages. The editor turns it into plain words.
//   credentials_missing    network: the camera asks for access authentication and no user name is saved
//                          in ~/.config/camset/network.json (Connect is not tried)
//   credentials_rejected   network: the camera refused the user name or password
//   camera_not_trusted     network: the camera's fingerprint was read, and Connect found it did not check out
//   camera_changed         network: the camera at the address shows another fingerprint than the one kept for it in
//                          ~/.config/camset/known_cameras.json (Connect is not tried, nothing is sent); one line
//                          `trusted_before: <MAC address or address>` follows for each kept entry that differs
//   credentials_file_open  network: ~/.config/camset/network.json can be read by other users (it is not used)
//   usb_cable_in          network: the camera at the address was not seen, but a camera is on USB
//                          (while the cable is in, the camera does not answer on the network)
//   no_answer              network: the camera did not answer: its fingerprint could not be read at all (a camera
//                          restarting after an upload, not yet on the network), or Connect started but no connection
//                          came (timeout, disconnect, other error)
//   held_by_other_program  USB: the camera was held by another program on every attempt
//   no_usb_camera          USB: the SDK lists no camera
//   usb_no_permission      USB, Linux only: a Sony device is on the USB bus but the SDK lists nothing
//                          (the udev rule kit/setup.py prints is missing)
//   bad_address            network: CAMSET_IP is not four numbers 0-255 (nothing is tried)
//   connect_failed         the camera object or the Connect call failed at once, or the connection failed with no
//                          cause above (the last word, printed only when none came first)
// and, once connected, when the command itself fails:
//   download_refused       the camera would not save its settings (no card, a menu open, a timeout)
//   upload_refused         the camera would not take the file
//   not_a_settings_file    upload: the file is not a settings file (kit/common/settings_file.h); nothing was sent

#include <algorithm>
#include <atomic>
#include <cctype>
#include <chrono>
#include <climits>
#include <condition_variable>
#include <csignal>
#include <cstdio>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <mutex>
#include <regex>
#include <set>
#include <sstream>
#include <string>
#include <system_error>
#include <thread>
#include <vector>

// kit/common: camera_net.h first (the MAC address, the login, the trusted cameras; on Windows winsock2.h must come
// before the SDK's headers), sdk_session.h (the SDK's steps both helpers share, with the SDK's headers),
// callback_wait.h (the wait on the SDK's thread), never_touch.h (written from kit/camkit/safety.py: the buttons and
// properties never sent) and remote.h (the button and dial codes and their rule), sdk_values.h (a property's value
// as its type reads it, and a number as a command gives it), settings_file.h (the check before an upload)
#include "camera_net.h"
#include "sdk_session.h"
#include "callback_wait.h"
#include "never_touch.h"
#include "remote.h"
#include "sdk_values.h"
#include "settings_file.h"

#ifdef _WIN32
#include <shellapi.h>   // CommandLineToArgvW: the arguments as UTF-16
#endif

namespace fs = std::filesystem;
using namespace std::chrono_literals;
using sdk_session::fromCr;

// Properties never touched by the sweep: actions, connectivity, media,
// clock, lens motion and anything that is only a status readout.
static const char* kDefaultExclude =
    "S1|S2|AEL|FEL|AWBL|Reserved|Shutter_?Half|Release|Remocon|Touch|"
    "Format|Reset|Delete|Erase|Power|Cleaning|Pixel_?Mapping|"
    "Zoom|Focus_?Position|FocusDriveWithoutAF|Iris_?Drive|Lens_?Drive|PushAuto|"
    "FTP|Network|Wired|Wireless|Wi_?Fi|WiFi|Bluetooth|Password|SSH|LAN|IPTC|Stream|"
    "Upload|Media|Slot|Card|Recording_?State|Movie_?Rec|RecordingFolder|FileNumber|"
    "DateTime|TimeZone|Area|Daylight|Battery|Temperature|Status|Enable$|EnableStatus|"
    "LiveView|Monitor_?LUT_?Setting|SceneFile|Custom_?Grid|Contents|Playback|"
    "ImageID|Copyright|Artist|Owner|Camera_?Name|Serial|Version|Model|"
    "BodyKeyLock|PriorityKey|StoreDestination|Trans_?Size|RemoteSaveImageSize|OSDImageMode|"
    "RecorderControl|CameraButtonFunction|CameraDialFunction|CameraLeverFunction|Synchroterminal|Eframing";

// ---------- small helpers ----------

// The one machine-readable cause line (see the header): printed at most once per run, the first cause found.
static void printCause(const char* token) {
    static bool printed = false;
    if (printed) return;
    printed = true;
    std::cout << "cause: " << token << std::endl;
}

// Linux: a Sony device (USB vendor 054c) on the bus. When the SDK lists nothing while one is there,
// this user may not open it: the udev rule kit/setup.py prints is missing.
static bool sonyOnUsbBus() {
#ifdef __linux__
    std::error_code ec;
    for (fs::directory_iterator it("/sys/bus/usb/devices", ec), end; !ec && it != end; it.increment(ec)) {
        std::ifstream f(it->path() / "idVendor");
        std::string v;
        if (f >> v && v == "054c") return true;
    }
#endif
    return false;
}

// The SDK's name for a property code as its table spells it ("unknown(0x5021)" for one it does not name).
static std::string propName(uint32_t code) {
    return CrDevicePropertyString(static_cast<SCRSDK::CrDevicePropertyCode>(code));
}

// Settable values: GetSetValues when present, else GetValues. For range types the list is [min, max, step], spelled
// out here (at most 64 values; it stops before a step would pass the maximum, or overflow).
static std::vector<long long> possibleValues(const SCRSDK::CrDeviceProperty& p, bool* isRange) {
    *isRange = (p.GetValueType() & SCRSDK::CrDataType_RangeBit) != 0;
    // ArrayBit only describes the list of allowed values; the current value is a scalar.
    std::vector<long long> out = sdk_session::packedValues(p);
    if (*isRange && out.size() >= 3 && out[2] > 0) {
        std::vector<long long> r;
        const unsigned long long step = static_cast<unsigned long long>(out[2]);
        for (long long v = out[0]; v <= out[1] && r.size() < 64;) {
            r.push_back(v);
            // the distance left, exact in unsigned arithmetic whatever the signs
            if (static_cast<unsigned long long>(out[1]) - static_cast<unsigned long long>(v) < step) break;
            v = static_cast<long long>(static_cast<unsigned long long>(v) + step);
        }
        return r;
    }
    return out;
}

// ---------- SDK session ----------

// One outstanding wait at a time; the callback thread ends it (kit/common/callback_wait.h). Nothing the callbacks
// touch lives on the main thread's stack, so a callback that comes after its wait gave up finds the wait disarmed.
static CallbackWait g_wait;
static std::atomic<bool> g_connected{false};
static std::atomic<bool> g_stop{false};
static std::atomic<bool> g_disconnected{false};
static std::atomic<CrInt32u> g_lastError{0};   // the last code OnError received (0: none); the connect paths read it

class Callback final : public SCRSDK::IDeviceCallback {   // static, never deleted through the SDK's base, which has no virtual destructor
public:
    void OnConnected(SCRSDK::DeviceConnectionVersioin) override {
        g_connected = true;
        g_wait.finish("connect", true);
    }
    void OnDisconnected(CrInt32u) override {
        g_connected = false;
        g_disconnected = true;
        g_wait.failAny("disconnected");
    }
    // Nothing here writes to stdout, where the main thread writes the lines the editor reads (cause:, serial:, mac:):
    // a line from this thread could land inside one of them. The main thread says what OnError meant (connectAndWait);
    // the SDK's own error goes to stderr, in one write.
    void OnError(CrInt32u e) override {
        g_lastError = e;
        if (e != SCRSDK::CrError_Connect_SessionAlreadyOpened)
            std::cerr << ("SDK error: " + CrErrorString(static_cast<SCRSDK::CrError>(e)) + "\n");
        g_wait.failAny("error");
    }
    void OnCompleteDownload(CrChar* filename, CrInt32u) override { g_wait.finish("download", true, fromCr(filename)); }
    void OnWarning(CrInt32u w) override {
        if (w == SCRSDK::CrWarning_Connect_Reconnecting) return;
        if (w == SCRSDK::CrWarning_CameraSettings_Save_Result_NG ||
            w == SCRSDK::CrWarning_CameraSettings_Read_Result_NG ||
            w == SCRSDK::CrWarning_CameraSettings_Read_Result_Invalid) {
            g_wait.failAny(CrErrorString(static_cast<SCRSDK::CrError>(w)));
            return;
        }
        if (w == SCRSDK::CrWarning_CameraSettings_Read_Result_OK) g_wait.finish("upload", true, "read_ok");
    }
    void OnPropertyChangedCodes(CrInt32u num, CrInt32u* codes) override { g_wait.changed(num, codes); }
};

static Callback g_cb;
static SCRSDK::CrDeviceHandle g_dev = 0;
static SCRSDK::ICrEnumCameraObjectInfo* g_enum = nullptr;
// Network connection: set CAMSET_IP=192.168.x.y. The camera object made from the address, when the search does not
// list the camera there.
static SCRSDK::ICrCameraObjectInfo* g_netInfo = nullptr;

static bool getProp(uint32_t code, SCRSDK::CrDeviceProperty* out) { return sdk_session::fetch(g_dev, code, out); }

// A camera object's id as text: its printable bytes when every byte is printable ASCII or NUL and one at least is
// printable (a USB camera's id is the body's serial number), whatever GetIdType() says; empty otherwise (the network
// id is a binary record). The id type is not checked: on a Linux PC the USB serial number stopped showing once the
// helper kept the id only for the USB id type (docs/PORTING.md, 2026-11-05).
static std::string idText(const SCRSDK::ICrCameraObjectInfo* o) {
    std::string id;
    if (!o || !o->GetId()) return id;
    const CrInt8u* b = o->GetId();
    for (CrInt32u j = 0; j < o->GetIdSize(); ++j) {
        if (b[j] >= 32 && b[j] <= 126) id += static_cast<char>(b[j]);
        else if (b[j] != 0) return std::string();
    }
    return id;
}

// A camera object's raw id, whatever its type, as lower-case hex: at most the first 64 bytes.
static std::string idHex(const SCRSDK::ICrCameraObjectInfo* o) {
    static const char digits[] = "0123456789abcdef";
    std::string hex;
    if (o && o->GetId()) {
        const CrInt8u* b = o->GetId();
        for (CrInt32u j = 0; j < o->GetIdSize() && j < 64; ++j) { hex += digits[b[j] >> 4]; hex += digits[b[j] & 15]; }
    }
    return hex;
}

static void printIdentity(const SCRSDK::ICrCameraObjectInfo* info, bool made, const std::string& ip);   // after listProps

// The connection's last step, shared by both ways in: Connect, then up to `timeout` for OnConnected. False, with
// *called false, when the SDK refused the call itself.
static bool connectAndWait(SCRSDK::ICrCameraObjectInfo* info, const Login& login, const sdk_session::Fingerprint& fp,
                           std::chrono::milliseconds timeout, bool* called, SCRSDK::CrError* err) {
    g_lastError = 0;
    g_wait.arm("connect");
    *err = sdk_session::connectTo(info, &g_cb, &g_dev, login, fp);
    *called = *err == SCRSDK::CrError_None;
    if (!*called) {
        g_wait.arm("");
        return false;
    }
    if (g_wait.until(timeout, nullptr)) return true;
    // macOS's own camera service grabs a USB camera first; the connect loop releases it and retries, so this one is
    // expected and not an error
    if (g_lastError == SCRSDK::CrError_Connect_SessionAlreadyOpened)
        std::cout << "note: the camera was held by another program (macOS camera service); released it\n";
    return false;
}

static bool connectNetwork(const std::string& ip) {
    unsigned b[4];
    if (!ipv4Bytes(ip, b)) {         // camera_net.h: four numbers 0-255, nothing else (300.1.1.1 and 1.2.3.4.5 are not)
        printCause("bad_address");
        std::cerr << "CAMSET_IP is not an IPv4 address: " << ip << "\n";
        return false;
    }
    // a login file other users can read is not used (the header)
    const fs::path dir = camsetDir();
    const Credentials creds = readCredentials(dir);
    if (creds.open) {
        printCause("credentials_file_open");
        std::cerr << openToOthersText(creds.file) << "\n";
        return false;
    }
    // prefer the camera object the SDK itself discovers on the network (it carries everything Connect needs)
    bool usbCamera = false;
    SCRSDK::ICrCameraObjectInfo* info = sdk_session::searchAt(&g_enum, 5, ip, [&](const SCRSDK::ICrCameraObjectInfo* o) {
        const std::string oip = narrow(o->GetIPAddressChar()), via = narrow(o->GetConnectionTypeName());
        std::cout << "found: " << narrow(o->GetModel()) << " via " << via << (oip.empty() ? "" : " at " + oip)
                  << (o->GetSSHsupport() ? " (SSH)" : "") << "\n";
        if (via.find("USB") != std::string::npos) usbCamera = true;
    });
    // a camera on a USB cable does not answer on the network; the connect below then fails on its own
    if (usbCamera && !info) {
        printCause("usb_cable_in");
        std::cout << "note: a camera is on a USB cable and none answered at " << ip
                  << "; while the cable is in, the camera does not answer on the network\n";
    }
    const std::string envMac = macKey(envText("CAMSET_MAC"));   // e.g. 00:11:22:33:44:55
    // the login (the header): the entry for the MAC address the SDK names for the camera it found at the address, else
    // for the one this computer's neighbour table holds for the address, else for CAMSET_MAC, else the default pair
    const std::string sdkMac = macKey(sdkMacText(info)), seenMac = neighbourMac(ip);
    if (!sdkMac.empty() && !seenMac.empty() && sdkMac != seenMac)
        std::cout << "note: the SDK names the camera's MAC address " << sdkMac << "; this computer's network table holds "
                  << seenMac << " for " << ip << " (the SDK may name the camera's other network card)\n";
    const Login login = chooseLogin(creds.text, sdkMac, seenMac, envMac);
    const char* via = login.under == "neighbour_mac" ? ", under the MAC address this computer's network table holds for its address"
                    : login.under == "CAMSET_MAC" ? ", under CAMSET_MAC" : "";
    if (login.from == "camera") std::cout << "note: using the user name saved for this camera" << via << "\n";
    else if (login.from == "default") std::cout << "note: using the default user name (none is saved for this camera)\n";
    const bool ssh = !login.user.empty();
    if (!info) {
        // made from the address: the body is CAMSET_MODEL's (the header)
        SCRSDK::CrError err = SCRSDK::CrError_None;
        g_netInfo = sdk_session::makeAt(b, ip, trimmed(envText("CAMSET_MODEL")), envMac, ssh,
                                        [](const std::string& text) { std::cout << "note: " << text << "\n"; }, &err);
        if (!g_netInfo) {
            printCause("connect_failed");
            std::cerr << "network camera object failed: " << CrErrorString(err) << "\n";
            return false;
        }
        info = g_netInfo;
    }
    if (info->GetSSHsupport() && !ssh) {
        // the camera will refuse a connection without the pair: say so instead of trying
        printCause("credentials_missing");
        std::cerr << "the camera asks for access authentication and no user name is saved in ~/.config/camset/network.json\n";
        return false;
    }
    // the login goes only to the camera it was saved for (the header): the fingerprint against the one kept for it,
    // under every MAC address it carries now (the neighbour table is read again: the camera has just answered)
    const fs::path trustedFile = dir / "known_cameras.json";
    sdk_session::Fingerprint fp;
    if (ssh) {
        if (const SCRSDK::CrError err = sdk_session::readFingerprint(info, &fp)) {
            // nothing answered at the address (a camera restarting after an upload makes its object from the address
            // and fails here): no trust was checked, so this is no trust problem
            printCause("no_answer");
            std::cerr << "the camera did not answer: its fingerprint could not be read: " << CrErrorString(err) << "\n";
            return false;
        }
        std::cout << "fingerprint: " << fp.text() << "\n";
        const TrustCheck trust = checkTrust(readTrusted(fileText(trustedFile)), fp.text(), {sdkMac, seenMac, neighbourMac(ip), envMac}, ip);
        if (trust.verdict == "changed") {
            printCause("camera_changed");
            for (const std::string& k : trust.differ) std::cout << "trusted_before: " << k << "\n";
            std::cerr << cameraChangedText(ip, trustedFile) << "\n";
            return false;
        }
        if (trust.verdict == "new") std::cout << "note: the first connection to this camera: its fingerprint is kept for the next ones\n";
    }
    std::cout << "Camera: network " << ip << (ssh ? " (authenticated)" : "") << "\n";
    bool called = false;
    SCRSDK::CrError err = SCRSDK::CrError_None;
    if (!connectAndWait(info, login, fp, 20s, &called, &err)) {
        if (!called) {
            printCause("connect_failed");
            std::cerr << "Connect call failed: " << CrErrorString(err) << "\n";
            return false;
        }
        const CrInt32u e = g_lastError;
        if (e == SCRSDK::CrError_Connect_SSH_UserAuthenticationFailed) printCause("credentials_rejected");
        else if (e == SCRSDK::CrError_Connect_SSH_ServerAuthenticationFailed)
            printCause("camera_not_trusted");   // the fingerprint was read and did not check out; one not read is no_answer
        else printCause("no_answer");   // timed out, disconnected or another error, unless a cause above came first
        std::cerr << "network connection failed (check Wired LAN Connect, Remote Shoot Setting and the access user/password)\n";
        return false;
    }
    std::this_thread::sleep_for(1s);
    printIdentity(info, info == g_netInfo, ip);
    // connected: the camera's fingerprint is kept (again) under its MAC addresses and its address
    if (ssh && !dir.empty() && !keepTrusted(trustedFile, fp.text(), {sdkMac, neighbourMac(ip)}, ip))
        std::cout << "note: the camera's fingerprint could not be kept in " << trustedFile.u8string() << "\n";
    return true;
}

static bool connectUsb() {
    sdk_session::releaseFromMacCameraService(300ms);
    const SCRSDK::CrError enumErr = SCRSDK::EnumCameraObjects(&g_enum, 5);
    if (enumErr != SCRSDK::CrError_None || !g_enum || g_enum->GetCount() == 0) {
        if (sonyOnUsbBus()) {
            printCause("usb_no_permission");
            std::cerr << "A Sony camera is plugged in, but this user may not open it. If a normal user cannot see the camera\n"
                         "over USB, a udev rule (kit/setup.py prints it under camera access):\n"
                         "  echo 'SUBSYSTEM==\"usb\", ATTR{idVendor}==\"054c\", MODE=\"0666\"' | sudo tee /etc/udev/rules.d/60-sony-camera.rules"
                         " && sudo udevadm control --reload-rules && sudo udevadm trigger\n"
                         "then unplug and replug the camera.\n";
        } else {
            printCause("no_usb_camera");
        }
        std::cerr << "SDK enumeration result: " << (enumErr ? CrErrorString(enumErr) : std::string("no devices")) << "\n";
        std::cerr << "No camera found. Connect the camera by USB, turn on PC Remote in the\n"
                     "camera's Network menu, and set its connection method to USB.\n";
        return false;
    }
    auto* info = const_cast<SCRSDK::ICrCameraObjectInfo*>(g_enum->GetCameraObjectInfo(0));
    std::cout << "Camera: " << narrow(info->GetModel()) << "\n";
    // launchd relaunches ptpcamerad within seconds and it re-grabs the camera, so it is stopped again right before
    // each attempt
    const int attempts = 5;
    int held = 0;   // attempts refused because another program holds the camera
    for (int attempt = 1; attempt <= attempts; ++attempt) {
        sdk_session::releaseFromMacCameraService(200ms);
        bool called = false;
        SCRSDK::CrError err = SCRSDK::CrError_None;
        if (connectAndWait(info, Login{}, sdk_session::Fingerprint{}, 15s, &called, &err)) {
            std::this_thread::sleep_for(1s);
            printIdentity(info, false, "");
            return true;
        }
        if (!called) { printCause("connect_failed"); std::cerr << "Connect call failed\n"; return false; }
        if (g_lastError == SCRSDK::CrError_Connect_SessionAlreadyOpened) ++held;
        std::cout << "note: connect attempt " << attempt << " did not get the camera; retrying\n";
        sdk_session::closeDevice(&g_dev, g_wait, g_connected);
        std::this_thread::sleep_for(1s);
    }
    if (held == attempts) printCause("held_by_other_program");
    std::cerr << "Could not connect. Quit Image Capture, Photos, Lightroom or browser tabs using the camera.\n";
    return false;
}

static bool connectCamera() {
    if (!SCRSDK::Init()) { std::cerr << "SDK Init failed\n"; return false; }
    if (const std::string ip = envText("CAMSET_IP"); !ip.empty()) return connectNetwork(ip);
    return connectUsb();
}

static void disconnectCamera() {
    sdk_session::closeDevice(&g_dev, g_wait, g_connected);
    if (g_enum) g_enum->Release();
    if (g_netInfo) g_netInfo->Release();
    g_enum = nullptr;
    g_netInfo = nullptr;
    SCRSDK::Release();
}

// Download the settings file and move it to dir/name.DAT, replacing one there. Returns the final path or "".
static std::string downloadSettings(const fs::path& dir, const std::string& name) {
    const sdk_session::Download d = sdk_session::downloadSettings(g_dev, g_wait, dir, name, {"_probe_tmp", false, true});
    if (!d.error.empty()) { std::cerr << "  " << d.error << "\n"; return ""; }
    return d.path.u8string();
}

// Set a property and wait until the camera reports the new value. Every set goes through here (set, serve's set, the
// sweep and its restore), so the properties never_touch.h names are refused here too, by the SDK's name for the code.
static bool setAndConfirm(uint32_t code, long long value) {
    if (const std::string why = sdk_session::neverSet(code); !why.empty()) {
        std::cerr << propName(code) << " REFUSED: never set: " << why << "\n";
        return false;
    }
    SCRSDK::CrDeviceProperty p;
    std::string why;
    return sdk_session::setValue(g_dev, g_wait, code, value, false, &p, &why) == sdk_session::Set::held;
}

struct PropInfo {
    uint32_t code; std::string name; SCRSDK::CrDataType type;
    int enableFlag; bool settable; long long current; bool isRange;
    std::vector<long long> values;
    std::string text;   // string properties (e.g. SoftwareVersion)
};

static std::vector<PropInfo> listProps() {
    std::vector<PropInfo> out;
    CrInt32 n = 0;
    SCRSDK::CrDeviceProperty* list = nullptr;
    if (SCRSDK::GetDeviceProperties(g_dev, &list, &n) != SCRSDK::CrError_None || !list) {
        if (list) SCRSDK::ReleaseDeviceProperties(g_dev, list);
        return out;
    }
    for (CrInt32 i = 0; i < n; ++i) {
        const auto& p = list[i];
        PropInfo pi;
        pi.code = p.GetCode();
        pi.name = propName(pi.code);
        pi.type = p.GetValueType();
        pi.enableFlag = p.GetPropertyEnableFlag();
        pi.settable = p.IsSetEnableCurrentValue();
        pi.current = sdk_values::current(p);
        pi.values = possibleValues(p, &pi.isRange);
        pi.text = sdk_session::text(p);
        out.push_back(pi);
    }
    SCRSDK::ReleaseDeviceProperties(g_dev, list);
    return out;
}

// After a connection: the lines that name the camera (see the header), each only when known. `made`: the camera
// object was made from the address (the SDK did not find the camera), so its model is a guess and the camera's own
// ModelName property is preferred, and without a MAC address of its own the one the neighbour table holds for `ip`
// (the address; empty over USB) is printed.
static void printIdentity(const SCRSDK::ICrCameraObjectInfo* info, bool made, const std::string& ip) {
    std::string serial, propModel;
    bool listed = false;
    for (int k = 0; k < 10 && !listed; ++k) {   // right after a connect the camera may not list every property yet
        if (k) std::this_thread::sleep_for(300ms);
        for (auto& p : listProps()) {
            if (p.code == SCRSDK::CrDeviceProperty_BodySerialNumber) { serial = trimmed(p.text); listed = true; }
            else if (p.code == SCRSDK::CrDeviceProperty_ModelName) propModel = trimmed(p.text);
        }
    }
    if (!listed) std::cout << "note: the camera did not list its serial number property\n";
    else if (serial.empty()) std::cout << "note: the camera listed its serial number property with no text\n";
    if (serial.empty()) {
        serial = trimmed(idText(info));
        if (!serial.empty()) std::cout << "note: serial taken from the camera object's id\n";
    }
    const std::string objModel = info ? trimmed(narrow(info->GetModel())) : "";
    const std::string model = made ? (propModel.empty() ? objModel : propModel) : (objModel.empty() ? propModel : objModel);
    std::string mac = macKey(sdkMacText(info));
    if (mac.empty() && made) mac = neighbourMac(ip);   // the card that answered at the address just now
    if (!serial.empty()) std::cout << "serial: " << serial << "\n";
    if (!mac.empty()) std::cout << "mac: " << mac << "\n";
    if (!model.empty()) std::cout << "model: " << model << "\n";
    std::cout << std::flush;
}

static void writePropsJson(const std::vector<PropInfo>& props, const fs::path& file) {
    std::ofstream o(file);
    o << "[\n";
    for (size_t i = 0; i < props.size(); ++i) {
        const auto& p = props[i];
        o << "  {\"code\": " << p.code << ", \"name\": " << jsonText(p.name) << ", \"type\": " << p.type
          << ", \"enable_flag\": " << p.enableFlag << ", \"settable\": " << (p.settable ? "true" : "false")
          << ", \"current\": " << p.current << ", \"text\": " << jsonText(p.text) << ", \"is_range\": " << (p.isRange ? "true" : "false") << ", \"values\": [";
        for (size_t j = 0; j < p.values.size(); ++j) o << (j ? ", " : "") << p.values[j];
        o << "]}" << (i + 1 < props.size() ? "," : "") << "\n";
    }
    o << "]\n";
    if (!o) std::cerr << "could not write " << file.u8string() << "\n";
}

static std::string safeName(std::string s) {
    for (auto& c : s) if (!std::isalnum(static_cast<unsigned char>(c))) c = '_';
    return s.substr(0, 60);
}

// A path for a message, quoted as streaming a path quotes it, but as UTF-8: a path streamed itself goes through
// path::string(), the ANSI code page on Windows, which throws on a name outside it.
static std::string shown(const fs::path& p) {
    std::ostringstream o;
    o << std::quoted(p.u8string());
    return o.str();
}

// The name of a file in a path given as UTF-8 text, for the logs; "" for none.
static std::string fileName(const std::string& path) { return path.empty() ? "" : fs::u8path(path).filename().u8string(); }

// ---------- remote buttons, dials and screen capture ----------

// Why this program does not press a button, or "": it presses only the menus' own buttons (never_touch.h's menu list,
// by remote.h's rule), since it reads no screen first. C4, Delete, Playback, Fn, Display and Back are pressed only by
// the kit, after it has read the screen (docs/decisions/0007); C1-C3, C5-C7, Movie, AF-On, AEL, Mode, Home and
// Thumbnail never (docs/decisions/0002).
static std::string pressRefused(const std::string& name) {
    switch (remote::pressRule(name, false)) {
        case remote::Press::allowed: return "";
        case remote::Press::never: return "never pressed (docs/decisions/0002 and 0007)";
        case remote::Press::guarded: return "pressed only by the kit, once it has read the screen (docs/decisions/0007)";
        case remote::Press::unlisted: break;
    }
    return "not a button this program presses";
}

// One press: down, hold, up (the release tried three times, so the button is not left held), then `settle` for the
// screen to redraw. False when refused (pressRefused) or not accepted.
static bool press(const std::string& name, std::chrono::milliseconds hold, std::chrono::milliseconds settle) {
    if (const std::string why = pressRefused(name); !why.empty()) { std::cerr << name << " refused: " << why << "\n"; return false; }
    const uint32_t code = remote::buttonCode(name);
    if (!code) { std::cerr << "unknown button " << name << "\n"; return false; }
    const sdk_session::Pressed r = sdk_session::press(g_dev, code, hold);
    if (!r.up) std::cerr << name << ": its release was refused three times, so it may still be held\n";
    std::this_thread::sleep_for(settle);
    return r.down && r.up;
}

// a press that waits for the redraw (calibrated 2026-10-26: always redrawn within 0.2 s)
static bool pressButton(const std::string& name) { return press(name, 100ms, 220ms); }

// A dial turned `steps`, then 350 ms for the screen. The dials as never_touch.h names them (rear_l, rear_r), or as
// this program named them before (rearl, rearr).
static bool turnDial(const std::string& name, int steps) {
    const std::string dial = name == "rearl" ? "rear_l" : name == "rearr" ? "rear_r" : name;
    const uint32_t code = remote::dialCode(dial);
    if (!code) { std::cerr << "unknown dial " << name << "\n"; return false; }
    if (remote::pressRule(dial, false) != remote::Press::allowed) { std::cerr << name << " refused: not a dial this program turns\n"; return false; }
    const bool ok = sdk_session::turn(g_dev, code, steps);
    std::this_thread::sleep_for(350ms);
    return ok;
}

static bool grabOSD(const fs::path& file) {
    long long bytes = 0;
    const std::string why = sdk_session::saveOsd(g_dev, file, &bytes);
    if (!why.empty()) std::cerr << "osd: " << why << "\n";
    return why.empty();
}

static void onSigint(int) { g_stop = true; }

// ---------- the command line ----------

// The arguments as UTF-8. Windows hands main its arguments in the ANSI code page, which cannot hold every name a
// folder may have (the editor's camera folder is under the user's own); the UTF-16 command line holds them all.
static std::vector<std::string> commandLine(int argc, char** argv) {
    std::vector<std::string> out;
#ifdef _WIN32
    int n = 0;
    if (LPWSTR* wide = CommandLineToArgvW(GetCommandLineW(), &n)) {
        for (int k = 0; k < n; ++k) out.push_back(fs::path(wide[k]).u8string());
        LocalFree(wide);
        if (n == argc) return out;
        out.clear();
    }
#endif
    for (int k = 0; k < argc; ++k) out.push_back(argv[k]);
    return out;
}

struct Options {
    std::string cmd, outDir = "probe_out", include, exclude = kDefaultExclude, valuesMode = "one";
    std::vector<std::string> args;   // the arguments that are no option: NAME, VALUE, TEXT, FILE, the buttons
    int maxProps = 100000, maxValues = 0, maxSeconds = 600;
    bool maxGiven = false, dryRun = false;
    std::string arg(size_t k) const { return k < args.size() ? args[k] : std::string(); }
};

// The options and the other arguments, in any order; false and *why for an option that is not known or lacks its
// value, or a number that is not one.
static bool parseOptions(const std::vector<std::string>& argv, Options* o, std::string* why) {
    o->cmd = argv[1];
    for (size_t i = 2; i < argv.size(); ++i) {
        const std::string& a = argv[i];
        auto text = [&](std::string* v) {
            if (i + 1 >= argv.size()) { *why = a + " needs a value"; return false; }
            *v = argv[++i];
            return true;
        };
        auto number = [&](int* v) {
            std::string t;
            long long n = 0;
            if (!text(&t)) return false;
            if (!sdk_values::parse(t, &n) || n < INT_MIN || n > INT_MAX) { *why = "a number was expected after " + a + ", not " + t; return false; }
            *v = static_cast<int>(n);
            return true;
        };
        bool ok = true;
        if (a == "--out") ok = text(&o->outDir);
        else if (a == "--include") ok = text(&o->include);
        else if (a == "--exclude") ok = text(&o->exclude);
        else if (a == "--values") ok = text(&o->valuesMode);
        else if (a == "--max") { ok = number(&o->maxProps); o->maxGiven = true; }
        else if (a == "--max-values") ok = number(&o->maxValues);
        else if (a == "--max-seconds") ok = number(&o->maxSeconds);
        else if (a == "--dry-run") o->dryRun = true;
        else if (a.rfind("--", 0) == 0) { *why = "unknown option " + a; return false; }
        else o->args.push_back(a);   // a negative VALUE ("-3") is an argument too
        if (!ok) return false;
    }
    return true;
}

static void usage() {
    std::cerr << "usage: camset_probe discover|list|download NAME|upload FILE|sweep|watch|osd [FILE]|press BTN..|"
                 "serve|set NAME VALUE|setstr NAME TEXT [--out DIR] [--include RE] [--exclude RE] [--values one|all] "
                 "[--max N] [--max-values N] [--max-seconds N] [--dry-run]\n";
}

// ---------- the commands ----------

// Cameras the SDK can see right now: USB ones in PC Remote, and network ones with Remote Shoot Function on. One JSON
// object per line, so the editor can list them; "found" says how (the header).
static int cmdDiscover() {
    if (!SCRSDK::Init()) { std::cerr << "SDK Init failed\n"; return 1; }
    sdk_session::releaseFromMacCameraService(300ms);
    int n = 0;
    bool sawEnvIp = false;
    const std::string envIp = envText("CAMSET_IP");
    std::set<std::string> listed;   // the rows printed: a second search lists them again
    auto search = [&]() {
        SCRSDK::ICrEnumCameraObjectInfo* en = nullptr;
        const SCRSDK::CrError err = SCRSDK::EnumCameraObjects(&en, 5);
        if (err != SCRSDK::CrError_None || !en) {
            if (err) std::cerr << "enumeration: " << CrErrorString(err) << "\n";
            if (en) en->Release();
            return;
        }
        for (CrInt32u k = 0; k < en->GetCount(); ++k) {
            const auto* o = en->GetCameraObjectInfo(k);
            if (!o) continue;
            const std::string ip = fromCr(o->GetIPAddressChar()), mac = sdkMacText(o), conn = fromCr(o->GetConnectionTypeName());
            if (!envIp.empty() && ip == envIp) sawEnvIp = true;
            // A USB camera's id is the body's serial number as text, kept whatever the id type says; an id that
            // is not text (the network id is a binary record Sony's samples never display) is left out of "id",
            // the MAC tells it apart; "id_hex" carries the raw bytes in every case.
            const std::string id = idText(o);
            if (!listed.insert(conn + "|" + ip + "|" + mac + "|" + id).second) continue;
            std::cout << "{\"model\":" << jsonText(fromCr(o->GetModel())) << ",\"name\":" << jsonText(fromCr(o->GetName()))
                      << ",\"connection\":" << jsonText(conn) << ",\"ip\":" << jsonText(ip)
                      << ",\"mac\":" << jsonText(mac) << ",\"ssh\":" << (o->GetSSHsupport() ? "true" : "false")
                      << ",\"pairing\":" << jsonText(fromCr(o->GetPairingNecessity())) << ",\"id\":" << jsonText(id)
                      << ",\"id_hex\":\"" << idHex(o) << "\",\"id_type\":" << o->GetIdType() << ",\"usb_pid\":" << static_cast<int>(o->GetUsbPid())
                      << ",\"found\":\"search\"}\n";
            ++n;
        }
        en->Release();
    };
    search();
    if (!envIp.empty() && !sawEnvIp) {
        // the SDK's search does not always list a network camera; once more before asking at the address
        std::cout << "note: the search did not list a camera at " << envIp << "; searching once more\n";
        search();
    }
    unsigned b[4];
    if (!envIp.empty() && !sawEnvIp && ipv4Bytes(envIp, b)) {
        // the body is CAMSET_MODEL's (the header); the row names it only when it is one the list knows
        const std::string modelName = trimmed(envText("CAMSET_MODEL"));
        SCRSDK::CrCameraDeviceModelList body{};
        const bool known = lanModel(modelName, &body);
        SCRSDK::CrError err = SCRSDK::CrError_None;
        auto noteLine = [](const std::string& text) { std::cout << "note: " << text << "\n"; };
        if (SCRSDK::ICrCameraObjectInfo* netInfo = sdk_session::makeAt(b, envIp, modelName, "", true, noteLine, &err)) {
            sdk_session::Fingerprint fp;
            if (const SCRSDK::CrError fpErr = sdk_session::readFingerprint(netInfo, &fp); fpErr == SCRSDK::CrError_None) {
                // it has just answered: this computer's neighbour table holds the card it answered on
                std::cout << "{\"model\":" << jsonText(known ? modelName : "") << ",\"name\":\"\",\"connection\":\"IP\",\"ip\":" << jsonText(envIp)
                          << ",\"mac\":" << jsonText(neighbourMac(envIp)) << ",\"ssh\":true,\"pairing\":\"\",\"id\":\"\",\"id_hex\":\"\",\"id_type\":"
                          << static_cast<int>(SCRSDK::CAMERAOBJECTID_TYPE_IP) << ",\"usb_pid\":0,\"found\":\"address\"}\n";
                ++n;
            } else {
                std::cerr << "direct check of " << envIp << ": " << CrErrorString(fpErr)
                          << " (if the camera is on, check macOS System Settings > Privacy & Security > Local Network, ensure the camera screen is open, and unplug USB)\n";
            }
            netInfo->Release();
        }
    }
    std::cout << "found " << n << " camera(s)\n";
    SCRSDK::Release();
    return 0;
}

static int cmdList(const fs::path& out) {
    const auto props = listProps();
    writePropsJson(props, out / "properties.json");
    std::cout << props.size() << " properties written to " << shown(out / "properties.json") << "\n";
    return 0;
}

static int cmdDownload(const fs::path& out, const std::string& name) {
    const std::string f = downloadSettings(out, name.empty() ? "settings" : name);
    if (f.empty()) printCause("download_refused");
    std::cout << (f.empty() ? "download failed" : "saved " + f) << "\n";
    return f.empty() ? 1 : 0;
}

// Capture a settings file each time the camera settles into a new state (mode dial turned, memory recall slot
// selected). Stops after `captures` (8 by default, the starting state included), or after 15 minutes.
static int cmdWatch(const fs::path& out, int captures) {
    auto modeName = [](long long v) -> std::string {
        switch (v) {
            case 1: return "M"; case 2: return "P"; case 3: return "A"; case 4: return "S";
            case 0x8000: return "Auto"; case 0x8001: return "AutoPlus"; case 0x8020: return "MR";
        }
        char b[24]; std::snprintf(b, sizeof b, "0x%llx", static_cast<unsigned long long>(v)); return b;
    };
    // Fingerprint = exposure mode + every settable property's value. Readouts
    // such as battery or the meter are not settable, so they do not trigger.
    auto fingerprint = [&]() {
        std::vector<long long> f;
        for (auto& p : listProps())
            if (p.settable || p.code == SCRSDK::CrDeviceProperty_ExposureProgramMode) {
                f.push_back(p.code); f.push_back(p.current);
            }
        return f;
    };
    auto currentMode = [&]() { SCRSDK::CrDeviceProperty m; return getProp(SCRSDK::CrDeviceProperty_ExposureProgramMode, &m) ? sdk_values::current(m) : -1; };
    std::ofstream man(out / "captures.jsonl", std::ios::app);
    std::vector<long long> last;
    int n = 0;
    const auto deadline = std::chrono::steady_clock::now() + 15min;
    std::cout << "Watching. Turn the mode dial; each new position is captured after it stays put for 3 seconds.\n";
    while (n < captures && !g_stop && !g_disconnected && std::chrono::steady_clock::now() < deadline) {
        auto f = fingerprint();
        if (f != last) {
            std::this_thread::sleep_for(3s);           // let the dial settle
            if (fingerprint() != f) continue;
            const long long mode = currentMode();
            char nm[64]; std::snprintf(nm, sizeof nm, "%02d_%s", n, modeName(mode).c_str());
            const std::string file = downloadSettings(out, nm);
            // The camera refuses settings saves at memory-recall positions; keep the
            // live property values instead (mr_match.py matches them to the sets).
            writePropsJson(listProps(), out / (std::string(nm) + "_properties.json"));
            std::cout << "captured " << nm << (file.empty() ? "  (settings file refused here; live properties saved)" : "") << "\n" << std::flush;
            man << "{\"n\": " << n << ", \"mode\": " << mode << ", \"mode_name\": \"" << modeName(mode)
                << "\", \"file\": " << jsonText(fileName(file)) << "}\n";
            man.flush();
            last = fingerprint();
            ++n;
        }
        std::this_thread::sleep_for(500ms);
    }
    std::cout << n << " captures written to " << shown(out) << "\n";
    return 0;
}

static int cmdOsd(const fs::path& out, const std::string& file) {
    const fs::path f = file.empty() ? out / "osd.png" : fs::u8path(file);
    const bool ok = grabOSD(f);
    std::cout << (ok ? "saved " + f.u8string() : std::string("OSD capture failed")) << "\n";
    return ok ? 0 : 1;
}

// only the menus' own buttons (pressRefused): no screen is read here first. main() refused the others before
// connecting; asked again here, next to the press
static int cmdPress(const std::vector<std::string>& buttons) {
    int rc = 0;
    for (const std::string& b : buttons) {
        if (const std::string why = pressRefused(b); !why.empty()) {
            std::cout << b << " REFUSED: " << why << "\n";
            rc = 2;
            continue;
        }
        std::cout << b << (pressButton(b) ? " ok" : " FAILED") << "\n";
    }
    return rc;
}

// serve's input, read by a thread of its own so the session can end on time with no line coming
struct Lines {
    std::mutex m;
    std::condition_variable cv;
    std::deque<std::string> q;
    bool eof = false;
};

// One serve command (its word `c`, its arguments in `ss`) and its reply line.
static std::string serveCommand(const std::string& c, std::istringstream& ss, const fs::path& out) {
    std::string reply = "ok";
    if (c == "press") { std::string b; while (ss >> b) if (!pressButton(b)) reply = "error " + b; }
    else if (c == "tap") {
        // tap BTN: one press with no redraw wait (timing measurements)
        std::string b; ss >> b;
        if (!press(b, 60ms, 0ms)) reply = "error " + b;
    }
    else if (c == "burst") {
        // burst BTN N: N quick presses (menu row moves, at most 64), one redraw wait at the end
        std::string b; int n = 1; ss >> b >> n;
        if (n < 1 || n > 64) reply = "error burst takes 1-64 presses";
        else {
            for (int k = 0; k < n && reply == "ok"; ++k)
                if (!press(b, 60ms, 90ms)) reply = "error " + b;
            std::this_thread::sleep_for(350ms);
        }
    }
    else if (c == "dial") { std::string n; int st = 0; ss >> n >> st; if (!turnDial(n, st)) reply = "error"; }
    else if (c == "osd") { std::string f; ss >> f; if (f.empty() || !grabOSD(fs::u8path(f))) reply = "error osd"; }
    else if (c == "download") { std::string n; ss >> n; const std::string f = downloadSettings(out, n); reply = f.empty() ? "error download" : "ok " + f; }
    else if (c == "get") {
        std::string n; ss >> n; reply = "error unknown";
        for (auto& p : listProps()) if (p.name == n) reply = "ok " + (p.text.empty() ? std::to_string(p.current) : p.text);
    }
    else if (c == "values") {
        // values PROP -> "ok settable=0|1 current=N values=a,b,c"
        std::string n; ss >> n; reply = "error unknown";
        for (auto& p : listProps()) if (p.name == n) {
            std::string v;
            for (size_t i = 0; i < p.values.size(); ++i) v += (i ? "," : "") + std::to_string(p.values[i]);
            reply = "ok settable=" + std::string(p.settable ? "1" : "0") + " current=" + std::to_string(p.current) + " values=" + v;
        }
    }
    else if (c == "set") {
        std::string n, v; ss >> n >> v;
        long long value = 0;
        if (const std::string why = never_touch::property(n); !why.empty()) reply = "error refused: never set: " + why;
        else if (!sdk_values::parse(v, &value)) reply = "error not a number: " + v;
        else {
            reply = "error unknown";
            for (auto& p : listProps()) if (p.name == n) reply = setAndConfirm(p.code, value) ? "ok" : "error rejected";
        }
    }
    else if (c == "sleep") { int ms = 0; ss >> ms; std::this_thread::sleep_for(std::chrono::milliseconds(std::max(0, std::min(ms, 10000)))); }
    else reply = "error unknown command";
    return reply;
}

// One connection, commands on stdin, one reply line each:
//   press BTN [BTN..] | tap BTN | burst BTN N | dial NAME STEPS | osd FILE | download NAME | get PROP |
//   values PROP | set PROP VALUE | sleep MS | quit
// The guards are the program's own (pressRefused, never_touch::property, setAndConfirm); the session ends after
// --max-seconds (default 600) whatever arrives, even when no line comes, as a run's STOP file would.
static int cmdServe(const fs::path& out, int maxSeconds) {
    std::cout << "ready" << std::endl;
    auto in = std::make_shared<Lines>();
    std::thread([in] {
        std::string l;
        while (std::getline(std::cin, l)) { std::lock_guard<std::mutex> g(in->m); in->q.push_back(l); in->cv.notify_one(); }
        std::lock_guard<std::mutex> g(in->m);
        in->eof = true;
        in->cv.notify_one();
    }).detach();
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(maxSeconds);
    while (!g_stop && !g_disconnected) {
        std::string line;
        {
            std::unique_lock<std::mutex> l(in->m);
            in->cv.wait_for(l, 500ms, [&] { return !in->q.empty() || in->eof; });
            if (std::chrono::steady_clock::now() >= deadline) {
                std::cout << "stopped: --max-seconds (" << maxSeconds << " s) reached" << std::endl;
                break;
            }
            if (in->q.empty()) {
                if (in->eof) break;
                continue;
            }
            line = in->q.front();
            in->q.pop_front();
        }
        std::istringstream ss(line);
        std::string c;
        ss >> c;
        if (c.empty()) continue;
        if (c == "quit") break;
        std::string reply;
        try {
            reply = serveCommand(c, ss, out);
        } catch (const std::exception& e) {   // never an exception out of the session: it would drop it uncleanly
            reply = std::string("error ") + e.what();
        }
        std::cout << reply << std::endl;
    }
    return 0;
}

// camset_probe set NAME VALUE   (VALUE decimal or 0x hex)
static int cmdSet(const std::string& name, const std::string& valueText) {
    uint32_t code = 0;
    for (auto& p : listProps()) if (p.name == name) code = p.code;
    long long v = 0;
    if (!code || !sdk_values::parse(valueText, &v)) { std::cerr << "usage: camset_probe set PROPERTY VALUE\n"; return 2; }
    const bool ok = setAndConfirm(code, v);
    std::cout << name << " = " << v << (ok ? "  ok" : "  NOT accepted") << "\n";
    return ok ? 0 : 1;
}

// camset_probe setstr NAME TEXT   (ASCII text; "" clears)
static int cmdSetStr(const std::string& name, const std::string& text, bool have) {
    uint32_t code = 0;
    for (auto& p : listProps()) if (p.name == name) code = p.code;
    if (!code || !have) { std::cerr << "usage: camset_probe setstr PROPERTY TEXT\n"; return 2; }
    if (const std::string why = sdk_session::neverSet(code); !why.empty()) { std::cerr << name << " REFUSED: never set: " << why << "\n"; return 2; }
    SCRSDK::CrDeviceProperty p;
    if (!getProp(code, &p)) { std::cerr << "property not readable\n"; return 1; }
    if (const std::string why = sdk_session::sendText(g_dev, &p, text); !why.empty()) {
        std::cerr << why << "\n";
        return why.rfind("set: ", 0) == 0 ? 1 : 2;   // the camera refused it, or the text was never sent
    }
    const bool ok = sdk_session::holdsText(g_dev, code, text, &p);
    std::cout << name << " = \"" << sdk_session::text(p) << "\"" << (ok ? "  ok" : "  NOT accepted") << "\n";
    return ok ? 0 : 1;
}

static int cmdUpload(const std::string& file) {
    const fs::path f = fs::u8path(file);
    std::error_code ec;
    if (file.empty() || !fs::exists(f, ec)) { std::cerr << "upload needs an existing .DAT path\n"; return 2; }
    const fs::path abs = fs::absolute(f, ec);
    std::cout << "Uploading " << (ec ? f : abs).u8string() << ". The camera will reboot.\n";
    const sdk_session::Upload u = sdk_session::uploadSettings(g_dev, g_wait, f);
    if (!u.called) { printCause("upload_refused"); std::cerr << u.detail << "\n"; return 1; }
    switch (u.ended) {
        case CallbackWait::Ended::ok: std::cout << "Upload accepted.\n"; return 0;
        case CallbackWait::Ended::failed: printCause("upload_refused"); std::cerr << "upload: " << u.detail << "\n"; return 1;
        case CallbackWait::Ended::timedOut: break;
    }
    std::cout << "No confirmation received; check the camera.\n";
    return 0;
}

// Whether a folder already holds a sweep (a .DAT or probe_log.jsonl): two sweeps never share one, since the analyzer
// relies on one clean log.
static bool holdsSweep(const fs::path& out) {
    std::error_code ec;
    for (fs::directory_iterator it(out, ec), end; !ec && it != end; it.increment(ec))
        if (it->path().extension() == ".DAT" || it->path().filename() == "probe_log.jsonl") return true;
    return false;
}

// The sweep's regular expressions, compiled before any connection: what to include, and what never to sweep. The
// exclusions are kDefaultExclude, "Flash" (the flash's settings, its compensation among them, which never_touch.h
// lets the kit set as live exposure but a sweep has no business changing) and --exclude, which adds to them, never
// replaces them (2026-11-05). What never_touch.h names (sound, light, motion, credentials, identity, actions, the
// buttons and dials; docs/decisions/0002) is left out by name as well, and refused by setAndConfirm whatever.
struct SweepRules {
    std::regex include, exclude;
};

static bool sweepRules(const Options& o, SweepRules* r, std::string* why) {
    std::string never = std::string(kDefaultExclude) + "|Flash";
    if (!o.exclude.empty() && o.exclude != kDefaultExclude) never += "|(?:" + o.exclude + ")";
    try {
        r->include = std::regex(o.include.empty() ? ".*" : o.include, std::regex::icase);
        r->exclude = std::regex(never, std::regex::icase);
    } catch (const std::regex_error& e) {
        *why = std::string("--include or --exclude is not a regular expression: ") + e.what();
        return false;
    }
    return true;
}

static int cmdSweep(const fs::path& out, const Options& o, const SweepRules& rules) {
    const auto props = listProps();
    if (!holdsSweep(out)) writePropsJson(props, out / "properties.json");   // a dry run in a sweep's folder keeps its file
    std::vector<PropInfo> todo;
    for (auto& p : props) {
        if (!p.settable || p.values.size() < 2) continue;
        if (!std::regex_search(p.name, rules.include) || std::regex_search(p.name, rules.exclude)) continue;
        if (!sdk_session::neverSet(p.code).empty()) continue;   // never_touch.h: never set, so never swept
        todo.push_back(p);
        if (static_cast<int>(todo.size()) >= o.maxProps) break;
    }
    std::cout << todo.size() << " of " << props.size() << " properties will be probed\n";
    if (o.dryRun) {
        for (auto& p : todo) std::cout << "  " << p.name << "  current=" << p.current << "  options=" << p.values.size() << "\n";
        return 0;
    }
    // Two baselines back to back: anything that differs between them is noise.
    if (downloadSettings(out, "000_baseline_a").empty() || downloadSettings(out, "001_baseline_b").empty()) {
        std::cerr << "Baseline download failed. Is a memory card in the camera?\n";
        return 1;
    }
    std::ofstream log(out / "probe_log.jsonl");
    std::vector<std::string> notRestored;
    int seq = 0;
    for (auto& p : todo) {
        if (g_stop || g_disconnected) break;
        std::vector<long long> targets;
        for (auto v : p.values) if (v != p.current) targets.push_back(v);
        if (o.valuesMode == "one" && !targets.empty()) {
            // nearest neighbour in the list keeps changes small and safe
            auto it = std::find(p.values.begin(), p.values.end(), p.current);
            long long pick = targets[0];
            if (it != p.values.end()) pick = (it + 1 != p.values.end()) ? *(it + 1) : (it != p.values.begin() ? *(it - 1) : targets[0]);
            targets = {pick};
        }
        if (o.valuesMode == "all" && o.maxValues > 1 && static_cast<int>(targets.size()) > o.maxValues) {
            // evenly spaced sample that keeps both ends
            std::vector<long long> sample;
            const double last = static_cast<double>(targets.size() - 1);
            for (int i = 0; i < o.maxValues; ++i)
                sample.push_back(targets[static_cast<size_t>(i * last / (o.maxValues - 1) + 0.5)]);
            sample.erase(std::unique(sample.begin(), sample.end()), sample.end());
            targets = sample;
        }
        std::cout << "[" << ++seq << "/" << todo.size() << "] " << p.name << "\n";
        for (auto v : targets) {
            if (g_stop || g_disconnected) break;
            const bool ok = setAndConfirm(p.code, v);
            std::string file;
            if (ok) {
                char nm[160];
                std::snprintf(nm, sizeof nm, "p%04x_%s_%lld", p.code, safeName(p.name).c_str(), v);
                file = downloadSettings(out, nm);
            }
            log << "{\"code\": " << p.code << ", \"name\": " << jsonText(p.name) << ", \"original\": " << p.current
                << ", \"value\": " << v << ", \"set_ok\": " << (ok ? "true" : "false")
                << ", \"file\": " << jsonText(fileName(file)) << "}\n";
            log.flush();
            std::cout << "    -> " << v << (ok ? (file.empty() ? "  set, download FAILED" : "  ok") : "  not accepted") << "\n";
        }
        const bool restored = setAndConfirm(p.code, p.current);
        if (!restored) {
            notRestored.push_back(p.name + " (original " + std::to_string(p.current) + ")");
            std::cerr << "    !! could not restore " << p.name << "\n";
        }
        // Reference file with this property restored: the clean "before" state
        // for the next property and the "after" state for side-effect checks.
        char rn[160];
        std::snprintf(rn, sizeof rn, "r%04x_%s", p.code, safeName(p.name).c_str());
        const std::string ref = downloadSettings(out, rn);
        log << "{\"code\": " << p.code << ", \"name\": " << jsonText(p.name)
            << ", \"restore_file\": " << jsonText(fileName(ref))
            << ", \"restored\": " << (restored ? "true" : "false") << "}\n";
        log.flush();
    }
    downloadSettings(out, "zzz_after_sweep");
    if (g_stop) std::cout << "Stopped by Ctrl-C after restoring the current property.\n";
    if (!notRestored.empty()) {
        std::cout << "\nThese properties could not be restored automatically:\n";
        for (auto& s : notRestored) std::cout << "  " << s << "\n";
        std::cout << "Fix them by hand, or load 000_baseline_a.DAT from a card with the camera menu.\n";
    }
    std::cout << "Done: the downloads and probe_log.jsonl are in " << out.u8string()
              << "; compare each download with 000_baseline_a.DAT (kit/camkit/camset.py, diff).\n";
    return 0;
}

// ---------- main ----------

int main(int argc, char** argv) {
    const std::vector<std::string> argvUtf8 = commandLine(argc, argv);
    if (argvUtf8.size() < 2) { usage(); return 2; }
    Options o;
    std::string why;
    if (!parseOptions(argvUtf8, &o, &why)) { std::cerr << why << "\n"; usage(); return 2; }
    if (o.maxSeconds < 1 || o.maxSeconds > 86400) { std::cerr << "--max-seconds takes 1-86400\n"; return 2; }
    std::signal(SIGINT, onSigint);
    const std::string& cmd = o.cmd;
    if (cmd == "discover") return cmdDiscover();

    static const std::set<std::string> kCommands = {"list", "download", "watch", "osd", "press", "serve", "set", "setstr", "upload", "sweep"};
    if (!kCommands.count(cmd)) { std::cerr << "unknown command " << cmd << "\n"; usage(); return 2; }
    std::error_code ec;
    const fs::path out = fs::absolute(fs::u8path(o.outDir), ec);
    if (ec) { std::cerr << "--out " << o.outDir << ": " << ec.message() << "\n"; return 2; }
    // the refusals that need no camera, before any connection
    if ((cmd == "set" || cmd == "setstr") && !never_touch::property(o.arg(0)).empty()) {
        // the properties never set (never_touch.h, written from kit/camkit/safety.py)
        std::cerr << o.arg(0) << " REFUSED: never set: " << never_touch::property(o.arg(0)) << "\n";
        return 2;
    }
    long long value = 0;
    if (cmd == "set" && !sdk_values::parse(o.arg(1), &value)) { std::cerr << "usage: camset_probe set PROPERTY VALUE\n"; return 2; }
    if (cmd == "setstr" && o.args.size() < 2) { std::cerr << "usage: camset_probe setstr PROPERTY TEXT\n"; return 2; }
    if (cmd == "press") {
        // only the menus' own buttons (pressRefused); one refused, and none is pressed
        int refused = 0;
        for (const std::string& b : o.args)
            if (const std::string no = pressRefused(b); !no.empty()) { std::cout << b << " REFUSED: " << no << "\n"; ++refused; }
        if (refused || o.args.empty()) {
            if (o.args.empty()) std::cerr << "usage: camset_probe press BUTTON [BUTTON ...]\n";
            return 2;
        }
    }
    if (cmd == "upload") {
        // only a settings file goes to the camera (kit/common/settings_file.h)
        const std::string bad = o.arg(0).empty() ? std::string("no file named") : settings_file::problemOfFile(fs::u8path(o.arg(0)));
        if (!bad.empty()) {
            printCause("not_a_settings_file");
            std::cerr << "Not sent: " << bad << "\n";
            return 2;
        }
    }
    SweepRules rules;
    if (cmd == "sweep") {
        if (!sweepRules(o, &rules, &why)) { std::cerr << why << "\n"; return 2; }
        if (!o.dryRun && holdsSweep(out)) { std::cerr << shown(out) << " already holds a sweep. Use a new --out folder.\n"; return 1; }
    }
    // only the commands that write into --out make it (the header): discover and upload, which the editor runs from
    // the program's own folder (inside its app bundle, or one this user may not write), make nothing there
    const bool writesOut = cmd == "list" || cmd == "download" || cmd == "watch" || cmd == "sweep" || cmd == "serve" ||
                           (cmd == "osd" && o.arg(0).empty());
    if (writesOut) {
        fs::create_directories(out, ec);
        if (ec) { std::cerr << "could not make the folder " << out.u8string() << ": " << ec.message() << "\n"; return 2; }
    }

    if (!connectCamera()) {
        printCause("connect_failed");   // the fallback: a cause found on the way was printed first
        disconnectCamera();
        return 1;
    }
    // the SDK's work folder, set after connecting as Sony's samples do: --out where the command writes into it, else
    // the system's temporary folder, so that nothing is made beside the program
    fs::path work = out;
    if (!writesOut) {
        const fs::path tmp = fs::temp_directory_path(ec);
        if (!ec) work = tmp;
    }
    sdk_session::CrString crDir = sdk_session::crPath(work), crPrefix = sdk_session::toCr("DSC");
    SCRSDK::SetSaveInfo(g_dev, crDir.data(), crPrefix.data(), -1);
    int rc = 0;
    try {
        if (cmd == "list") rc = cmdList(out);
        else if (cmd == "download") rc = cmdDownload(out, o.arg(0));
        else if (cmd == "watch") rc = cmdWatch(out, o.maxGiven ? o.maxProps : 8);
        else if (cmd == "osd") rc = cmdOsd(out, o.arg(0));
        else if (cmd == "press") rc = cmdPress(o.args);
        else if (cmd == "serve") rc = cmdServe(out, o.maxSeconds);
        else if (cmd == "set") rc = cmdSet(o.arg(0), o.arg(1));
        else if (cmd == "setstr") rc = cmdSetStr(o.arg(0), o.arg(1), o.args.size() >= 2);
        else if (cmd == "upload") rc = cmdUpload(o.arg(0));
        else if (cmd == "sweep") rc = cmdSweep(out, o, rules);
    } catch (const std::exception& e) {   // said, and the session still closed below: never dropped by an exception
        std::cerr << cmd << " stopped: " << e.what() << "\n";
        rc = 1;
    }
    disconnectCamera();
    return rc;
}
