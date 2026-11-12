// sdk_session.h: what camlink (kit/link) and the editor's camera helper (kit/probe) do the same way through Sony's
// Camera Remote SDK, so that each step is written once: the SDK's text and paths, a property read and set, a button
// press and a dial turn, the camera's screen (OSD) saved, a settings file downloaded and uploaded, macOS's camera
// service kept off a USB camera, the steps of a network connection (the camera at the address, its object made from
// the address, its fingerprint, Connect) and the session's end. Each program says what happened in its own words
// (camlink in JSON replies and events, camset_probe in lines the editor reads); the SDK is called here. It includes
// camera_net.h first, which on Windows must come before anything that brings in windows.h, then the SDK's headers.
// It needs the SDK, so no test compiles it; the parts that need none are in camera_net.h, callback_wait.h, remote.h
// and sdk_values.h, which kit/common's tests check.
#pragma once

#include "camera_net.h"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>
#include <system_error>
#include <thread>
#include <vector>

#include "CameraRemote_SDK.h"
#include "CrDebugString.h"
#include "CrDeviceProperty.h"
#include "CrImageDataBlock.h"
#include "IDeviceCallback.h"

#include "callback_wait.h"
#include "remote.h"
#include "sdk_values.h"

namespace sdk_session {

namespace fs = std::filesystem;
using namespace std::chrono_literals;
using CrString = std::basic_string<CrChar>;

// ---------- the SDK's text and paths ----------
// CrChar is wchar_t on Windows, where the SDK is built with UNICODE as in Sony's samples, and char elsewhere. Text and
// paths are UTF-8 everywhere else in the programs, and a path goes to the SDK whole (never through the ANSI code page).

inline CrString toCr(const std::string& utf8) {
#if defined(_UNICODE) || defined(UNICODE)
    return fs::u8path(utf8).wstring();
#else
    return utf8;
#endif
}

inline CrString crPath(const fs::path& p) {
#if defined(_UNICODE) || defined(UNICODE)
    return p.wstring();
#else
    return p.string();
#endif
}

// The SDK's text as UTF-8, for text that need not be ASCII: a file name, the camera's name. ASCII text (addresses,
// model names) goes through narrow (camera_net.h).
inline std::string fromCr(const CrChar* s) {
    if (!s) return "";
#if defined(_UNICODE) || defined(UNICODE)
    return fs::path(s).u8string();
#else
    return s;
#endif
}

// ---------- properties ----------

// The SDK's name for a property code (CrDebugString's table, without "CrDeviceProperty_"); "" for a code the table
// does not name, which it spells "unknown(0x5021)" (so a check for "" alone never saw one), and which has no name to
// judge it by: never set.
inline std::string propertyName(uint32_t code) {
    const std::string n = CrDevicePropertyString(static_cast<SCRSDK::CrDevicePropertyCode>(code));
    return n.rfind("unknown(", 0) == 0 ? std::string() : n;
}

// Why a property is never set (never_touch.h, written from kit/camkit/safety.py), judged by the SDK's name for its
// code, whatever name or code the caller gave; "" when it may be set.
inline std::string neverSet(uint32_t code) {
    const std::string name = propertyName(code);
    return name.empty() ? "a property the SDK's table does not name" : never_touch::property(name);
}

// One property as the camera holds it now; false when the camera does not answer for it.
inline bool fetch(SCRSDK::CrDeviceHandle dev, uint32_t code, SCRSDK::CrDeviceProperty* out) {
    CrInt32 n = 0;
    SCRSDK::CrDeviceProperty* list = nullptr;
    CrInt32u c = code;
    const bool ok = SCRSDK::GetSelectDeviceProperties(dev, 1, &c, &list, &n) == SCRSDK::CrError_None && list && n >= 1;
    if (ok) *out = list[0];   // CrDeviceProperty copies deeply: the copy outlives the list released here
    if (list) SCRSDK::ReleaseDeviceProperties(dev, list);
    return ok;
}

// A text property's value: Sony's string starts with its length in UTF-16 units, the terminator counted. Non-ASCII
// comes out as '?'.
inline std::string text(const SCRSDK::CrDeviceProperty& p) {
    std::string out;
    if (p.GetValueType() != SCRSDK::CrDataType_STR) return out;
    if (const CrInt16u* s = p.GetCurrentStr())
        for (int k = 1; k < s[0] && s[k]; ++k) out += s[k] < 128 ? static_cast<char>(s[k]) : '?';
    return out;
}

// The values a property may take, as the SDK packs them (GetSetValues when it has them, else GetValues), each read as
// its type reads it; for a range type, [min, max, step]. None for a text property.
inline std::vector<long long> packedValues(const SCRSDK::CrDeviceProperty& p) {
    std::vector<long long> out;
    const unsigned type = static_cast<unsigned>(p.GetValueType());
    const CrInt32u w = static_cast<CrInt32u>(sdk_values::width(type));
    if (!w || p.GetValueType() == SCRSDK::CrDataType_STR) return out;
    const CrInt8u* buf = p.GetSetValues();
    CrInt32u size = p.GetSetValueSize();
    if (!buf || !size) {
        buf = p.GetValues();
        size = p.GetValueSize();
    }
    for (CrInt32u k = 0; buf && size - k >= w; k += w) out.push_back(sdk_values::at(buf + k, type));   // k <= size throughout
    return out;
}

// A raw value sent as the property's new value (the button and dial functions); true when the SDK took it.
inline bool sendValue(SCRSDK::CrDeviceHandle dev, uint32_t code, CrInt64u value) {
    SCRSDK::CrDeviceProperty p;
    if (!fetch(dev, code, &p)) return false;
    p.SetCurrentValue(value);
    return SCRSDK::SetDeviceProperty(dev, &p) == SCRSDK::CrError_None;
}

// How a number set ended: the camera holds the value (it may have held it already); the property is not there, or
// not writable now (asked only with `needWritable`); the SDK refused the set; or the camera kept another value.
enum class Set { held, unknown, notWritable, refused, kept };

// Set a number property and wait until the camera holds it: its change notice is waited for up to 3 s, as a hint,
// then the value read back (20 tries, 100 ms apart) decides. *p is the property as last read; *why says a refusal.
inline Set setValue(SCRSDK::CrDeviceHandle dev, CallbackWait& wait, uint32_t code, long long value, bool needWritable,
                    SCRSDK::CrDeviceProperty* p, std::string* why) {
    if (!fetch(dev, code, p)) return Set::unknown;
    if (needWritable && !p->IsSetEnableCurrentValue()) return Set::notWritable;
    if (sdk_values::current(*p) == value) return Set::held;
    wait.arm("prop", code);
    p->SetCurrentValue(static_cast<CrInt64u>(value));
    if (const SCRSDK::CrError err = SCRSDK::SetDeviceProperty(dev, p)) {
        wait.arm("");
        *why = "set: " + CrErrorString(err);
        return Set::refused;
    }
    std::string ignored;
    wait.until(3s, &ignored);
    for (int k = 0; k < 20; ++k) {
        if (fetch(dev, code, p) && sdk_values::current(*p) == value) return Set::held;
        std::this_thread::sleep_for(100ms);
    }
    return Set::kept;
}

// A text property (fetched into *p) set to `value`, ASCII only, as Sony's string: its length with the terminator,
// then one UTF-16 unit a character. "" when the SDK took it, else why not. Non-ASCII is refused, since its UTF-8
// bytes would go out as characters of their own and the read-back could never match.
inline std::string sendText(SCRSDK::CrDeviceHandle dev, SCRSDK::CrDeviceProperty* p, const std::string& value) {
    if (p->GetValueType() != SCRSDK::CrDataType_STR) return "not a string property";
    for (unsigned char c : value)
        if (c == 0 || c >= 128) return "the text is not ASCII";
    if (value.size() > 250) return "text too long";
    std::vector<CrInt16u> buf(value.size() + 2, 0);
    buf[0] = value.empty() ? 0 : static_cast<CrInt16u>(value.size() + 1);
    for (size_t k = 0; k < value.size(); ++k) buf[1 + k] = static_cast<unsigned char>(value[k]);
    p->SetCurrentStr(buf.data());
    if (const SCRSDK::CrError err = SCRSDK::SetDeviceProperty(dev, p)) return "set: " + CrErrorString(err);
    return "";
}

// Read a text property back until the camera holds `value` (20 tries, 150 ms apart); *p is the property as last read.
inline bool holdsText(SCRSDK::CrDeviceHandle dev, uint32_t code, const std::string& value, SCRSDK::CrDeviceProperty* p) {
    for (int k = 0; k < 20; ++k) {
        std::this_thread::sleep_for(150ms);
        if (fetch(dev, code, p) && text(*p) == value) return true;
    }
    return false;
}

// ---------- buttons and dials ----------

// Whether the camera's buttons are idle (CameraButtonFunctionStatus), asked every 20 ms for up to `timeout`.
inline bool buttonsIdle(SCRSDK::CrDeviceHandle dev, std::chrono::milliseconds timeout) {
    const auto end = std::chrono::steady_clock::now() + timeout;
    SCRSDK::CrDeviceProperty st;
    do {
        if (fetch(dev, SCRSDK::CrDeviceProperty_CameraButtonFunctionStatus, &st) &&
            st.GetCurrentValue() == SCRSDK::CrCameraButtonFunctionStatus_Idle) return true;
        std::this_thread::sleep_for(20ms);
    } while (std::chrono::steady_clock::now() < end);
    return false;
}

// One press of a button (remote::buttonCode), whose rule the caller checked: the buttons idle first (up to 2 s; it is
// pressed all the same when they never are), then Down, the hold, and Up, tried three times 100 ms apart so a refused
// Up does not leave the button held. No wait for the screen to redraw.
struct Pressed {
    bool idle = false, down = false, up = false;
};

inline Pressed press(SCRSDK::CrDeviceHandle dev, uint32_t button, std::chrono::milliseconds hold) {
    Pressed r;
    r.idle = buttonsIdle(dev, 2s);
    r.down = sendValue(dev, SCRSDK::CrDeviceProperty_CameraButtonFunction, button | SCRSDK::CrCameraButtonFunctionValue_Down);
    std::this_thread::sleep_for(hold);
    for (int k = 0; k < 3 && !r.up; ++k) {
        if (k) std::this_thread::sleep_for(100ms);
        r.up = sendValue(dev, SCRSDK::CrDeviceProperty_CameraButtonFunction, button | SCRSDK::CrCameraButtonFunctionValue_Up);
    }
    return r;
}

// A dial (remote::dialCode) turned `steps` (negative: the other way); true when the SDK took it.
inline bool turn(SCRSDK::CrDeviceHandle dev, uint32_t dial, int steps) {
    return sendValue(dev, SCRSDK::CrDeviceProperty_CameraDialFunction, remote::dialValue(dial, steps));
}

// ---------- the camera's screen ----------

// The camera's screen (its OSD image, a PNG) saved to `file`, written as `file`.part and renamed over it, so a reader
// never sees half a frame and a failed write leaves none. OSDImageMode is turned on first when it is off. "" when
// saved, with its size in *bytes, else why not.
inline std::string saveOsd(SCRSDK::CrDeviceHandle dev, const fs::path& file, long long* bytes) {
    if (file.empty()) return "no file named for the frame";
    SCRSDK::CrDeviceProperty mode;
    if (fetch(dev, SCRSDK::CrDeviceProperty_OSDImageMode, &mode) && mode.GetCurrentValue() != SCRSDK::CrOSDImageMode_On) {
        mode.SetCurrentValue(SCRSDK::CrOSDImageMode_On);
        SCRSDK::SetDeviceProperty(dev, &mode);
        std::this_thread::sleep_for(800ms);
    }
    std::vector<CrInt8u> buf(CR_OSD_IMAGE_MAX_SIZE);
    SCRSDK::CrOSDImageDataBlock img;
    img.SetData(buf.data());
    for (int k = 0; k < 10; ++k) {
        if (SCRSDK::GetOSDImage(dev, &img) == SCRSDK::CrError_None && img.GetImageSize() > 0) {
            fs::path tmp = file;
            tmp += ".part";
            std::error_code ec;
            std::ofstream f(tmp, std::ios::binary | std::ios::trunc);
            f.write(reinterpret_cast<const char*>(img.GetImageData()), static_cast<std::streamsize>(img.GetImageSize()));
            f.close();
            if (!f) {
                fs::remove(tmp, ec);
                return "write " + file.u8string() + ": the frame could not be written";
            }
            fs::rename(tmp, file, ec);
            if (ec) {
                std::error_code ignored;
                fs::remove(tmp, ignored);
                return "write " + file.u8string() + ": " + ec.message();
            }
            *bytes = img.GetImageSize();
            return "";
        }
        std::this_thread::sleep_for(150ms);
    }
    return "no OSD image";
}

// ---------- settings files ----------

// The files in `dir` whose names start with `prefix`, without throwing (a folder that cannot be read lists none).
inline std::vector<fs::path> startingWith(const fs::path& dir, const std::string& prefix) {
    std::vector<fs::path> out;
    std::error_code ec;
    for (fs::directory_iterator it(dir, ec), end; !ec && it != end; it.increment(ec))
        if (it->path().filename().u8string().rfind(prefix, 0) == 0) out.push_back(it->path());
    return out;
}

// How a download goes: the name the SDK saves under before the file is renamed, each download with a number of its
// own after it, so a late file from a download that timed out is never taken for the next (those left by a stopped
// run are removed first); whether a camera that does not allow a save within 5 s is refused (else asked all the
// same); whether an existing DIR/NAME.DAT is replaced (else the download is refused before the camera is asked).
struct DownloadRules {
    const char* tmpName;
    bool needEnable;
    bool overwrite;
};

// The download's end: the file saved, or why not, and whether the camera refused or failed it (rather than a file
// problem on this computer).
struct Download {
    fs::path path;
    std::string error;
    bool refused = false;
};

// The camera's settings file saved as DIR/NAME.DAT (DownloadSettingFile; the camera must not be in a menu and needs a
// card). The SDK saves under the name given with ".DAT" (and "(1)" added on a clash, Sony's API reference) and names
// the file it wrote in OnCompleteDownload (`wait`'s "download", which takes only this download's temporary name);
// when that names no file, the newest under this download's temporary name is taken.
inline Download downloadSettings(SCRSDK::CrDeviceHandle dev, CallbackWait& wait, const fs::path& dir, const std::string& name,
                                 const DownloadRules& rules) {
    Download r;
    std::error_code ec;
    fs::create_directories(dir, ec);
    if (ec) {
        r.error = "could not make the folder " + dir.u8string() + ": " + ec.message();
        return r;
    }
    const fs::path dst = dir / fs::u8path(name + ".DAT");
    if (!rules.overwrite && fs::exists(dst, ec)) {
        r.error = "refusing to overwrite " + dst.u8string();
        return r;
    }
    SCRSDK::CrDeviceProperty st;
    bool allowed = false;
    for (int k = 0; k < 50 && !allowed; ++k) {
        allowed = fetch(dev, SCRSDK::CrDeviceProperty_CameraSetting_SaveOperationEnableStatus, &st) &&
                  st.GetCurrentValue() == SCRSDK::CrCameraSettingSaveOperation_Enable;
        if (!allowed) std::this_thread::sleep_for(100ms);
    }
    if (!allowed && rules.needEnable) {
        r.refused = true;
        r.error = "camera does not allow a settings download now";
        return r;
    }
    for (const fs::path& old : startingWith(dir, rules.tmpName)) fs::remove(old, ec);
    static std::atomic<unsigned> downloads{0};
    const std::string tmpName = std::string(rules.tmpName) + "_" + std::to_string(++downloads) + "_";   // "_3_": not a prefix of "_31_"
    CrString crDir = crPath(dir), crName = toCr(tmpName);
    wait.arm("download", 0, tmpName);
    if (const SCRSDK::CrError err = SCRSDK::DownloadSettingFile(dev, SCRSDK::CrDownloadSettingFileType_Setup, crDir.data(), crName.data())) {
        wait.arm("");
        r.refused = true;
        r.error = "download: " + CrErrorString(err);
        return r;
    }
    std::string got;
    if (!wait.until(60s, &got)) {
        r.refused = true;
        r.error = "download: " + got;
        return r;
    }
    fs::path src = got.empty() ? fs::path() : fs::u8path(got);
    if (!src.empty() && src.is_relative()) src = dir / src;
    if (src.empty() || !fs::is_regular_file(src, ec)) {   // an empty name would make src the folder itself
        src.clear();
        fs::file_time_type newest{};
        for (const fs::path& p : startingWith(dir, tmpName)) {
            const fs::file_time_type t = fs::last_write_time(p, ec);
            if (!ec && fs::is_regular_file(p, ec) && (src.empty() || t > newest)) {
                src = p;
                newest = t;
            }
        }
    }
    if (src.empty()) {
        r.error = "the camera's settings file is not in " + dir.u8string();
        return r;
    }
    if (!rules.overwrite && fs::exists(dst, ec)) {
        r.error = "refusing to overwrite " + dst.u8string();
        return r;
    }
    fs::rename(src, dst, ec);
    if (ec) {
        r.error = "move " + src.u8string() + ": " + ec.message();
        return r;
    }
    r.path = dst;
    return r;
}

// A settings file sent to the camera (UploadSettingFile), which reads it and restarts. `called`: the SDK took the
// call (else `detail` says why not); then how the camera's answer ended within 120 s, and its text.
struct Upload {
    bool called = false;
    CallbackWait::Ended ended = CallbackWait::Ended::failed;
    std::string detail;
};

inline Upload uploadSettings(SCRSDK::CrDeviceHandle dev, CallbackWait& wait, const fs::path& file) {
    Upload r;
    std::error_code ec;
    const fs::path abs = fs::absolute(file, ec);
    CrString crFile = crPath(ec ? file : abs);
    wait.arm("upload");
    if (const SCRSDK::CrError err = SCRSDK::UploadSettingFile(dev, SCRSDK::CrUploadSettingFileType_Setup, crFile.data())) {
        wait.arm("");
        r.detail = "upload: " + CrErrorString(err);
        return r;
    }
    r.called = true;
    r.ended = wait.wait(120s, &r.detail);
    return r;
}

// ---------- the connection ----------

// macOS's camera service (ptpcamerad) takes a USB camera for itself, and launchd starts it again within seconds, so
// it is stopped right before each attempt to open the camera, then `settle` waited. Elsewhere nothing is done: on
// Linux a gvfs or gphoto2 monitor can hold the camera the same way, which is left to the person, and Windows has no
// pkill.
inline void releaseFromMacCameraService(std::chrono::milliseconds settle) {
#ifdef __APPLE__
    const int ignored = std::system("pkill -KILL ptpcamerad >/dev/null 2>&1");
    (void)ignored;
    std::this_thread::sleep_for(settle);
#else
    (void)settle;
#endif
}

// The camera the SDK's search lists at `ip`, or nullptr (the last one, should two claim it). The search takes up to
// `seconds`; *list keeps what it found until the caller releases it, and `seen` is shown each camera listed.
template <class Seen>
inline SCRSDK::ICrCameraObjectInfo* searchAt(SCRSDK::ICrEnumCameraObjectInfo** list, CrInt8u seconds, const std::string& ip, Seen seen) {
    SCRSDK::ICrCameraObjectInfo* found = nullptr;
    if (SCRSDK::EnumCameraObjects(list, seconds) != SCRSDK::CrError_None || !*list) return nullptr;
    for (CrInt32u k = 0; k < (*list)->GetCount(); ++k) {
        auto* o = const_cast<SCRSDK::ICrCameraObjectInfo*>((*list)->GetCameraObjectInfo(k));
        if (!o) continue;
        seen(o);
        if (narrow(o->GetIPAddressChar()) == ip) found = o;
    }
    return found;
}

// The camera object for a camera the search did not list, made from its address (ipv4Bytes' numbers b) with the body
// `model` names (lanModel: a missing or unknown one is said through `note`, and the list's first body is asked for),
// the MAC address when one is known (else zeros) and whether a login will be sent. nullptr, and *err, when the SDK
// refuses; the caller releases what it gets.
template <class Note>
inline SCRSDK::ICrCameraObjectInfo* makeAt(const unsigned b[4], const std::string& ip, const std::string& model, const std::string& mac,
                                           bool ssh, Note note, SCRSDK::CrError* err) {
    unsigned char bytes[6];
    macBytes(mac, bytes);
    SCRSDK::CrCameraDeviceModelList body{};
    if (!lanModel(model, &body)) note(lanModelNote(model, ip));
    SCRSDK::ICrCameraObjectInfo* made = nullptr;
    *err = SCRSDK::CreateCameraObjectInfoEthernetConnection(&made, body, ipv4Value(b), bytes, ssh ? 1 : 0);
    if (*err != SCRSDK::CrError_None && made) {
        made->Release();
        made = nullptr;
    }
    return made;
}

// The camera's SSH host key fingerprint (GetFingerprint), read before a login is sent: the bytes as the SDK wrote
// them, which Connect is handed back, and their text (fingerprintText), which is kept and compared. Empty when none
// was read.
struct Fingerprint {
    char bytes[512] = {};
    CrInt32u size = 0;
    std::string text() const { return fingerprintText(bytes, size); }
};

inline SCRSDK::CrError readFingerprint(SCRSDK::ICrCameraObjectInfo* info, Fingerprint* fp) {
    fp->size = sizeof fp->bytes;
    const SCRSDK::CrError err = SCRSDK::GetFingerprint(info, fp->bytes, &fp->size);
    if (err != SCRSDK::CrError_None) fp->size = 0;
    else if (fp->size > sizeof fp->bytes) fp->size = sizeof fp->bytes;
    return err;
}

// Connect to the camera object for remote control, no reconnecting: with the login and the fingerprint read for it
// when a login is sent (a user name in `login`), else with neither (a USB camera, or a network one that asks for none).
inline SCRSDK::CrError connectTo(SCRSDK::ICrCameraObjectInfo* info, SCRSDK::IDeviceCallback* callback, SCRSDK::CrDeviceHandle* dev,
                                 const Login& login, const Fingerprint& fp) {
    const bool ssh = !login.user.empty();
    return SCRSDK::Connect(info, callback, dev, SCRSDK::CrSdkControlMode_Remote, SCRSDK::CrReconnecting_OFF,
                           ssh ? login.user.c_str() : nullptr, ssh ? login.password.c_str() : nullptr,
                           ssh ? fp.bytes : nullptr, ssh ? fp.size : 0);
}

// The session's end: Disconnect while connected (OnDisconnected ends `wait`'s "disconnect", up to 3 s), then the device
// released; *dev is 0 after.
inline void closeDevice(SCRSDK::CrDeviceHandle* dev, CallbackWait& wait, bool connected) {
    if (connected && *dev) {
        wait.arm("disconnect");
        SCRSDK::Disconnect(*dev);
        std::string ignored;
        wait.until(3s, &ignored);
    }
    if (*dev) SCRSDK::ReleaseDevice(*dev);
    *dev = 0;
}

}  // namespace sdk_session
