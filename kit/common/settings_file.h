// settings_file.h: whether a file is a camera settings file, checked before camlink (kit/link) or the editor's camera
// helper (kit/probe) sends it with upload. The check needs no fact of one body (docs/decisions/0020), only the
// vocabulary the kit and the editor read every container block with (kit/camkit/camset.py, editor/src/camset.rs):
// after a header, sections of a u32 record count and records framed as u16 id, u16 marker, u16 element size, u16
// element count and the value bytes, little-endian, with one marker throughout, running up to a u32 byte sum of
// those bytes in the file's last four bytes. The header's length is not given but found: the first, within the first
// 256 bytes, from which the records frame exactly and the sum holds. A picture, a text, a cut-off or damaged file
// fails. kit/common/guards_test.cpp checks it with the a1 II definition's sample.
//
// What camlink uploads is read once (toSend): the bytes checked, as a settings file and against the SHA-256 the kit
// checked the file by (kit/camkit/link.py, Link.upload: the hash of one of the camera's own downloads), are the bytes
// sent, from a copy camlink writes itself (writeCopy), since the SDK uploads from a path. A file swapped in after the
// kit's check is never sent: "hash_mismatch".
#pragma once

#include "sha256.h"

#include <cctype>
#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <system_error>
#include <vector>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#include <process.h>
#include <share.h>
#include <sys/types.h>
#include <sys/stat.h>
#else
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace settings_file {

constexpr std::size_t kMinBytes = 64, kMaxBytes = 16u << 20, kMaxHeader = 256;

inline uint32_t u32(const std::vector<unsigned char>& d, std::size_t at) {
    return static_cast<uint32_t>(d[at]) | static_cast<uint32_t>(d[at + 1]) << 8 | static_cast<uint32_t>(d[at + 2]) << 16 |
           static_cast<uint32_t>(d[at + 3]) << 24;
}
inline unsigned u16(const std::vector<unsigned char>& d, std::size_t at) {
    return static_cast<unsigned>(d[at]) | static_cast<unsigned>(d[at + 1]) << 8;
}

// Whether the records frame exactly from `start` up to `end` with one marker, at least one record in all.
inline bool frames(const std::vector<unsigned char>& d, std::size_t start, std::size_t end) {
    std::size_t off = start, records = 0;
    long marker = -1;
    while (off < end) {
        if (end - off < 4) return false;
        const uint32_t n = u32(d, off);
        off += 4;
        if (n > (end - off) / 8) return false;
        for (uint32_t k = 0; k < n; ++k) {
            if (end - off < 8) return false;
            const unsigned m = u16(d, off + 2);
            if (marker < 0) marker = static_cast<long>(m);
            if (static_cast<long>(m) != marker) return false;
            const std::size_t len = static_cast<std::size_t>(u16(d, off + 4)) * u16(d, off + 6);
            if (len > end - off - 8) return false;
            off += 8 + len;
            ++records;
        }
    }
    return off == end && records > 0;
}

// "" when the bytes are a settings file, else why not, in plain words.
inline std::string problem(const std::vector<unsigned char>& d) {
    if (d.size() < kMinBytes) return "it is too short to be a camera settings file";
    if (d.size() > kMaxBytes) return "it is too large to be a camera settings file";
    const std::size_t end = d.size() - 4;
    const uint32_t stored = u32(d, end);
    uint32_t sum = 0;
    for (std::size_t k = kMaxHeader < end ? kMaxHeader : end; k < end; ++k) sum += d[k];   // the sum past any header
    for (std::size_t start = kMaxHeader < end ? kMaxHeader : end; start-- > 4;) {
        sum += d[start];                                                                   // the sum from `start`
        if (sum == stored && frames(d, start, end)) return "";
    }
    return "it is not a camera settings file: its records do not frame up to a checksum that holds";
}

// The file's bytes into *d, read once; "" when read, else why not. Only a regular file is read: a folder, a device or
// a pipe is "not a file", and so is one put in its place after that check (what was opened is asked again, and the
// open does not wait for a pipe's writer). At most kMaxBytes are read: the size is asked first, so a large file named
// by mistake (a video) is refused without being read into memory, and one that grows while it is read is refused at
// the cap.
inline std::string read(const std::filesystem::path& p, std::vector<unsigned char>* d) {
    d->clear();
    std::error_code ec;
    const std::filesystem::file_status kind = std::filesystem::status(p, ec);
    if (ec || !std::filesystem::exists(kind)) return "it cannot be read";
    if (!std::filesystem::is_regular_file(kind)) return "it is not a file";
    const std::uintmax_t size = std::filesystem::file_size(p, ec);
    if (!ec && size > kMaxBytes) return "it is too large to be a camera settings file";
#ifdef _WIN32
    int fd = -1;
    if (_wsopen_s(&fd, p.c_str(), _O_RDONLY | _O_BINARY | _O_NOINHERIT, _SH_DENYWR, 0) != 0) return "it cannot be read";
    struct _stat64 opened;
    const bool regular = _fstat64(fd, &opened) == 0 && (opened.st_mode & _S_IFMT) == _S_IFREG;
#else
    const int fd = ::open(p.c_str(), O_RDONLY | O_CLOEXEC | O_NONBLOCK);
    if (fd < 0) return "it cannot be read";
    struct stat opened;
    const bool regular = ::fstat(fd, &opened) == 0 && S_ISREG(opened.st_mode);
#endif
    std::string why = regular ? "" : "it is not a file";
    unsigned char chunk[1 << 16];
    while (why.empty()) {
#ifdef _WIN32
        const long long got = _read(fd, chunk, static_cast<unsigned>(sizeof chunk));
#else
        const long long got = ::read(fd, chunk, sizeof chunk);
        if (got < 0 && errno == EINTR) continue;                 // a signal (camlink's handler) is no failure
#endif
        if (got == 0) break;
        if (got < 0) {
            why = "it cannot be read";
        } else {
            d->insert(d->end(), chunk, chunk + got);
            if (d->size() > kMaxBytes) why = "it is too large to be a camera settings file";
        }
    }
#ifdef _WIN32
    _close(fd);
#else
    ::close(fd);
#endif
    if (!why.empty()) d->clear();
    return why;
}

// The file read and checked; "" when it is a settings file.
inline std::string problemOfFile(const std::filesystem::path& p) {
    std::vector<unsigned char> d;
    const std::string unread = read(p, &d);
    return unread.empty() ? problem(d) : unread;
}

// What an upload sends, read once: the bytes, their SHA-256, and when they may not go, why not (`problem`, plain words
// that start "not sent: ") with the token camlink's reply carries (`cause`): "hash_mismatch" when the bytes are not
// the ones whose SHA-256 the caller gave (the kit gives the hash of the camera download it checked; either case),
// "not_a_settings_file" when they are no settings file (problem above), none when the file cannot be read. An empty
// `expected` (an upload typed by hand) checks no hash.
struct ToSend {
    std::vector<unsigned char> bytes;
    std::string sha256, problem, cause;
};

inline ToSend toSend(const std::filesystem::path& p, const std::string& expected) {
    ToSend s;
    if (const std::string unread = read(p, &s.bytes); !unread.empty()) {
        s.problem = "not sent: " + unread;
        return s;
    }
    s.sha256 = sha256::hex(s.bytes);
    std::string want = expected;
    for (char& c : want) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    if (!want.empty() && want != s.sha256) {
        s.problem = "not sent: these are not the bytes whose SHA-256 the upload named (theirs is " + s.sha256 + ", not " +
                    want + "): the file was written after it was checked";
        s.cause = "hash_mismatch";
    } else if (const std::string bad = problem(s.bytes); !bad.empty()) {
        s.problem = "not sent: " + bad;
        s.cause = "not_a_settings_file";
    }
    return s;
}

// The bytes in a new file of camlink's own beside `beside`, in its folder: "<prefix>_<process id>.DAT", or with "_<n>"
// before ".DAT" when that name is taken (the SDK uploads from a path, and the extension must be DAT). It is created
// exclusively, so it is never an existing file or a link, readable and writable by this user alone (0600; on Windows
// the folder's permissions). "" with the file in *out, else why not; the caller removes it once the SDK is done. One
// left by a crash is passed over by the kit's download pickers, which skip camlink's prefix ("_camlink_upload").
inline std::string writeCopy(const std::filesystem::path& beside, const std::vector<unsigned char>& bytes,
                             const std::string& prefix, std::filesystem::path* out) {
    std::error_code ec;
    const std::filesystem::path abs = std::filesystem::absolute(beside, ec);
    const std::filesystem::path dir = (ec ? beside : abs).parent_path();
#ifdef _WIN32
    const int pid = _getpid();
#else
    const long pid = static_cast<long>(getpid());
#endif
    for (int n = 0; n < 100; ++n) {
        const std::filesystem::path p =
            dir / (prefix + "_" + std::to_string(pid) + (n ? "_" + std::to_string(n) : std::string()) + ".DAT");
        int err = 0;
#ifdef _WIN32
        int fd = -1;
        err = _wsopen_s(&fd, p.c_str(), _O_WRONLY | _O_CREAT | _O_EXCL | _O_BINARY | _O_NOINHERIT, _SH_DENYRW,
                        _S_IREAD | _S_IWRITE);
#else
        const int fd = ::open(p.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, S_IRUSR | S_IWUSR);
        if (fd < 0) err = errno;
#endif
        if (err == EEXIST) continue;
        if (err) return "the copy to send could not be made in " + dir.u8string() + ": " + std::generic_category().message(err);
        std::size_t at = 0;
        int failed = 0;
        while (at < bytes.size()) {
            const std::size_t left = bytes.size() - at, chunk = left > (1u << 30) ? (1u << 30) : left;
#ifdef _WIN32
            const long long wrote = _write(fd, bytes.data() + at, static_cast<unsigned>(chunk));
#else
            const long long wrote = ::write(fd, bytes.data() + at, chunk);
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
            std::filesystem::remove(p, ec);
            return "the copy to send could not be written in " + dir.u8string() + ": " + std::generic_category().message(failed);
        }
        *out = p;
        return "";
    }
    return "the copy to send could not be made in " + dir.u8string() + ": 100 names were taken";
}

}  // namespace settings_file
