// lut_file_test: checks, with no camera and no SDK, every refusal camlink makes before it imports a user LUT
// (kit/common/lut_file.h, camlink's importlut, Sony's ImportLUTFile): the file (under a folder private/lut/, never
// through a link, a regular file read once with the SHA-256 the kit gave, its name as Sony's API reference allows it and
// ".cube" alone, less than 3 MB, text with a LUT size line), the place (a user place, 1-16), the camera's state (the
// import enabled, not recording, the place not one the camera lists as holding a LUT), and importlut's command line
// (kit/link/protocol.h). Files go into a folder of its own under the system's temporary folder (TMPDIR), removed at
// the end. kit/tests/test_lut_import.py builds and runs it:
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

static void places() {
    for (long long p : {1LL, 2LL, 15LL, 16LL}) CHECK(lut_file::placeProblem(p).empty());
    for (long long p : {0LL, -1LL, 17LL, 256LL, 0x10000LL, 0xFFFFLL}) CHECK(!lut_file::placeProblem(p).empty());
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
    // the places the camera lists as user LUTs it can delete: the place among them, or "All" with no place by number,
    // or a list that cannot be read, refuses; a list without the place (none at all, others) does not
    CHECK(lut_file::placeHeld(true, {}, 16).empty());
    CHECK(lut_file::placeHeld(true, {0}, 16).empty());                            // Invalid alone: nothing to delete
    CHECK(lut_file::placeHeld(true, {1, 2, 0xFFFF}, 16).empty());
    CHECK(lut_file::placeHeld(true, {16}, 16).find("16") != std::string::npos);
    CHECK(!lut_file::placeHeld(true, {3, 16, 0xFFFF}, 16).empty());
    CHECK(lut_file::placeHeld(true, {0xFFFF}, 16).find("All") != std::string::npos);
    CHECK(lut_file::placeHeld(false, {}, 16).find("could not be read") != std::string::npos);
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

// the file: where it is, what it is, read once, its SHA-256 the kit's
static void files(const fs::path& top) {
    const fs::path lut = top / "clone" / "private" / "lut";
    const fs::path good = lut / "Sony Pack" / "1_ok.cube";
    write(good, kCube);
    const std::string hash = sha256::hex(kCube);
    lut_file::Checked c = lut_file::check(good, hash);
    CHECK(c.problem.empty() && c.cause.empty());
    CHECK(c.path == fs::canonical(good) && c.name == "1_ok.cube" && c.sha256 == hash && c.bytes == kCube.size());
    std::string upper = hash;
    for (char& ch : upper) ch = static_cast<char>(std::toupper(static_cast<unsigned char>(ch)));
    CHECK(lut_file::check(good, upper).problem.empty());                         // either case
    CHECK(lut_file::check(good, "").problem.empty());                            // typed by hand: no hash given, none checked
    CHECK(lut_file::check(lut / "2_top.cube", "").cause == "not_a_lut");         // not there
    write(lut / "2_top.cube", kCube);
    CHECK(lut_file::check(lut / "2_top.cube", hash).problem.empty());            // right under private/lut/
    // another file's hash: the bytes read are not the ones the kit checked; nothing is imported
    c = lut_file::check(good, sha256::hex(std::string("other bytes")));
    CHECK(c.cause == "hash_mismatch" && c.problem.rfind("not imported: ", 0) == 0 && c.problem.find(hash) != std::string::npos);
    // anywhere but under a folder private/lut/: refused, whatever the file
    for (const fs::path& away : {top / "clone" / "x.cube", top / "clone" / "private" / "x.cube", top / "clone" / "lut" / "x.cube",
                                 top / "clone" / "private" / "lutx" / "x.cube", top / "clone" / "privatelut" / "x.cube",
                                 top / "lut" / "private" / "x.cube"}) {
        write(away, kCube);
        c = lut_file::check(away, sha256::hex(kCube));
        CHECK(c.cause == "not_a_lut" && c.problem.find("private/lut") != std::string::npos);
    }
    // a path that climbs out of private/lut/ with ".." is judged where it ends
    CHECK(lut_file::check(lut / ".." / "x.cube", hash).cause == "not_a_lut");
    // the name, read from the file itself
    for (const char* name : {"x.cub", "x.txt", "x.CUBE", ".hidden.cube", "a!b.cube"}) {
        write(lut / name, kCube);
        CHECK(lut_file::check(lut / name, hash).cause == "not_a_lut");
    }
    // a link is never followed, into private/lut/ or out of it
    std::error_code ec;
    fs::create_symlink(top / "clone" / "x.cube", lut / "out.cube", ec);
    if (!ec) CHECK(lut_file::check(lut / "out.cube", hash).problem.find("link") != std::string::npos);
    fs::create_symlink(good, lut / "in.cube", ec);
    if (!ec) CHECK(lut_file::check(lut / "in.cube", hash).cause == "not_a_lut");
    // a folder, a pipe: no file
    fs::create_directories(lut / "folder.cube");
    CHECK(lut_file::check(lut / "folder.cube", "").cause == "not_a_lut");
#ifndef _WIN32
    const fs::path pipe = lut / "pipe.cube";
    if (mkfifo(pipe.c_str(), 0600) == 0) CHECK(lut_file::check(pipe, "").cause == "not_a_lut");
#endif
    // the size: less than 3 MB (3,000,000 bytes), as the reference asks
    std::string big = kCube;
    big.resize(lut_file::kMaxBytes - 1, ' ');
    write(lut / "big_ok.cube", big);
    CHECK(lut_file::check(lut / "big_ok.cube", sha256::hex(big)).problem.empty());
    big.push_back(' ');
    write(lut / "too_big.cube", big);
    c = lut_file::check(lut / "too_big.cube", "");
    CHECK(c.cause == "not_a_lut" && c.problem.find("3000000") != std::string::npos);
    // not a .cube LUT's text: no size line, or binary
    write(lut / "words.cube", "only words, no size line\n");
    CHECK(lut_file::check(lut / "words.cube", "").cause == "not_a_lut");
    write(lut / "binary.cube", std::string("LUT_3D_SIZE 2\n\0\0\0", 17));
    CHECK(lut_file::check(lut / "binary.cube", "").cause == "not_a_lut");
}

// importlut's command line: PATH PLACE [SHA256], the path quoted when it holds a space
static void command_lines() {
    auto args = [](const std::string& line, std::string* place, std::string* hash) {
        std::istringstream in(line);
        return protocol::lutArgs(in, *place, *hash);
    };
    const std::string h(64, 'a');
    std::string place, hash;
    CHECK(args("\"/a b/private/lut/x y.cube\" 16 " + h, &place, &hash) == "/a b/private/lut/x y.cube" && place == "16" &&
          hash == h);
    CHECK(args("/c/private/lut/x.cube 1", &place, &hash) == "/c/private/lut/x.cube" && place == "1" && hash.empty());
    const std::vector<std::string> bad_lines = {"", "\"/a b/x.cube\"", "\"/a b/x.cube\" 16 now",
                                                "\"/a b/x.cube\" 16 " + h + " more", "\"/a b/x.cube 16",
                                                "\"/a b/x.cube\" 16 " + h.substr(1)};
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
    command_lines();
    std::error_code ec;
    fs::remove_all(top, ec);
    if (failures) std::cerr << failures << " check(s) failed\n";
    else std::cout << "lut file: all checks passed\n";
    return failures ? 1 : 0;
}
