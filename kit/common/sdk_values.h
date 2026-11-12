// sdk_values.h: a camera property's values as numbers, read the same way by camlink (kit/link) and the editor's camera
// helper (kit/probe). The SDK keeps a property's current value as a raw u64 (GetCurrentValue) and its value lists as
// packed bytes; a signed type's value is sign-extended from its width. The type is the SDK's CrDataType (CrDefines.h):
// the width in its low four bits (1 one byte, 2 two, 3 four, 4 eight), 0x1000 the sign bit, 0x4000 a range
// [min, max, step]. current() is a template on the property, so this file needs none of the SDK's headers;
// kit/common/guards_test.cpp checks it on a stand-in property. parse() reads a value as a command gives it.
#pragma once

#include <charconv>
#include <cstdint>
#include <cstring>
#include <string>
#include <system_error>

namespace sdk_values {

constexpr unsigned kSignBit = 0x1000;
constexpr unsigned kRangeBit = 0x4000;

// The width in bytes of one value of the type; 0 for a text or an unknown type.
inline int width(unsigned type) {
    switch (type & 0x000F) {
        case 1: return 1;
        case 2: return 2;
        case 3: return 4;
        case 4: return 8;
        default: return 0;
    }
}

// One value of the type at p (little-endian, as the SDK packs them), sign-extended for a signed type.
inline long long at(const unsigned char* p, unsigned type) {
    const bool sign = (type & kSignBit) != 0;
    switch (width(type)) {
        case 1: return sign ? static_cast<long long>(static_cast<int8_t>(p[0])) : static_cast<long long>(p[0]);
        case 2: { uint16_t v; std::memcpy(&v, p, 2); return sign ? static_cast<long long>(static_cast<int16_t>(v)) : static_cast<long long>(v); }
        case 4: { uint32_t v; std::memcpy(&v, p, 4); return sign ? static_cast<long long>(static_cast<int32_t>(v)) : static_cast<long long>(v); }
        case 8: { int64_t v; std::memcpy(&v, p, 8); return static_cast<long long>(v); }
        default: return 0;
    }
}

// A property's current value (GetCurrentValue, a raw u64) as its type reads it: -3 for an Int8 that holds 0xFD, where
// the raw value is 253. A value compared or printed without this never matches a negative one.
template <class Property>
inline long long current(const Property& p) {
    const uint64_t raw = static_cast<uint64_t>(p.GetCurrentValue());
    unsigned char b[8];
    std::memcpy(b, &raw, sizeof b);
    return at(b, static_cast<unsigned>(p.GetValueType()));
}

// A number as a command gives it (a value to set, a hold in ms, a dial's steps): decimal, or hexadecimal after "0x",
// with an optional sign; a leading 0 is still decimal ("08" is 8, where std::stoll's octal read 0). False for an empty
// text, text after the number ("12abc", "1e3", which stoll read as 12 and 1) or a number past a long long, so a typo
// never sends another value than the one meant.
inline bool parse(const std::string& text, long long* out) {
    std::size_t i = 0;
    const bool negative = !text.empty() && text[0] == '-';
    if (!text.empty() && (text[0] == '-' || text[0] == '+')) ++i;
    int base = 10;
    if (text.size() - i > 2 && text[i] == '0' && (text[i + 1] == 'x' || text[i + 1] == 'X')) {
        base = 16;
        i += 2;
    }
    const char* first = text.data() + i;
    const char* last = text.data() + text.size();
    if (first == last || *first == '+' || *first == '-') return false;
    unsigned long long magnitude = 0;
    const std::from_chars_result r = std::from_chars(first, last, magnitude, base);
    if (r.ec != std::errc() || r.ptr != last) return false;
    constexpr unsigned long long kMax = 9223372036854775807ull;   // LLONG_MAX; one more for a negative number
    if (magnitude > kMax + (negative ? 1 : 0)) return false;
    if (negative) *out = magnitude == kMax + 1 ? -static_cast<long long>(kMax) - 1 : -static_cast<long long>(magnitude);
    else *out = static_cast<long long>(magnitude);
    return true;
}

}  // namespace sdk_values
