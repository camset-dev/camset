// remote.h: the buttons and dials camlink (kit/link) and the editor's camera helper (kit/probe) press through the SDK,
// by the codes CrDeviceProperty.h gives them (CrCameraButtonFunction_*, CrCameraDialFunction_*), and which of them may
// be pressed, by never_touch.h's lists (written from kit/camkit/safety.py). The rule refuses whatever those lists do
// not name as pressable, so a button added to the table without a rule is refused, not pressed. Needs none of the
// SDK's headers; kit/common/guards_test.cpp checks that every name in the tables is on one of never_touch.h's lists.
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

#include "never_touch.h"

namespace remote {

struct Code {
    const char* name;
    uint32_t code;
};

// CrCameraButtonFunction_*: the value set is the code with Down (2) or Up (1) in its low bits
inline const Code kButtons[] = {
    {"up", 0x00010000}, {"down", 0x00020000}, {"left", 0x00030000}, {"right", 0x00040000},
    {"enter", 0x00050000}, {"menu", 0x00060000},
    {"ms_up", 0x00070000}, {"ms_down", 0x00080000}, {"ms_left", 0x00090000}, {"ms_right", 0x000A0000},
    {"ms_enter", 0x000B0000}, {"ms_right_up", 0x000C0000}, {"ms_right_down", 0x000D0000},
    {"ms_left_up", 0x000E0000}, {"ms_left_down", 0x000F0000},
    {"fn", 0x00100000}, {"playback", 0x00110000}, {"delete", 0x00120000}, {"mode", 0x00130000},
    {"c1", 0x00140000}, {"c2", 0x00150000}, {"c3", 0x00160000}, {"c4", 0x00170000}, {"c5", 0x00180000},
    {"c6", 0x00190000}, {"movie", 0x001A0000}, {"ael", 0x001B0000}, {"af_on", 0x001C0000},
    {"home", 0x001D0000}, {"display", 0x00200000}, {"c7", 0x00210000}, {"back", 0x00220000},
    {"thumbnail", 0x00230000},
};
// CrCameraDialFunction_*: the value set is the code with the steps, a signed 16-bit count, in its low bits
inline const Code kDials[] = {
    {"wheel", 0x40010000}, {"front", 0x40020000}, {"rear_l", 0x40030000}, {"rear_r", 0x40040000},
};

template <std::size_t N>
inline uint32_t codeIn(const Code (&table)[N], const std::string& name) {
    for (const Code& c : table)
        if (name == c.name) return c.code;
    return 0;
}

// The code of the button or dial with this name; 0 for a name the table does not have.
inline uint32_t buttonCode(const std::string& name) { return codeIn(kButtons, name); }
inline uint32_t dialCode(const std::string& name) { return codeIn(kDials, name); }

// The dial's value: its code with the steps (negative: the other way) as a signed 16-bit count in the low bits.
inline uint32_t dialValue(uint32_t code, int steps) {
    return code | (static_cast<uint32_t>(static_cast<uint16_t>(static_cast<int16_t>(steps))) & 0xFFFFu);
}

// What the rule says of pressing a button or turning a dial: allowed; never (it records, lights up, drives the lens
// or runs what it is assigned); guarded (C4 and the others pressed only on a screen the caller checked first, which
// `allowGuarded` says it did); or unlisted (no rule names it). The refusing lists are asked first, so a name that
// ever landed on the menu list as well (a slip in kit/camkit/safety.py) is still refused; guards_test.cpp checks the
// lists share no name.
enum class Press { allowed, never, guarded, unlisted };

inline Press pressRule(const std::string& name, bool allowGuarded) {
    if (never_touch::neverButton(name)) return Press::never;
    if (never_touch::guardedButton(name)) return allowGuarded ? Press::allowed : Press::guarded;
    if (never_touch::menuButton(name)) return Press::allowed;
    return Press::unlisted;
}

}  // namespace remote
