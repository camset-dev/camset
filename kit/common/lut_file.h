// lut_file.h: everything camlink (kit/link) decides when it imports a user LUT into the camera (its importlut command,
// Sony's ImportLUTFile; docs/decisions/0026), with none of the SDK's headers, so that kit/common/lut_file_test.cpp checks
// every refusal and the path the SDK is given with no camera: camlink only reads the camera's three properties, calls
// plan(), then the SDK with the plan's copy, and judges the answer with judge(). A refusal's words start "not imported: ".
//
// Sony's API reference (ImportLUTFile) asks of the file: a name that does not start with a period, of single-byte
// letters, digits, spaces and # $ % & ' ( ) + , - . ; = @ [ ] ^ ` { } ~ _ alone, 63 characters or fewer with its
// extension, the extension "cube" or "cub", and less than 3 MB; of the camera, that BaseLookImportOperationEnableStatus
// reads Enable. Decision 26 asks more: the extension ".cube" alone; the file's real path (".." and a folder that is a
// link followed) strictly under the clone's own private/lut/, which camlink is built with (kit/link/CMakeLists.txt:
// CAMSET_LUT_DIR) and which must be there, the file itself never a link; a regular file, read once, whose bytes have the
// SHA-256 the command names (it must name one: kit/camkit/link.py logs it); "less than 3 MB" read as 3,000,000 bytes,
// the stricter reading; text with a LUT_3D_SIZE or LUT_1D_SIZE line (a .cube LUT's size line), so another file renamed
// .cube is not sent; user place 16 alone. Of the camera, where the reference leaves open what an import does: it must
// not be recording (RecordingState), and the place must not be one it lists as holding a LUT (the user LUTs it offers to
// delete, DeleteUserBaseLook's values, read and never set), nor may that list hold a value no reading of it explains;
// a property that cannot be read refuses too.
//
// The SDK imports from a path, which it opens itself once asked. It is never given the file checked: the bytes checked
// are written into a fresh folder only this user can open (0700), under the same file name (Sony's rules are about the
// name), and that copy's path is what it gets, so a file renamed over the original, or a folder on its path swapped for
// a link, after the check is never what the camera receives. camlink removes the copy once the camera has answered, and
// keeps one whose import may still be reading it (no answer) until it exits.
#pragma once

#include "callback_wait.h"
#include "settings_file.h"      // read: a regular file read once
#include "sha256.h"

#include <algorithm>
#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <system_error>
#include <vector>

#ifdef _WIN32
#include <direct.h>
#include <fcntl.h>
#include <io.h>
#include <process.h>
#include <share.h>
#include <sys/stat.h>
#include <sys/types.h>
#else
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace lut_file {

namespace fs = std::filesystem;

constexpr std::uintmax_t kMaxBytes = 3000000;   // "less than 3 MB": a file of this many bytes or more is refused
constexpr std::size_t kMaxName = 63;            // "63 characters or less, including the file extension"
constexpr long long kPlace = 16;                // the one user place decision 26 allows (CrBaseLookNumber_16)
constexpr long long kFirstUser = 1, kLastUser = 16;     // CrBaseLookNumber_1 .. _16: the user places a list may name
constexpr long long kEnable = 1;                // CrBaseLookImportOperation_Enable (camlink.cpp checks it is the SDK's)
constexpr long long kNotRecording = 0;          // CrMovie_Recording_State_Not_Recording (likewise)
constexpr long long kDeleteAll = 0xFFFF;        // CrDeleteUserBaseLook_All, in DeleteUserBaseLook's values
constexpr long long kDeleteNone = 0;            // CrDeleteUserBaseLook_Invalid
inline const std::string kSuffix = ".cube";
inline const std::string kSigns = " #$%&'()+,-.;=@[]^`{}~_";       // the reference's signs, the space among them
inline const std::string kCopyPrefix = "camlink_lut_";             // the copy's folder, in the system's temporary one

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

// Why a place may not be imported into, "" when it may: user place 16 alone (decision 26).
inline std::string placeProblem(long long place) {
    if (place != kPlace)
        return "place " + std::to_string(place) + " is not user place " + std::to_string(kPlace) +
               ", the one place decision 26 allows";
    return "";
}

// Why a file's real path is not one the kit imports from, "" when it is: strictly under `lutDir`, the clone's own LUT
// folder as camlink was built with it, which must be there (followed to where it really is).
inline std::string folderProblem(const fs::path& real, const fs::path& lutDir) {
    std::error_code ec;
    if (lutDir.empty()) return "camlink was built without the clone's LUT folder (CAMSET_LUT_DIR): rebuild it with "
                               "python3 kit/setup.py";
    const fs::path top = fs::canonical(lutDir, ec);
    if (ec || !fs::is_directory(top, ec))
        return "the clone's own LUT folder, " + lutDir.u8string() + ", is not there";
    auto t = top.begin();
    auto r = real.begin();
    for (; t != top.end(); ++t, ++r)
        if (r == real.end() || *r != *t) break;
    if (t != top.end() || r == real.end() || real == top)
        return "it is not under the clone's own LUT folder, " + top.u8string() + " (private/lut/, the only one the kit "
               "imports from)";
    return "";
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

// The file checked, read once: its real path, name, bytes, size and SHA-256; when it may not go, why not (`problem`,
// "not imported: ...") and the token camlink's reply carries (`cause`): "hash_mismatch" when its bytes are not the ones
// whose SHA-256 the command names (either case), "refused" when it names none, else "not_a_lut".
struct Checked {
    fs::path path;
    std::string name, sha256, problem, cause;
    std::vector<unsigned char> data;
    std::uintmax_t bytes = 0;
};

inline Checked check(const fs::path& given, const std::string& expected, const fs::path& lutDir) {
    Checked c;
    auto refuse = [&](const std::string& why, const std::string& cause = "not_a_lut") {
        c.problem = "not imported: " + given.u8string() + ": " + why;
        c.cause = cause;
        c.data.clear();
        return c;
    };
    if (expected.empty())
        return refuse("the command names no SHA-256 for its bytes (importlut PATH 16 SHA256, as kit/camkit/link.py "
                      "sends it)", "refused");
    std::error_code ec;
    const fs::file_status own = fs::symlink_status(given, ec);
    if (ec || !fs::exists(own)) return refuse("it cannot be read");
    if (fs::is_symlink(own)) return refuse("it is a link: camlink imports the file itself, never through a link");
    const fs::path real = fs::canonical(given, ec);     // ".." and a folder that is a link followed: the place judged
    if (ec || real.empty()) return refuse("its path cannot be followed");
    c.path = real;
    c.name = real.filename().u8string();
    if (const std::string why = folderProblem(real, lutDir); !why.empty()) return refuse(why);
    if (const std::string why = nameProblem(c.name); !why.empty()) return refuse(why);
    if (!fs::is_regular_file(own)) return refuse("it is not a file");
    const std::uintmax_t size = fs::file_size(real, ec);
    if (!ec && size >= kMaxBytes)
        return refuse("it is " + std::to_string(size) + " bytes; Sony's reference takes less than 3 MB (" +
                      std::to_string(kMaxBytes) + " bytes, the stricter reading)");
    if (const std::string why = settings_file::read(real, &c.data); !why.empty()) return refuse(why);
    if (c.data.size() >= kMaxBytes)
        return refuse("it grew to " + std::to_string(c.data.size()) + " bytes while it was read; Sony's reference takes "
                      "less than 3 MB (" + std::to_string(kMaxBytes) + " bytes)");
    if (!cubeText(c.data)) return refuse("it is not a .cube LUT's text (no LUT_3D_SIZE or LUT_1D_SIZE line, or not text)");
    c.bytes = c.data.size();
    c.sha256 = sha256::hex(c.data);
    std::string want = expected;
    for (char& ch : want) ch = static_cast<char>(ch >= 'A' && ch <= 'Z' ? ch - 'A' + 'a' : ch);
    if (want != c.sha256)
        return refuse("these are not the bytes whose SHA-256 the command named (theirs is " + c.sha256 + ", not " + want +
                      "): the file was written after the kit checked it", "hash_mismatch");
    return c;
}

// The camera's state as camlink read it, before the SDK is asked: each property's value and whether it could be read.
struct CameraState {
    bool enableRead = false;
    long long enable = -1;
    bool recordingRead = false;
    long long recording = -1;
    bool listRead = false;
    std::vector<long long> listed;      // DeleteUserBaseLook's values: the user LUTs the camera offers to delete
};

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

// Why the place may not be imported into by what the camera lists (`listed`: DeleteUserBaseLook's values, a user place
// by number, All, Invalid), "" when it may. Sony's reference does not document how a held place is listed: a value
// that is none of Invalid, All or a user place 1-16 refuses, as does All with no place by number, or the place itself.
inline std::string placeHeld(bool read, const std::vector<long long>& listed, long long place) {
    const std::string p = std::to_string(place);
    if (!read) return "DeleteUserBaseLook could not be read, so whether place " + p + " already holds a LUT is not "
                      "known (Sony's reference does not say what an import over one does)";
    for (const long long v : listed)
        if (v != kDeleteNone && v != kDeleteAll && (v < kFirstUser || v > kLastUser))
            return "the camera lists a value among the user LUTs it can delete that no reading of the list explains (" +
                   std::to_string(v) + "), so whether place " + p + " already holds a LUT is not known";
    const bool all = std::find(listed.begin(), listed.end(), kDeleteAll) != listed.end();
    const bool numbered = std::any_of(listed.begin(), listed.end(), [](long long v) {
        return v >= kFirstUser && v <= kLastUser;
    });
    if (std::find(listed.begin(), listed.end(), place) != listed.end())
        return "place " + p + " already holds a LUT (the camera lists it among the user LUTs it can delete), and Sony's "
               "reference does not say what an import over one does: delete it on the camera by hand first";
    if (all && !numbered)
        return "the camera lists All among the user LUTs it can delete but no place by number, so whether place " + p +
               " already holds a LUT is not known (Sony's reference does not say what an import over one does)";
    return "";
}

// The camera's refusal before the SDK is asked: the import not enabled ("import_disabled"), or recording, or the place
// held or not known to be empty ("import_refused"); none when it may go.
struct Refusal {
    std::string problem, cause;
};

inline Refusal stateRefusal(const CameraState& s, long long place) {
    if (const std::string why = enableProblem(s.enableRead, s.enable); !why.empty())
        return {"not imported: " + why, "import_disabled"};
    if (const std::string why = recordingProblem(s.recordingRead, s.recording); !why.empty())
        return {"not imported: " + why, "import_refused"};
    if (const std::string why = placeHeld(s.listRead, s.listed, place); !why.empty())
        return {"not imported: " + why, "import_refused"};
    return {};
}

// The copy the SDK imports from: a folder of its own and the file in it.
struct Copy {
    fs::path dir, path;
};

// The checked bytes written as a new file of the same name in a new folder under `under` ("camlink_lut_<pid>_<n>"),
// the folder made only this user can open (0700) and the file only this user can read and write (0600; on Windows the
// temporary folder's permissions), neither ever an existing one or a link. "" with the copy in *out, else why not.
inline std::string writeCopy(const Checked& f, Copy* out, const fs::path& under) {
#ifdef _WIN32
    const int pid = _getpid();
#else
    const long pid = static_cast<long>(getpid());
#endif
    for (int n = 0; n < 100; ++n) {
        const fs::path dir = under / (kCopyPrefix + std::to_string(pid) + "_" + std::to_string(n));
#ifdef _WIN32
        const int made = _wmkdir(dir.c_str());
#else
        const int made = ::mkdir(dir.c_str(), S_IRWXU);
#endif
        if (made != 0 && errno == EEXIST) continue;
        if (made != 0) return "the copy's folder could not be made in " + under.u8string() + ": " +
                              std::generic_category().message(errno);
        const fs::path file = dir / fs::u8path(f.name);
        int err = 0;
#ifdef _WIN32
        int fd = -1;
        err = _wsopen_s(&fd, file.c_str(), _O_WRONLY | _O_CREAT | _O_EXCL | _O_BINARY | _O_NOINHERIT, _SH_DENYRW,
                        _S_IREAD | _S_IWRITE);
#else
        const int fd = ::open(file.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, S_IRUSR | S_IWUSR);
        if (fd < 0) err = errno;
#endif
        std::error_code ec;
        if (err) {
            fs::remove(dir, ec);
            return "the copy could not be made in " + dir.u8string() + ": " + std::generic_category().message(err);
        }
        std::size_t at = 0;
        int failed = 0;
        while (at < f.data.size()) {
#ifdef _WIN32
            const long long wrote = _write(fd, f.data.data() + at, static_cast<unsigned>(f.data.size() - at));
#else
            const long long wrote = ::write(fd, f.data.data() + at, f.data.size() - at);
            if (wrote < 0 && errno == EINTR) continue;           // a signal (camlink's handler) is no failure
#endif
            if (wrote <= 0) {
                failed = wrote < 0 ? errno : ENOSPC;
                break;
            }
            at += static_cast<std::size_t>(wrote);
        }
#ifdef _WIN32
        if (_close(fd) != 0 && !failed) failed = errno;
#else
        if (::close(fd) != 0 && !failed) failed = errno;
#endif
        if (failed) {
            fs::remove_all(dir, ec);
            return "the copy could not be written in " + dir.u8string() + ": " + std::generic_category().message(failed);
        }
        out->dir = dir;
        out->path = file;
        return "";
    }
    return "the copy's folder could not be made in " + under.u8string() + ": 100 names were taken";
}

// The copy and its folder removed; "" when gone, else why not (never throws).
inline std::string removeCopy(Copy* c) {
    if (c->dir.empty()) return "";
    std::error_code ec;
    fs::remove_all(c->dir, ec);
    const std::string why = ec ? ec.message() : "";
    if (!ec) *c = Copy{};
    return why;
}

// What importlut does before the SDK is asked, in order: the place (16 alone), the file (check), then the camera's
// state read by `readCamera()` (called only once the place and the file pass), then the copy written under `copyUnder`.
// A refusal leaves `problem` and `cause` set and no copy; otherwise `copy.path` is the one path the SDK is given.
struct Plan {
    std::string problem, cause;
    long long place = 0;
    Checked file;
    bool stateRead = false;
    CameraState state;
    Copy copy;
};

template <class ReadCamera>
inline Plan plan(long long place, const fs::path& given, const std::string& expected, const fs::path& lutDir,
                 ReadCamera readCamera, const fs::path& copyUnder) {
    Plan p;
    p.place = place;
    if (const std::string why = placeProblem(place); !why.empty()) {
        p.problem = "not imported: " + why;
        p.cause = "refused";
        return p;
    }
    p.file = check(given, expected, lutDir);
    if (!p.file.problem.empty()) {
        p.problem = p.file.problem;
        p.cause = p.file.cause;
        return p;
    }
    p.state = readCamera();
    p.stateRead = true;
    if (const Refusal r = stateRefusal(p.state, place); !r.problem.empty()) {
        p.problem = r.problem;
        p.cause = r.cause;
        return p;
    }
    if (const std::string why = writeCopy(p.file, &p.copy, copyUnder); !why.empty()) {
        p.problem = "not imported: " + why;
        p.cause = "not_a_lut";
    }
    return p;
}

// The camera's answer judged, once importlut's wait has ended (`ended`), with the ImportLUTFile warning the camera
// sent, if any (`warning`, its name; `warningOk` whether it is ImportLUTFile_Result_OK), the wait's own words (`detail`)
// and how long it waited: a success only on the OK in a wait that ended well; an OK in a wait a dropped session ended,
// no answer, or a session that ended before any answer is "import_unconfirmed"; any other answer "import_refused".
// keepCopy: the import may still be reading the copy (no answer from the camera), so camlink keeps it until it exits.
struct Answer {
    bool ok = false;
    std::string cause, why;
    bool keepCopy = false;
};

inline Answer judge(CallbackWait::Ended ended, bool warningOk, const std::string& warning, const std::string& detail,
                    long long waitedSeconds) {
    const std::string look = " (look at Manage User LUTs on the camera)";
    if (ended == CallbackWait::Ended::ok && warningOk) return {true, "", "", false};
    if (ended == CallbackWait::Ended::timedOut)
        return {false, "import_unconfirmed", "no answer from the camera within " + std::to_string(waitedSeconds) +
                " s: whether the LUT went in is not known" + look, true};
    if (warningOk)
        return {false, "import_unconfirmed", "the camera reported ImportLUTFile_Result_OK, but its session ended as it "
                "answered (" + detail + "): whether the LUT went in is not known" + look, false};
    if (!warning.empty()) return {false, "import_refused", "not imported: the camera answered " + warning, false};
    return {false, "import_unconfirmed", "the camera's session ended while it imported (" + detail + "): whether the "
            "LUT went in is not known" + look, true};
}

}  // namespace lut_file
