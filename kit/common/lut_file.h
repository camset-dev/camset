// lut_file.h: what camlink (kit/link) checks before it imports a user LUT into the camera (its importlut command, Sony's
// ImportLUTFile), with none of the SDK's headers, so that kit/common/lut_file_test.cpp checks every refusal with no
// camera. Every check here is made before the SDK is asked anything; a refusal's words start "not imported: ".
//
// Sony's API reference (ImportLUTFile) asks of the file: a name that does not start with a period, of single-byte
// letters, digits, spaces and # $ % & ' ( ) + , - . ; = @ [ ] ^ ` { } ~ _ alone, 63 characters or fewer with its
// extension, the extension "cube" or "cub", and less than 3 MB; of the camera, that BaseLookImportOperationEnableStatus
// reads Enable. The kit asks more, as the owner allowed the import (2026-11-19: only .cube files under the owner's own
// private/lut/): the extension ".cube" alone; the file under a folder private/lut/ where its path really ends (".."
// and a folder that is a link followed; camkit.link checks first that it is the clone's own, LUT_DIR), the file itself
// never a link; a regular file, read once, whose bytes have the SHA-256 the kit gave (kit/camkit/link.py logs it); "less than 3 MB"
// read as 3,000,000 bytes, the stricter reading; text with a LUT_3D_SIZE or LUT_1D_SIZE line (a .cube LUT's size line),
// so another file renamed .cube is not sent. Of the camera, where the reference leaves open what an import does: it
// must not be recording (RecordingState), and the place must not be one it lists as holding a LUT (the user LUTs it
// offers to delete, DeleteUserBaseLook's values, read and never set); a property that cannot be read refuses too. The
// place is a user base look, CrBaseLookNumber 1 to 16.
#pragma once

#include "settings_file.h"      // read: a regular file read once
#include "sha256.h"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <system_error>
#include <vector>

namespace lut_file {

constexpr std::uintmax_t kMaxBytes = 3000000;   // "less than 3 MB": a file of this many bytes or more is refused
constexpr std::size_t kMaxName = 63;            // "63 characters or less, including the file extension"
constexpr long long kFirstPlace = 1, kLastPlace = 16;    // CrBaseLookNumber_1 .. CrBaseLookNumber_16
constexpr long long kEnable = 1;                // CrBaseLookImportOperation_Enable (camlink.cpp checks it is the SDK's)
constexpr long long kNotRecording = 0;          // CrMovie_Recording_State_Not_Recording (likewise)
constexpr long long kDeleteAll = 0xFFFF;        // CrDeleteUserBaseLook_All, in DeleteUserBaseLook's values
constexpr long long kDeleteNone = 0;            // CrDeleteUserBaseLook_Invalid
inline const std::string kSuffix = ".cube";
inline const std::string kSigns = " #$%&'()+,-.;=@[]^`{}~_";       // the reference's signs, the space among them

// Why a file name may not be imported, "" when it may: ".cube", 63 characters at most, no period first, the
// reference's characters alone.
inline std::string nameProblem(const std::string& name) {
    if (name.size() <= kSuffix.size() || name.compare(name.size() - kSuffix.size(), kSuffix.size(), kSuffix) != 0)
        return "its name does not end in \"" + kSuffix + "\" (the kit imports .cube files alone)";
    if (name.size() > kMaxName)
        return "its name is " + std::to_string(name.size()) + " characters; Sony's reference takes " +
               std::to_string(kMaxName) + " at most, the extension counted";
    if (name[0] == '.') return "its name starts with a period, which Sony's reference does not take";
    for (const char c : name) {
        const bool alnum = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
        if (!alnum && kSigns.find(c) == std::string::npos)
            return "its name holds a character Sony's reference does not take (single-byte letters, digits, spaces "
                   "and " + kSigns.substr(1) + " alone)";
    }
    return "";
}

// Why a place may not be imported into, "" when it may: a user base look, 1 to 16.
inline std::string placeProblem(long long place) {
    if (place < kFirstPlace || place > kLastPlace)
        return "place " + std::to_string(place) + " is no user base look (CrBaseLookNumber " +
               std::to_string(kFirstPlace) + " to " + std::to_string(kLastPlace) + ")";
    return "";
}

// Why a file's real path is not one the kit imports from, "" when it is: under a folder "lut" in a folder "private".
inline std::string folderProblem(const std::filesystem::path& real) {
    std::vector<std::string> parts;
    for (const auto& p : real.parent_path()) parts.push_back(p.u8string());
    for (std::size_t k = 0; k + 1 < parts.size(); ++k)
        if (parts[k] == "private" && parts[k + 1] == "lut") return "";
    return "it is not under a folder private/lut/ (the owner's own LUT folder, the only one the kit imports from)";
}

// Whether the bytes are a .cube LUT's text: no NUL, and a line (after spaces or tabs, a byte order mark before the
// first) that starts with LUT_3D_SIZE or LUT_1D_SIZE, then spaces or tabs and a digit; lines end in "\n", "\r\n" or "\r".
inline bool cubeText(const std::vector<unsigned char>& d) {
    if (std::find(d.begin(), d.end(), 0) != d.end()) return false;
    std::size_t at = d.size() >= 3 && d[0] == 0xEF && d[1] == 0xBB && d[2] == 0xBF ? 3 : 0;
    while (at < d.size()) {
        std::size_t end = at;
        while (end < d.size() && d[end] != '\n' && d[end] != '\r') ++end;
        std::size_t s = at;
        while (s < end && (d[s] == ' ' || d[s] == '\t')) ++s;
        const std::string line(d.begin() + static_cast<std::ptrdiff_t>(s), d.begin() + static_cast<std::ptrdiff_t>(end));
        for (const char* word : {"LUT_3D_SIZE", "LUT_1D_SIZE"}) {
            const std::string w = word;
            if (line.compare(0, w.size(), w) != 0) continue;
            std::size_t k = w.size();
            const std::size_t gap = k;
            while (k < line.size() && (line[k] == ' ' || line[k] == '\t')) ++k;
            if (k > gap && k < line.size() && line[k] >= '0' && line[k] <= '9') return true;
        }
        at = end + 1;
    }
    return false;
}

// The file checked, read once: its real path (what the SDK is given), name, size and SHA-256; when it may not go, why
// not (`problem`, "not imported: ...") and the token camlink's reply carries (`cause`): "hash_mismatch" when its bytes
// are not the ones whose SHA-256 the caller gave (either case; none given, as typed by hand, checks none), else
// "not_a_lut".
struct Checked {
    std::filesystem::path path;
    std::string name, sha256, problem, cause;
    std::uintmax_t bytes = 0;
};

inline Checked check(const std::filesystem::path& given, const std::string& expected) {
    namespace fs = std::filesystem;
    Checked c;
    auto refuse = [&](const std::string& why, const std::string& cause = "not_a_lut") {
        c.problem = "not imported: " + given.u8string() + ": " + why;
        c.cause = cause;
        return c;
    };
    std::error_code ec;
    const fs::file_status own = fs::symlink_status(given, ec);
    if (ec || !fs::exists(own)) return refuse("it cannot be read");
    if (fs::is_symlink(own)) return refuse("it is a link: camlink imports the file itself, never through a link");
    // where the path really ends ("..", and a folder that is a link, followed): that is the place judged, and the path
    // the SDK is given
    const fs::path real = fs::canonical(given, ec);
    if (ec || real.empty()) return refuse("its path cannot be followed");
    c.path = real;
    c.name = real.filename().u8string();
    if (const std::string why = folderProblem(real); !why.empty()) return refuse(why);
    if (const std::string why = nameProblem(c.name); !why.empty()) return refuse(why);
    if (!fs::is_regular_file(own)) return refuse("it is not a file");
    const std::uintmax_t size = fs::file_size(real, ec);
    if (!ec && size >= kMaxBytes)
        return refuse("it is " + std::to_string(size) + " bytes; Sony's reference takes less than 3 MB (" +
                      std::to_string(kMaxBytes) + " bytes, the stricter reading)");
    std::vector<unsigned char> d;
    if (const std::string why = settings_file::read(real, &d); !why.empty()) return refuse(why);
    if (d.size() >= kMaxBytes)
        return refuse("it grew to " + std::to_string(d.size()) + " bytes while it was read; Sony's reference takes less "
                      "than 3 MB (" + std::to_string(kMaxBytes) + " bytes)");
    if (!cubeText(d)) return refuse("it is not a .cube LUT's text (no LUT_3D_SIZE or LUT_1D_SIZE line, or not text)");
    c.bytes = d.size();
    c.sha256 = sha256::hex(d);
    std::string want = expected;
    for (char& ch : want) ch = static_cast<char>(ch >= 'A' && ch <= 'Z' ? ch - 'A' + 'a' : ch);
    if (!want.empty() && want != c.sha256)
        return refuse("these are not the bytes whose SHA-256 the command named (theirs is " + c.sha256 + ", not " + want +
                      "): the file was written after the kit checked it", "hash_mismatch");
    return c;
}

// The camera's state, read before the SDK is asked: why the import may not go, "" when it may.
inline std::string enableProblem(bool read, long long value) {
    if (!read) return "BaseLookImportOperationEnableStatus could not be read, and Sony's reference allows the import "
                      "only while it reads Enable";
    if (value != kEnable)
        return "BaseLookImportOperationEnableStatus reads " + std::to_string(value) + (value == 0 ? " (Disable)" : "") +
               ", and Sony's reference allows the import only while it reads Enable (" + std::to_string(kEnable) + ")";
    return "";
}

inline std::string recordingProblem(bool read, long long value) {
    if (!read) return "RecordingState could not be read, so whether the camera is recording is not known (Sony's "
                      "reference does not say what an import does while it records)";
    if (value != kNotRecording)
        return "RecordingState reads " + std::to_string(value) + ", not " + std::to_string(kNotRecording) +
               " (Not Recording), and Sony's reference does not say what an import does while the camera records";
    return "";
}

// `listed`: DeleteUserBaseLook's values, the user LUTs the camera offers to delete (a place by number, All, Invalid).
inline std::string placeHeld(bool read, const std::vector<long long>& listed, long long place) {
    const std::string p = std::to_string(place);
    if (!read) return "DeleteUserBaseLook could not be read, so whether place " + p + " already holds a LUT is not "
                      "known (Sony's reference does not say what an import over one does)";
    const bool all = std::find(listed.begin(), listed.end(), kDeleteAll) != listed.end();
    const bool numbered = std::any_of(listed.begin(), listed.end(), [](long long v) {
        return v >= kFirstPlace && v <= kLastPlace;
    });
    if (std::find(listed.begin(), listed.end(), place) != listed.end())
        return "place " + p + " already holds a LUT (the camera lists it among the user LUTs it can delete), and Sony's "
               "reference does not say what an import over one does: delete it on the camera by hand first, or name "
               "an empty place";
    if (all && !numbered)
        return "the camera lists All among the user LUTs it can delete but no place by number, so whether place " + p +
               " already holds a LUT is not known (Sony's reference does not say what an import over one does)";
    return "";
}

}  // namespace lut_file
