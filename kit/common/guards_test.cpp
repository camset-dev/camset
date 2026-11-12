// guards_test: checks what both C++ programs compile in from kit/common, with no camera and no SDK: never_touch.h (the
// buttons and properties never sent, written from kit/camkit/safety.py), remote.h (the button and dial codes and the
// rule each press goes through), sdk_values.h (a property's value, signed types sign-extended, on a stand-in
// property, and a number as a command gives it), settings_file.h (the check before an upload) on the a1 II
// definition's sample and files spoilt from it, and what camlink uploads (read once, its SHA-256 the one the kit gave,
// else "hash_mismatch"; the copy the SDK is given), sha256.h (the standard's test vectors), callback_wait.h (the wait
// on the SDK's thread), and the request's id on camlink's command line (kit/link/protocol.h). Run from the clone's
// root; kit/tests/test_link_protocol.py builds and runs it, as kit CI does:
//   c++ -std=c++17 -Wall -Wextra -I kit/common kit/common/guards_test.cpp -o /tmp/guards_test && /tmp/guards_test
#include "callback_wait.h"
#include "never_touch.h"
#include "remote.h"
#include "sdk_values.h"
#include "settings_file.h"
#include "sha256.h"
#include "../link/protocol.h"

#ifndef _WIN32
#include <sys/stat.h>            // mkfifo
#endif

#include <cctype>
#include <chrono>
#include <climits>
#include <fstream>
#include <iostream>
#include <iterator>
#include <sstream>
#include <utility>

static int failures = 0;
#define CHECK(x) do { if (!(x)) { ++failures; std::cerr << __FILE__ << ":" << __LINE__ << ": not true: " #x "\n"; } } while (0)

// a stand-in for the SDK's CrDeviceProperty: its raw current value and its type
struct Property {
    uint64_t raw;
    unsigned type;
    uint64_t GetCurrentValue() const { return raw; }
    unsigned GetValueType() const { return type; }
};

static void values() {
    const unsigned Int8 = 0x1001, UInt8 = 0x0001, Int16 = 0x1002, UInt16 = 0x0002, Int32 = 0x1003, Int64 = 0x1004;
    CHECK(sdk_values::current(Property{0xFD, Int8}) == -3);              // the raw 253 a signed byte holds
    CHECK(sdk_values::current(Property{0xFD, UInt8}) == 253);
    CHECK(sdk_values::current(Property{0xFFF6, Int16}) == -10);
    CHECK(sdk_values::current(Property{0xFC18, Int16}) == -1000);       // the SDK's -1.0 EV in thousandths
    CHECK(sdk_values::current(Property{0xFC18, UInt16}) == 64536);
    CHECK(sdk_values::current(Property{0xFFFFFFFF, Int32}) == -1);
    CHECK(sdk_values::current(Property{0xFFFFFFFFFFFFFFFEull, Int64}) == -2);
    CHECK(sdk_values::current(Property{0x41, 0xFFFF}) == 0);              // a text property has no number
    CHECK(sdk_values::width(0x4002) == 2 && sdk_values::width(0x2003) == 4);   // a range's and an array's element
    const unsigned char packed[] = {0x18, 0xFC, 0xE8, 0x03};
    CHECK(sdk_values::at(packed, Int16) == -1000 && sdk_values::at(packed + 2, Int16) == 1000);

    // a number as a command gives it: decimal or 0x hex, signed; anything after it, or past a long long, is refused
    long long v = 0;
    CHECK(sdk_values::parse("65786", &v) && v == 65786);
    CHECK(sdk_values::parse("-3", &v) && v == -3);
    CHECK(sdk_values::parse("+5", &v) && v == 5);
    CHECK(sdk_values::parse("0x1A", &v) && v == 26);
    CHECK(sdk_values::parse("-0x10", &v) && v == -16);
    CHECK(sdk_values::parse("08", &v) && v == 8);                         // decimal, where std::stoll's octal read 0
    CHECK(sdk_values::parse("9223372036854775807", &v) && v == LLONG_MAX);
    CHECK(sdk_values::parse("-9223372036854775808", &v) && v == LLONG_MIN);
    v = 42;
    for (const char* bad : {"", "-", "+", "0x", "12abc", "1e3", " 5", "5 ", "--5", "0x-5", "+-1", "0xZZ", "allowed",
                            "9223372036854775808", "-9223372036854775809", "0x10000000000000000"})
        CHECK(!sdk_values::parse(bad, &v));
    CHECK(v == 42);                                                       // left as it was
}

// the buttons and dials each helper presses: every name has a rule in never_touch.h, and the rule is the lists'
static void remote_inputs() {
    for (const remote::Code& c : remote::kButtons) {
        const std::string n = c.name;
        CHECK(never_touch::menuButton(n) || never_touch::guardedButton(n) || never_touch::neverButton(n));
        CHECK(c.code != 0 && (c.code & 0xFFFFu) == 0);
    }
    for (const remote::Code& c : remote::kDials) CHECK(never_touch::menuButton(c.name) && (c.code & 0xFFFFu) == 0);
    // the three lists share no name: a button is pressed always, only when allowed, or never, never two of these
    for (const char* n : never_touch::kMenuButtons) CHECK(!never_touch::guardedButton(n) && !never_touch::neverButton(n));
    for (const char* n : never_touch::kGuardedButtons) CHECK(!never_touch::neverButton(n));
    // every button the lists name is in the table, and every other name in the lists is a dial
    for (const char* n : never_touch::kGuardedButtons) CHECK(remote::buttonCode(n) != 0);
    for (const char* n : never_touch::kNeverButtons) CHECK(remote::buttonCode(n) != 0);
    for (const char* n : never_touch::kMenuButtons) CHECK((remote::buttonCode(n) != 0) != (remote::dialCode(n) != 0));
    CHECK(remote::buttonCode("up") == 0x00010000 && remote::buttonCode("c4") == 0x00170000 && remote::buttonCode("C4") == 0);
    CHECK(remote::dialCode("rear_l") == 0x40030000 && remote::dialCode("rearl") == 0 && remote::buttonCode("wheel") == 0);
    CHECK(remote::dialValue(0x40010000, 3) == 0x40010003 && remote::dialValue(0x40010000, -2) == 0x4001FFFE);
    // the rule: the menus' own always, a guarded one only when allowed, a never one and any other name never
    using remote::Press;
    CHECK(remote::pressRule("up", false) == Press::allowed && remote::pressRule("wheel", false) == Press::allowed);
    CHECK(remote::pressRule("c4", false) == Press::guarded && remote::pressRule("c4", true) == Press::allowed);
    CHECK(remote::pressRule("c1", true) == Press::never && remote::pressRule("movie", true) == Press::never);
    for (const char* n : {"C4", "c4 ", "", "trash", "shutter", "c8"}) CHECK(remote::pressRule(n, true) == Press::unlisted);
}

// the wait on the SDK's callback thread: one kind at a time, nothing after it timed out
static void callback_wait() {
    using std::chrono::milliseconds;
    CallbackWait w;
    std::string detail;
    w.arm("download");
    w.finish("upload", true, "wrong kind");                               // another kind's ending is ignored
    w.finish("download", true, "_camlink_tmp.DAT");
    w.finish("download", false, "second");                                // the first ending stands
    CHECK(w.wait(milliseconds(10), &detail) == CallbackWait::Ended::ok && detail == "_camlink_tmp.DAT");
    w.finish("download", false, "late");                                  // disarmed: a late callback changes nothing
    w.arm("prop", 0x5004);
    const unsigned codes[] = {0x5001, 0x5004};
    w.changed(1, codes);                                                  // 0x5001 only
    CHECK(w.wait(milliseconds(1), &detail) == CallbackWait::Ended::timedOut && detail == "prop timed out");
    w.arm("prop", 0x5004);
    w.changed(2, codes);
    CHECK(w.until(milliseconds(10), &detail));
    w.arm("connect");
    w.failAny("disconnected");
    CHECK(w.wait(milliseconds(10), &detail) == CallbackWait::Ended::failed && detail == "disconnected");
    w.failAny("nothing armed");
    w.arm("upload");
    CHECK(w.wait(milliseconds(1), nullptr) == CallbackWait::Ended::timedOut);
    w.finish("upload", true);                                             // after the timeout: ignored
    w.arm("");
    w.finish("", true);                                                   // "" is no kind to end
    CHECK(w.wait(milliseconds(1), &detail) == CallbackWait::Ended::timedOut);
    // a download that timed out finishes during the next one's wait: its file is not this download's
    w.arm("download", 0, "_camlink_tmp_2_");
    w.finish("download", true, "/runs/dat/_camlink_tmp_1_.DAT");
    w.finish("download", true, "/runs/dat/_camlink_tmp_21_.DAT");
    CHECK(w.wait(milliseconds(1), &detail) == CallbackWait::Ended::timedOut);
    w.arm("download", 0, "_camlink_tmp_2_");
    w.finish("download", true, "/runs/dat/_camlink_tmp_1_.DAT");
    w.finish("download", true, "/runs/dat/_camlink_tmp_2_.DAT");
    CHECK(w.wait(milliseconds(10), &detail) == CallbackWait::Ended::ok && detail == "/runs/dat/_camlink_tmp_2_.DAT");
    w.arm("download", 0, "_camlink_tmp_3_");
    w.finish("download", true, "");                                       // no name: nothing to tell it by, taken
    CHECK(w.until(milliseconds(10), &detail) && detail.empty());
    w.arm("download", 0, "_camlink_tmp_4_");
    w.finish("download", false, "Save_Result_NG");                        // a failure names no file: taken
    CHECK(w.wait(milliseconds(10), &detail) == CallbackWait::Ended::failed);
}

// camlink's command line: the request's id comes back as a JSON number, without leading zeros
static void request_ids() {
    auto id = [](const std::string& line, std::string* cmd) {
        std::istringstream in(line);
        return protocol::command(in, *cmd);
    };
    std::string cmd;
    CHECK(id("@17 ping", &cmd) == "17" && cmd == "ping");
    CHECK(id("@007 ping", &cmd) == "7" && cmd == "ping");
    CHECK(id("@000 ping", &cmd) == "0" && cmd == "ping");
    CHECK(id("@5", &cmd) == "5" && cmd.empty());                         // camlink answers it: no command after the id
    CHECK(id("@x1 ping", &cmd).empty() && cmd == "@x1");
}

static void settings_files() {
    const std::filesystem::path sample = "editor/definitions/ILCE-1M2_fw4.00.DAT";
    std::ifstream f(sample, std::ios::binary);
    CHECK(f.good());
    std::vector<unsigned char> d((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    CHECK(settings_file::problem(d).empty());
    CHECK(settings_file::problemOfFile(sample).empty());
    // a longer header (another container's block): the records still frame and the sum still holds
    std::vector<unsigned char> longer(d.begin(), d.begin() + 0x39);
    longer.insert(longer.end(), 4, 0);
    longer.insert(longer.end(), d.begin() + 0x39, d.end());
    CHECK(settings_file::problem(longer).empty());
    // spoilt: one value byte changed, cut off, a byte too many, a picture's first bytes, text
    std::vector<unsigned char> changed = d;
    changed[0x200] ^= 1;
    CHECK(!settings_file::problem(changed).empty());
    CHECK(!settings_file::problem(std::vector<unsigned char>(d.begin(), d.end() - 100)).empty());
    std::vector<unsigned char> extra = d;
    extra.insert(extra.end() - 4, 0);
    CHECK(!settings_file::problem(extra).empty());
    std::vector<unsigned char> jpeg(4096, 0x20);
    jpeg[0] = 0xFF; jpeg[1] = 0xD8; jpeg[2] = 0xFF;
    CHECK(!settings_file::problem(jpeg).empty());
    const std::string text = "not a settings file, only words, long enough to be read past the shortest a file can be";
    CHECK(!settings_file::problem(std::vector<unsigned char>(text.begin(), text.end())).empty());
    CHECK(!settings_file::problem({}).empty());
    CHECK(!settings_file::problemOfFile("no/such/file.DAT").empty());
    // a file past the largest a settings file can be is refused by its size, without being read
    const std::filesystem::path big = std::filesystem::temp_directory_path() / "guards_test_big.DAT";
    {
        std::ofstream o(big, std::ios::binary);
        o.seekp(static_cast<std::streamoff>(settings_file::kMaxBytes));
        o.put('\0');
    }
    CHECK(settings_file::problemOfFile(big).find("too large") != std::string::npos);
    std::error_code ec;
    std::filesystem::remove(big, ec);
}

// sha256.h: the standard's examples (FIPS 180-2, appendix B, and NIST's), and lengths about the padding's block
// boundaries (55, 56, 63, 64 ... bytes of (7k + 1) mod 256) as Python's hashlib.sha256 gives them
static void sha256_vectors() {
    CHECK(sha256::hex(std::string()) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    CHECK(sha256::hex(std::string("abc")) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    CHECK(sha256::hex(std::string("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq")) ==
          "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");
    CHECK(sha256::hex(std::string("abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmnoijklmnopjklmnopqklmnopqrlmnopq"
                                  "rsmnopqrstnopqrstu")) == "cf5b16a778af8380036ce59e7b0492370b249b11e8f07a51afac45037afee9d1");
    CHECK(sha256::hex(std::string(1000000, 'a')) == "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
    const struct { std::size_t n; const char* want; } lengths[] = {
        {55, "16fa57a0a3423a715d594516339f36189d6b5f93754a9714fef202616a9fabfe"},
        {56, "c37b44e5f1b18554b36966f4f8e08bfbf3164c4b6c10374d12d89850892073c5"},
        {63, "bbba992d2c85af960fb2987a1fd05e0aa82a3db3c740dd8982a9e273b75e36a3"},
        {64, "66bd4633ed6f71c4ecfa4763bf7ba1c8ec7612de9aa6c0578a7b675207c71e0b"},
        {65, "9f7dc47107b750a1f3d35db5d9547f24ef40da5b731b9540d4f43710a154f6c9"},
        {119, "a3ed307b730fa77c07531300c6e4a282330011d4d4caf6bb7b63ae05950f4b66"},
        {120, "8e3b15d9fea7472655aa069620b7f8c2e55ee1499f763200a7515fe826e99d20"},
        {127, "44480fb9672845177f5368a08b69ea263275f2a5ec42e06a933370fe0d2968a4"},
        {128, "e462c130fef8c97e34f7dc3ff3ad2f8b3533ab849af21c10531552a2852387a4"},
        {1000, "095ecb62e30793ab4b954cd6a0586d0cc91f7ea5b1332694d8da780e98676d78"}};
    for (const auto& l : lengths) {
        std::vector<unsigned char> d(l.n);
        for (std::size_t k = 0; k < l.n; ++k) d[k] = static_cast<unsigned char>((k * 7 + 1) & 0xFF);
        CHECK(sha256::hex(d) == l.want);
    }
}

static std::vector<unsigned char> bytesOf(const std::filesystem::path& p) {
    std::ifstream f(p, std::ios::binary);
    return std::vector<unsigned char>((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
}

static void writeBytes(const std::filesystem::path& p, const std::vector<unsigned char>& d) {
    std::ofstream o(p, std::ios::binary);
    o.write(reinterpret_cast<const char*>(d.data()), static_cast<std::streamsize>(d.size()));
}

// what camlink uploads (settings_file.h toSend and writeCopy): the file read once, sent only when its bytes have the
// SHA-256 the kit gave (that of the camera download it checked), else "hash_mismatch", and from a copy of its own
static void uploads() {
    namespace fs = std::filesystem;
    const fs::path sample = "editor/definitions/ILCE-1M2_fw4.00.DAT";
    const std::vector<unsigned char> d = bytesOf(sample);
    const std::string hash = sha256::hex(d);
    std::string upper = hash;
    for (char& c : upper) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    settings_file::ToSend s = settings_file::toSend(sample, hash);
    CHECK(s.problem.empty() && s.cause.empty() && s.bytes == d && s.sha256 == hash);
    CHECK(settings_file::toSend(sample, upper).problem.empty());               // either case
    CHECK(settings_file::toSend(sample, "").problem.empty());                  // no hash given (typed by hand): none checked

    const fs::path dir = fs::temp_directory_path() /
                         ("guards_test_upload_" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    fs::create_directories(dir);
    // a file swapped in after the kit's check (here the download with one byte changed): its bytes are not the hash's
    const fs::path swapped = dir / "00001_start.DAT";
    std::vector<unsigned char> changed = d;
    changed[0x200] ^= 1;
    writeBytes(swapped, changed);
    s = settings_file::toSend(swapped, hash);
    CHECK(s.cause == "hash_mismatch" && s.problem.rfind("not sent: ", 0) == 0);
    CHECK(s.problem.find(hash) != std::string::npos && s.problem.find(sha256::hex(changed)) != std::string::npos);
    CHECK(settings_file::toSend(swapped, upper).cause == "hash_mismatch");
    // with its own hash it is still no settings file; with none, the same; a file that is not there cannot be read
    CHECK(settings_file::toSend(swapped, sha256::hex(changed)).cause == "not_a_settings_file");
    CHECK(settings_file::toSend(swapped, "").cause == "not_a_settings_file");
    s = settings_file::toSend(dir / "no such file.DAT", hash);
    CHECK(s.cause.empty() && s.problem == "not sent: it cannot be read");
    // only a regular file is read: a folder is no file (not a "hash_mismatch" of zero bytes), and neither is a pipe
    // (whose open would wait for a writer) or a device (/dev/zero would be read until memory ran out)
    std::vector<unsigned char> got = {1};
    CHECK(settings_file::read(dir, &got) == "it is not a file" && got.empty());
    s = settings_file::toSend(dir, hash);
    CHECK(s.cause.empty() && s.problem == "not sent: it is not a file");
    CHECK(settings_file::problemOfFile(dir) == "it is not a file");
#ifndef _WIN32
    const fs::path pipe = dir / "pipe.DAT";
    if (mkfifo(pipe.c_str(), 0600) == 0) {
        s = settings_file::toSend(pipe, hash);
        CHECK(s.cause.empty() && s.problem == "not sent: it is not a file");
    }
    if (fs::exists("/dev/zero")) CHECK(settings_file::read("/dev/zero", &got) == "it is not a file" && got.empty());
#endif

    // the copy the SDK is given: beside the file, ".DAT", the bytes checked, this user's alone, never an existing file
    const fs::path original = dir / "00002_start.DAT";
    writeBytes(original, d);
    fs::path copy, second;
    CHECK(settings_file::writeCopy(original, d, "_guards_upload", &copy).empty());
    CHECK(copy.parent_path() == fs::absolute(original).parent_path() && copy.extension() == ".DAT");
    CHECK(copy.filename().string().rfind("_guards_upload_", 0) == 0 && bytesOf(copy) == d);
#ifndef _WIN32
    CHECK((fs::status(copy).permissions() & fs::perms::all) == (fs::perms::owner_read | fs::perms::owner_write));
#endif
    const std::vector<unsigned char> small = {1, 2, 3};
    CHECK(settings_file::writeCopy(original, small, "_guards_upload", &second).empty());
    CHECK(second != copy && bytesOf(second) == small && bytesOf(copy) == d);  // the name taken: one of its own
    // a link where the copy would go is not followed: the file it points at is left as it was
    fs::path first, linked;
    CHECK(settings_file::writeCopy(original, small, "_guards_link", &first).empty());
    fs::remove(first);
    std::error_code ec;
    fs::create_symlink(original, first, ec);
    if (!ec) {
        CHECK(settings_file::writeCopy(original, small, "_guards_link", &linked).empty());
        CHECK(linked != first && bytesOf(original) == d && bytesOf(linked) == small);
    }
    // a folder it cannot write in: why, in words, and no copy
    fs::path none;
    CHECK(!settings_file::writeCopy(dir / "no such folder" / "x.DAT", d, "_guards_upload", &none).empty() && none.empty());
    fs::remove_all(dir, ec);
}

int main() {
    values();
    settings_files();
    sha256_vectors();
    uploads();
    remote_inputs();
    callback_wait();
    request_ids();
    // the buttons: the menus' always, C4 and the other guarded ones only when allowed, C1-C3, C5-C7 and Movie never
    CHECK(never_touch::menuButton("down") && never_touch::menuButton("menu") && !never_touch::menuButton("c4"));
    CHECK(never_touch::guardedButton("c4") && never_touch::guardedButton("playback"));
    for (const char* b : {"c1", "c2", "c3", "c5", "c6", "c7", "movie", "af_on", "mode"}) CHECK(never_touch::neverButton(b));
    CHECK(!never_touch::neverButton("c4") && !never_touch::neverButton("up"));
    CHECK(never_touch::kMinHoldMs == 20 && never_touch::kMaxHoldMs == 2000);

    // the properties: sound, light, motion, credentials, identity, actions and the buttons themselves are never set
    for (const char* p : {"PreAF", "CrDeviceProperty_PreAF", "Focus_Operation", "FocusOperationWithInt16", "Zoom_Operation",
                          "TallyLampControlRed", "AFIlluminator", "FlashMode", "WirelessFlash", "ImageStabilizationSteadyShot",
                          "SilentModeShutterWhenPowerOff", "AudioSignals", "PlaybackVolumeSettings", "SetCopyright",
                          "DateTime_Settings", "LanguageSetting", "WakeOnLAN", "FTP_Function", "CameraButtonFunction",
                          "CameraDialFunction", "S1", "S2", "MediaSLOT1_FormatEnableStatus", "RecorderStartMain",
                          "CustomWB_Capture", "PictureProfile_Copy", "SdkControlMode", "CameraPowerStatus"})
        CHECK(!never_touch::property(p).empty());
    CHECK(never_touch::property("PreAF").rfind("sound, light or motion: motion", 0) == 0);
    // a code or no name: never set either
    CHECK(!never_touch::property("0x1234").empty() && !never_touch::property("").empty());
    // the live exposure the kit sets (camkit.safety.SET_PROPERTIES), and settings that only hold a value, pass
    for (const char* p : {"ShutterSpeed", "FNumber", "ExposureBiasCompensation", "FlashCompensation", "IsoSensitivity",
                          "WhiteBalance", "FocusMode", "DriveMode", "OSDImageMode"})
        CHECK(never_touch::property(p).empty());
    // the case matters, as in kit/camkit/safety.py (kit/tests/test_guards.py's two lists): matched with case ignored,
    // these 23 of the a1 II's names were refused by accident inside other words ("usB", "sSh", "format", "rating",
    // "eraSe", "reset", "ftP"); a name as the SDK writes it is judged where its words start
    for (const char* p : {"FocusBracketExposureLock1stImg", "FocusBracketFocusRange", "FocusBracketIntervalUntilNextShot",
                          "FocusBracketOrder", "FocusBracketRecordingFolder", "FocusBracketShootingStatus",
                          "FocusBracketShotNumber", "ContinuousShootingSpeedInElectricShutterHi",
                          "ContinuousShootingSpeedInElectricShutterHiPlus", "ContinuousShootingSpeedInElectricShutterLo",
                          "ContinuousShootingSpeedInElectricShutterMid", "ContinuousShootingSpotBoostEnableStatus",
                          "ContinuousShootingSpotBoostFrameSpeed", "ContinuousShootingSpotBoostStatus", "FlickerLessShooting",
                          "FlickerLessShootingStatus", "LensInformationEnableStatus", "CameraOperatingMode",
                          "CameraSetting_ReadOperationEnableStatus", "IsoAutoMinShutterSpeedPreset", "TimeCodePreset",
                          "UserBitPreset", "TimeShiftPreShootingTimeSetting"})
        CHECK(never_touch::property(p).empty());
    // and the true refusals stay, each for its reason, with or without "CrDeviceProperty_": names in the a1 II's SDK
    // property list, as kit/tests/test_guards.py's TRUE_REFUSALS
    const std::pair<const char*, const char*> refusals[] = {
        {"PreAF", "motion"}, {"Zoom_Operation", "motion"}, {"VideoStreamSettingVersion", "credentials"},
        {"RemoteTouchOperation", "credentials"}, {"USBPowerSupply", "credentials"},
        {"MediaSLOT1_FormatEnableStatus", "action"}, {"DeleteContentOperationEnableStatusSLOT1", "action"},
        {"TimeCodePresetResetEnableStatus", "action"}, {"AFIlluminator", "light"}, {"FTP_Function", "credentials"},
        {"SetCopyright", "by hand"}, {"CameraButtonFunction", "a button"}};
    for (const auto& [name, kind] : refusals) {
        const std::string why = never_touch::property(name);
        CHECK(why.find(kind) != std::string::npos);
        CHECK(never_touch::property(std::string("CrDeviceProperty_") + name) == why);
    }

    if (failures) std::cerr << failures << " check(s) failed\n";
    else std::cout << "guards: all checks passed\n";
    return failures ? 1 : 0;
}
