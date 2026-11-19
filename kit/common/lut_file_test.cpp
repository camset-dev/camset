// lut_file_test: checks, with no camera and no SDK, everything camlink decides when it imports a user LUT
// (kit/common/lut_file.h, camlink's importlut, Sony's ImportLUTFile, docs/decisions/0026): the file (strictly under the
// clone's own LUT folder, never through a link, a regular file read once with the SHA-256 the command must name, its
// name as Sony's API reference allows it and ".cube" alone, less than 3 MB, text with a LUT size line), the place (16
// alone), the camera's state (the import enabled, not recording, the place not one the camera lists as holding a LUT,
// nor a list no reading explains), plan()'s order and the copy the SDK is given in place of the file, judge()'s reading
// of the camera's answer, and importlut's command line (kit/link/protocol.h). Files go into a folder of its own under
// the system's temporary folder (TMPDIR), removed at the end. kit/tests/test_lut_import.py builds and runs it:
//   c++ -std=c++17 -Wall -Wextra -I kit/common kit/common/lut_file_test.cpp -o /tmp/lut_file_test && /tmp/lut_file_test
#include "lut_file.h"
#include "sha256.h"
#include "../link/protocol.h"

#ifndef _WIN32
#include <sys/stat.h>            // mkfifo
#endif

#include <cctype>
#include <chrono>
#include <fstream>
#include <iostream>
#include <iterator>
#include <sstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

static int failures = 0;
#define CHECK(x) do { if (!(x)) { ++failures; std::cerr << __FILE__ << ":" << __LINE__ << ": not true: " #x "\n"; } } while (0)

static const std::string kCube = "#a test LUT\n\nTITLE \"test\"\nLUT_3D_SIZE 2\n\n0.0 0.0 0.0\n1.0 0.0 0.0\n"
                                 "0.0 1.0 0.0\n1.0 1.0 0.0\n0.0 0.0 1.0\n1.0 0.0 1.0\n0.0 1.0 1.0\n1.0 1.0 1.0\n";

static void write(const fs::path& p, const std::string& text) {
    fs::create_directories(p.parent_path());
    std::ofstream o(p, std::ios::binary);
    o << text;
}

static std::string text(const fs::path& p) {
    std::ifstream f(p, std::ios::binary);
    return std::string((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
}

// the name rules (Sony's API reference, ImportLUTFile, and the kit's ".cube" alone)
static void names() {
    CHECK(lut_file::nameProblem("1_test_look_to_709.cube").empty());
    CHECK(lut_file::nameProblem("a#$%&'()+,-.;=@[]^`{}~_ b.cube").empty());       // every sign the reference allows
    const std::string longest = std::string(63 - 5, 'a') + ".cube";               // 63 with its extension: taken
    CHECK(longest.size() == 63 && lut_file::nameProblem(longest).empty());
    CHECK(lut_file::nameProblem("a" + longest).find("63") != std::string::npos);  // 64: refused, the limit said
    for (const char* bad : {"x.cub", "x.CUBE", "x.Cube", "x.txt", "x.cube.txt", "x", ".cube", "cube", "x.cube ", ".x.cube",
                            "a*b.cube", "a:b.cube", "a\"b.cube", "a!b.cube", "a|b.cube", "a?b.cube", "a<b.cube",
                            "a\\b.cube", "a\tb.cube", "caf\xc3\xa9.cube", ""})
        CHECK(!lut_file::nameProblem(bad).empty());
    CHECK(lut_file::nameProblem(".x.cube").find("period") != std::string::npos);
    CHECK(lut_file::nameProblem("x.cub").find(".cube") != std::string::npos);
}

// user place 16 alone (decision 26)
static void places() {
    CHECK(lut_file::placeProblem(16).empty());
    for (long long p : {1LL, 15LL, 0LL, -1LL, 17LL, 256LL, 0x10000LL, 0xFFFFLL, 0x110LL})
        CHECK(lut_file::placeProblem(p).find("16") != std::string::npos);
}

// the camera's state, read before the SDK is asked: each refusal says what was read
static void states() {
    CHECK(lut_file::enableProblem(true, lut_file::kEnable).empty());
    CHECK(lut_file::enableProblem(true, 0).find("reads 0") != std::string::npos);
    CHECK(lut_file::enableProblem(true, 2).find("reads 2") != std::string::npos);
    CHECK(lut_file::enableProblem(false, 0).find("could not be read") != std::string::npos);
    CHECK(lut_file::recordingProblem(true, lut_file::kNotRecording).empty());
    for (long long v : {1LL, 2LL, 3LL}) CHECK(lut_file::recordingProblem(true, v).find("reads " + std::to_string(v)) != std::string::npos);
    CHECK(lut_file::recordingProblem(false, 0).find("could not be read") != std::string::npos);
    // DeleteUserBaseLook's list names every place there is, not the places that hold a LUT: the a1 II listed 1 to 16
    // and All with all sixteen empty (2026-11-19), so a listed place refuses nothing. A value no reading of the list
    // explains, or a list that cannot be read, still refuses
    std::vector<long long> every;
    for (long long p = 1; p <= 16; ++p) every.push_back(p);
    every.push_back(0xFFFF);
    CHECK(lut_file::listProblem(true, every).empty());                            // what the camera listed, all empty
    for (const std::vector<long long>& listed : std::vector<std::vector<long long>>{{}, {0}, {16}, {1, 2, 0xFFFF}, {0xFFFF}})
        CHECK(lut_file::listProblem(true, listed).empty());
    for (long long odd : {0x110LL, 0x8010LL, 17LL, -1LL, 0x10LL << 8, 0xFFFELL})                // none explained
        CHECK(lut_file::listProblem(true, {1, odd}).find("no reading of the list explains") != std::string::npos);
    CHECK(lut_file::listProblem(false, {}).find("could not be read") != std::string::npos);
    // all three, in order, and the cause each gives
    lut_file::CameraState s;
    s.enableRead = s.recordingRead = s.listRead = true;
    s.enable = 1;
    s.recording = 0;
    CHECK(lut_file::stateRefusal(s, 16).problem.empty());
    s.recording = 1;
    CHECK(lut_file::stateRefusal(s, 16).cause == "import_refused");
    s.recording = 0;
    s.listed = every;                                                             // every place listed: no refusal
    CHECK(lut_file::stateRefusal(s, 16).problem.empty());
    s.listed = {16, 0x110};
    CHECK(lut_file::stateRefusal(s, 16).cause == "import_refused");
    s.listRead = false;
    CHECK(lut_file::stateRefusal(s, 16).cause == "import_refused");
    s.listRead = true;
    s.listed = {};
    s.enable = 0;
    const lut_file::Refusal r = lut_file::stateRefusal(s, 16);
    CHECK(r.cause == "import_disabled" && r.problem.rfind("not imported: ", 0) == 0 && r.problem.find("reads 0") != std::string::npos);
}

// a .cube LUT's text: its size line, whatever the line ends, a byte order mark first, spaces before it
static void texts() {
    auto v = [](const std::string& s) { return std::vector<unsigned char>(s.begin(), s.end()); };
    CHECK(lut_file::cubeText(v(kCube)));
    CHECK(lut_file::cubeText(v("LUT_1D_SIZE 1024\r\n0 0 0\r\n")));
    CHECK(lut_file::cubeText(v("\xEF\xBB\xBF  \tLUT_3D_SIZE 33\n")));
    CHECK(lut_file::cubeText(v("# c\rLUT_3D_SIZE\t17\r")));
    CHECK(!lut_file::cubeText(v("TITLE x\n0 0 0\n")));                             // no size line
    CHECK(!lut_file::cubeText(v("TITLE LUT_3D_SIZE 2\n")));                      // the word inside another line
    CHECK(!lut_file::cubeText(v("LUT_3D_SIZE\n")));                               // no number after it
    CHECK(!lut_file::cubeText(v("LUT_3D_SIZEX 2\n")));
    std::string nul = kCube;
    nul[5] = '\0';
    CHECK(!lut_file::cubeText(v(nul)));                                           // a NUL: no text file
    CHECK(!lut_file::cubeText({}));
}

// the file: where it is (the clone's own LUT folder alone), what it is, read once, its SHA-256 the command's
static void files(const fs::path& top) {
    const fs::path lut = top / "clone" / "private" / "lut";
    const fs::path good = lut / "Look Pack" / "1_ok.cube";
    write(good, kCube);
    const std::string hash = sha256::hex(kCube);
    lut_file::Checked c = lut_file::check(good, hash, lut);
    CHECK(c.problem.empty() && c.cause.empty());
    CHECK(c.path == fs::canonical(good) && c.name == "1_ok.cube" && c.sha256 == hash && c.bytes == kCube.size());
    CHECK(std::string(c.data.begin(), c.data.end()) == kCube);
    std::string upper = hash;
    for (char& ch : upper) ch = static_cast<char>(std::toupper(static_cast<unsigned char>(ch)));
    CHECK(lut_file::check(good, upper, lut).problem.empty());                    // either case
    // the command must name the bytes' SHA-256: none named, nothing imported
    c = lut_file::check(good, "", lut);
    CHECK(c.cause == "refused" && c.problem.find("SHA-256") != std::string::npos && c.data.empty());
    CHECK(lut_file::check(lut / "2_top.cube", hash, lut).cause == "not_a_lut");  // not there
    write(lut / "2_top.cube", kCube);
    CHECK(lut_file::check(lut / "2_top.cube", hash, lut).problem.empty());       // right under the folder
    // another file's hash: the bytes read are not the ones the kit checked; nothing is imported
    c = lut_file::check(good, sha256::hex(std::string("other bytes")), lut);
    CHECK(c.cause == "hash_mismatch" && c.problem.rfind("not imported: ", 0) == 0 && c.problem.find(hash) != std::string::npos);
    // a folder named private/lut anywhere else, and every other place: refused, whatever the file
    for (const fs::path& away : {top / "other" / "private" / "lut" / "x.cube", top / "clone" / "x.cube",
                                 top / "clone" / "private" / "x.cube", top / "clone" / "lut" / "x.cube",
                                 top / "clone" / "private" / "lutx" / "x.cube", top / "lut" / "private" / "x.cube"}) {
        write(away, kCube);
        c = lut_file::check(away, hash, lut);
        CHECK(c.cause == "not_a_lut" && c.problem.find("clone's own LUT folder") != std::string::npos);
    }
    // the clone's folder missing, or camlink built without one: refused, saying so
    CHECK(lut_file::check(good, hash, top / "clone" / "private" / "no lut").problem.find("is not there") != std::string::npos);
    CHECK(lut_file::check(good, hash, fs::path()).problem.find("CAMSET_LUT_DIR") != std::string::npos);
    // a path that climbs out of the folder with ".." is judged where it ends
    CHECK(lut_file::check(lut / ".." / "x.cube", hash, lut).cause == "not_a_lut");
    // the name, read from the file itself
    for (const char* name : {"x.cub", "x.txt", "x.CUBE", ".hidden.cube", "a!b.cube"}) {
        write(lut / name, kCube);
        CHECK(lut_file::check(lut / name, hash, lut).cause == "not_a_lut");
    }
    // a link is never followed, into the folder or out of it, nor a folder that is a link out of it
    std::error_code ec;
    fs::create_symlink(top / "other" / "private" / "lut" / "x.cube", lut / "out.cube", ec);
    if (!ec) CHECK(lut_file::check(lut / "out.cube", hash, lut).problem.find("link") != std::string::npos);
    fs::create_symlink(good, lut / "in.cube", ec);
    if (!ec) CHECK(lut_file::check(lut / "in.cube", hash, lut).cause == "not_a_lut");
    fs::create_directory_symlink(top / "other" / "private" / "lut", lut / "pack", ec);
    if (!ec) CHECK(lut_file::check(lut / "pack" / "x.cube", hash, lut).problem.find("clone's own LUT folder") != std::string::npos);
    // a folder, a pipe: no file
    fs::create_directories(lut / "folder.cube");
    CHECK(lut_file::check(lut / "folder.cube", hash, lut).cause == "not_a_lut");
#ifndef _WIN32
    const fs::path pipe = lut / "pipe.cube";
    if (mkfifo(pipe.c_str(), 0600) == 0) CHECK(lut_file::check(pipe, hash, lut).cause == "not_a_lut");
#endif
    // the size: less than 3 MB (3,000,000 bytes), as the reference asks
    std::string big = kCube;
    big.resize(lut_file::kMaxBytes - 1, ' ');
    write(lut / "big_ok.cube", big);
    CHECK(lut_file::check(lut / "big_ok.cube", sha256::hex(big), lut).problem.empty());
    big.push_back(' ');
    write(lut / "too_big.cube", big);
    c = lut_file::check(lut / "too_big.cube", sha256::hex(big), lut);
    CHECK(c.cause == "not_a_lut" && c.problem.find("3000000") != std::string::npos);
    // not a .cube LUT's text: no size line, or binary
    write(lut / "words.cube", "only words, no size line\n");
    CHECK(lut_file::check(lut / "words.cube", sha256::hex(std::string("only words, no size line\n")), lut).cause == "not_a_lut");
    const std::string bin("LUT_3D_SIZE 2\n\0\0\0", 17);
    write(lut / "binary.cube", bin);
    CHECK(lut_file::check(lut / "binary.cube", sha256::hex(bin), lut).cause == "not_a_lut");
}

// plan(): the place, the file, then (only then) the camera's state, then the copy; the SDK gets the copy's path alone
static void plans(const fs::path& top) {
    const fs::path lut = top / "plan" / "private" / "lut";
    const fs::path pack = lut / "Look Pack";
    const fs::path given = pack / "1_ok.cube";
    write(given, kCube);
    const std::string hash = sha256::hex(kCube);
    const fs::path copies = top / "copies";
    fs::create_directories(copies);
    int asked = 0;
    lut_file::CameraState ready;
    ready.enableRead = ready.recordingRead = ready.listRead = true;
    ready.enable = 1;
    ready.recording = 0;
    for (long long n = 1; n <= 16; ++n) ready.listed.push_back(n);             // as the a1 II lists them, all empty
    ready.listed.push_back(0xFFFF);
    auto reading = [&](lut_file::CameraState s) {
        return [&asked, s]() { ++asked; return s; };
    };
    // a place or a file refused: the camera is not asked, and no copy is made
    lut_file::Plan p = lut_file::plan(15, given, hash, lut, reading(ready), copies);
    CHECK(p.cause == "refused" && asked == 0 && p.copy.path.empty());
    p = lut_file::plan(16, top / "other" / "private" / "lut" / "x.cube", hash, lut, reading(ready), copies);
    CHECK(p.cause == "not_a_lut" && asked == 0 && !p.stateRead);
    p = lut_file::plan(16, given, "", lut, reading(ready), copies);
    CHECK(p.cause == "refused" && asked == 0);
    // the camera's refusals: recording, a list no reading explains, the import not enabled; no copy
    lut_file::CameraState recording = ready, odd = ready, disabled = ready;
    recording.recording = 1;
    odd.listed = {16, 0x110};
    disabled.enable = 0;
    p = lut_file::plan(16, given, hash, lut, reading(recording), copies);
    CHECK(asked == 1 && p.stateRead && p.cause == "import_refused" && p.problem.find("RecordingState") != std::string::npos);
    p = lut_file::plan(16, given, hash, lut, reading(odd), copies);
    CHECK(p.cause == "import_refused" && p.problem.find("no reading of the list explains") != std::string::npos &&
          p.copy.path.empty());
    p = lut_file::plan(16, given, hash, lut, reading(disabled), copies);
    CHECK(p.cause == "import_disabled" && p.copy.path.empty());
    CHECK(fs::is_empty(copies));
    // everything passes: the copy, never the file given nor its real path, is what the SDK gets
    p = lut_file::plan(16, given, hash, lut, reading(ready), copies);
    CHECK(p.problem.empty() && p.place == 16 && asked == 4);
    CHECK(!p.copy.path.empty() && p.copy.path != given && p.copy.path != fs::canonical(given));
    CHECK(p.copy.path.filename() == "1_ok.cube" && p.copy.path.parent_path() == p.copy.dir);
    CHECK(p.copy.dir.parent_path() == copies && p.copy.dir.filename().string().rfind(lut_file::kCopyPrefix, 0) == 0);
    CHECK(text(p.copy.path) == kCube);
#ifndef _WIN32
    CHECK((fs::status(p.copy.dir).permissions() & fs::perms::all) == fs::perms::owner_all);
    CHECK((fs::status(p.copy.path).permissions() & fs::perms::all) == (fs::perms::owner_read | fs::perms::owner_write));
#endif
    // the SDK opens its path only later: an editor's save renamed over the file, then its folder swapped for a link to
    // other bytes, after the check, change nothing it reads
    write(pack / "saved.tmp", "#written after the check\nLUT_3D_SIZE 2\n");
    fs::rename(pack / "saved.tmp", given);
    CHECK(text(given) != kCube && text(p.copy.path) == kCube);
    std::error_code ec;
    fs::rename(pack, lut / "moved", ec);
    fs::create_directory_symlink(top / "other" / "private" / "lut", pack, ec);
    CHECK(text(p.copy.path) == kCube);
    // a second plan gets a folder of its own; the copy goes with removeCopy
    lut_file::Plan q = lut_file::plan(16, lut / "moved" / "1_ok.cube", sha256::hex(text(lut / "moved" / "1_ok.cube")), lut,
                                      reading(ready), copies);
    CHECK(q.problem.empty() && q.copy.dir != p.copy.dir);
    const fs::path dir = p.copy.dir;
    CHECK(lut_file::removeCopy(&p.copy).empty() && !fs::exists(dir) && p.copy.dir.empty());
    CHECK(lut_file::removeCopy(&p.copy).empty());                                // twice: nothing left to remove
    lut_file::removeCopy(&q.copy);
    CHECK(fs::is_empty(copies));
    // a folder it cannot make the copy in: refused in words, and nothing to remove
    p = lut_file::plan(16, lut / "moved" / "1_ok.cube", sha256::hex(text(lut / "moved" / "1_ok.cube")), lut, reading(ready),
                       top / "no such folder");
    CHECK(p.cause == "not_a_lut" && p.problem.find("copy") != std::string::npos && p.copy.dir.empty());
}

// judge(): only the camera's OK, in a wait that ended well, is an import
static void answers() {
    using E = CallbackWait::Ended;
    lut_file::Answer a = lut_file::judge(E::ok, true, "ImportLUTFile_Result_OK", "", 120);
    CHECK(a.ok && a.cause.empty() && !a.keepCopy);
    a = lut_file::judge(E::timedOut, false, "", "importlut timed out", 120);
    CHECK(!a.ok && a.cause == "import_unconfirmed" && a.keepCopy && a.why.find("120 s") != std::string::npos);
    // LOW 2: the camera's OK as its session dropped (the wait ended by the disconnect first): not known, said so
    a = lut_file::judge(E::failed, true, "ImportLUTFile_Result_OK", "disconnected", 120);
    CHECK(!a.ok && a.cause == "import_unconfirmed" && a.why.find("reported ImportLUTFile_Result_OK") != std::string::npos);
    a = lut_file::judge(E::failed, false, "ImportLUTFile_Result_DeviceBusy", "ImportLUTFile_Result_DeviceBusy", 120);
    CHECK(!a.ok && a.cause == "import_refused" && a.why.find("DeviceBusy") != std::string::npos && !a.keepCopy);
    a = lut_file::judge(E::failed, false, "", "disconnected", 120);
    CHECK(!a.ok && a.cause == "import_unconfirmed" && a.keepCopy && a.why.find("disconnected") != std::string::npos);
    a = lut_file::judge(E::ok, false, "", "", 120);                               // a good end with no OK: never a success
    CHECK(!a.ok && a.cause == "import_unconfirmed");
}

// importlut's command line: PATH PLACE SHA256, the path quoted when it holds a space, the SHA-256 required
static void command_lines() {
    auto args = [](const std::string& line, std::string* place, std::string* hash) {
        std::istringstream in(line);
        return protocol::lutArgs(in, *place, *hash);
    };
    const std::string h(64, 'a');
    std::string place, hash;
    CHECK(args("\"/a b/private/lut/x y.cube\" 16 " + h, &place, &hash) == "/a b/private/lut/x y.cube" && place == "16" &&
          hash == h);
    CHECK(args("/c/private/lut/x.cube 16 " + h, &place, &hash) == "/c/private/lut/x.cube" && hash == h);
    const std::vector<std::string> bad_lines = {"", "\"/a b/x.cube\"", "\"/a b/x.cube\" 16", "/c/private/lut/x.cube 16",
                                                "\"/a b/x.cube\" 16 now", "\"/a b/x.cube\" 16 " + h + " more",
                                                "\"/a b/x.cube 16", "\"/a b/x.cube\" 16 " + h.substr(1)};
    for (const std::string& bad : bad_lines) {
        bool threw = false;
        try {
            args(bad, &place, &hash);
        } catch (const std::exception&) {
            threw = true;
        }
        CHECK(threw);
    }
}

int main() {
    const fs::path top = fs::temp_directory_path() /
                         ("lut_file_test_" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    fs::create_directories(top);
    names();
    places();
    states();
    texts();
    files(top);
    plans(top);
    answers();
    command_lines();
    std::error_code ec;
    fs::remove_all(top, ec);
    if (failures) std::cerr << failures << " check(s) failed\n";
    else std::cout << "lut file: all checks passed\n";
    return failures ? 1 : 0;
}
