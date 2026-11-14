"""What the kit may never do on the camera.

The guards:
  check_input(name, allow)   inputs outside the menu allow-list need an explicit, named allowance;
                             some are never sent at all (they record, light up, or act).
  name_refused(name)         a key's name as the link takes it: lower case, unpadded, unquoted, no look-alikes.
  check_property(name)       camera properties the link may set through the SDK: the live exposure only, and never
                             one that makes sound, light or motion, holds credentials or identity, or acts.
  never_open(label)          menu rows the walker must not enter: actions, credentials, identity/connection/region
                             settings, anything that makes sound, light or motion (user rules), and the Wi-Fi and
                             Bluetooth settings and address screens (NETWORK, judged last).
  network_decided(scope)     the Wi-Fi and Bluetooth rows, address screens and identity rows (lift_class) a dated owner
                             decision ("lifts": "network") names, and why each other row such a decision names is
                             refused (decision 8); option_refused, an option it may not name.
  network_lifted(lit, rows)  whether such a decision opens the lit row: a row it names, its label followed by nothing
                             or one of its own values, never an address screen unless the caller looks at one (drive.py
                             alone), never anything else; or the same row read with its page's icon glued on ("LANIP
                             Address Setting" on Wired LAN) where another reader of it read the row exactly
                             (lifted_readings, row_read_as, glued_icon); bar_on_row, the lit bar back on such a row.
  group_refused(name, known) a group the menu's group column must not step into: never_open, or one letter from a
                             never-open group's or action's name ("FTP Transter").
  look_refused(key, lit, row, options)  inside such a row: up, down and MENU, and Enter only on an option the decision
                             names (network_options); a row with none named is looked at only. The callers' locks
                             (camkit.live.LiveCamera, kit/drive.py) end only once a MENU or such an Enter has gone out
                             and the page the row was opened from, or the shooting screen, is back.
  identity_screen(text)      a screen naming identity or credentials (pairing, an SSID...): MENU alone inside such a row.
  address_fields(lines)      the field names an address screen shows (MAC Address, IP Address...), never a value;
                             screen_fields, those and whole row labels, never a line that is a known value.
  notice_kept(text)          a greyed network setting's notice as the crawl keeps it: a known shape naming no identity.
  confirmation(text)         dialog text asking to execute something; never press Enter on it.
  fold(text)                 a reading as the checks compare it: Unicode look-alikes, dashes and spacing mended.
  readings(text)             every reading a guard judges (as read, folded, slips undone): any one matching refuses.
  owner_may_approve(reason)  whether a dated owner decision can lift a never_open reason for one row (sound, light
                             or motion: decision 2); actions and credentials never.
  allow_refused(label)       why a run's --allow cannot name a row: the cards, Initialize, Reset Network Set.,
                             credentials, the camera's identity, a connection or its region, and the Wi-Fi and
                             Bluetooth settings and address screens, which only a dated decision opens (decision 8).
  shooting_refused(key, kind, named)  a key on the shooting screen: MENU only, unless the caller names it (decision 21).
  profile_reset_row(lit, title, profile)   why the lit row is not a Picture Profile's own Reset row, or "".
  profile_reset_dialog(text, profile)      why a screen is not that row's own "Reset PPn to the default setting?".

The button lists and the never-set properties are also compiled into both C++ programs (camlink and the editor's
camera helper), which refuse them on their own: kit/tools/build_docs.py writes them into kit/common/never_touch.h
from this file, so they are edited here only (docs/decisions/0014).

Actions match whole labels only, so settings that merely contain the word ("File Format",
"Focus Area", "Delete confirm.") are still walked. Review the exclusions with:
    .venv/bin/python -m camkit.safety

Every label and screen text is judged as read, with the usual OCR slips undone (deslip), and folded too (fold): the
readers return Cyrillic look-alikes ("С.Temp", camkit.match), a vision reader writes "Wi‑Fi" with a non-breaking
hyphen, OCR doubles a space or adds a full stop. The folded readings are judged beside the others, never instead of
them (readings): folding can also turn a character into letters that hide a slip ("①lnitialize" folds to
"1lnitialize", where deslip's word-start rule no longer sees the "l"), so a guard refuses when any reading matches,
and a fold only adds refusals.
"""
import re
import unicodedata

from .match import LOOKALIKES

# Moving around menus and dialogs: always allowed.
MENU_INPUTS = {
    "up", "down", "left", "right", "enter", "menu",
    "ms_up", "ms_down", "ms_left", "ms_right", "ms_enter",
    "ms_right_up", "ms_right_down", "ms_left_up", "ms_left_down",
    "wheel", "front", "rear_l", "rear_r",
}
# Allowed only when the caller names them (Playback for the playback crawl, Fn for the Fn menu crawl).
# C4 is the trash button: on a menu or option screen whose footer draws the help button it opens the
# In-Camera Guide (the SDK's Delete key does nothing there, 2026-11-01); callers check screen.help_glyph first
# (drive.py help_refused). Since 2026-11-02 also Focus Area's SET with a Custom box lit, which opens the box's size
# editor (drive.py c4set_refused), and since 2026-11-03 a Creative Look panel's Reset (c4reset_refused).
GUARDED_INPUTS = {"fn", "playback", "delete", "display", "back", "c4"}
# C4's guard is the screen (decision 7, 2026-11-06). In Playback, or wherever a picture is displayed, C4 is the trash
# button and deletes it; on the shooting screen it does whatever the body assigns to it, a change the kit must not
# make. So C4 goes out only on the menu, option, panel and editor screens below, whose footer draws what C4 does there:
# the help button (C4_HELP_SCREENS), Focus Area's SET (a dialog) or a Creative Look panel's Reset ("look"); drive.py
# checks the footer itself. Link.press refuses C4 on any other screen, and while the camera says it is in Playback.
C4_HELP_SCREENS = frozenset({"menu", "submenu", "dialog", "list", "sidelist", "checklist", "picker", "fields"})
C4_SCREENS = C4_HELP_SCREENS | {"look"}
# Never sent: Movie records (tally lamp), AF-On drives the lens, C1-C3/C5-C7/AEL do whatever they are
# assigned to, Mode/Home/Thumbnail leave the menu system in ways the walker does not model.
NEVER_INPUTS = {"movie", "af_on", "ael", "mode", "home", "thumbnail", "c1", "c2", "c3", "c5", "c6", "c7"}
# The shooting screen is the guard for every key but MENU (decision 21, 2026-11-10). There a key does what the body
# makes of it, never what it does in a menu: in the shipped definition the control wheel's Center, Left, Right and Down
# buttons and the multi-selector's centre are Custom Keys, whose lists hold Movie Shooting, Wireless Test Flash, FEL
# Lock, AF On, FTP Transfer, Send and Interval Shooting; the multi-selector's four directions move the focus frame; a
# dial changes the live exposure, which no settings file holds. A Right meant for a menu once landed there and opened
# ISO (2026-10-29, kit/proving/nav.py to_row). Which keys a body lets its owner assign differs by body, so the guard does
# not rest on it: on a screen read as the shooting screen only these go out, and any other key only when the caller
# names it for that press (shooting_refused's `named`: Link.press's and Link.dial's on_shooting), where pressing it
# there is the point (the focus frame's moves, the Fn hold that registers an area); with no screen given, only these,
# named or not. C4's own guard (c4_refused) stands beside it: naming C4 never sends it there. What this does not cover:
# a shooting screen the reader takes for another kind (a DISP mode that draws no battery reads "unknown", and the kit
# presses on unknown screens on purpose: the memory slots read as one); camkit.live asks the camera's own picture only
# when the frame is black (HDMI blanked).
SHOOTING_FREE = frozenset({"menu"})
# A press holds its button this long at most: a Down accepted and an Up refused would leave it held (2026-11-06)
MAX_HOLD_MS = 2000
MIN_HOLD_MS = 20

# Camera properties never set through the SDK (the link's set and setstr, camlink's and the camera helper's own), by
# the SDK's property name (CrDeviceProperty.h, "CrDeviceProperty_" left off), each a regular expression searched in
# the name as written, written so that Python and C++ (ECMAScript) read it alike. The playbook's rules 1-4 and
# decisions 2-9 name what they cover; a name the SDK's table does not hold is never set either.
# The case counts (2026-11-08): the SDK's names are CamelCase and every pattern starts with its capital, so a pattern
# matches where a word of the name starts. Matched with case ignored, 23 of the a1 II's 475 names were refused by
# accident inside other words: FocusBracket* ("usB"), ContinuousShooting* and FlickerLessShooting* ("sSh"),
# LensInformationEnableStatus ("format"), CameraOperatingMode ("rating"), CameraSetting_ReadOperationEnableStatus
# ("eraSe"), the *Preset names ("reset"), TimeShiftPreShootingTimeSetting ("ftP"); the 194 true refusals all stay
# (kit/tests/test_guards.py). The C++ programs match the same way: kit/common/never_touch.h compiles each pattern
# ECMAScript with no icase ("Case matters", its comment says), as build_docs.py writes it from this list.
NEVER_PROPERTIES = {
    # lens motors, the shutter curtain, stabilisation and a pan/tilt head (decision 2; the playbook's rule 1)
    "sound, light or motion: motion": [
        r"Pre_?AF", r"Eye_?Start", r"Focus_?Operation", r"FocusDriv", r"FocusPositionSetting", r"FollowFocus",
        r"PushAuto", r"Zoom", r"Iris_?Drive", r"IrisClose", r"NDFilterPosition", r"Pan_?Tilt", r"PanLimit",
        r"PanPosition", r"TiltLimit", r"TiltPosition", r"PTZF", r"ShutterWhenPower", r"SteadyShot",
        r"ImageStabilization"],
    # anything that lights up: the AF illuminator, the tally lamps, the flash on the shoe and its light (rule 1)
    "sound, light or motion: light": [
        r"Illuminator", r"Tally", r"Lamp", r"FlashMode", r"WirelessFlash", r"RedEye", r"TestFlash", r"Modell?ing",
        r"Video_?Light"],
    # sound (a run woke people at night, 2026-10-25) and the screen reader (decision 3)
    "sound, light or motion: sound": [
        r"Volume", r"AudioSignal", r"Beep", r"Speaker", r"Headphone", r"Sound", r"ScreenReader"],
    # credentials and the network, USB and remote session settings: by hand only (decisions 8 and 9)
    "credentials or connection": [
        r"Password", r"SSH", r"User_?Name", r"Authen", r"Fingerprint", r"Network", r"Wired", r"Wireless", r"Wi_?Fi",
        r"Bluetooth", r"WakeOnLAN", r"IPSetup", r"IP_?Address", r"MAC_?Address", r"SSID", r"FTP", r"Stream",
        r"Pairing", r"Tether", r"USB", r"Remote", r"Remocon", r"Monitoring", r"SdkControlMode", r"DebugMode"],
    # region, language, date and power, and what a person types about themselves: by hand only (decision 8)
    "by hand only": [
        r"DateTime", r"TimeZone", r"Language", r"Power", r"Copyright", r"Photographer", r"Artist", r"Owner",
        r"Camera_?Name", r"Device_?Name", r"Serial", r"IPTC", r"ImageID"],
    # actions, and whatever records, plays or works on the cards (decisions 4 and 5)
    "action": [
        r"Format", r"Delete", r"Erase", r"Reset", r"Initiali[sz]", r"Cleaning", r"PixelMapping", r"Firmware",
        r"UpdateBody", r"CreateNewFolder", r"FileNumber", r"Copy", r"_Save", r"_Load", r"Upload", r"Download",
        r"Import", r"Embed", r"Capture", r"Snapshot", r"SceneFile", r"Media", r"Slot", r"Playback", r"MoviePlay",
        r"MovieRec", r"RecorderStart", r"RecorderControl", r"RecordingState", r"TimeShiftShooting", r"Interval_?Rec",
        r"SelfTimer", r"ContentsTransfer", r"PostView", r"Touch", r"Protect", r"Rating"],
    # buttons, dials and levers go only through press and dial, which the input lists above guard
    "a button, dial or lever": [
        r"Button", r"Dial", r"Lever", r"^S1$", r"^S2$", r"^AEL$", r"^FEL$", r"^AWBL?$"],
}
# What the link may set: the live exposure, which no settings file holds (kit/tools/sdk_set.py puts it back after a
# run). Values are the SDK's (ShutterSpeed: numerator << 16 | denominator; FNumber: F x 100).
SET_PROPERTIES = frozenset({"ShutterSpeed", "FNumber", "ExposureBiasCompensation", "FlashCompensation",
                            "IsoSensitivity"})
_PROPERTY_RES = [(why, re.compile("|".join(pats))) for why, pats in NEVER_PROPERTIES.items()]     # case counts


class Refused(Exception):
    pass


def check_input(name: str, allow: frozenset | set = frozenset()):
    """Returns when the input may be sent, raises Refused when not. `allow` names guarded inputs; one name given as a
    string is that name, never the names it contains ("playback" does not allow "back")."""
    allow = {allow} if isinstance(allow, str) else allow
    if name in MENU_INPUTS:
        return
    if name in GUARDED_INPUTS and name in allow:
        return
    if name in NEVER_INPUTS:
        raise Refused(f"input {name!r} is never sent")
    if name in GUARDED_INPUTS:
        raise Refused(f"input {name!r} needs an explicit allowance")
    raise Refused(f"unknown input {name!r}")


# quotation marks a caller or a reader can put round a key's name
QUOTES = "'\"`\u2018\u2019\u201c\u201d"
KEY_NAME = re.compile(r"[a-z0-9_]+")


def canonical_input(name) -> str:
    """A button's or dial's name as the guards read it and camlink would: the spaces and quotation marks round it left
    out (camlink's parser drops them), look-alike letters as the Latin ones they are drawn as (fold), the case folded.
    " Enter", '"right"' and a Cyrillic "rіght" are all read as enter and right (kit/drive.py canonical_key reads its
    --press keys so)."""
    return fold(str(name)).strip().strip(QUOTES).strip().casefold()


def name_refused(name) -> str:
    """Why a button's or dial's name may not go to the link, or "": it must be written as the guards read it
    (canonical_input) and be lower-case letters, digits and "_" only. A padded, quoted, upper-case or look-alike
    spelling is refused rather than mended: a check made on the name as given (LiveCamera's never-open check on Right
    and Enter) would otherwise judge one key while camlink presses another."""
    canon = canonical_input(name)
    if isinstance(name, str) and name == canon and KEY_NAME.fullmatch(name):
        return ""
    return (f"the key {name!r} is not written as the guards read it ({canon!r}): keys are named in lower-case letters, "
            f"digits and _ only")


def c4_refused(kind) -> str:
    """Why C4 may not be pressed on a screen the reader read as `kind`, or "" when it may (C4_SCREENS)."""
    if kind in C4_SCREENS:
        return ""
    if kind is None:
        return "C4 is pressed only on a screen just read, and none was given"
    if kind == "shooting":
        return ("the screen is the shooting screen, where C4 does whatever the body assigns to it: a change the kit "
                "must not make")
    return (f"the screen reads as {kind!r}, not a menu, option or panel screen: in Playback, or wherever a picture is "
            "displayed, C4 deletes it")


def shooting_refused(key, kind, named=frozenset()) -> str:
    """Why `key` (a button pressed, or a dial turned) may not go out on a screen the reader read as `kind`, or "" when
    it may (decision 21): MENU always; on the shooting screen any other key only when the caller names it (`named`, the
    keys named for this press; one name given as a string is that name, as check_input's allow); with no screen given
    at all (kind None), no key but MENU, since nothing says it is not the shooting screen. Any other kind, "unknown"
    among them, is not judged here (SHOOTING_FREE's comment says what that leaves)."""
    named = {named} if isinstance(named, str) else named
    if key in SHOOTING_FREE:
        return ""
    if kind is None:
        return "a key is pressed only on a screen just read, and none was given: unseen, only MENU goes out"
    if kind == "shooting" and key not in named:
        return (f"the screen is the shooting screen, where {key!r} does what the body makes of it (a Custom Key, the "
                "focus frame, or the live exposure on a dial): only MENU goes out there, unless the caller names the key")
    return ""


def check_hold(hold_ms) -> int:
    """A press's hold time in ms, between MIN_HOLD_MS and MAX_HOLD_MS; Refused otherwise."""
    ms = int(hold_ms)
    if not MIN_HOLD_MS <= ms <= MAX_HOLD_MS:
        raise Refused(f"a press holds its button {MIN_HOLD_MS}-{MAX_HOLD_MS} ms, not {ms}")
    return ms


def never_property(name: str) -> str | None:
    """Why a camera property is never set through the SDK, or None. A code ("0x1234") has no name to judge it by, so
    it is never set either."""
    bare = (name or "").strip().removeprefix("CrDeviceProperty_")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", bare):
        return "no property name: a code or an empty name is never set"
    for why, rx in _PROPERTY_RES:
        m = rx.search(bare)
        if m:
            return f"{why}: {m.group(0)}"
    return None


def check_property(name: str, allowed=SET_PROPERTIES):
    """A property the link may set: never one never_property names, and only one `allowed` names (the live exposure,
    SET_PROPERTIES)."""
    why = never_property(name)
    if why:
        raise Refused(f"property {name!r} is never set: {why}")
    if name.removeprefix("CrDeviceProperty_") not in allowed:
        raise Refused(f"property {name!r} is not one the kit sets (only {', '.join(sorted(allowed)) or 'none'})")


# Rows whose label IS one of these (after icon noise is stripped): actions and editors.
_ACTIONS = [
    r"format", r"deleter", r"recover image db", r"protect", r"rating", r"delete", r"delete all",
    r"delete item", r"delete page", r"delete slot ?1/2", r"crop", r"rotate", r"copy", r"photo capture",
    r"create still image", r"create new folder", r"setting reset", r"camera settings reset",
    r"initialize", r"factory reset", r"reset network set\.?", r"series counter reset",
    r"reset transfer status", r"ssid/pw reset", r"save/load settings", r"camera set\. memory",
    r"recall camera setting", r"reg\. custom shoot set", r"del\. regist\. af area", r"focus magnifier",
    r"enlarge image", r"enlarge screen", r"slide show", r"image index", r"add item", r"sort item",
    r"face memory", r"preset focus/zoom", r"lock operation parts", r"cleaning mode", r"pixel mapping",
    r"auto pixel mapping", r"anti-dust function", r"version", r"certification logo", r"privacy notice",
    r"display serial number", r"select rec folder", r"update", r"firmware update",
    # found 2026-10-28 in the old runs' labels: the first opens with OK preselected and creates a folder
    r"forced file number reset", r"send",
    # Playback rows that act on images rather than set something (2026-10-29)
    r"clip flag", r"disp specified time img\.?",
    # FTP Transfer Func. (opened for mapping 2026-10-29, user: "we could do it without a server"):
    # the rows that send images or load/save the FTP file
    r"ftp transfer", r"save/load ftp settings",
]
# Rows containing any of these: by hand only. The first part, the camera's identity, its connections and its region
# (USB, language, NTSC/PAL, area and date, network identity: decision 8, and what a person types about themselves),
# is _IDENTITY: no allowance lets a run open or set one of them (identity_row, which never_lifted, allow_refused and
# screen_refused take in, so drive.py's, card_actions.py's and every prover's --allow and path_refused refuse them
# too); the rest a dated owner's word may open
# "Wi-Fi" as a reader returns it, in lower case as the guards judge it: spaced round its hyphen, without one, run into
# the next word ("Wi-FiConnect"), its last i read as l, 1, | or ! ("Wi-Fl", "Wi-F1"); the word after it follows
# (2026-11-13, a review)
_WIFI = r"wi\s?-?\s?f[il1|!]\s?"
_IDENTITY = [
    # identity, connection, region
    r"date/time", r"^area/", r"ntsc", r"language", r"usb connection", r"usb lun", r"usb power",
    r"usb streaming", r"wired lan connect", r"ip address", r"ssid", r"\bwps\b",
    r"access point", r"access authen", r"pairing", r"paired",
    r"cloud", r"streaming", r"tether", r"device name", r"root certif",
    # FTP: the server and its login stay by hand, FTP Function starts a connection to that server
    # (asked separately), and the Display rows are reports, not settings
    r"ftp function", r"server setting", r"save/load ftp", r"display ftp",
    r"remote shoot function", r"cnct\. while", r"wake on lan", r"smartphone", r"copyright", r"iptc",
    r"select on cam",   # Select on Cam & Send: sends images to a phone
    # the screen that shows the body's serial number, which every saved frame, the OCR output and a hosted reader's
    # request would then hold: Display Serial Number on the a1 II (2026-11-13, a review); Write Serial Number, whether
    # pictures carry the number, is walked
    r"disp(?:lay|\.)?\s?serial",
]
# Of those, the identity, connection and region rows a dated owner decision naming the row may open to look at (decision
# 8, the a1 II's owner's of 2026-11-13: "you have my full permission to open any menu and map items"), still never by
# --allow and never without --network: identity_liftable. Only rows whose opening is known to start or end nothing:
# Right on them opens an option list (Wired LAN Connect, Cnct. while Power OFF, Wake On LAN, the USB rows, Language), a
# submenu (Remote Shoot Function, IP Address Setting, Area/Date/Time Setting) or an information screen (Manage Paired
# Device's list, Display FTP Result, NTSC/PAL Selector's message). What stays never opened whatever is decided
# (_IDENTITY_FIXED), with credentials and every action (never_open's other classes): the SSID, WPS, access point,
# access authentication and pairing rows, Import Root Certificate, Save/Load FTP Settings, the copyright and IPTC rows,
# Select on Cam & Send and Display Serial Number; and the rows whose opening may itself start or end a connection or act,
# which nobody has yet seen Right do on the camera (2026-11-13, a review: look-only governs the presses after the
# opening, never the opening): Smartphone Connection, Cloud Connection and Cloud Information, Network Streaming and USB
# Streaming, Tethering Connection and Tethering Disconnection, FTP Function; and Server Setting, behind which the FTP
# login sits (credentials, decision 9), and Edit Device Name, whose opening shows a keyboard and the device's name, and
# which no settings file holds
_IDENTITY_LIFTABLE = [
    r"date/time", r"^area/", r"ntsc", r"language", r"usb connection", r"usb lun", r"usb power",
    r"wired lan connect", r"ip address", r"paired", r"display ftp", r"remote shoot function", r"cnct\. while",
    r"wake on lan",
]
_IDENTITY_FIXED = [p for p in _IDENTITY if p not in _IDENTITY_LIFTABLE]
# Why network_refused refuses the identity rows _IDENTITY_LIFTABLE left out on 2026-11-13 (a review), in the words a
# run stops with: matched in every reading of the row a decision names
_NOT_LIFTED_WHY = [(re.compile(rx), why) for rx, why in (
    (r"smartphone|cloud|streaming|tether|ftp function",
     "its opening may itself start or end a connection or act, and nobody has yet seen on the camera what Right does "
     "there"),
    (r"server setting", "the FTP server's login sits behind it (credentials, docs/decisions/0009)"),
    (r"device name", "its opening shows a keyboard and the device's name, which no settings file holds"),
)]
# Rows of the classes a network decision opens in which no option is ever chosen, whatever a decision names: the choice
# drops the link a run needs (Wired LAN Connect, USB, the IP address settings; Airplane Mode, which drops the Wi-Fi and
# Bluetooth links), starts a connection or a pairing (Remote Shoot Function and all under it, Smartphone Connection,
# Cnct. while Power OFF, Wi-Fi Connect's On, which joins the access point, Bluetooth Rmt Ctrl's On, which opens the
# Pairing screen (the a1 II's notes), Cloud, streaming, tethering, FTP), or changes what no settings file puts back or
# what every other setting means (Language, NTSC/PAL, Area/Date/Time, the device's name, a paired device). Matched in
# the row's name as a decision names it (never_choose)
_NEVER_CHOOSE = [
    r"wired lan connect", r"remote shoot", r"connection method", r"pairing", r"paired", r"ip address", r"subnet",
    r"gateway", r"\bdns\b", r"smartphone", r"cnct\. while", r"cloud", r"streaming", r"tether", r"\busb\b", r"language",
    r"ntsc", r"^area/", r"date/time", r"device name", r"ftp", r"server",
    _WIFI + r"connect", r"[b8]lue\s?t[o0]{1,2}th\s?r(?:m|n|rn)t", r"bluetooth\s?remote\s?c(?:trl|ontrol)",
    r"airplane mode",
]
# The Wi-Fi and Bluetooth settings and the screens that show the camera's network addresses (decision 8, as it stands
# since 2026-11-13): by hand only, like _IDENTITY, and no --allow opens them; but unlike _IDENTITY, a dated owner
# decision that names the row ({"lifts": "network", "date", "rows", "why"} in the reviewed scope, network_decided) opens
# it for a run given --network (network_lifted). never_open names them last (NETWORK), only when no other class of the
# list matches any reading, so a misread that also looks like credentials, an action or an identity row keeps that
# reason. The patterns were found on 2026-11-13 (a review): Wi-Fi Connect, Bluetooth Function and Airplane Mode were
# identity rows before, and Bluetooth Rmt Ctrl and Wi-Fi Frequency Band were on no list though the playbook's rule 3
# names them. Each pattern takes the slips a reader makes in its row's own words (a space dropped or put in; 1, l or |
# for i or l; 0 for o; rn or n for m; 8 for B; a letter dropped; Addr. for Address) and names those words only, so the
# group names (Wi-Fi, Bluetooth, Wired LAN) and the other Display rows are walked as before.
_NETWORK_SETTINGS = [
    _WIFI + r"connect", r"bluetooth function", r"airplane mode",
    r"[b8]lue\s?t[o0]{1,2}th\s?r(?:m|n|rn)t", r"bluetooth\s?remote\s?c(?:trl|ontrol)", _WIFI + r"freq",
    r"frequency\s?band",
]
# The screens that show the camera's addresses (its MAC and IP addresses, its Bluetooth device address), which every
# saved frame, the OCR output and a hosted reader's request would then hold: Display Wi-Fi Info., Display Wired LAN
# Info. and Disp Device Address on the a1 II, and a MAC address row another body may show. A decision opens one only in
# kit/drive.py, which shows the screen's field names alone (address_fields), asks local readers only and sends no key
# but MENU once it is open; the walker and the provers never open one (network_lifted's screens).
_ADDRESS_SCREENS = [
    _WIFI + r"[il1|]nf", r"(?:wired\s?|(?<![a-z]))[il1|]an\s?[il1|]nf", r"(?:dev[il1|!]ce|mac)\s?addr",
]
_ANYWHERE = _IDENTITY + [
    r"auto power off temp",
    # sound and light (a run woke people on 2026-10-25), and the screen reader
    r"screen reader", r"accessib", r"long press", r"illuminator", r"tally", r"\blamp\b", r"beep",
    r"sound", r"speaker", r"headphone", r"volume", r"play vol", r"\bvol\.", r"voice memo", r"audio signal",
    r"video light",
    # the flash on the shoe (attached 2026-10-28): anything that fires it or lights it
    r"test flash", r"\btest\b", r"modell?ing", r"\bfire\b", r"\bled\b",
]
# Credentials and the screens that show them: never opened, and no allowance lifts it (decision 9). Wi-Fi Direct
# Info. shows the camera's Wi-Fi Direct SSID and password on screen, which every saved frame, the OCR output and a
# hosted reader's request would then hold (2026-11-05, the kit review). "Wi-Fi Direct" as a reader returns it too
# (_WIFI; "Wi-FiDirect", "Wi-Fl Direct", 2026-11-13).
_CREDENTIALS = [r"access authen", _WIFI + r"d[il1|]rect", r"password", r"\bpw\b"]
# Motion (decision 2; the playbook's rule 1): lens motors (Pre-AF, Eye-Start AF), the shutter curtain (Shutter When
# Pwr OFF) and SteadyShot. By hand only, unless a dated owner decision names the row (the a1 II's owner allowed
# Shutter When Pwr OFF and SteadyShot from the menu on 2026-10-29). Added 2026-11-05.
_MOTION = [r"pre-?\s?af\b", r"eye-?\s?start", r"shutter when pwr", r"steady\s?shot"]
# a whole label, with any stop, colon or question mark a reader puts after it ("Format.", "Copy?")
_ACTION_RE = re.compile(r"^(" + "|".join(_ACTIONS) + r")[\s.:;,!?…]*$")
# Words that make a row an action wherever they appear: every row named with "reset" is one
# (Setting Reset, SSID/PW Reset, Forced File Number Reset...), and Picture Profile's settings have a
# bare "Reset" row (2026-10-28)
_ACTION_WORD_RE = re.compile(r"\breset\b")
_ANYWHERE_RE = re.compile("|".join(_ANYWHERE))
_IDENTITY_RE = re.compile("|".join(_IDENTITY))
_CREDENTIALS_RE = re.compile("|".join(_CREDENTIALS))
_MOTION_RE = re.compile("|".join(_MOTION))
_NETWORK_SETTINGS_RE = re.compile("|".join(_NETWORK_SETTINGS))
_ADDRESS_RE = re.compile("|".join(_ADDRESS_SCREENS))
_NETWORK_RE = re.compile("|".join(_NETWORK_SETTINGS + _ADDRESS_SCREENS))
_IDENTITY_LIFTABLE_RE = re.compile("|".join(_IDENTITY_LIFTABLE))
_IDENTITY_FIXED_RE = re.compile("|".join(_IDENTITY_FIXED))
_OTHER_BY_HAND_RE = re.compile("|".join(_ANYWHERE[len(_IDENTITY):]))     # sound, light, flash, Auto Power OFF Temp.
_NEVER_CHOOSE_RE = re.compile("|".join(_NEVER_CHOOSE))
MOTION = "sound, light or motion"          # the reason's prefix a dated owner decision can lift for one row
NETWORK = "network setting or address screen"   # the reason's prefix only a dated decision naming the row lifts
NETWORK_LIFT = "network"                   # a decision's "lifts" that opens such rows (network_decided)


# Look-alikes of Latin letters beyond camkit.match's table, for the guards only (an extra one only adds a refusal):
# Ukrainian and Serbian letters, Greek capitals and the Greek small letters drawn as Latin ones, the lower case of
# the Cyrillic letters drawn as small capitals
_GUARD_LOOKALIKES = {**LOOKALIKES, **str.maketrans("ІіЈјЅѕԁԛԝΑΒΕΖΗΙΚΜΝΟΡΤΥΧαοιρνκмтвн",
                                                   "IiJjSsdqwABEZHIKMNOPTYXaoipvkmtbh")}
_DASHES = re.compile(r"[\u2010-\u2015\u2212\ufe58\ufe63]")


def fold(text) -> str:
    """A reading as the guards compare it: compatibility forms as their plain letters (full-width "ＦＯＲＭＡＴ",
    a no-break space), format characters (zero-width spaces, joiners) left out, every dash a hyphen ("Wi‑Fi", "Pre–AF"),
    Cyrillic and Greek look-alikes as the Latin letters they are drawn as, and each run of spacing one space."""
    t = unicodedata.normalize("NFKC", str(text or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Cf")
    t = _DASHES.sub("-", t).translate(_GUARD_LOOKALIKES)
    return re.sub(r"\s+", " ", t)


def deslip(t: str) -> str:
    """The usual OCR slips undone, for the never-open check only: "rn" read for "m" ("Forrnat"), a zero or a one
    inside a word ("F0rmat", "De1ete"), and a lower-case L for a capital I at a word's start ("lnitialize"). The text
    is not folded here: readings() judges the folded text as one more reading."""
    t = t.replace("|", "l").replace("rn", "m")
    t = re.sub(r"(?<=[a-z])0|0(?=[a-z])", "o", t)
    t = re.sub(r"(?<=[a-z])1(?=[a-z])", "l", t)
    return re.sub(r"\bl(?=[bcdfghjkmnpqrstvwxz])", "i", t)


def clean_label(text: str) -> str:
    """Strip the icon glyphs OCR puts in front of labels ("S Focus Area" -> "focus area")."""
    t = re.sub(r"^[^A-Za-z0-9(]+", "", (text or "").strip())
    t = re.sub(r"^(?:[A-Za-z0-9]{1,2}\s+)(?=[A-Z(])|^[a-z](?=[A-Z])", "", t)
    return t.strip().lower()


def _capital_i(text: str) -> str:
    """OCR's capital I for a lower-case L inside a word ("Delete AII"), as an L: one more reading to judge."""
    return re.sub(r"(?<=[A-Za-z])I", "l", text)


def _sources(text) -> list:
    """The text as read, folded, and folded with OCR's capital I read as an l: in their own case, which clean_label
    needs to tell an icon from a label."""
    folded = fold(text)
    return list(dict.fromkeys((str(text or ""), folded, _capital_i(folded))))


def readings(text) -> list:
    """Every reading of a text the guards judge, in lower case: as read, folded (fold) and folded with OCR's capital I
    read as an l, each also with the usual OCR slips undone (deslip). A guard refuses when any of them matches, so
    another reading only ever adds a refusal (never_lifted; drive.py's Enter guard once it takes it)."""
    out = []
    for s in _sources(text):
        low = s.lower()
        out += [low, deslip(low)]
    return list(dict.fromkeys(out))


def _pairs(label) -> list:
    """(the label cleaned of its icon, the label as read), in lower case, for each source (_sources) and each also with
    the usual slips undone (deslip): every text never_open judges. The second of each pair is readings()'s."""
    pairs = []
    for s in _sources(label):
        text, raw = clean_label(s), s.lower()
        pairs += [(text, raw), (deslip(text), deslip(raw))]
    return list(dict.fromkeys(pairs))


def never_open(label: str) -> str | None:
    """Reason the row must not be entered, or None. A label that carries its breadcrumb
    ("Playback > Delete > Delete Slot1/2") is judged by its last part too, and an OCR reading also as it
    reads with the usual slips undone ("lnitialize", "Forrnat"), folded ("Fоrmat", "Wi‑Fi Direct"), with a capital I
    read for an l ("Delete AII"), and with a stop or a colon after it ("Format."): a slip never opens a row. Each
    reading is judged beside the others (readings), so none takes another's refusal away. A Wi-Fi or Bluetooth setting
    or an address screen (NETWORK) is named only when no reading matches any other class: every reading is judged for an
    action, credentials, a by-hand row and motion first, so a reading that also looks like one of those keeps that
    reason, which no network decision lifts."""
    pairs = _pairs(label)
    for text, raw in pairs:
        last = clean_label(text.rsplit(">", 1)[-1])
        m = _ACTION_RE.search(text) or _ACTION_RE.search(last) or _ACTION_WORD_RE.search(text)
        if m:
            return f"action: {m.group(m.lastindex or 0)}"     # the label as the camera writes it, stop and all
        m = _CREDENTIALS_RE.search(text) or _CREDENTIALS_RE.search(raw)
        if m:
            return f"credentials: {m.group(0)}"
        m = _ANYWHERE_RE.search(text) or _ANYWHERE_RE.search(raw)
        if m:
            return f"by hand only: {m.group(0)}"
        m = _MOTION_RE.search(text) or _MOTION_RE.search(raw)
        if m:
            return f"{MOTION}: {m.group(0)}"
    for text, raw in pairs:
        m = _NETWORK_RE.search(text) or _NETWORK_RE.search(raw)
        if m:
            return f"{NETWORK}: {m.group(0)}"
    return None


def _literal(pattern: str) -> str:
    """A whole-label pattern of _ACTIONS as the name it matches written out in full ("reset network set\\.?" is "reset
    network set."): its optional characters kept, its escapes undone."""
    return re.sub(r"\\(.)", r"\1", re.sub(r"(\\?.)\?", r"\1", pattern))


# the actions the never-open list names whole, as names (group_refused compares a group's name with each)
_ACTION_NAMES = tuple(dict.fromkeys(_literal(p) for p in _ACTIONS))
# a name this short in letters and digits is one letter from too many words ("File" from "fire", which the list holds,
# "Copy" from "Coby"): only a longer one is compared one letter apart (group_refused)
GROUP_MIN = 5


def name_key(text) -> str:
    """A name as group_refused compares it: folded (fold), lower case, its letters and digits alone."""
    return re.sub(r"[^0-9a-z]", "", fold(text).lower())


def one_apart(a: str, b: str) -> bool:
    """Whether a and b are the same but for at most one letter read for another, dropped or put in. Past their common
    start, the rest of the shorter must be the rest of the longer less one letter (or, as long, less its first): two
    texts whose lengths differ by more than one never are."""
    if a == b:
        return True
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i + (len(a) == len(b)):] == b[i + 1:]


def group_refused(name, known=()) -> str | None:
    """Why the menu's group column must not step into the group named `name` (Right on it in the column: kit/crawl_run.py
    go_to's jump, and find_position's way back from the column), or None: never_open on it, every reading judged with
    its slips undone; or, in any reading (readings), one letter apart (a letter read for another, dropped or put in:
    "FTP Transter", 2026-11-13) from a name never_open refuses, of `known` (the group names the camera's definition and
    page model hold: runner.known_groups) or of the actions the list names whole (_ACTION_NAMES, "FTP Transfer" among
    them), both at least GROUP_MIN letters and digits long. Only adds refusals to never_open's, for group names alone:
    the rows' own checks (never_open, open_refused, path_refused) are as they were."""
    why = never_open(name)
    if why:
        return why
    keys = {k for k in (name_key(r) for r in readings(name)) if len(k) >= GROUP_MIN}
    for other in (*known, *_ACTION_NAMES):
        if not isinstance(other, str) or len(name_key(other)) < GROUP_MIN:
            continue
        reason = never_open(other)
        if reason and any(one_apart(k, name_key(other)) for k in keys):
            return f"{reason} (read as {str(name).strip()!r}, one letter from {other.strip()!r})"
    return None


def _network_match(label, rx) -> str | None:
    """The words of `label` the pattern `rx` matches in any text never_open judges (_pairs), or None."""
    for text, raw in _pairs(label):
        m = rx.search(text) or rx.search(raw)
        if m:
            return m.group(0)
    return None


def network_row(label: str) -> str | None:
    """Why `label` is a Wi-Fi or Bluetooth setting (_NETWORK_SETTINGS) in any reading, or None: whatever else it is too.
    A row so named is never opened by --allow, an approved motion decision or a run's may_open (decision 8), only by a
    dated decision naming it when never_open names nothing else (network_lifted)."""
    m = _network_match(label, _NETWORK_SETTINGS_RE)
    return f"a Wi-Fi or Bluetooth setting: {m}" if m else None


def address_screen(label: str) -> str | None:
    """Why `label` is a screen that shows the camera's network addresses (_ADDRESS_SCREENS) in any reading, or None.
    Only kit/drive.py opens one, where a decision names it (network_lifted's screens)."""
    m = _network_match(label, _ADDRESS_RE)
    return f"a screen with the camera's addresses: {m}" if m else None


def network_words(label: str) -> str | None:
    """network_row or address_screen: the words that keep `label` from every allowance but a network decision."""
    return network_row(label) or address_screen(label)


def identity_liftable(label: str) -> str | None:
    """The words that make `label` an identity, connection or region row a dated network decision may open to look at
    (_IDENTITY_LIFTABLE), or None: every reading (as never_open judges them) is judged, and any reading that names
    anything else of the never-open list (an action, "reset", credentials, the cards or Initialize, sound, light or
    motion, a Wi-Fi or Bluetooth setting or an address screen, or an identity row that stays closed, _IDENTITY_FIXED)
    gives None. Such a row stays refused by never_open, identity_row, never_lifted and allow_refused as ever: only
    network_lifted, for a run given --network whose decision names it, opens it, to look only (never_choose)."""
    found = None
    for text, raw in _pairs(label):
        last = clean_label(text.rsplit(">", 1)[-1])
        if _ACTION_RE.search(text) or _ACTION_RE.search(last) or _ACTION_WORD_RE.search(text):
            return None
        for rx in (_CREDENTIALS_RE, _NEVER_LIFTED_RE, _MOTION_RE, _OTHER_BY_HAND_RE, _IDENTITY_FIXED_RE, _NETWORK_RE):
            if rx.search(text) or rx.search(raw):
                return None
        m = _IDENTITY_LIFTABLE_RE.search(text) or _IDENTITY_LIFTABLE_RE.search(raw)
        found = found or (m.group(0) if m else None)
    return found


# The classes a network decision lifts a row from (lift_class): the words the logs and the decision's print use
LIFT_NETWORK, LIFT_ADDRESS, LIFT_IDENTITY = "Wi-Fi or Bluetooth setting", "address screen", "identity or connection row"


def lift_class(label: str) -> str | None:
    """The class of the never-open list a network decision may lift `label` from, or None: a Wi-Fi or Bluetooth setting
    or an address screen (never_open names NETWORK and nothing else, never_lifted nothing), or an identity, connection
    or region row (identity_liftable)."""
    why = never_open(label)
    if not why:
        return None
    if why.startswith(NETWORK + ":") and not never_lifted(label):
        return LIFT_ADDRESS if address_screen(label) else LIFT_NETWORK
    return LIFT_IDENTITY if identity_liftable(label) else None


def never_choose(row) -> str | None:
    """Why no option of `row` is ever chosen, whatever a decision names (_NEVER_CHOOSE: the choice drops the link,
    starts a connection or a pairing, or changes what no file puts back), or None."""
    for r in readings(row):
        m = _NEVER_CHOOSE_RE.search(r)
        if m:
            return f"no option of a row naming {m.group(0)!r} is chosen, whatever a decision names"
    return None


# Never entered whatever a run is allowed (drive.py --allow, an owner decision): anything on the cards, settings
# included (decision 4), Initialize and Reset Network Set. (decision 5), and credentials (decision 9); never_lifted adds
# the camera's identity, its connections and its region (decision 8: identity_row)
_NEVER_LIFTED_RE = re.compile(r"\b(?:format|delete)\b|initiali[sz]e|reset network|" + "|".join(_CREDENTIALS))


def identity_row(label: str) -> str | None:
    """Why no allowance may let a run set this row, or None: the camera's identity, a connection or the region (USB,
    language, NTSC/PAL, area and date, network identity: decision 8), every reading judged, as in never_open. A by-hand
    row of sound or light (a volume) is not one: the owner's word for the row may open it. Nor is a Wi-Fi or Bluetooth
    setting or an address screen (network_words): no --allow opens one either (allow_refused), but a dated decision
    naming the row may (network_lifted)."""
    for text in readings(label):
        m = _IDENTITY_RE.search(text)
        if m:
            return f"by hand only, whatever is allowed: {m.group(0)} (docs/decisions/0008)"
    return None


def never_lifted(label: str) -> str | None:
    """Why no allowance may open this row, or None (every reading judged, as in never_open): anything on the cards,
    Initialize, Reset Network Set. and credentials (decisions 4, 5 and 9), and the camera's identity, a connection or
    its region (decision 8: identity_row). live.open_refused, drive.py's path check and allow_refused take it, so no
    name a run was given opens one of these rows."""
    for text in readings(label):
        m = _NEVER_LIFTED_RE.search(text)
        if m:
            return f"never, whatever is allowed: {m.group(0)} (docs/decisions/0004, 0005, 0009)"
    return identity_row(label)


# an action's name anywhere in a screen's text, as a word ("Camera Set. Memory" in a title, "Delete" on a button):
# screen_refused judges a whole screen with it, where never_open judges one row's label whole
_ACTION_ANY_RE = re.compile(r"(?<![a-z])(" + "|".join(_ACTIONS) + r")(?![a-z])")


def screen_refused(text: str, allow=()) -> str | None:
    """Why a press nobody could read the target of may not be sent on a screen whose whole text is `text` (drive.py's
    enter!:REGEX, the operator vouching for Enter where nothing lit can be read), or None: any reading of the text
    names, anywhere, what the never-open list holds (an action's name as a word, credentials, a by-hand row, sound,
    light or motion, "reset"). A name the run was given (drive.py --allow) lifts its own words on the screen, never what
    never_lifted names (the cards, Initialize, Reset Network Set., credentials, and the camera's identity, a connection
    or its region: decision 8), nor a Wi-Fi or Bluetooth setting or an address screen, whatever a decision names: a
    vouched Enter never goes out where one is named. Fails closed: a word in a footer or a description refuses too."""
    for r in readings(text):
        m = _NEVER_LIFTED_RE.search(r)
        if m:
            return f"the screen reads {m.group(0)!r}: never, whatever is allowed"
        m = _IDENTITY_RE.search(r)
        if m:
            return f"the screen reads {m.group(0)!r}: by hand only, whatever is allowed (docs/decisions/0008)"
        m = _NETWORK_RE.search(r)
        if m:
            return (f"the screen reads {m.group(0)!r}: a Wi-Fi or Bluetooth setting or an address screen, never vouched "
                    "for (docs/decisions/0008)")
    names = [n for n in (clean_label(fold(m)) for m in allow) if n]
    for r in readings(text):
        for n in names:
            r = r.replace(n, " ")
        for why, rx in (("action", _ACTION_ANY_RE), ("action", _ACTION_WORD_RE), ("credentials", _CREDENTIALS_RE),
                        ("by hand only", _ANYWHERE_RE), (MOTION, _MOTION_RE)):
            m = rx.search(r)
            if m:
                return f"the screen reads {m.group(0)!r} ({why})"
    return None


def owner_may_approve(reason: str | None) -> bool:
    """A never_open reason a dated owner decision may lift for the one row it names (decision 2: "the owner may
    approve one change at a time when it is harmless"). Actions, credentials and identity rows never."""
    return bool(reason) and reason.startswith(MOTION + ":")


def approved_rows(scope: dict) -> set:
    """The rows a dated owner decision in a reviewed scope names: {"date": "YYYY-MM-DD", "rows": [...], "why"}. A
    decision that says what it lifts ("lifts": a network decision, network_decided) is no such approval and is left
    out."""
    out = set()
    for d in scope.get("decisions") or []:
        if isinstance(d, dict) and "lifts" not in d and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d.get("date", ""))):
            out |= {str(r) for r in d.get("rows") or []}
    return out


def allow_refused(label: str) -> str | None:
    """Why `--allow LABEL` cannot name this row, or None: anything on the cards, Initialize, Reset Network Set. and
    credentials (decisions 4, 5 and 9), and the camera's identity, a connection or its region (decision 8), whatever the
    owner said: never_lifted. drive.py and card_actions.py judge their --allow so, and every prover through
    runner.allowed_or_exit, before anything connects; path_refused, live.open_refused and screen_refused refuse those
    rows however a run named them. A Wi-Fi or Bluetooth setting or an address screen (network_words, whatever else the
    label is) is refused too: only a dated owner decision naming the row opens it, for a run given --network
    (network_lifted), never a run's --allow."""
    if re.search(r"\b(format|delete)\b", label, re.I):
        return "nothing on the cards is formatted or deleted remotely, not even its settings (docs/decisions/0004)"
    hard = never_lifted(label)
    if hard:
        return f"{hard}; no --allow opens it"
    net = network_words(label)
    if net:
        return (f"{net}: by hand only, and opened remotely only where a dated owner decision names the row (--network, "
                "docs/decisions/0008); no --allow opens it")
    return None


def named(label: str, allow) -> bool:
    """Whether a run's --allow words (`allow`) name `label` itself, for a run that opens that one row only with its
    owner's word: compared folded (fold), case and spacing aside, or as the guards clean a reading (clean_label, as
    live.open_refused compares them), so "reg. custom shoot set" names Reg. Custom Shoot Set."""
    def said(x) -> str:
        return " ".join(fold(x).casefold().split())
    want = {said(label), clean_label(fold(label))} - {""}
    return any({said(x), clean_label(fold(x))} & want for x in allow or ())


def allowance(labels, today: str | None = None) -> str:
    """The words a proof line carries for the never-open rows the owner allowed this run ("" when none)."""
    import datetime
    day = today or datetime.date.today().isoformat()
    return "; ".join(f"the owner allowed {x} remotely, {day}" for x in labels)


def path_refused(path: list, approved: set = frozenset(), allowed=(), network=frozenset()) -> str | None:
    """Why a row (its path of labels) is not opened, or None: never_open on any label of the path, except a
    sound/light/motion reason for a row a dated owner decision names ("Silent Mode Settings > ... > Shutter When
    Pwr OFF"), a label the run was given with --allow (never what allow_refused refuses), or a Wi-Fi or Bluetooth
    setting a network decision names (`network`, network_decided's rows, for a run given --network: network_lifted,
    never an address screen). A label with a network setting's or an address screen's words in it is lifted by the
    last alone, whatever other reason it reads as."""
    name = " > ".join(path)
    for label in path:
        why = never_open(label)
        if not why:
            continue
        if network and network_lifted(label, network):
            continue
        if label in allowed and not allow_refused(label):
            continue
        if not (owner_may_approve(why) and name in approved and not network_words(label)):
            return why
    return None


def _valid_day(text) -> bool:
    """A calendar day written YYYY-MM-DD, today or before ("2026-11-13"; never "2026-13-45", "someday" or a day still to
    come: a decision is one the owner has made)."""
    import datetime
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return False
    try:
        day = datetime.date.fromisoformat(text)
    except ValueError:
        return False
    return day <= datetime.date.today()


def network_refused(row) -> str | None:
    """Why a network decision cannot name `row`, or None: the row must be one label as the camera writes it (no path),
    of a class a network decision lifts (lift_class: a Wi-Fi or Bluetooth setting, an address screen, or an identity,
    connection or region row of _IDENTITY_LIFTABLE) and of nothing else. Credentials, the cards, Initialize, Reset
    Network Set., an action (SSID/PW Reset, WPS Push, Pairing, Reset Transfer Status), the identity rows that stay
    closed (_IDENTITY_FIXED: the serial number among them, and the rows whose opening may start or end a connection or
    act, _NOT_LIFTED_WHY saying why), anything that reads as another class too, and a name the list does not know or
    that names a group ("Wi-Fi") are refused."""
    if not isinstance(row, str) or not row.strip():
        return "a row is named by its label, as the camera writes it"
    if ">" in row:
        return "a row is named by its own label, not a path"
    if lift_class(row):
        return None
    for rx, why in _NOT_LIFTED_WHY:
        if any(rx.search(r) for r in readings(row)):
            return f"{why}: no decision opens it (docs/decisions/0008)"
    hard = never_lifted(row)
    if hard:
        return hard
    why = never_open(row)
    if not why:
        return ("not a row the never-open list names that a decision may open: a group's or an unknown name opens "
                "nothing")
    return f"{why}: no decision opens that"


def plain(text) -> str:
    """A label, an option or a value as the network checks compare them: folded (fold), the signs at either end that an
    icon, a radio button or a stop reads as left out (a + or - sign kept), spacing one space, case folded. No short
    first word is dropped (clean_label drops one for the other guards, an icon OCR reads as letters): the whole text is
    compared, so "No Wi-Fi Connect" is never "Wi-Fi Connect"."""
    t = re.sub(r"^[^0-9A-Za-z(+\-±]+|[^0-9A-Za-z)+\-±%]+$", "", fold(text).strip())
    return " ".join(t.split()).casefold()


# The words a button or a key says (an OK, a Cancel, a keyboard's Done), which no decision names as an option: Enter on
# one commits or cancels, whatever the decision meant (option_refused)
BUTTON_WORDS = frozenset({"ok", "enter", "execute", "yes", "no", "cancel", "set", "done"})


def option_refused(option) -> str:
    """Why a network decision may not name `option` as one the kit chooses, or "": an option is a row's own value as
    the list writes it ("On", "Off", "Enable", "5GHz"), compared folded (plain). Refused: no text, one character (a
    keyboard's key, a lone digit), a button's word (BUTTON_WORDS: OK, Execute, Cancel, Done...), and anything the
    never-open list names (never_open: credentials, an action, an identity or connection row) or that names identity or
    credentials on a screen (identity_screen: a password, an SSID, a PIN, a pairing)."""
    seen = plain(option) if isinstance(option, str) else ""
    if not seen:
        return "an option is named by its text, as the list writes it"
    if len(seen) == 1:
        return "one character is a keyboard's key or a digit, never an option a decision names"
    if seen in BUTTON_WORDS:
        return "a button's word, which commits or cancels, never an option a decision names"
    why = never_open(option) or identity_screen(option)
    return f"it reads as what no decision lets the kit choose ({why})" if why else ""


def _network_decisions(scope) -> tuple:
    """(rows {row: date}, options {row: [options a decision lets the kit choose]}, refusals) of a reviewed scope's
    network decisions: network_decided's reading, with each decision's "options"."""
    rows, options, refusals = {}, {}, []
    decisions = scope.get("decisions") if isinstance(scope, dict) else None
    for i, d in enumerate(decisions if isinstance(decisions, list) else []):
        if not isinstance(d, dict) or d.get("lifts") != NETWORK_LIFT:
            continue
        where, day = f"decision {i + 1}", d.get("date")
        if not _valid_day(day):
            refusals.append(f"{where}: its date {day!r} is not a day written YYYY-MM-DD, today or before, so it lifts "
                            "nothing")
            continue
        if not isinstance(d.get("why"), str) or not d["why"].strip():
            refusals.append(f"{where} ({day}): it says no why, so it lifts nothing")
            continue
        named = d.get("rows")
        if not isinstance(named, list) or not named:
            refusals.append(f"{where} ({day}): it names no rows")
            continue
        accepted = []
        for row in named:
            why = network_refused(row)
            if why:
                refusals.append(f"{where} ({day}) names {row!r}: {why}")
            else:
                rows.setdefault(row.strip(), day)
                accepted.append(row.strip())
        chosen = d.get("options")
        if chosen is None:
            continue
        if not isinstance(chosen, dict):
            refusals.append(f"{where} ({day}): its \"options\" is not an object naming, for a row it names, the options "
                            "the kit may choose ({\"<row>\": [\"<option>\", ...]})")
            continue
        listed = {r.strip() for r in named if isinstance(r, str)}
        for row, opts in chosen.items():
            if not isinstance(row, str) or row.strip() not in listed:
                refusals.append(f"{where} ({day}): its \"options\" name {row!r}, a row it does not name in \"rows\"")
            elif not isinstance(opts, list) or not opts or not all(isinstance(o, str) and plain(o) for o in opts):
                refusals.append(f"{where} ({day}): its \"options\" for {row!r} are not a list of option names")
            elif any(option_refused(o) for o in opts):
                bad = next(o for o in opts if option_refused(o))
                refusals.append(f"{where} ({day}): its \"options\" for {row!r} name {bad!r}: {option_refused(bad)}")
            elif address_screen(row):
                refusals.append(f"{where} ({day}): its \"options\" name {row!r}, an address screen, which has no "
                                "option to choose")
            elif never_choose(row):
                refusals.append(f"{where} ({day}): its \"options\" name {row!r}: {never_choose(row)} (the choice drops "
                                "the link, starts a connection or a pairing, or changes what no file puts back)")
            elif row.strip() in accepted:
                have = options.setdefault(row.strip(), [])
                have += [o.strip() for o in opts if plain(o) not in {plain(x) for x in have}]
    return rows, options, refusals


def network_decided(scope) -> tuple[dict, list]:
    """({row: the decision's date}, [why each other thing is refused]) of a reviewed scope's dated owner decisions that
    open Wi-Fi and Bluetooth rows: {"lifts": "network", "date": "YYYY-MM-DD", "rows": [labels], "why": "...", and,
    to let the kit choose some options, "options": {"<row>": ["<option>", ...]}} under "decisions" (decision 8). A
    decision without "lifts": "network" counts for nothing here (a motion decision, or one that names a row to keep it
    by hand, as the a1 II's owner's of 2026-10-30 named Bluetooth Rmt Ctrl); one with it but no valid date (a day today
    or before), no why or no rows is refused whole; each row it names that network_refused refuses (credentials,
    identity, an action, the serial number, a vague name) is refused alone, and so is an "options" that is no object, or
    names a row the decision does not name, an address screen, no list of options or an option option_refused refuses
    (one character, a button's word, a name of the never-open list or of identity). A row named twice keeps its first
    date. The options are network_options'."""
    rows, _, refusals = _network_decisions(scope)
    return rows, refusals


def network_options(scope) -> dict:
    """{row: [the options a dated owner decision lets the kit choose in it]} for the rows network_decided accepts. A
    row with none is opened to look only: its options are read, and none is chosen (look_refused)."""
    return _network_decisions(scope)[1]


def row_read_as(row: str, texts) -> bool:
    """Whether `texts`, every reading the page model keeps of one menu row (its label and each reader's reading of it),
    stand for the decided row `row`: one reading of it is `row` exactly once folded (plain), and every reading of it is
    of `row`'s own class (lift_class, the same for each: none names an action, credentials, the cards, Initialize, an
    identity row that stays closed, sound, light or motion, or another class, and none names nothing the list holds). A
    reader that read the row right then vouches for the readings beside it ("LANIP Address Setting", OCR's reading of
    the Wired LAN page's icon glued to "IP Address Setting", with the vision reader's "IP Address Setting"), and no
    reading of the row widens the class the row is judged by."""
    cls, want = lift_class(row), plain(row)
    texts = [t for t in texts or () if isinstance(t, str) and t.strip()]
    if cls is None or not want or want not in {plain(t) for t in texts}:
        return False
    return all(lift_class(t) == cls for t in texts)


# What OCR reads a row's icon as, glued to the front of its label: the a1 II's Wired LAN page draws a LAN icon, read as
# "LAN" in "LANIP Address Setting" (2026-11-13). At most this many letters or digits, with no space after them
ICON_MAX = 4


def group_words(group) -> set:
    """The words of a menu group's name (its letters and digits, folded: "Wired LAN" is wired and lan)."""
    return set(re.findall(r"[0-9a-z]+", plain(group or "")))


def glued_icon(prefix: str, row: str, group) -> str | None:
    """Why `prefix`, read glued to the front of the decided row `row`'s label on a page of the menu group `group`, is no
    icon of that page, or None when it may be one: it must be a word of the group's own name (group_words: "lan" of
    "Wired LAN"), at most ICON_MAX letters and digits; never_open must name nothing in it alone and identity_screen
    nothing either (a WPS, a PW, a PIN glued on is no icon: their word-boundary patterns never fire on glued text); and
    the label read with it set apart must stay of `row`'s class (lift_class). A word read in front of a label ("No",
    "Off", "Del") is no icon of the page, and stays another label."""
    p = fold(prefix).casefold()                     # as read, a space after it kept: "lan " is no glued icon
    if not p or len(p) > ICON_MAX or p not in group_words(group):
        return f"{p!r} is no word of the page's group {group!r} of at most {ICON_MAX} letters"
    why = never_open(p) or identity_screen(p)
    if why:
        return f"{p!r} reads as what the never-open list or identity holds ({why})"
    if lift_class(f"{p} {row}") != lift_class(row):
        return f"{row!r} read with {p!r} before it is of another class"
    return None


def lifted_readings(row: str, readings=None) -> set:
    """The texts (plain) a lit bar may start with to name the decided row `row`: `row` itself, and each reading of an
    entry of `readings` ({row: [{"group": the page's group name, "readings": [texts]}]}, runner.network_readings: every
    reading the page model keeps of one menu row, and the group of the page it is on) that stands for it (row_read_as)
    and is `row` with an icon of that page read as letters glued to its front (glued_icon). Two readers agreeing, never
    one alone: a reading lifts nothing unless another reader of the same row read it as `row` exactly, every reading of
    the row is of `row`'s class, and what it adds is a word of the page's own group name, glued on. An entry naming no
    group (a list of readings alone) adds nothing."""
    want = plain(row)
    out = {want} - {""}
    for entry in (readings or {}).get(row, ()) or ():
        texts = entry.get("readings") if isinstance(entry, dict) else None
        if not isinstance(texts, (list, tuple)) or not row_read_as(row, texts):
            continue
        for t in texts:
            seen = plain(t) if isinstance(t, str) else ""
            if want and seen.endswith(want) and seen != want \
                    and glued_icon(seen[:-len(want)], row, entry.get("group")) is None:
                out.add(seen)
    return out


def bar_on_row(lit, row: str, readings=None) -> bool:
    """Whether a lit bar, as read (`lit`), is on the decided row `row`: it starts with the row's label, or with a reading
    of it lifted_readings takes (the row's icon glued on), followed by nothing alphanumeric (its value may follow). A
    network row's lock ends on its page only with the bar on the row itself (camkit.live and kit/drive.py
    network_left)."""
    seen = plain(lit or "")
    return any(w and seen.startswith(w) and not seen[len(w):len(w) + 1].isalnum() for w in lifted_readings(row, readings))


def network_lifted_row(lit: str, decided, screens: bool = False, values=None, readings=None) -> str | None:
    """The row of `decided` (a network decision's rows) that opens the row whose text, as read, is `lit`, or None.
    The text must be of a class a network decision lifts and of nothing else (lift_class: a Wi-Fi or Bluetooth setting
    or an address screen, never_lifted naming nothing; or an identity, connection or region row of _IDENTITY_LIFTABLE,
    identity_liftable); the text, compared whole (plain: no first word dropped), must start with a row the decision
    names (each one a decision may name: network_refused), or with a reading of the same menu row that another reader
    read as that row exactly, an icon of its page glued on (`readings`, {row: [entries]}: lifted_readings, row_read_as,
    glued_icon; its class the row's, every reading of it judged), and what follows the label must be nothing or one of
    that row's own values (`values`, {row: [values]} as the page model and the definition know them: a menu row's bar
    carries its value after its label); with no values known for the row, nothing may follow. So "Wi-Fi Connect On"
    opens Wi-Fi Connect where On is one of its values, and "Wi-Fi Connect Settings" or "No Wi-Fi Connect" never do;
    "LANIP Address Setting" opens IP Address Setting only where the page model's row on the Wired LAN page holds both
    readings. An address screen only where the caller looks at one (`screens`: kit/drive.py alone), never for the
    walker or the provers."""
    cls = lift_class(lit) if decided else None
    if cls is None or (cls == LIFT_ADDRESS and not screens):
        return None
    seen = plain(lit)
    for row in decided:
        if network_refused(row) or (not screens and address_screen(row)):
            continue
        known = {plain(v) for v in (values or {}).get(row, ()) if plain(v)}
        for want in sorted(lifted_readings(row, readings), key=len, reverse=True):
            if not seen.startswith(want) or seen[len(want):len(want) + 1].isalnum():
                continue
            rest = plain(seen[len(want):])
            if not rest or rest in known:
                return row
    return None


def network_lifted(lit: str, decided, screens: bool = False, values=None, readings=None) -> bool:
    """Whether a network decision opens the row whose text is `lit` (network_lifted_row)."""
    return network_lifted_row(lit, decided, screens, values, readings) is not None


def network_allowance(decided, options=None) -> str:
    """The words a proof line carries for the rows a network decision opened ("" when none): {row: date}, and the
    options it lets the kit choose ({row: [options]})."""
    def chosen(row) -> str:
        opts = (options or {}).get(row)
        return f" and choose {', '.join(opts)}" if opts else ", to look only"
    return "; ".join(f"the owner decided on {day} that the kit may open {row} remotely{chosen(row)}"
                     for row, day in decided.items())


# Inside a row a network decision opened (its list, its panel, whatever it led to), the keys that read its options or
# close it; every other key can choose or commit an option (Enter, a carousel's or a panel's Right, a dial)
LOOK_KEYS = frozenset({"up", "down", "ms_up", "ms_down", "menu"})


def look_refused(key, lit, row: str, options=()) -> str:
    """Why `key` may not go out while the row `row` a network decision opened is open, or "": up, down and MENU
    (LOOK_KEYS) read its options or close it; Enter (or the multi-selector's centre) chooses only an option the decision
    names for the row (`options`), the lit text (`lit`, as read now) being that option once folded (plain): an
    unreadable or misread one refuses. Every other key (Right, Left, a dial, C4...) can commit a carousel's or a
    panel's option and is refused. A row with no option named is opened to look only."""
    k = canonical_input(key)
    if k in LOOK_KEYS:
        return ""
    if k in ("enter", "ms_enter"):
        if never_choose(row):
            return f"inside {row!r}: {never_choose(row)} (docs/decisions/0008)"
        if not options:
            return (f"the owner's decision opens {row!r} to look only: no option of it is chosen unless the decision names "
                    "it (\"options\", docs/decisions/0008)")
        if not plain(lit):
            return f"the lit option inside {row!r} cannot be read, so nothing is chosen"
        if plain(lit) not in {plain(o) for o in options}:
            return f"the lit option {str(lit).strip()!r} is not one the decision lets the kit choose in {row!r}"
        return ""
    return (f"{key!r} could choose or commit an option inside {row!r}, which a decision opens to look at its options: "
            "only up, down, MENU and Enter on an option the decision names go out there (docs/decisions/0008)")


# What a screen met inside a row a network decision opened may hold that names the camera's identity, a connection or
# credentials: a pairing screen ("Pairing", "Searching..."), a connecting notice naming an SSID, an access point or a
# device's name, an address. Every pattern of _IDENTITY, _CREDENTIALS and _ADDRESS_SCREENS, and these words besides
_IDENTITY_SCREEN = [r"pairing", r"paired", r"ssid", r"access point", r"device name", r"dev[il1|!]ce\s?addr",
                    r"mac\s?addr", r"ip\s?addr", r"password", r"pass\s?key", r"\bpw\b", r"\bwps\b", r"\bpin\b",
                    r"searching", r"awaiting\s?connect", r"connecting", r"connected to", r"connect\s?to\b", r"user\s?name",
                    r"account", r"server"]
_IDENTITY_SCREEN_RE = re.compile("|".join(_IDENTITY_SCREEN + _IDENTITY + _CREDENTIALS + _ADDRESS_SCREENS))
# What, on a screen met inside an identity or connection row a decision opened, gets MENU alone and nothing of its text
# kept: credentials, and a connection, a pairing or a network list in the making (an SSID list, an access point, a
# pass key or PIN, "Searching...", "Connecting...")
_SECRET_SCREEN = [r"ssid", r"access point", r"password", r"pass\s?key", r"\bpw\b", r"\bpin\b", r"pairing",
                  r"searching", r"awaiting\s?connect", r"connecting", r"connected to", r"connect\s?to\b", r"\bwps\b"]
_SECRET_SCREEN_RE = re.compile("|".join(_SECRET_SCREEN + _CREDENTIALS))
# the kinds of screen whose text may be shown inside such a row when it holds no such word: the row's own list or
# carousel, a notice, and the menu pages around it; any other kind (unknown above all) is shown as its field names
SHOWN_KINDS = frozenset({"list", "dialog", "sidelist", "checklist", "notice", "menu", "submenu", "tiles", "shooting"})


def identity_screen(text) -> str | None:
    """Why a screen's whole text names the camera's identity, a connection or credentials (any reading:
    _IDENTITY_SCREEN), or None. Inside a row a network decision opened, such a screen gets MENU alone, no reader, and
    its text is shown and kept as its field names only (network_withheld)."""
    for r in readings(text):
        m = _IDENTITY_SCREEN_RE.search(r)
        if m:
            return f"identity or credentials: {m.group(0)}"
    return None


# The notices the kit knows a greyed row answers Right with (camkit.crawl keeps one for a Wi-Fi or Bluetooth setting a
# network decision opened: notice_kept), each its whole text once folded, spacing as one space and the OK button left
# out: the camera's "This function is currently disabled." (kit/schema_update.py DISABLED_RE) and "This operation or
# setting not available."; and the blocker form (_NOTICE_FOLLOWS), "... not available as follows" and, after it, the
# setting that blocks it with its value (kit/proving/screens.py refuse_or_fail), whose part after "as follows" is kept
# only where it is a row label the kit knows, or one and a value it knows for that row (blocker_known)
_NOTICE_SHAPES = [re.compile(p) for p in (
    r"this function is currently disabled\.?",
    r"this operation or setting (?:is )?not available\.?",
)]
_NOTICE_FOLLOWS = re.compile(r"(this operation or setting (?:is )?not available as follows)\b\W*([^?]{0,80})", re.I)
_NOTICE_OK = re.compile(r"[\s•●]*\bok\b[\s•●.]*$", re.I)


def blocker_known(tail, labels=(), values=None) -> bool:
    """Whether what a blocker notice names after "as follows" (`tail`) is a row label the kit knows (`labels`:
    runner.known_labels), alone or followed by one of the values it knows for that row (`values`, {label: [values]}:
    runner.row_values), all compared as plain: "Airplane Mode On". An address, a device's name, an SSID or anything else
    the kit does not know as a label is not."""
    seen = plain(tail)
    known = {plain(x) for x in labels or () if isinstance(x, str) and plain(x)}
    told = {plain(k): {plain(v) for v in vs if isinstance(v, str) and plain(v)}
            for k, vs in (values or {}).items() if isinstance(k, str)}
    if not seen:
        return False
    if seen in known:
        return True
    return any(seen.startswith(k + " ") and plain(seen[len(k):]) in told.get(k, ()) for k in known)


def notice_kept(text, labels=(), values=None) -> str:
    """The text of a notice as the kit keeps it for a Wi-Fi or Bluetooth setting a network decision opened, or "": its
    whole text (folded, spacing as one space, the OK button left out) when it is one of the notices the kit knows
    (_NOTICE_SHAPES); for the blocker form (_NOTICE_FOLLOWS), its fixed sentence, and what it names after "as follows"
    only where that is a row label the kit knows, or one and one of that row's known values (blocker_known, `labels` and
    `values` as runner.known_labels and runner.row_values give them), else the fixed sentence alone. Nothing at all where
    the text holds a question, reads as a confirmation anywhere (confirmation, on the whole text and on what follows "as
    follows"), names identity or credentials (identity_screen: an SSID, a device's name, a pairing, an address, a
    connection) or anything no allowance opens (never_lifted), or is of no shape the kit knows: then the frame is the
    evidence, as before 2026-11-13."""
    t = _NOTICE_OK.sub("", " ".join(fold(text).split())).strip()
    m = _NOTICE_FOLLOWS.fullmatch(t)
    tail = t[m.start(2):].strip() if m else ""
    if not t or "?" in t or confirmation(t) or confirmation(tail) or identity_screen(t) or never_lifted(t):
        return ""
    if any(rx.fullmatch(t.lower()) for rx in _NOTICE_SHAPES):
        return t
    if not m:
        return ""
    head = t[:len(m.group(1))]
    return f"{head} {tail}" if tail and blocker_known(tail, labels, values) else head


_QUOTED_TEXT = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")


def quoted_withheld(message) -> str:
    """A message with every quoted text in it withheld: what a run prints or keeps of a refusal or an error inside a
    network row, or on an address run, whose quoted parts can be a screen's or a row's text."""
    return _QUOTED_TEXT.sub("'(withheld)'", str(message))


def inside_menu_only(cls: str, kind, text) -> str | None:
    """Why only MENU may go out on a screen met inside a row a network decision opened from class `cls` (lift_class),
    or None, its kind and whole text as read: an address screen always; inside an identity, connection or region row,
    a screen of a kind whose text is not shown (SHOWN_KINDS: a keyboard, an address entry read as no known kind) or one
    naming credentials or a connection or network list in the making (_SECRET_SCREEN); inside a Wi-Fi or Bluetooth
    setting, a screen naming identity or credentials at all (identity_screen); and inside any of them a screen that
    reads as no known kind ("unknown": an information screen such as Display FTP Result's, a keyboard, a pairing list,
    or the row's own screen read as the shooting screen right after it opened, camkit.live and kit/drive.py), which no
    rule of the reader can say is the row's own list. Then no reader is asked either, and nothing of the text is kept
    but its field names and whole row labels."""
    if cls == LIFT_ADDRESS:
        return "an address screen"
    if kind == "unknown":
        return "a screen of no known kind inside the row (an information screen, a keyboard or an entry screen)"
    if cls == LIFT_IDENTITY:
        if kind not in SHOWN_KINDS:
            return f"a {kind!r} screen inside an identity row (a keyboard or an entry screen)"
        for r in readings(text):
            m = _SECRET_SCREEN_RE.search(r)
            if m:
                return f"credentials or a connection: {m.group(0)}"
        return None
    return identity_screen(text)


def network_withheld(kind, text) -> str | None:
    """Why a screen met inside a row a network decision opened is shown and kept as its field names alone
    (address_fields), never as read, or None when its text may be: a kind not in SHOWN_KINDS, or a text naming identity
    or credentials (identity_screen)."""
    if kind not in SHOWN_KINDS:
        return f"the screen reads as {kind!r}, no kind whose text is shown inside a network row"
    return identity_screen(text)


# The field names an address screen shows (Display Wi-Fi Info., Display Wired LAN Info., Disp Device Address), each
# with the readings a reader gives it: kit/drive.py shows and keeps these alone, never a value (address_fields)
ADDRESS_FIELDS = {
    "MAC Address": r"mac\s?addr(?:ess|\.)?",
    "IP Address": r"ip\s?addr(?:ess|\.)?",
    "Subnet Mask": r"subnet\s?mask",
    "Default Gateway": r"default\s?gateway",
    "Primary DNS Server": r"primary\s?dns(?:\s?server)?",
    "Secondary DNS Server": r"secondary\s?dns(?:\s?server)?",
    "IPv6 Link-local Address": r"ipv6\s?link\s?-?\s?local\s?addr(?:ess|\.)?",
    "IPv6 Address": r"ipv6\s?addr(?:ess|\.)?",
    "Link-local Address": r"link\s?-?\s?local\s?addr(?:ess|\.)?",
    "Device Address": r"dev[il1|!]ce\s?addr(?:ess|\.)?",
    "SSID": r"ssid",
    "Device Name": r"dev[il1|!]ce\s?name",
    "User Name": r"user\s?name",
    "Server": r"server",
}
_FIELD_RES = [(name, re.compile(rx + r"(?![a-z0-9])")) for name, rx in ADDRESS_FIELDS.items()]


def address_fields(lines, values=()) -> tuple[list, int]:
    """(the field names, each once and in order, the count of lines withheld) of an address screen's OCR lines (each a
    camkit.ocr Line or a text): a line that starts with a field name ADDRESS_FIELDS knows gives that name, as the list
    writes it, never as the line reads; any other line (a value: an address, an SSID, a device name), a field name
    with anything after it on its line, and a line that is wholly one of `values` (the values the definition and the
    page model know for the menu's rows: runner.known_values), counts as withheld. Never a value: what a run shows of
    such a screen."""
    told = {plain(v) for v in values or () if isinstance(v, str) and plain(v)}
    names, withheld = [], 0
    for ln in lines or ():
        text = str(getattr(ln, "text", ln) or "")
        if not text.strip():
            continue
        if plain(text) in told:
            withheld += 1
            continue
        found, whole = None, False
        for s in _sources(text):
            for r in (s.lower(), deslip(s.lower())):
                r = re.sub(r"^[^a-z0-9]+", "", r)
                for name, rx in _FIELD_RES:
                    m = rx.match(r)
                    if m:
                        found, whole = name, bool(re.fullmatch(r"[\s.:;]*", r[m.end():]))
                        break
                if found:
                    break
            if found:
                break
        if found and found not in names:
            names.append(found)
        withheld += not (found and whole)
    return names, withheld


def screen_fields(lines, labels=(), values=()) -> tuple[list, int]:
    """address_fields, keeping besides each line that is wholly one of `labels` (the menu's row labels, as the page model
    and the definition know them: a row's label is no value) as that label is written there, never as the line reads:
    what a --network run shows and keeps of a screen whose text it withholds. A row's value beside its label ("IP
    Address Setting  Manual") is no whole label, and is withheld with it; a line that is wholly one of `values` (the
    values the definition and the page model know for the menu's rows, runner.known_values: "Auto", an option's name)
    is withheld whatever `labels` hold, so a value that is also some row's or some path's label is never kept."""
    told = {plain(v) for v in values or () if isinstance(v, str) and plain(v)}
    known = {plain(x): x for x in labels or () if isinstance(x, str) and plain(x)}
    names, withheld = [], 0
    for ln in lines or ():
        text = str(getattr(ln, "text", ln) or "")
        if not text.strip():
            continue
        if plain(text) in told:
            withheld += 1
            continue
        label = known.get(plain(text))
        if label:
            names += [label] if label not in names else []
            continue
        got, hidden = address_fields([text])
        names += [n for n in got if n not in names]
        withheld += hidden
    return names, withheld


# The one reset an owner's word lets a run open (decision 5; the a1 II's owner, 2026-11-11, for the public sample): a
# Picture Profile's own Reset, the last row of the profile's settings panel, whose title is the profile's name ("PP1",
# runs/ILCE-1M2_fw4.00/kit2_panels 02353_down.png) and which asks "Reset PPn to the default setting?". Only
# kit/provers/pp_reset_run.py opens it, only with --allow PROFILE_RESET, and only where profile_reset_row says the lit
# row is that row and profile_reset_dialog says the screen after it is that question. Nothing else changes: the
# never-open list keeps "reset" for every row (_ACTION_WORD_RE: Setting Reset, Camera Settings Reset, Reset Network
# Set., this Reset too, for every other run), PROFILE_RESET lifts no row in drive.py or a LiveCamera (it names no
# row's own label), and never_lifted, allow_refused and drive.py's Enter guards are as they were.
PROFILE_RESET = "Picture Profile Reset"
PROFILE_NAME = re.compile(r"PP(\d{1,2})")
# words a profile's reset question never holds: another reset's (the camera's settings, the network, everything)
_NOT_PROFILE_RESET = re.compile(r"\b(?:all|camera|network|initiali[sz]e|format|delete|setting reset)\b")


def _profile_number(profile) -> str | None:
    m = PROFILE_NAME.fullmatch(fold(profile).strip())
    return m.group(1) if m else None


def profile_reset_row(lit: str, title: str, profile: str, second: str | None = None) -> str:
    """Why the lit row is not `profile`'s own Reset row, or "" when it is: the profile is named as the camera names one
    (PP and its number), every reading of the lit row's text is "Reset" alone (a stop after it aside: never "Setting
    Reset", "Camera Settings Reset", "Reset Network Set."), and the panel's title is that profile's (the profile's own
    settings, not another profile's or another menu's) by profile_reset_title: OCR's title as read (profile_title), or,
    where the vision model's reading `second` is given, OCR's and the vision model's agreeing (profile_title_agreed); a
    vision reading that names another profile refuses either way. Fails closed: a title or a row nobody could read is
    no Reset row."""
    n = _profile_number(profile)
    if n is None:
        return f"{profile!r} is not a Picture Profile's name (PP and its number)"
    lit_readings = [clean_label(s) for s in _sources(lit)] + [deslip(clean_label(s)) for s in _sources(lit)]
    if not (lit or "").strip() or not all(re.fullmatch(r"reset[\s.:;,!?…]*", r) for r in lit_readings):
        return f"the lit row reads {str(lit or '').strip()!r}, not Reset alone"
    if never_lifted(lit):
        return f"the lit row reads {str(lit).strip()!r}: {never_lifted(lit)}"
    return profile_reset_title(title, profile, second)[0]


def profile_reset_title(title: str, profile: str, second: str | None = None) -> tuple:
    """(why the panel's title is not `profile`'s, or "", the way it was accepted: "title" or "both readers", or None).
    The vision model's reading `second` (None: not asked or not reachable; "": it read nothing) is judged first: one
    that names another profile anywhere in its text ("Picture Profile PP10" for PP1; the digits' look-alikes read as
    digits: profile_names_in) refuses, whatever OCR read; so does OCR's title naming another profile anywhere. Then the
    first way, OCR's title as read
    (profile_title, strict), and the second, OCR's title naming the profile alone once folded and its digits'
    look-alikes read as digits (profile_title_names: "PРЗ" is PP3) and the vision model's reading the profile's name
    alone (profile_title_agreed): two readers agreeing. Anything else refuses."""
    t = str(title or "").strip()
    other = [n for n in profile_names_in(second) if n != profile] if second else []
    if other:
        return (f"the vision model reads the panel's title as {str(second).strip()!r}, naming {', '.join(other)}, not "
                f"{profile}"), None
    other = [n for n in profile_names_in(t) if n != profile]
    if other:
        return f"the panel's title reads {t!r}, naming {', '.join(other)}, not {profile}", None
    if profile_title(t, profile):
        return "", "title"
    if second is not None and profile_title_agreed(t, second, profile):
        return "", "both readers"
    said = ("" if second is None else f"; the vision model reads {str(second).strip()!r}" if second.strip()
            else "; the vision model read no title")
    return f"the panel's title reads {t!r}, not {profile} alone{said}", None


def profile_title(title: str, profile: str) -> bool:
    """Whether a panel's title (its top line, as read) is `profile`'s name alone in every reading ("PP1", "PP 1"; never
    "PP10" for PP1): the profile's own settings panel. A title nobody could read is not."""
    n = _profile_number(profile)
    rs = [r for r in readings(title) if r.strip()]
    return bool(n and rs) and all(re.fullmatch(rf"\W*pp\s*{n}\W*", r) for r in rs)


# Letters and signs OCR reads for digits, judged only in a profile's number (after "PP" or "User"). fold already turns
# the Cyrillic and Greek letters drawn as Latin ones into those ("PР3" is PP3), but no letter read for a digit: the
# a1 II's PP3 read as "PРЗ", a Cyrillic Р and a Cyrillic З, on the carousel and the panel's title (2026-11-11). Taken
# only where a second reading must agree (profile_title_agreed) or where no press follows (the carousel's list, the
# check after a panel is left): never alone for a guard.
_PROFILE_DIGITS = {"0": "OoОоΟο", "1": "lI|!іІ", "2": "Zz", "3": "ЗзƷʒ", "5": "SsЅѕ", "6": "бb", "8": "BВ"}
PROFILE_DIGIT_LOOKALIKES = str.maketrans({c: d for d, cs in _PROFILE_DIGITS.items() for c in cs})
# a name the carousel shows: PP or User, then its number in one or two characters (look-alikes among them), then the
# label's end or a sign ("User1: (No Import)"); an icon read in front as signs is let through, a letter is not
PROFILE_OPTION = re.compile(r"\W*(PP|User)\s*([0-9A-Za-z|!" + "".join(sorted({c for cs in _PROFILE_DIGITS.values()
                                                                             for c in cs}))
                            + r"]{1,2})(?![0-9A-Za-z])(?!\s*[0-9])", re.I)   # "PP 1 0" is not PP1
_PROFILE_OFF = re.compile(r"\W*[O0]ff\W*", re.I)


def profile_label_kind(label) -> tuple:
    """What a Picture Profile carousel option's label is, after fold and the digits' look-alikes: ("off", "Off");
    ("profile", "PP3"); ("other", "User1"), a Movie mode's User1-User4 (profiles that apply an imported LUT); or
    ("unread", None), a label no rule reads."""
    t = fold(label or "").strip()
    if _PROFILE_OFF.fullmatch(t):
        return "off", "Off"
    m = PROFILE_OPTION.match(t)
    if m:
        num = m.group(2).translate(PROFILE_DIGIT_LOOKALIKES)
        if re.fullmatch(r"[0-9]{1,2}", num) and int(num) >= 1:
            return ("profile", f"PP{int(num)}") if m.group(1).upper() == "PP" else ("other", f"User{int(num)}")
    return "unread", None


def profile_title_names(text) -> str | None:
    """The profile a panel's title names when its whole text, after fold and the digits' look-alikes
    (profile_label_kind), is that profile's name alone ("PРЗ" is PP3; "PP3 Gamma", "Picture Profile" and "User1" name
    none). Never a guard alone: profile_title_agreed takes it only with a second reader's agreeing."""
    t = fold(text or "").strip()
    m = PROFILE_OPTION.match(t)
    if not m or not re.fullmatch(r"\W*", t[m.end():]):
        return None
    kind, name = profile_label_kind(t)
    return name if kind == "profile" else None


# a profile's name anywhere in a text: PP not after a letter or digit ("Apps" holds none), its number in one or two
# characters (look-alikes among them), not followed by a letter, a digit or a spaced digit
_PROFILE_ANYWHERE = re.compile(r"(?<![0-9A-Za-z])PP\s*([0-9A-Za-z|!" + "".join(sorted({c for cs in _PROFILE_DIGITS.values()
                                                                                    for c in cs}))
                               + r"]{1,2})(?![0-9A-Za-z])(?!\s*[0-9])", re.I)


def profile_names_in(text) -> list:
    """Every profile (PP and a number) a text names anywhere, each once, after fold and the digits' look-alikes ("PРЗ"
    is PP3, "PP1O" PP10): a veto's reading, never a permission. "Picture Profile PP10" names PP10; "Picture Profile",
    "User1" and "Apps" name none."""
    out = []
    for m in _PROFILE_ANYWHERE.finditer(fold(text or "")):
        num = m.group(1).translate(PROFILE_DIGIT_LOOKALIKES)
        if re.fullmatch(r"[0-9]{1,2}", num) and int(num) >= 1:
            out.append(f"PP{int(num)}")
    return list(dict.fromkeys(out))


def profile_title_agreed(title: str, second: str, profile: str) -> bool:
    """The second way a panel's title is `profile`'s (pp_reset_run's guard before Reset, after the strict
    profile_title): OCR's title names the profile alone once folded and its digits' look-alikes read as digits
    (profile_title_names), AND the vision model's reading, independently, is the profile's name alone in every reading
    (profile_title). Two readers agreeing on the name; either one alone is not enough."""
    return bool(_profile_number(profile)) and profile_title_names(title) == profile and profile_title(second, profile)


def profile_reset_dialog(text: str, profile: str) -> str:
    """Why a screen's whole text is not `profile`'s own reset question, or "" when it is: the kit's confirmation check
    takes it for a confirmation (confirmation), some reading of it says reset, the profile's name and default in that
    order ("Reset PP1 to the default setting?"), every profile it names is that one (PP1, never PP10 or PP11 for it), and
    no reading names what no allowance opens (never_lifted: the cards, Initialize, Reset Network Set., credentials, the
    camera's identity; network_words: a Wi-Fi or Bluetooth setting, an address screen) or another reset's words (all,
    camera, network, Setting Reset). Anything else is no permission."""
    n = _profile_number(profile)
    if n is None:
        return f"{profile!r} is not a Picture Profile's name (PP and its number)"
    if not (text or "").strip():
        return "no text could be read on the screen"
    if not confirmation(text):
        return "the screen does not read as a confirmation"
    if never_lifted(text) or network_words(text):
        return f"the screen reads {never_lifted(text) or network_words(text)}"
    rs = readings(text)
    for r in rs:
        m = _NOT_PROFILE_RESET.search(r)
        if m:
            return f"the screen reads {m.group(0)!r}: not a Picture Profile's own reset"
        named = re.findall(r"\bpp\s*(\d{1,2})\b", r)
        if any(x != n for x in named):
            return f"the screen names {', '.join(f'PP{x}' for x in dict.fromkeys(named))}, not {profile} alone"
    other = [x for x in profile_names_in(text) if x != profile]
    if other:
        return f"the screen names {', '.join(other)} (the digits' look-alikes read as digits), not {profile} alone"
    if not any(re.search(rf"\breset\b.*\bpp\s*{n}\b.*\bdefault\b", r, re.S) for r in rs):
        return f"the screen does not read as 'Reset {profile} to the default setting?'"
    return ""


# The notice a profile's Reset ends with on the a1 II, after OK on its question: "Complete." over one lit button, OK
# (runs/ILCE-1M2_fw4.00/kit2_pp_reset_trial 00043_enter.png, 2026-11-11). The whole text, OK aside, is that word alone,
# a stop after it and spacing aside: no question, no Cancel, no other word.
_PROFILE_COMPLETE = re.compile(r"\s*complete\s*\.?\s*ok\s*\.?\s*")
_PROFILE_COMPLETE_SECOND = re.compile(r"\s*complete\s*\.?\s*(?:ok\s*\.?\s*)?")


def profile_reset_complete(text: str, lit: str, second: str | None = None) -> str:
    """Why the screen after OK on a profile's reset question is not the camera's completion notice, or "" when it is:
    every reading of its whole text (readings) is "Complete." and "OK" and nothing else, the lit button reads OK alone,
    nothing in it reads as a confirmation (confirmation), a question, Cancel or what no allowance opens (never_lifted),
    and, where the vision model's reading `second` is given (its text and buttons as one text; None: not reachable),
    that reading is "Complete." alone too, OK aside. Anything else ("This function is currently disabled.", "Unable
    to...", another question) is not, nor is a reading with one word more: the run stops on it."""
    t = str(text or "")
    if not t.strip():
        return "no text could be read on the screen"
    for what, said in ((t, "the screen"), (second, "the vision model's reading")):
        if what is None:
            continue
        if "?" in what:
            return f"{said} holds a question ({' '.join(what.split())!r})"
        if any(re.search(r"\bcancel\b", r) for r in readings(what)):
            return f"{said} offers Cancel ({' '.join(what.split())!r})"
        if never_lifted(what):
            return f"{said} reads {never_lifted(what)}"
        if confirmation(what):
            return f"{said} reads as a confirmation ({confirmation(what)})"
    if not all(_PROFILE_COMPLETE.fullmatch(r) for r in readings(t)):
        return f"the screen reads {' '.join(t.split())!r}, not 'Complete.' and OK alone"
    if not all(re.fullmatch(r"\s*ok\s*\.?\s*", r) for r in readings(lit)) or not str(lit or "").strip():
        return f"the lit button reads {str(lit or '').strip()!r}, not OK"
    if second is not None and not all(_PROFILE_COMPLETE_SECOND.fullmatch(r) for r in readings(second)):
        said = " ".join(second.split())
        return f"the vision model reads {said!r}, not 'Complete.' alone" if said else "the vision model read no text"
    return ""


_CONFIRM_RE = re.compile(
    r"\b(execute|format|delete|erase|initiali[sz]e|resets?|restore|update|clean|overwrite|"
    r"all data|will be lost|are you sure|new folder|send|fire|test flash)\b", re.I)


# Quotation marks, paired in order. A pair holds a menu item's name when what is between is a name's length (Sony's
# longest are about 30 characters) with no question or exclamation mark in it (_names_left_out).
_QUOTED = re.compile(r"[\"“”]([^\"“”]*)[\"“”]")
# a mark right after a digit is a seconds mark (30", 2″), never a quotation
_SECONDS = re.compile(r"(?<=\d)[\"“”]")


def _names_left_out(t: str) -> str:
    """The text with each quoted menu item name left out; a quoted span that is no name (a sentence, a question, a
    long passage) stays whole, and seconds marks pair with nothing."""
    t = _SECONDS.sub("″", t)
    return _QUOTED.sub(lambda m: " " if len(m[1]) <= 40 and not re.search(r"[?!\n]", m[1]) else m[0], t)


def confirmation(text: str) -> str | None:
    """Reason a screen looks like a confirmation of an action, or None. A blocker notice ("This
    operation or setting not available as follows" + the blocking setting and its value) is judged
    by its own sentence only: the setting it names can hold an action word ("File Format", 2026-10-29).
    A menu item named in quotation marks is a name too ('... through MENU button - "Select on Cam &
    Send".', 2026-10-29), but only a name's length (_names_left_out): two seconds marks, or a reading the reader put
    in quotation marks whole, hide no sentence. The text is also judged with every pair of marks left out, as the kit
    did before 2026-11-07, so a dialog that reading caught is still caught. "File Format" is a setting's name, on its
    own list too (the 8K drive was refused on it, 2026-10-31). Delete pressing twice On answers with a warning about
    the setting and only OK (frame 37079, 2026-10-31): that whole sentence, word for word, is no confirmation. The
    text is judged as read and folded (fold)."""
    for t in dict.fromkeys((text or "", fold(text))):
        why = _confirms(t)
        if why:
            return why
    return None


def _confirms(text: str) -> str | None:
    t = re.split(r"not\s+available\s+as\s+follows", text, flags=re.I)[0]
    t = re.sub(r"\bfile\s+format\b", " ", t, flags=re.I)
    t = re.sub(r"if\s+the\s+delete\s+button\s+is\s+pressed\s+in\s+the\s+delete\s+confirmation\s+screen,?\s+"
               r"the\s+target\s+image\s+is\s+deleted\.\s*be\s+careful\s+not\s+to\s+accident(?:al)?ly\s+delete\.?",
               " ", t, flags=re.I)
    t = t.strip()
    if len(t) > 1 and t[0] in "\"“”" and t[-1] in "\"“”" and not re.search(r"[\"“”]", t[1:-1]):
        t = t[1:-1]                      # the whole reading in quotation marks: a reader's quoting, not a name
    for judged in (_names_left_out(t), _QUOTED.sub(" ", t)):
        m = _CONFIRM_RE.search(judged)
        if m:
            return f"confirmation text: {m.group(0)}"
    return None


if __name__ == "__main__":
    from . import ROOT, jsonl

    labels = set()
    for f in sorted((ROOT / "data").glob("*/help_guide_menu_*.jsonl")):
        labels |= {r["item"] for r in jsonl.read(f) if r.get("item")}
    for t in sorted(labels):
        why = never_open(t)
        print(f"{'EXCLUDED' if why else 'walked  '}  {t}" + (f"   ({why})" if why else ""))
