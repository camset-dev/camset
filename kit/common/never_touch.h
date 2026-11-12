// kit/common/never_touch.h: what camlink and the editor's camera helper never send, compiled into both. Written by
// kit/tools/build_docs.py from kit/camkit/safety.py (MENU_INPUTS, GUARDED_INPUTS, NEVER_INPUTS, MIN_HOLD_MS, MAX_HOLD_MS,
// NEVER_PROPERTIES), which the kit's own guards read: edit safety.py, never this file (docs/decisions/0014). The kit's
// tests check that it is current and compile it (kit/common/guards_test.cpp).
#pragma once

#include <cctype>
#include <cstddef>
#include <regex>
#include <string>

namespace never_touch {

// buttons pressed whenever asked: the menus' arrows, Enter and Menu, the multi-selector and the dials
inline const char* const kMenuButtons[] = {"down", "enter", "front", "left", "menu", "ms_down", "ms_enter", "ms_left", "ms_left_down", "ms_left_up", "ms_right", "ms_right_down", "ms_right_up", "ms_up", "rear_l", "rear_r", "right", "up", "wheel"};
// buttons pressed only where the caller says it allows them, on a screen it checked first (C4 is the trash button)
inline const char* const kGuardedButtons[] = {"back", "c4", "delete", "display", "fn", "playback"};
// buttons never pressed: they record, light up, drive the lens or run what they are assigned
inline const char* const kNeverButtons[] = {"ael", "af_on", "c1", "c2", "c3", "c5", "c6", "c7", "home", "mode", "movie", "thumbnail"};
// how long a press holds its button, in ms: a Down accepted and an Up refused would leave it held
constexpr int kMinHoldMs = 20, kMaxHoldMs = 2000;

// properties never set, each with why: a regular expression (ECMAScript) searched in the SDK's property name
// (CrDeviceProperty.h, without "CrDeviceProperty_"). Case matters: the SDK's names are CamelCase and each pattern
// starts with its capital, so it matches where a word of the name starts (with case ignored, 23 of the a1 II's names
// were refused by accident inside other words: FocusBracket's "usB", the *Preset names' "reset")
struct Rule {
    const char* why;
    const char* pattern;
};
inline const Rule kProperties[] = {
    {"sound, light or motion: motion", "Pre_?AF|Eye_?Start|Focus_?Operation|FocusDriv|FocusPositionSetting|FollowFocus|PushAuto|Zoom|Iris_?Drive|IrisClose|NDFilterPosition|Pan_?Tilt|PanLimit|PanPosition|TiltLimit|TiltPosition|PTZF|ShutterWhenPower|SteadyShot|ImageStabilization"},
    {"sound, light or motion: light", "Illuminator|Tally|Lamp|FlashMode|WirelessFlash|RedEye|TestFlash|Modell?ing|Video_?Light"},
    {"sound, light or motion: sound", "Volume|AudioSignal|Beep|Speaker|Headphone|Sound|ScreenReader"},
    {"credentials or connection", "Password|SSH|User_?Name|Authen|Fingerprint|Network|Wired|Wireless|Wi_?Fi|Bluetooth|WakeOnLAN|IPSetup|IP_?Address|MAC_?Address|SSID|FTP|Stream|Pairing|Tether|USB|Remote|Remocon|Monitoring|SdkControlMode|DebugMode"},
    {"by hand only", "DateTime|TimeZone|Language|Power|Copyright|Photographer|Artist|Owner|Camera_?Name|Device_?Name|Serial|IPTC|ImageID"},
    {"action", "Format|Delete|Erase|Reset|Initiali[sz]|Cleaning|PixelMapping|Firmware|UpdateBody|CreateNewFolder|FileNumber|Copy|_Save|_Load|Upload|Download|Import|Embed|Capture|Snapshot|SceneFile|Media|Slot|Playback|MoviePlay|MovieRec|RecorderStart|RecorderControl|RecordingState|TimeShiftShooting|Interval_?Rec|SelfTimer|ContentsTransfer|PostView|Touch|Protect|Rating"},
    {"a button, dial or lever", "Button|Dial|Lever|^S1$|^S2$|^AEL$|^FEL$|^AWBL?$"},
};

template <std::size_t N>
inline bool listed(const char* const (&names)[N], const std::string& name) {
    for (const char* n : names)
        if (name == n) return true;
    return false;
}
inline bool menuButton(const std::string& name) { return listed(kMenuButtons, name); }
inline bool guardedButton(const std::string& name) { return listed(kGuardedButtons, name); }
inline bool neverButton(const std::string& name) { return listed(kNeverButtons, name); }

// Why a property is never set, "" when it may be. The name as the SDK's table spells it, with or without
// "CrDeviceProperty_"; one that is no name (a code such as 0x1234, or empty) is never set either.
inline std::string property(const std::string& name) {
    const std::string bare = name.rfind("CrDeviceProperty_", 0) == 0 ? name.substr(17) : name;
    bool word = !bare.empty() && std::isalpha(static_cast<unsigned char>(bare[0]));
    for (char c : bare) word = word && (std::isalnum(static_cast<unsigned char>(c)) || c == '_');
    if (!word) return "no property name: a code or an empty name is never set";
    for (const Rule& r : kProperties) {
        std::smatch m;
        if (std::regex_search(bare, m, std::regex(r.pattern, std::regex::ECMAScript)))
            return std::string(r.why) + ": " + m.str(0);
    }
    return "";
}

}  // namespace never_touch
