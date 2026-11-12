// camlink's command lines, kept apart so they can be tested without the SDK (kit/tests/test_link_protocol.py
// compiles this file with a small main and feeds it lines).
//
// One command per line. A trailing "\r" is dropped: on Windows a text pipe writes "\r\n". Arguments are words
// separated by spaces, or "quoted" with \" and \\ inside: the kit quotes every path and text it sends (camkit/link.py
// quoted), so a folder with a space in its name ("C:\Users\First Last\camset") and a Windows path's backslashes
// arrive whole. The last argument of osd, download, upload and setstr may also be the plain rest of the line, as
// before quoting (a path typed by hand); upload's path may be followed by a SHA-256 (pathAndHash). A line may start
// with "@N", the request's id, which the reply echoes.
#pragma once

#include <cstddef>
#include <istream>
#include <stdexcept>
#include <string>

namespace protocol {

// The next command line, without its line end; false at the end of input.
inline bool readLine(std::istream& in, std::string& line) {
    if (!std::getline(in, line)) return false;
    if (!line.empty() && line.back() == '\r') line.pop_back();
    return true;
}

// The command's word, into `cmd`, and the request's id, returned: a line may start with "@N" (N digits), which the
// reply echoes as "id": N, so the kit matches each reply to its command even past a stray line on stdout (the kit
// sends one with every command; a line typed by hand needs none). "" when the line has no id. The id comes back
// without leading zeros ("@007" is 7), since the reply carries it as a JSON number, where 007 is no number.
inline std::string command(std::istream& in, std::string& cmd) {
    cmd.clear();
    in >> cmd;
    if (cmd.size() < 2 || cmd[0] != '@' || cmd.size() > 19) return "";
    for (std::size_t k = 1; k < cmd.size(); ++k)
        if (cmd[k] < '0' || cmd[k] > '9') return "";
    std::string id = cmd.substr(1);
    const std::size_t digit = id.find_first_not_of('0');
    id.erase(0, digit == std::string::npos ? id.size() - 1 : digit);
    cmd.clear();
    in >> cmd;
    return id;
}

// One argument: a word, or a quoted string (\" and \\ inside; any other backslash is kept). False when none is left.
inline bool word(std::istream& in, std::string& out) {
    using Traits = std::char_traits<char>;
    out.clear();
    in >> std::ws;
    if (in.peek() != '"') return static_cast<bool>(in >> out);
    in.get();
    for (Traits::int_type c = in.get(); !Traits::eq_int_type(c, Traits::eof()); c = in.get()) {
        if (c == '"') return true;
        if (c == '\\') {
            const Traits::int_type d = in.get();
            if (Traits::eq_int_type(d, Traits::eof())) break;
            if (d != '"' && d != '\\') out.push_back('\\');
            c = d;
        }
        out.push_back(Traits::to_char_type(c));
    }
    throw std::runtime_error("a quoted argument has no closing quote");
}

// The last argument: a quoted string (nothing may follow it), or the rest of the line, trimmed.
inline std::string rest(std::istream& in) {
    std::string out;
    in >> std::ws;
    if (in.peek() == '"') {
        word(in, out);
        std::string extra;
        if (in >> extra) throw std::runtime_error("text after the quoted argument: " + extra);
        return out;
    }
    std::getline(in, out);
    while (!out.empty() && (out.back() == ' ' || out.back() == '\t')) out.pop_back();
    return out;
}

// Whether a word is a SHA-256 written as hex: 64 hex digits, either case.
inline bool isSha256(const std::string& s) {
    if (s.size() != 64) return false;
    for (const char c : s)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'))) return false;
    return true;
}

// upload's arguments, PATH [SHA256]: the path, returned, and into `hash` the SHA-256 the caller checked the file's
// bytes by ("" when none is given), which camlink checks the bytes it reads against (kit/common/settings_file.h). A
// quoted PATH may be followed by the hash and nothing else, and a word there that is no hash is refused; a PATH typed
// without quotes is the rest of the line, and its last word is the hash when it is 64 hex digits.
inline std::string pathAndHash(std::istream& in, std::string& hash) {
    hash.clear();
    in >> std::ws;
    if (in.peek() == '"') {
        std::string path, h, extra;
        word(in, path);
        if (in >> h) {
            if (!isSha256(h)) throw std::runtime_error("not a SHA-256 (64 hex digits) after the path: " + h);
            if (in >> extra) throw std::runtime_error("text after the SHA-256: " + extra);
            hash = h;
        }
        return path;
    }
    std::string line = rest(in);
    const std::size_t gap = line.find_last_of(" \t");
    if (gap != std::string::npos && isSha256(line.substr(gap + 1))) {
        hash = line.substr(gap + 1);
        line.erase(gap);
        while (!line.empty() && (line.back() == ' ' || line.back() == '\t')) line.pop_back();
    }
    return line;
}

}  // namespace protocol
