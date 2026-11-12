// camera_net.h: what the camera link (kit/link/camlink.cpp) and the editor's camera helper (kit/probe/camset_probe.cpp)
// share about a network camera: its address and MAC address, as the SDK names it and as this computer's own network
// neighbour table (ARP) holds it; where the files below are (homeDir, camsetDir); the login the credentials file
// ~/.config/camset/network.json keeps for it (the file's shape and the order the login is looked up in: each
// program's header), and the check that the file is private; the fingerprint each camera showed the first time
// (~/.config/camset/known_cameras.json, below), so a login goes only to the camera it was saved for; and the body a
// camera reached by its address is (lanModel). Header-only; both programs are one file.
// kit/common/camera_net_test.cpp checks the parts that need no camera.
//
// The helpers take plain std::strings; only narrow and sdkMacText read the SDK's text (CrChar: wchar_t on Windows,
// where the SDK is built with UNICODE as in Sony's samples, char elsewhere), and they and lanModel are templates, so
// this file needs none of the SDK's headers. Include it before them: on Windows it brings in winsock2.h and
// iphlpapi.h (SendARP), which must come before anything that brings in windows.h.
#pragma once

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <winsock2.h>
#include <iphlpapi.h>   // SendARP, for neighbourMac
#endif

#include <cctype>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <map>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

// An environment variable's text; empty when it is not set. For the ASCII settings: CAMSET_IP, CAMSET_MAC, CAMSET_MODEL.
inline std::string envText(const char* name) {
    const char* v = std::getenv(name);
    return v ? std::string(v) : std::string();
}

// The text without the blanks at either end.
inline std::string trimmed(const std::string& s) {
    const size_t a = s.find_first_not_of(" \t\r\n"), b = s.find_last_not_of(" \t\r\n");
    return a == std::string::npos ? std::string() : s.substr(a, b - a + 1);
}

// The SDK's text (wchar_t on Windows, char elsewhere) as a narrow string, up to its first NUL and at most `size`
// characters; non-ASCII becomes '?'. For the SDK's ASCII texts: addresses, model names, connection types.
template <class C>
inline std::string narrow(const C* c, size_t size = (size_t)-1) {
    std::string s;
    if (c) for (size_t k = 0; k < size && c[k]; ++k) s += ((unsigned)c[k] < 128) ? (char)c[k] : '?';
    return s;
}

// The MAC address the SDK names for a camera object (an SCRSDK::ICrCameraObjectInfo), as text. It is read no further
// than the size the SDK gives, as Sony's RemoteCli sample reads it (the text need not end in a NUL); a size of 0 reads
// up to the NUL. Sony's API reference: it is the wired or the wireless LAN card's, by model, not by the connection in use.
template <class CameraInfo>
inline std::string sdkMacText(const CameraInfo* o) {
    if (!o) return "";
    const auto size = o->GetMACAddressCharSize();
    return narrow(o->GetMACAddressChar(), size ? (size_t)size : (size_t)-1);
}

// A MAC address as the SDK prints it: upper-case hex pairs joined by ':' ('-' is read as ':'); empty when the text
// is not one, or is all zero (a camera object made without a MAC).
inline std::string macKey(const std::string& m) {
    std::string o;
    for (char c : m) if (!std::isspace((unsigned char)c)) o += c == '-' ? ':' : (char)std::toupper((unsigned char)c);
    if (o.size() != 17 || o == "00:00:00:00:00:00") return "";
    for (size_t k = 0; k < o.size(); ++k)
        if (k % 3 == 2 ? o[k] != ':' : !std::isxdigit((unsigned char)o[k])) return "";
    return o;
}

// The four numbers of a dotted-decimal IPv4 address ("192.168.1.50"); false for any other text.
inline bool ipv4Bytes(const std::string& ip, unsigned b[4]) {
    size_t i = 0;
    for (int part = 0; part < 4; ++part) {
        if (part) { if (i >= ip.size() || ip[i] != '.') return false; ++i; }
        size_t j = i;
        unsigned v = 0;
        while (j < ip.size() && j - i < 3 && std::isdigit((unsigned char)ip[j])) v = v * 10 + (unsigned)(ip[j++] - '0');
        if (j == i || v > 255) return false;
        b[part] = v;
        i = j;
    }
    return i == ip.size();
}

// The address as the SDK's CreateCameraObjectInfoEthernetConnection takes it, from ipv4Bytes: the first number in the
// lowest byte.
inline uint32_t ipv4Value(const unsigned b[4]) {
    return static_cast<uint32_t>(b[0] | b[1] << 8 | b[2] << 16 | b[3] << 24);
}

// The six bytes of a MAC address (any text macKey reads), for the camera object made from the address; false, and six
// zeros, for any other text.
inline bool macBytes(const std::string& mac, unsigned char out[6]) {
    for (int k = 0; k < 6; ++k) out[k] = 0;
    const std::string m = macKey(mac);
    if (m.empty()) return false;
    for (int k = 0; k < 6; ++k) out[k] = static_cast<unsigned char>(std::stoul(m.substr(3 * static_cast<size_t>(k), 2), nullptr, 16));
    return true;
}

// The MAC address this computer's own network neighbour table (ARP) holds for an IPv4 address it has just talked to,
// as macKey prints it; empty when the table holds none or the text is not a dotted-decimal address. It names the
// network card that answered at the address, which can be another card than the one the SDK names (sdkMacText).
inline std::string neighbourMac(const std::string& ip) {
    unsigned b[4];
    if (!ipv4Bytes(ip, b)) return "";
#if defined(_WIN32)
    // SendARP answers from the table, or asks on the network when the table has no entry
    ULONG mac[2] = {0, 0}, len = 6;
    const IPAddr dest = (IPAddr)(b[0] | b[1] << 8 | b[2] << 16 | b[3] << 24);   // network byte order
    if (SendARP(dest, 0, mac, &len) != NO_ERROR || len != 6) return "";
    const unsigned char* m = (const unsigned char*)mac;
    char text[18];
    std::snprintf(text, sizeof text, "%02X:%02X:%02X:%02X:%02X:%02X", m[0], m[1], m[2], m[3], m[4], m[5]);
    return macKey(text);
#elif defined(__linux__)
    // /proc/net/arp: a heading line, then one entry per line: IP address, HW type, Flags, HW address, Mask, Device;
    // an entry still being resolved has an all-zero HW address, which macKey turns into ""
    std::ifstream f("/proc/net/arp");
    std::string line;
    std::getline(f, line);
    while (std::getline(f, line)) {
        std::istringstream ss(line);
        std::string addr, type, flags, hw;
        if (ss >> addr >> type >> flags >> hw && addr == ip)
            if (std::string k = macKey(hw); !k.empty()) return k;
    }
    return "";
#elif defined(__APPLE__)
    // "? (192.168.1.50) at 0:11:22:33:44:55 on en0 ifscope [ethernet]": each byte without its leading zero;
    // "... -- no entry" or "at (incomplete)" when the table holds none. The address was checked above.
    std::string out;
    if (FILE* p = popen(("/usr/sbin/arp -n " + ip + " 2>/dev/null").c_str(), "r")) {
        char buf[256];
        while (std::fgets(buf, sizeof buf, p)) out += buf;
        pclose(p);
    }
    const size_t at = out.find(" at ");
    unsigned v[6];
    if (at == std::string::npos ||
        std::sscanf(out.c_str() + at + 4, "%x:%x:%x:%x:%x:%x", &v[0], &v[1], &v[2], &v[3], &v[4], &v[5]) != 6) return "";
    for (unsigned x : v) if (x > 0xFF) return "";
    char text[18];
    std::snprintf(text, sizeof text, "%02X:%02X:%02X:%02X:%02X:%02X", v[0], v[1], v[2], v[3], v[4], v[5]);
    return macKey(text);
#else
    return "";
#endif
}

// ---------- where the files are ----------
// The user's home folder: HOME, else (Windows) USERPROFILE, as the editor looks them up; empty when neither is set.
// Windows: read as UTF-16, since the narrow environment is in the ANSI code page and a user name outside it (or any
// non-ASCII one, read as UTF-8) would name another folder, where no credentials file is.
#ifdef _WIN32
inline std::filesystem::path envPath(const wchar_t* name) {
    const DWORD size = GetEnvironmentVariableW(name, nullptr, 0);
    if (size == 0) return {};
    std::wstring v(size, L'\0');
    const DWORD got = GetEnvironmentVariableW(name, v.data(), size);
    if (got == 0 || got >= size) return {};
    v.resize(got);
    return std::filesystem::path(v);
}
#endif

inline std::filesystem::path homeDir() {
#ifdef _WIN32
    std::filesystem::path h = envPath(L"HOME");
    return h.empty() ? envPath(L"USERPROFILE") : h;
#else
    const char* h = std::getenv("HOME");
    return h ? std::filesystem::path(h) : std::filesystem::path();
#endif
}

// The folder that keeps the credentials file (network.json) and the cameras this computer trusts
// (known_cameras.json): ~/.config/camset; empty without a home folder.
inline std::filesystem::path camsetDir() {
    const std::filesystem::path home = homeDir();
    return home.empty() ? home : home / ".config" / "camset";
}

// ---------- the credentials file ----------
// A small reader for its shape: every string, keyed by its path of keys joined by '\n' ("user",
// "cameras\nAA:BB:CC:DD:EE:FF\nuser"); numbers, booleans and arrays are skipped. It stops at the first malformed part.
namespace creds {
inline void ws(const std::string& s, size_t& i) { while (i < s.size() && std::isspace((unsigned char)s[i])) ++i; }

inline bool hex4(const std::string& s, size_t at, unsigned* v) {
    if (at + 4 > s.size()) return false;
    *v = 0;
    for (size_t k = at; k < at + 4; ++k) {
        char c = s[k];
        *v <<= 4;
        if (c >= '0' && c <= '9') *v |= (unsigned)(c - '0');
        else if (c >= 'a' && c <= 'f') *v |= (unsigned)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F') *v |= (unsigned)(c - 'A' + 10);
        else return false;
    }
    return true;
}

inline void utf8(std::string& o, unsigned c) {
    if (c < 0x80) o += (char)c;
    else if (c < 0x800) { o += (char)(0xC0 | c >> 6); o += (char)(0x80 | (c & 0x3F)); }
    else if (c < 0x10000) { o += (char)(0xE0 | c >> 12); o += (char)(0x80 | (c >> 6 & 0x3F)); o += (char)(0x80 | (c & 0x3F)); }
    else { o += (char)(0xF0 | c >> 18); o += (char)(0x80 | (c >> 12 & 0x3F)); o += (char)(0x80 | (c >> 6 & 0x3F)); o += (char)(0x80 | (c & 0x3F)); }
}

// The JSON string at s[i], escapes decoded; i moves past it.
inline bool str(const std::string& s, size_t& i, std::string& o) {
    if (i >= s.size() || s[i] != '"') return false;
    while (++i < s.size()) {
        char c = s[i];
        if (c == '"') { ++i; return true; }
        if (c != '\\') { o += c; continue; }
        if (++i >= s.size()) return false;
        switch (s[i]) {
            case 'n': o += '\n'; break;
            case 't': o += '\t'; break;
            case 'r': o += '\r'; break;
            case 'b': o += '\b'; break;
            case 'f': o += '\f'; break;
            case 'u': {
                unsigned hi = 0, lo = 0;
                if (!hex4(s, i + 1, &hi)) return false;
                i += 4;
                if (hi >= 0xD800 && hi < 0xDC00 && i + 2 < s.size() && s[i + 1] == '\\' && s[i + 2] == 'u' &&
                    hex4(s, i + 3, &lo) && lo >= 0xDC00 && lo < 0xE000) {
                    hi = 0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00);
                    i += 6;
                }
                utf8(o, hi);
                break;
            }
            default: o += s[i];   // \" \\ \/
        }
    }
    return false;
}

// The JSON value at s[i]: its strings go into out under their path; i moves past it.
inline bool value(const std::string& s, size_t& i, const std::string& path, std::map<std::string, std::string>& out, int depth = 0) {
    ws(s, i);
    if (i >= s.size() || depth > 16) return false;
    const char open = s[i];
    if (open == '"') { std::string v; if (!str(s, i, v)) return false; out[path] = v; return true; }
    if (open == '{' || open == '[') {
        const char close = open == '{' ? '}' : ']';
        ++i; ws(s, i);
        if (i < s.size() && s[i] == close) { ++i; return true; }
        for (;;) {
            std::string sub = path + "\n[]";   // an array's strings are kept apart from any key
            if (open == '{') {
                std::string k;
                ws(s, i);
                if (!str(s, i, k)) return false;
                ws(s, i);
                if (i >= s.size() || s[i] != ':') return false;
                ++i;
                sub = path.empty() ? k : path + "\n" + k;
            }
            if (!value(s, i, sub, out, depth + 1)) return false;
            ws(s, i);
            if (i < s.size() && s[i] == ',') { ++i; continue; }
            if (i < s.size() && s[i] == close) { ++i; return true; }
            return false;
        }
    }
    while (i < s.size() && !std::strchr(",}] \t\r\n", s[i])) ++i;   // a number, true, false or null
    return true;
}
}   // namespace creds

// from: "camera" (its own entry), "default", or "" (none). under: for "camera", the MAC address it was found under
// (chooseLogin): "sdk_mac", "neighbour_mac" or "CAMSET_MAC".
struct Login { std::string user, password, from, under; };

// The login for the camera with this MAC address: its own entry under "cameras", else the default pair.
inline Login pickLogin(const std::string& text, const std::string& mac) {
    std::map<std::string, std::string> f;
    size_t i = 0;
    creds::value(text, i, "", f);
    if (const std::string want = macKey(mac); !want.empty())
        for (auto& [k, v] : f) {
            auto a = k.find('\n'), b = k.rfind('\n');   // "cameras\n<MAC>\nuser"
            if (a == std::string::npos || a == b || k.compare(0, a, "cameras") != 0 || k.substr(b + 1) != "user" || v.empty()) continue;
            std::string key = k.substr(a + 1, b - a - 1);
            if (macKey(key) != want) continue;
            auto p = f.find("cameras\n" + key + "\npassword");
            return {v, p == f.end() ? "" : p->second, "camera", ""};
        }
    if (!f["user"].empty()) return {f["user"], f["password"], "default", ""};
    return {};
}

// The login for a network camera: its own entry under the first of these MAC addresses that has one, the one the SDK
// names for the camera it found at the address (sdkMac), the one this computer's neighbour table holds for the
// address (seenMac), CAMSET_MAC (envMac); else the default pair, else none. One camera can carry two MAC addresses,
// since the SDK names its wired or its wireless card by model, while the neighbour table holds the card that answered.
inline Login chooseLogin(const std::string& text, const std::string& sdkMac, const std::string& seenMac, const std::string& envMac) {
    const std::pair<const std::string*, const char*> tries[] = {
        {&sdkMac, "sdk_mac"}, {&seenMac, "neighbour_mac"}, {&envMac, "CAMSET_MAC"}};
    for (const auto& [mac, under] : tries)
        if (!mac->empty())
            if (Login l = pickLogin(text, *mac); l.from == "camera") { l.under = under; return l; }
    return pickLogin(text, "");   // the default pair, when there is one
}

// ---------- the credentials file must be private ----------
// True when other users of this computer may read or change the file (any group or others permission bit), as ssh
// refuses a private key others can read: the helpers then refuse to use it and say how to make it private. False when
// there is no file. Windows: not checked (false); the file sits in the user's own profile folder, whose access list
// keeps other users out.
inline bool openToOthers(const std::filesystem::path& p) {
#ifdef _WIN32
    (void)p;
    return false;
#else
    namespace fs = std::filesystem;
    std::error_code ec;
    const fs::file_status st = fs::status(p, ec);
    if (ec || !fs::exists(st) || st.permissions() == fs::perms::unknown) return false;
    return (st.permissions() & (fs::perms::group_all | fs::perms::others_all)) != fs::perms::none;
#endif
}

// What to say about a credentials file others can read: why it was not used, and how to make it private.
inline std::string openToOthersText(const std::filesystem::path& p) {
    const std::string f = p.u8string();
    return "The file that keeps the camera's user name and password (" + f + ") can be read by other users of this "
           "computer, so it was not used. Make it private (chmod 600 '" + f + "', or save the login again in the "
           "editor), then try again.";
}

// A file's whole text; empty when there is none.
inline std::string fileText(const std::filesystem::path& p) {
    std::ifstream f(p, std::ios::binary);
    return std::string((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
}

// The credentials file in `dir` (camsetDir): its text, or `open` when other users of this computer may read it, which
// is then not read (openToOthers). No folder or no file: an empty text.
struct Credentials {
    std::filesystem::path file;
    std::string text;
    bool open = false;
};

inline Credentials readCredentials(const std::filesystem::path& dir) {
    Credentials c;
    if (dir.empty()) return c;
    c.file = dir / "network.json";
    c.open = openToOthers(c.file);
    if (!c.open) c.text = fileText(c.file);
    return c;
}

// ---------- the cameras this computer trusts: ~/.config/camset/known_cameras.json ----------
// The fingerprint each network camera showed when a helper first connected to it (the camera's SSH host key, read with
// GetFingerprint before the user name and password are sent), so a login only ever goes to the camera it was saved
// for. The helpers write it after a successful connection, mode 600, whole (a temporary file renamed over it):
//   {"by_mac": {"00:11:22:33:44:55": "<fingerprint>"}, "by_address": {"192.168.1.50": "<fingerprint>"}}
// A camera is kept under the MAC addresses the SDK and this computer's neighbour table named for it, and under its
// address. Before a login is sent, the fingerprint the camera at the address shows now is compared (checkTrust) with the
// ones kept under any MAC address it carries (the SDK's, the neighbour table's, CAMSET_MAC), or, when none of those has
// one, with the one kept under the address. When it differs, the connection is refused (cause camera_changed) and
// nothing is sent; a camera met for the first time is trusted and kept. The editor's Forget (Connect to the camera,
// Known cameras) removes a camera's entries, so after a reset of the camera's network settings, which gives it a new
// fingerprint, it is trusted again on the next connection; without the editor, remove its lines from the file.

struct Trusted { std::map<std::string, std::string> byMac, byAddress; };

// The file's entries; an empty or unreadable text holds none. MAC addresses are kept as macKey prints them.
inline Trusted readTrusted(const std::string& text) {
    std::map<std::string, std::string> f;
    size_t i = 0;
    creds::value(text, i, "", f);
    Trusted t;
    for (auto& [k, v] : f) {
        const size_t a = k.find('\n');
        if (a == std::string::npos || k.find('\n', a + 1) != std::string::npos || v.empty()) continue;
        const std::string group = k.substr(0, a), key = k.substr(a + 1);
        if (group == "by_mac") { if (std::string m = macKey(key); !m.empty()) t.byMac[m] = v; }
        else if (group == "by_address" && !key.empty()) t.byAddress[key] = v;
    }
    return t;
}

// A JSON string literal.
inline std::string jsonText(const std::string& s) {
    std::string o = "\"";
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') { o += '\\'; o += (char)c; }
        else if (c == '\n') o += "\\n";
        else if (c < 0x20) { char b[8]; std::snprintf(b, sizeof b, "\\u%04x", c); o += b; }
        else o += (char)c;
    }
    return o + "\"";
}

// The file's text for these entries.
inline std::string trustedText(const Trusted& t) {
    auto block = [](const std::map<std::string, std::string>& m) {
        std::string o = "{";
        for (auto& [k, v] : m) o += (o.size() > 1 ? ",\n    " : "\n    ") + jsonText(k) + ": " + jsonText(v);
        return o + (m.empty() ? "}" : "\n  }");
    };
    return "{\n  \"by_mac\": " + block(t.byMac) + ",\n  \"by_address\": " + block(t.byAddress) + "\n}\n";
}

// The fingerprint GetFingerprint wrote (at most len bytes, up to a NUL), without trailing blanks: the text kept and
// compared. Connect is handed the bytes as the SDK wrote them.
inline std::string fingerprintText(const char* fp, size_t len) {
    std::string s;
    for (size_t k = 0; fp && k < len && fp[k]; ++k) s += fp[k];
    while (!s.empty() && std::isspace((unsigned char)s.back())) s.pop_back();
    return s;
}

// What the kept fingerprints say of the camera at `address` that shows `fp` now: "new" (none is kept for it), "same",
// or "changed" (a kept one differs; `differ` names those entries: MAC addresses, or the address). `macs` are the MAC
// addresses the camera carries now (empty ones are skipped); the address's entry counts only when none of them has one.
struct TrustCheck { std::string verdict; std::vector<std::string> differ; };

inline TrustCheck checkTrust(const Trusted& t, const std::string& fp, const std::vector<std::string>& macs, const std::string& address) {
    TrustCheck r{"new", {}};
    bool kept = false;
    for (const std::string& m : macs) {
        const std::string k = macKey(m);
        const auto it = k.empty() ? t.byMac.end() : t.byMac.find(k);
        if (it == t.byMac.end()) continue;
        kept = true;
        bool listed = false;
        for (const std::string& d : r.differ) listed = listed || d == k;
        if ((it->second != fp || fp.empty()) && !listed) r.differ.push_back(k);
    }
    if (!kept) {
        if (const auto it = t.byAddress.find(address); it != t.byAddress.end()) {
            kept = true;
            if (it->second != fp || fp.empty()) r.differ.push_back(address);
        }
    }
    r.verdict = !r.differ.empty() ? "changed" : kept ? "same" : "new";
    return r;
}

// Keep `fp` for the camera just connected to: under each of its MAC addresses and under its address. Another address
// that held the same fingerprint is dropped (the camera moved: that address no longer names it). Nothing is kept for
// an empty fingerprint.
inline void trustCamera(Trusted& t, const std::string& fp, const std::vector<std::string>& macs, const std::string& address) {
    if (fp.empty()) return;
    for (const std::string& m : macs)
        if (std::string k = macKey(m); !k.empty()) t.byMac[k] = fp;
    for (auto it = t.byAddress.begin(); it != t.byAddress.end();) it = it->second == fp ? t.byAddress.erase(it) : std::next(it);
    if (!address.empty()) t.byAddress[address] = fp;
}

// Write a file whole, readable by this user only (mode 600 before anything is written into it), through a temporary
// file beside it that is renamed over it, so a crash never leaves half a file. A missing folder is made, mode 700.
inline bool writePrivateFile(const std::filesystem::path& p, const std::string& text) {
    namespace fs = std::filesystem;
    std::error_code ec;
    const fs::path dir = p.parent_path();
    if (!dir.empty() && !fs::exists(dir, ec)) {
        fs::create_directories(dir, ec);
        fs::permissions(dir, fs::perms::owner_all, fs::perm_options::replace, ec);
    }
    const fs::path tmp = dir / ("." + p.filename().u8string() + ".part");
    {
        std::ofstream make(tmp, std::ios::binary | std::ios::trunc);
        if (!make) return false;
    }
    fs::permissions(tmp, fs::perms::owner_read | fs::perms::owner_write, fs::perm_options::replace, ec);
    bool ok = !ec;
    if (ok) {
        std::ofstream o(tmp, std::ios::binary | std::ios::trunc);
        o << text;
        o.flush();
        ok = o.good();
    }
    if (ok) fs::rename(tmp, p, ec);
    if (!ok || ec) {
        std::error_code ignored;
        fs::remove(tmp, ignored);
        return false;
    }
    return true;
}

// Keep `fp` for the camera just connected to (trustCamera) in `file`, written whole and private; false when it could
// not be written.
inline bool keepTrusted(const std::filesystem::path& file, const std::string& fp, const std::vector<std::string>& macs,
                        const std::string& address) {
    Trusted kept = readTrusted(fileText(file));
    trustCamera(kept, fp, macs, address);
    return writePrivateFile(file, trustedText(kept));
}

// What both helpers say when the camera at `address` shows another fingerprint than the one kept for it in `file`.
inline std::string cameraChangedText(const std::string& address, const std::filesystem::path& file) {
    return "The camera at " + address + " is not the one this computer trusted before (its fingerprint differs), so its "
           "user name and password were not sent. If you reset the camera's network settings, forget it in the editor "
           "(Connect to the camera, Known cameras) or remove its lines from " + file.u8string() + ", then connect again.";
}

// ---------- the body a camera reached by its address is ----------
// When the SDK's search does not list a network camera, the helpers make its camera object from the address
// (CreateCameraObjectInfoEthernetConnection), which takes the body's model: from CAMSET_MODEL (the editor sets it from
// the known camera's model; the camera link also takes --model), by the name the camera gives its model. The bodies
// with Ethernet, as kit/tools/sdk_support.py and kit/tools/body_check.py name them. A template, so this file needs none
// of the SDK's headers: call lanModel<SCRSDK::CrCameraDeviceModelList>(name, &model) after including them. True for a
// name in the list; for a missing or unknown one, false and the list's first body, which the caller says in a note
// (lanModelNote): the SDK's list has no value for an unknown body.
template <class Model>
inline bool lanModel(const std::string& name, Model* model) {
    const std::pair<const char*, Model> bodies[] = {
        {"ILCE-1M2", Model::CrCameraDeviceModel_ILCE_1M2}, {"ILCE-1", Model::CrCameraDeviceModel_ILCE_1},
        {"ILCE-9M3", Model::CrCameraDeviceModel_ILCE_9M3}, {"ILCE-9M2", Model::CrCameraDeviceModel_ILCE_9M2},
        {"ILME-FX3", Model::CrCameraDeviceModel_ILME_FX3}, {"ILME-FX3A", Model::CrCameraDeviceModel_ILME_FX3A},
        {"ILME-FX30", Model::CrCameraDeviceModel_ILME_FX30}, {"ILME-FX6", Model::CrCameraDeviceModel_ILME_FX6},
        {"ILX-LR1", Model::CrCameraDeviceModel_ILX_LR1}, {"MPC-2610", Model::CrCameraDeviceModel_MPC_2610},
    };
    for (const auto& [n, m] : bodies)
        if (name == n) { *model = m; return true; }
    *model = bodies[0].second;
    return false;
}

// The note for a missing or unknown model: the search did not find the camera, its model is not known, and the
// helper asks as for the list's first body.
inline std::string lanModelNote(const std::string& name, const std::string& address) {
    return (name.empty() ? "the search did not find the camera at " + address + " and its model is unknown (no CAMSET_MODEL)"
                         : "the search did not find the camera at " + address + " and its model, " + name +
                               ", is not one the helpers can reach by its address")
           + "; asking as for an ILCE-1M2, which another body may not answer";
}
