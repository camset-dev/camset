// camera_net_test: checks the parts of camera_net.h that need no camera and no SDK: the address and MAC address text,
// where the files are, the credentials file and its login lookup, the kept fingerprints (known_cameras.json) and the
// model table. Made-up addresses only.
//   c++ -std=c++17 -Wall -Wextra -I kit/common kit/common/camera_net_test.cpp -o /tmp/camera_net_test && /tmp/camera_net_test
#include "camera_net.h"

#include <cstdlib>
#include <iostream>

static int failures = 0;
#define CHECK(x) do { if (!(x)) { ++failures; std::cerr << __FILE__ << ":" << __LINE__ << ": not true: " #x "\n"; } } while (0)

// The SDK's model list as lanModel reads it, made up here so the test needs none of the SDK.
namespace fake {
enum Models : unsigned {
    CrCameraDeviceModel_ILCE_9M2 = 1, CrCameraDeviceModel_ILCE_1, CrCameraDeviceModel_ILME_FX3, CrCameraDeviceModel_ILME_FX30,
    CrCameraDeviceModel_ILME_FX6, CrCameraDeviceModel_ILX_LR1, CrCameraDeviceModel_MPC_2610, CrCameraDeviceModel_ILCE_9M3,
    CrCameraDeviceModel_ILCE_1M2, CrCameraDeviceModel_ILME_FX3A,
};
}

int main() {
    CHECK(macKey("0a-1b-2c-3d-4e-5f") == "0A:1B:2C:3D:4E:5F");
    CHECK(macKey("00:00:00:00:00:00").empty());
    // the address and the MAC address as the SDK takes them, for a camera object made from the address
    unsigned b[4];
    CHECK(ipv4Bytes("192.168.1.50", b) && ipv4Value(b) == 0x3201A8C0u);   // the first number in the lowest byte
    CHECK(!ipv4Bytes("192.168.1.256", b) && !ipv4Bytes("1.2.3.4.5", b) && !ipv4Bytes(" 1.2.3.4", b));
    unsigned char mac[6] = {9, 9, 9, 9, 9, 9};
    CHECK(macBytes("0a-1b-2c-3d-4e-5f", mac) && mac[0] == 0x0A && mac[5] == 0x5F);
    CHECK(!macBytes("not a mac", mac) && mac[0] == 0 && mac[5] == 0);
    CHECK(trimmed("  ILCE-1M2 \r\n") == "ILCE-1M2" && trimmed(" \t ").empty());

    // the login: the camera's own pair by MAC address, else the default pair
    const std::string creds = R"({"user": "d", "password": "dp", "cameras": {"00:11:22:33:44:55": {"name": "x", "user": "c", "password": "cp"}}})";
    CHECK(chooseLogin(creds, "", "", "00:11:22:33:44:55").user == "c");
    CHECK(chooseLogin(creds, "", "", "AA:BB:CC:DD:EE:FF").from == "default");

    // the kept fingerprints: read, compared, kept, written and read back
    Trusted t = readTrusted(R"({"by_mac": {"00:11:22:33:44:55": "SHA256:first"}, "by_address": {"192.168.1.50": "SHA256:first"}})");
    CHECK(t.byMac.size() == 1 && t.byAddress.size() == 1);
    CHECK(readTrusted("").byMac.empty());
    CHECK(readTrusted("not json").byAddress.empty());
    // the same camera, by its MAC address or (no MAC address known) by its address
    CHECK(checkTrust(t, "SHA256:first", {"00:11:22:33:44:55"}, "192.168.1.99").verdict == "same");
    CHECK(checkTrust(t, "SHA256:first", {}, "192.168.1.50").verdict == "same");
    // another key under a kept MAC address: refused, whatever the address says
    TrustCheck c = checkTrust(t, "SHA256:other", {"", "00:11:22:33:44:55"}, "192.168.1.50");
    CHECK(c.verdict == "changed" && c.differ.size() == 1 && c.differ[0] == "00:11:22:33:44:55");
    // something new at a kept address (a MAC address never seen, as when another device claims it): refused
    c = checkTrust(t, "SHA256:other", {"0A:1B:2C:3D:4E:5F"}, "192.168.1.50");
    CHECK(c.verdict == "changed" && c.differ.size() == 1 && c.differ[0] == "192.168.1.50");
    // a kept MAC address that matches decides, even where the address held another camera
    CHECK(checkTrust(t, "SHA256:first", {"00:11:22:33:44:55"}, "192.168.1.60").verdict == "same");
    // a camera never met: new; an empty fingerprint never matches
    CHECK(checkTrust(t, "SHA256:new", {"0A:1B:2C:3D:4E:5F"}, "192.168.1.77").verdict == "new");
    CHECK(checkTrust(t, "", {"00:11:22:33:44:55"}, "").verdict == "changed");

    // kept after a connection: under each MAC address and the address; the camera's old address is dropped
    trustCamera(t, "SHA256:first", {"00:11:22:33:44:55", "0a:1b:2c:3d:4e:5f", ""}, "192.168.1.60");
    CHECK(t.byMac.size() == 2 && t.byMac["0A:1B:2C:3D:4E:5F"] == "SHA256:first");
    CHECK(t.byAddress.size() == 1 && t.byAddress.count("192.168.1.60") == 1);
    trustCamera(t, "", {"AA:BB:CC:DD:EE:FF"}, "192.168.1.20");
    CHECK(t.byMac.count("AA:BB:CC:DD:EE:FF") == 0);
    t.byAddress["192.168.1.20"] = "line \"two\"\nwith a \\ backslash";
    Trusted back = readTrusted(trustedText(t));
    CHECK(back.byMac == t.byMac && back.byAddress == t.byAddress);

    CHECK(fingerprintText("SHA256:abc\n\0junk", 16) == "SHA256:abc");
    CHECK(fingerprintText("SHA256:abc", 6) == "SHA256");

    // the file: written whole and private, read back
    namespace fs = std::filesystem;
    const fs::path dir = fs::temp_directory_path() / "camera_net_test" / "camset";
    std::error_code ec;
    fs::remove_all(dir.parent_path(), ec);
    CHECK(writePrivateFile(dir / "known_cameras.json", trustedText(t)));
    CHECK(readTrusted(fileText(dir / "known_cameras.json")).byMac == t.byMac);
    CHECK(!fs::exists(dir / ".known_cameras.json.part"));
#ifndef _WIN32
    CHECK(!openToOthers(dir / "known_cameras.json"));
    CHECK((fs::status(dir).permissions() & (fs::perms::group_all | fs::perms::others_all)) == fs::perms::none);
    fs::permissions(dir / "known_cameras.json", fs::perms::group_read | fs::perms::others_read, fs::perm_options::add);
    CHECK(openToOthers(dir / "known_cameras.json"));
#endif
    CHECK(!openToOthers(dir / "no_such_file.json"));

    // kept again after a connection: read, the camera added, written back whole
    CHECK(keepTrusted(dir / "kept.json", "SHA256:kept", {"0a:1b:2c:3d:4e:5f"}, "192.168.1.60"));
    const Trusted kept = readTrusted(fileText(dir / "kept.json"));
    CHECK(kept.byMac.at("0A:1B:2C:3D:4E:5F") == "SHA256:kept" && kept.byAddress.at("192.168.1.60") == "SHA256:kept");
    const std::string changed = cameraChangedText("192.168.1.60", dir / "kept.json");
    CHECK(changed.find("192.168.1.60") != std::string::npos && changed.find("were not sent") != std::string::npos &&
          changed.find((dir / "kept.json").u8string()) != std::string::npos);

    // the credentials file: read when private, not read when others may read it, nothing without a folder
    CHECK(writePrivateFile(dir / "network.json", creds));
    Credentials c1 = readCredentials(dir);
    CHECK(!c1.open && c1.text == creds && c1.file == dir / "network.json");
#ifndef _WIN32
    fs::permissions(dir / "network.json", fs::perms::others_read, fs::perm_options::add);
    c1 = readCredentials(dir);
    CHECK(c1.open && c1.text.empty());
#endif
    CHECK(readCredentials(fs::path()).text.empty() && readCredentials(dir / "none").text.empty());
    fs::remove_all(dir.parent_path(), ec);

#ifndef _WIN32
    // where the files are: under HOME (USERPROFILE is Windows'), none without one
    const std::string home = envText("HOME");
    setenv("HOME", "/home/user", 1);
    CHECK(homeDir() == fs::path("/home/user") && camsetDir() == fs::path("/home/user/.config/camset"));
    unsetenv("HOME");
    CHECK(homeDir().empty() && camsetDir().empty() && envText("HOME").empty());
    if (!home.empty()) setenv("HOME", home.c_str(), 1);
#endif

    // the body reached by its address
    fake::Models m{};
    CHECK(lanModel("ILME-FX3", &m) && m == fake::CrCameraDeviceModel_ILME_FX3);
    CHECK(lanModel("ILCE-1", &m) && m == fake::CrCameraDeviceModel_ILCE_1);
    CHECK(!lanModel("", &m) && m == fake::CrCameraDeviceModel_ILCE_1M2);
    CHECK(!lanModel("ILCE-7M9", &m) && m == fake::CrCameraDeviceModel_ILCE_1M2);
    CHECK(lanModelNote("", "192.168.1.50").find("unknown") != std::string::npos);

    if (failures) { std::cerr << failures << " check(s) failed\n"; return 1; }
    std::cout << "camera_net: all checks passed\n";
    return 0;
}
