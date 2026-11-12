// sha256.h: SHA-256 (FIPS 180-4), written out here so the camera helpers need no library for it. camlink checks the
// bytes of a settings file it is about to upload against the hash the kit checked the file by (kit/camkit/link.py,
// Link.upload: the hash of one of the camera's own downloads), so a file swapped in after the kit's check is never
// sent (kit/common/settings_file.h, toSend). kit/common/guards_test.cpp checks it against the standard's test
// vectors and against Python's hashlib at the block boundaries.
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace sha256 {

inline uint32_t rotr(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }

// One 64-byte block into the state.
inline void block(std::array<uint32_t, 8>& state, const unsigned char* p) {
    static const uint32_t k[64] = {
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
    uint32_t w[64];
    for (std::size_t t = 0; t < 16; ++t)
        w[t] = static_cast<uint32_t>(p[4 * t]) << 24 | static_cast<uint32_t>(p[4 * t + 1]) << 16 |
               static_cast<uint32_t>(p[4 * t + 2]) << 8 | static_cast<uint32_t>(p[4 * t + 3]);
    for (std::size_t t = 16; t < 64; ++t) {
        const uint32_t s0 = rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >> 3);
        const uint32_t s1 = rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >> 10);
        w[t] = w[t - 16] + s0 + w[t - 7] + s1;
    }
    uint32_t a = state[0], b = state[1], c = state[2], d = state[3], e = state[4], f = state[5], g = state[6], h = state[7];
    for (std::size_t t = 0; t < 64; ++t) {
        const uint32_t t1 = h + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + k[t] + w[t];
        const uint32_t t2 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
        h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    state[0] += a; state[1] += b; state[2] += c; state[3] += d; state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}

// The SHA-256 of n bytes as 64 lowercase hex digits, as Python's hashlib.sha256(...).hexdigest() writes it.
inline std::string hex(const unsigned char* data, std::size_t n) {
    std::array<uint32_t, 8> state = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    std::size_t done = 0;
    for (; n - done >= 64; done += 64) block(state, data + done);
    // the last bytes, the 1 bit after them, and the message's length in bits: one block, or two when they do not fit
    unsigned char tail[128] = {};
    const std::size_t left = n - done;
    for (std::size_t k = 0; k < left; ++k) tail[k] = data[done + k];
    tail[left] = 0x80;
    const std::size_t end = left < 56 ? 64 : 128;
    const uint64_t bits = static_cast<uint64_t>(n) * 8;
    for (std::size_t k = 0; k < 8; ++k) tail[end - 1 - k] = static_cast<unsigned char>(bits >> (8 * k));
    block(state, tail);
    if (end == 128) block(state, tail + 64);
    static const char digits[] = "0123456789abcdef";
    std::string out;
    for (const uint32_t v : state)
        for (int s = 28; s >= 0; s -= 4) out.push_back(digits[(v >> s) & 0xF]);
    return out;
}

inline std::string hex(const std::vector<unsigned char>& d) { return hex(d.data(), d.size()); }
inline std::string hex(const std::string& s) { return hex(reinterpret_cast<const unsigned char*>(s.data()), s.size()); }

}  // namespace sha256
