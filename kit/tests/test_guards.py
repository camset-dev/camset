"""The kit's guards, offline: the never-open list from the playbook's rule 1 and decision 9, OCR slips, owner
approvals, drive.py's fail-closed Enter and Right, the press choke point and the stop on a signal.
Nothing here talks to a camera.
"""
import json
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, definitions, live, safety  # noqa: E402
from camkit.runs import Run  # noqa: E402

# ---------------------------------------------------------------- the never-open list

# The playbook's rule 1 (decision 2): sound, light or motion, by hand only
RULE_1 = ["Audio signals", "Beep", "Volume Settings", "Screen Reader", "AF Illuminator", "Tally Lamp", "Test Flash",
          "Modeling Flash", "Video Light Mode", "Pre-AF", "Eye-Start AF", "Shutter When Pwr OFF", "SteadyShot",
          "SteadyShot Adjust.", "Silent Mode Settings > Target Function Settings > Shutter When Pwr OFF"]
# Decision 9: credentials and the screens that show them
CREDENTIALS = ["Access Authen. Info", "Access Authen. Settings", "Wi-Fi Direct Info.", "Wi-Fi Direct Settings",
               "Network > Wi-Fi > Wi-Fi Direct Info.", "Password"]
# OCR slips of actions (K-20): "rn" for "m", zero or one inside a word, a lower-case L for a capital I
SLIPS = ["lnitialize", "Forrnat", "F0rmat", "De1ete", "Initia1ize", "Reset Netw0rk Set."]


# What the readers return for the camera's own text: Cyrillic, Ukrainian and Greek look-alikes, full-width letters,
# a zero-width space, a no-break hyphen or an en dash, two spaces, a no-break space or a line break between words, a
# stop, colon or question mark after the label, a capital I for an l. Each of these opened its row until 2026-11-07.
READ_AS = ["Fоrmat", "FОRMAT", "Inіtialize", "ＦＯＲＭＡＴ", "Fo\u200brmat", " Format.", "Format:", "Copy?", "Protect.",
           "Delete  All", "Delete\u00a0All", "Delete\nAll", "Delete AII", "Wi\u2011Fi Direct Info.",
           "Wi\u2013Fi Direct Info.", "Access\u00a0Authen. Info", "Αccess Authen. Info", "Pre\u2011AF", "Stеady Shot",
           "Sсreen Reader"]


@pytest.mark.parametrize("label", RULE_1 + CREDENTIALS + SLIPS + READ_AS)
def test_never_open_from_the_rules(label):
    assert safety.never_open(label), label


@pytest.mark.parametrize("label", ["Fоrmat", "ＤＥＬＥＴＥ", "Delete AII", "Inіtialize", "Wi\u2011Fi Direct Info.",
                                   "Access\u00a0Authen. Info"])
def test_no_allowance_lifts_a_folded_reading(label):
    assert safety.never_lifted(label), label
    assert live.open_refused(label, {label})


def test_a_row_the_owner_named_opens_however_its_hyphen_is_read():
    """A dated owner decision names "Pre-AF"; the reader returns "Pre‑AF" with a no-break hyphen. The fold finds the
    row never-open, and the same fold finds the owner's name in it."""
    assert live.open_refused("Pre\u2011AF  Off", {"Pre-AF"}) == ""
    assert live.open_refused("Pre\u2011AF  Off", {"Eye-Start AF"})


# Readings the kit refused before the fold and must refuse still: a compatibility or combining character next to an
# OCR slip folds into letters that hide the slip ("①lnitialize" folds to "1lnitialize", where deslip's word-start
# rule no longer sees the l; "ë" composed breaks "initialize"). Round 1 of the review found them passing.
KEPT_NEVER_OPEN = ["①lnitialize", "ﬁlnitialize", "²lnitialize"]
KEPT_NEVER_LIFTED = ["lnitialize\u0308", "Reset Netw0rk\u0301", "lnitialize\u0301 Enter"]     # combining accents


@pytest.mark.parametrize("label", KEPT_NEVER_OPEN)
def test_a_fold_never_takes_a_refusal_away(label):
    assert safety.never_open(label), label


@pytest.mark.parametrize("label", KEPT_NEVER_LIFTED)
def test_a_fold_never_takes_a_never_lifted_away(label):
    assert safety.never_lifted(label), label
    assert safety.readings(label)[:2] == [label.lower(), safety.deslip(label.lower())]     # as read comes first


def test_deslip_undoes_slips_only():
    """deslip leaves the text's characters as they are (the fold is a reading of its own, beside it)."""
    assert safety.deslip("①lnitialize") == "①lnitialize"
    assert safety.deslip("lnitialize\u0308") == "initialize\u0308"


# characters a reader returns that the fold mends or that hide a slip: spacing and format characters, dashes,
# compatibility forms, combining marks, look-alikes, and the OCR slips themselves
NOISE = ["\u200b", "\u00ad", "\u200d", "\ufeff", "\u2060", "\u00a0", "\u2011", "\u2013", "\u2212", "\u0301",
         "\u0308", "\uff0e", "\u3000", "\t", "\n", "  ", "①", "²", "ﬁ", "ℓ", "Ⅰ", "ı", "İ", "µ", "|", "0", "1", "I",
         "l", "a", "Ж", "é", "ſ", "\u212a", "\u212b", "\u0345"]


def _repo_never_open_labels():
    labels = set()
    for f in sorted((ROOT / "data").glob("*/help_guide_menu_*.jsonl")):
        labels |= {r["item"] for r in map(json.loads, f.read_text(encoding="utf-8").splitlines()) if r.get("item")}
    # the menus' rows: the mapper's own menu trees where this computer has them (private whole), and every
    # definition's places and menu list, which are what is public of the menus
    sources = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(definitions.EVIDENCE_DIR.glob("*/menu_tree_*.json"))]
    for _, d in definitions.every(evidence=False):
        sources.append({"menu": d.get("menu") or []})
        labels |= {x for s in d.get("settings") or [] for x in s.get("row") or [] if isinstance(x, str)}
    for doc in sources:
        def walk(x):
            if isinstance(x, dict):
                if isinstance(x.get("label"), str):
                    labels.add(x["label"])
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(doc)
    return sorted(t for t in labels if safety.never_open(t) or safety.never_lifted(t))


def test_every_reading_refused_as_read_is_refused(monkeypatch):
    """The guards judge the folded readings beside the text as read, never instead of it: whatever the readings as
    read (and with slips undone) refuse, the guards refuse. Checked on the repo's own never-open labels and the slip
    seeds, each with Unicode and OCR noise put in (a seeded fuzz, about 5,000 strings)."""
    import random
    rng = random.Random(7)
    seeds = _repo_never_open_labels()[:60] + ["lnitialize", "Forrnat", "F0rmat", "De1ete", "Initia1ize",
                                              "Reset Netw0rk Set.", "x lnitialize"]
    texts = []
    for seed in seeds:
        for _ in range(40):
            s = list(seed)
            for _ in range(rng.randint(1, 3)):
                s.insert(rng.randint(0, len(s)), rng.choice(NOISE))
            texts += ["".join(s), "Playback > " + "".join(s)]
    full = [(safety.never_open(t), safety.never_lifted(t)) for t in texts]
    monkeypatch.setattr(safety, "_sources", lambda t: [str(t or "")])      # the text as read, slips undone: no fold
    lost = [(t, o, lifted) for t, (o, lifted) in zip(texts, full, strict=True)
            if (safety.never_open(t) and not o) or (safety.never_lifted(t) and not lifted)]
    assert not lost, lost[:5]


def test_fold_mends_only_what_a_reader_changes():
    assert safety.fold("Wi\u2011Fi  Direct\u00a0Info.\u200b") == "Wi-Fi Direct Info."
    assert safety.fold("С.Temp./Filter") == "C.Temp./Filter"
    assert safety.fold("Focus Area") == "Focus Area" and safety.fold(None) == ""


@pytest.mark.parametrize("text", ['"OK!" Delete "Slot 1"',                             # a quoted span that is no name
                                  '"Copyright Info. and the Artist Name and Copyright fields" Execute "Slot 1"',
                                  'Set "Shoot Mode" to "M" Format? "Slot 1"',
                                  'X 30" Delete? "Slot 1"',
                                  '30" Format? All data will be deleted. 2"',          # two seconds marks
                                  '"Format Slot 1 All data will be deleted"',          # the reading quoted whole
                                  "Fоrmat? Enter Cancel",                              # a look-alike letter
                                  "Initia\u200blize all settings? Enter Cancel",
                                  'Execute "Format"?'])
def test_a_confirmation_hides_behind_no_quotation_mark_or_look_alike(text):
    assert safety.confirmation(text), text


def test_a_quoted_menu_item_and_a_seconds_mark_are_still_names():
    assert safety.confirmation('Set it through MENU button - "Select on Cam & Send".') is None
    assert safety.confirmation('Shutter 2" Interval 1 Sec') is None


@pytest.mark.parametrize("label", ["Pre-AF", "Eye-Start AF", "Shutter When Pwr OFF", "SteadyShot"])
def test_motion_rows_only_an_owner_decision_lifts(label):
    why = safety.never_open(label)
    assert why.startswith("sound, light or motion") and safety.owner_may_approve(why)
    assert safety.path_refused([label]) and safety.path_refused([label], {"Other Row"})
    assert safety.path_refused([label], {label}) is None


@pytest.mark.parametrize("label", CREDENTIALS + ["Initialize", "Format", "Delete", "Reset Network Set."])
def test_credentials_and_actions_no_decision_lifts(label):
    why = safety.never_open(label)
    assert why and not safety.owner_may_approve(why)
    assert safety.path_refused([label], {label})


@pytest.mark.parametrize("label", ["Pre-Capture", "Return", "Pattern", "Internal", "Lens Comp.", "Focus Area",
                                   "File Format", "Delete confirm.", "Power Save by Monitor", "Drive Mode"])
def test_slip_undoing_opens_no_new_rows(label):
    assert safety.never_open(label) is None


def test_scope_ask_user_and_empty_prove():
    import prove_run as P
    rows = [{"path": p} for p in (["Drive Mode"], ["SteadyShot"], ["Beep"], ["Grid Line Display"], ["HDMI Info. Display"])]
    scope = {"prove": [], "exclude": {"HDMI": ["HDMI Info. Display"]},
             "ask_user": {"sound, light or motion": ["SteadyShot", "Grid Line Display"]},
             "decisions": [{"date": "2026-11-05", "rows": ["Grid Line Display"], "why": "owner: yes"},
                           {"date": "someday", "rows": ["SteadyShot"], "why": "undated: not a decision"}]}
    allowed, excluded, approved = P.scope_rows(scope, rows)
    assert allowed == {"Drive Mode", "Beep", "Grid Line Display"}       # every map row, as the template's note says
    assert "SteadyShot" in excluded and "HDMI Info. Display" in excluded
    assert approved == {"Grid Line Display"}
    assert safety.path_refused(["Beep"], approved)                        # never-open: checked per job still
    scope["prove"] = ["Drive Mode", "SteadyShot"]
    assert P.scope_rows(scope, rows)[0] == {"Drive Mode"}


# ---------------------------------------------------------------- drive.py fails closed

def test_drive_enter_refused_without_a_readable_button():
    import drive
    blank = np.zeros((480, 640, 3), np.uint8)                 # nothing orange: no cursor at all
    assert drive.highlighted(blank, ROOT / "no-such-frame.png") == ""
    assert drive.press_refused("enter", "", "Some Setting OK", "list")
    assert drive.press_refused("ms_enter", "   ", "Some Setting OK", "list")


@pytest.mark.parametrize("text", ["Initialize? Enter Cancel", "Reset Network Set.? Enter Cancel",
                                  "lnitialize all settings? Enter Cancel"])
def test_drive_enter_never_on_initialize_even_with_confirm(text):
    import drive
    for lit in ("Enter", "OK"):
        assert drive.press_refused("enter", lit, text, "dialog", confirm=True, allow=["Initialize", "Setting Reset"])
    assert drive.press_refused("enter", "Initialize", "Setting Reset Camera Settings Reset Initialize", "submenu",
                               confirm=True, allow=["Initialize"])


def test_drive_camera_settings_reset_needs_allow_and_confirm():
    import drive
    text = "Setting Reset Camera Settings Reset Initialize"       # Setting Reset's two rows on one screen
    assert drive.press_refused("enter", "Camera Settings Reset", text, "submenu", confirm=True)   # not allowed
    assert drive.press_refused("enter", "Camera Settings Reset", text, "submenu", allow=["Camera Settings Reset"])
    assert drive.press_refused("enter", "Camera Settings Reset", text, "submenu", confirm=True,
                               allow=["Camera Settings Reset"]) == ""
    assert drive.press_refused("enter", "Enter", "Reset camera settings? Enter Cancel", "dialog") != ""
    assert drive.press_refused("enter", "Enter", "Reset camera settings? Enter Cancel", "dialog", confirm=True) == ""


def test_drive_right_onto_a_never_open_row():
    import drive
    for lit in ("Access Authen. Info", "Wi-Fi Direct Info.", "Pre-AF  Off", "Format", "Language English"):
        assert drive.press_refused("right", lit, lit, "submenu"), lit
    assert drive.press_refused("right", "Access Authen. Info", "", "submenu", allow=["Access Authen. Info"])
    assert drive.press_refused("right", "Pre-AF  Off", "", "submenu", allow=["Pre-AF"]) == ""
    assert drive.press_refused("right", "", "", "menu")                  # an unreadable row is not opened
    assert drive.press_refused("right", "", "", "dialog") == ""          # a carousel's Right opens no row
    assert drive.press_refused("right", "Drive Mode  Single Shooting", "", "menu") == ""


@pytest.mark.parametrize("args", [["--path", "Initialize", "--allow", "Initialize"],
                                  ["--path", "Network", "--path", "Access Authen. Info", "--allow", "Access Authen. Info"],
                                  ["--path", "Reset Network Set.", "--allow", "Reset Network Set."]])
def test_drive_paths_no_allow_opens(args):
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "drive.py"), *args], capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "no --allow opens it" in r.stderr


# ---------------------------------------------------------------- the press choke point

class Presses:
    def __init__(self):
        self.sent, self.judged = [], []           # the keys sent; the (screen, on_shooting) each went with

    def press(self, key, hold_ms=60, allow=frozenset(), cleanup=False, screen=None, on_shooting=frozenset()):
        self.sent.append(key)
        self.judged.append((screen, on_shooting))


def camera(tmp_path, kind, lit, may_open=()):
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.link, cam.run, cam.may_open = Presses(), Run("guards", root=tmp_path), frozenset(may_open)
    cam.screen = SimpleNamespace(kind=kind)
    cam.frame = SimpleNamespace(image=None, path=tmp_path / "00001_down.png")
    return cam


@pytest.mark.parametrize("key", ["right", "enter", "ms_right", "ms_enter"])
def test_choke_point_refuses_opening_a_never_open_row(tmp_path, monkeypatch, key):
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Access Authen. Info")
    cam = camera(tmp_path, "submenu", "Access Authen. Info", may_open={"Access Authen. Info"})
    with pytest.raises(safety.Refused, match="never opened"):
        cam.press(key)
    assert cam.link.sent == []
    events = [json.loads(l) for l in (cam.run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[-1]["kind"] == "press_refused"


@pytest.mark.parametrize("key", [" right", "right ", '"right"', "Right", "ENTER", "rіght", "ｍｓ_ｅｎｔｅｒ", "ms_Right"])
def test_choke_point_judges_a_key_however_it_is_spelled(tmp_path, monkeypatch, key):
    """The never-open check judges the key as the guards read it: a padded, quoted, upper-case or look-alike Right or
    Enter on a never-open row is refused by the row check, and on any other row by the link, which presses only a
    key written as its own name. Neither press goes out."""
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Access Authen. Info")
    cam = camera(tmp_path, "submenu", "Access Authen. Info")
    with pytest.raises(safety.Refused, match="never opened"):
        cam.press(key)
    assert cam.link.sent == []
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Drive Mode  Single Shooting")
    with fake_link(tmp_path, monkeypatch) as lk:
        cam = camera(tmp_path, "submenu", "")
        cam.link = lk
        with pytest.raises(safety.Refused, match="not written as the guards read it"):
            cam.press(key)


def test_choke_point_lets_a_named_row_and_other_presses_through(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Reg. Custom Shoot Set")
    cam = camera(tmp_path, "submenu", "")
    with pytest.raises(safety.Refused):
        cam.press("right")
    cam = camera(tmp_path, "submenu", "", may_open={"Reg. Custom Shoot Set"})
    cam.hdmi = SimpleNamespace(settle=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sent")))
    with pytest.raises(RuntimeError, match="sent"):            # past the check: the press went out
        cam.press("right")
    assert cam.link.sent == ["right"]
    cam = camera(tmp_path, "list", "")
    cam.hdmi = SimpleNamespace(settle=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sent")))
    with pytest.raises(RuntimeError):                          # a list's Enter chooses an option: not a row
        cam.press("enter")
    assert cam.link.sent == ["enter"]


# ---------------------------------------------------------------- Ctrl-C stops the run as a STOP file does

def test_a_signal_asks_the_run_to_stop_and_a_second_one_interrupts(tmp_path, monkeypatch):
    from camkit import link as L
    run = Run("sig", root=tmp_path)
    monkeypatch.setattr(L, "_RUNS", [run])
    monkeypatch.setattr(L, "_PREVIOUS", {})
    assert not run.stop_requested()
    L._on_signal(signal.SIGINT, None)
    assert run.stop_requested()
    events = [json.loads(l) for l in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[-1]["kind"] == "stop_requested" and "SIGINT" in events[-1]["why"]
    with pytest.raises(L.StopRequested):                       # the next press: the run's own stop path
        L.Link(run, ip="192.0.2.10", catch_signals=False).press("down", screen="menu")
    with pytest.raises(KeyboardInterrupt):
        L._on_signal(signal.SIGTERM, None)
    assert not (run.dir / "STOP").exists()                     # nothing left behind to stop the next run


# ---------------------------------------------------------------- C4: the screen is the guard (decision 7, 2026-11-06)

FAKE = Path(__file__).resolve().parent / "fake_camlink.py"
# the stand-in, as fake_camlink.COMMAND starts it: -X utf8, which camkit needs on Windows
CAMLINK = [sys.executable, "-X", "utf8", str(FAKE)]


def fake_link(tmp_path, monkeypatch):
    from camkit import link as L
    monkeypatch.delenv("CAMSET_USB", raising=False)
    return L.Link(Run("c4", root=tmp_path), ip="192.0.2.10", binary=CAMLINK, catch_signals=False)


@pytest.mark.parametrize("kind", sorted(safety.C4_SCREENS))
def test_c4_goes_out_on_a_menu_option_or_panel_screen(tmp_path, monkeypatch, kind):
    """No config and no per-body yes: C4 is sent on a menu, option, panel or editor screen the caller read last."""
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind=kind))["args"] == ["c4", "60", "allowed"]


@pytest.mark.parametrize("kind,why", [("shooting", "assigns to it"), ("unknown", "picture is displayed"),
                                      ("tiles", "not a menu, option or panel"), ("guide", "deletes"),
                                      (None, "none was given")])
def test_c4_refused_on_the_shooting_screen_in_playback_and_with_a_picture(tmp_path, monkeypatch, kind, why):
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    with fake_link(tmp_path, monkeypatch) as lk:
        with pytest.raises(safety.Refused, match=why):
            lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind=kind) if kind else None)
        with pytest.raises(safety.Refused):
            lk.press("c4", screen=SimpleNamespace(kind="menu"))       # and never without the caller's allowance
    assert "c4" not in log.read_text(encoding="utf-8")


def test_c4_refused_while_the_camera_says_it_is_in_playback(tmp_path, monkeypatch):
    """A menu read on the screen, but the camera's own CameraOperatingMode (listed, props says) reads Playback, where
    C4 deletes."""
    from camkit import link as L
    monkeypatch.setenv("FAKE_CAMLINK_PROPS", json.dumps([{"name": "CameraOperatingMode"}]))
    monkeypatch.setenv("FAKE_CAMLINK_GET", json.dumps({"CameraOperatingMode": {"current": L.PLAYBACK_MODE}}))
    with fake_link(tmp_path, monkeypatch) as lk, pytest.raises(safety.Refused, match="in Playback"):
        lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"))
    monkeypatch.setenv("FAKE_CAMLINK_GET", json.dumps({"CameraOperatingMode": {"current": 1}}))       # Record
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"))["ok"]


def test_live_camera_hands_its_screen_to_the_link(tmp_path):
    """LiveCamera.press, the way every walker presses, gives the link the screen it read last."""
    seen = []
    cam = camera(tmp_path, "menu", "")
    cam.link = SimpleNamespace(press=lambda key, hold_ms=60, allow=frozenset(), screen=None, on_shooting=frozenset():
                               seen.append(screen))
    cam.hdmi = SimpleNamespace(settle=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sent")))
    with pytest.raises(RuntimeError):
        cam.press("c4", allow={"c4"})
    assert seen == [cam.screen]


# ---------------------------------------------------------------- the properties never set, case and all

# Refused by accident while the patterns were matched with case ignored (2026-11-08): each holds a pattern's letters
# inside another word ("FocUSBracket", "ContinuouSShooting", "LensInFORMATion", "OpeRATINGMode", "SettingReadOperation"
# is "_ReadOp" + "eraSe", "PRESET", "TimeShiftPreShootingTimeSetting" holds "ftP")
CASE_ACCIDENTS = [
    "FocusBracketExposureLock1stImg", "FocusBracketFocusRange", "FocusBracketIntervalUntilNextShot",
    "FocusBracketOrder", "FocusBracketRecordingFolder", "FocusBracketShootingStatus", "FocusBracketShotNumber",
    "ContinuousShootingSpeedInElectricShutterHi", "ContinuousShootingSpeedInElectricShutterHiPlus",
    "ContinuousShootingSpeedInElectricShutterLo", "ContinuousShootingSpeedInElectricShutterMid",
    "ContinuousShootingSpotBoostEnableStatus", "ContinuousShootingSpotBoostFrameSpeed",
    "ContinuousShootingSpotBoostStatus", "FlickerLessShooting", "FlickerLessShootingStatus",
    "LensInformationEnableStatus", "CameraOperatingMode", "CameraSetting_ReadOperationEnableStatus",
    "IsoAutoMinShutterSpeedPreset", "TimeCodePreset", "UserBitPreset", "TimeShiftPreShootingTimeSetting"]
# true refusals, one or more per kind: motion, credentials and connection, actions, by hand only, light, buttons; each
# a name in the a1 II's SDK property list (kit/common/guards_test.cpp checks the same twelve)
TRUE_REFUSALS = {"PreAF": "motion", "Zoom_Operation": "motion", "VideoStreamSettingVersion": "credentials",
                 "RemoteTouchOperation": "credentials", "USBPowerSupply": "credentials",
                 "MediaSLOT1_FormatEnableStatus": "action", "DeleteContentOperationEnableStatusSLOT1": "action",
                 "TimeCodePresetResetEnableStatus": "action", "AFIlluminator": "light", "FTP_Function": "credentials",
                 "SetCopyright": "by hand", "CameraButtonFunction": "a button"}


def test_property_names_are_judged_as_the_sdk_writes_them():
    assert len(CASE_ACCIDENTS) == 23
    for name in CASE_ACCIDENTS:
        assert safety.never_property(name) is None, (name, safety.never_property(name))
    for name, kind in TRUE_REFUSALS.items():
        why = safety.never_property(name)
        assert why and kind in why, (name, why)
        assert safety.never_property("CrDeviceProperty_" + name) == why
    # a name in another case is no name the kit sets either: only the live exposure's own spellings pass
    for name in ("preaf", "PREAF", "shutterspeed", "fnumber"):
        with pytest.raises(safety.Refused):
            safety.check_property(name)
    safety.check_property("ShutterSpeed")
    # the C++ side checks the same names (kit/common/guards_test.cpp, built and run by test_link_protocol.py)
    cpp = (ROOT / "kit" / "common" / "guards_test.cpp").read_text(encoding="utf-8")
    assert all(f'"{name}"' in cpp for name in CASE_ACCIDENTS)
    assert all(f'{{"{name}", "{kind}"}}' in cpp for name, kind in TRUE_REFUSALS.items())


def test_the_cpp_header_matches_the_property_names_as_written_too():
    """camlink and the camera helper compile the same patterns (kit/common/never_touch.h, which build_docs.py writes
    from safety.py) with the case counting as the kit's own check does: no icase."""
    sys.path.insert(0, str(ROOT / "kit" / "tools"))
    import build_docs
    header = build_docs.never_touch_h()
    assert "icase" not in header and "std::regex(r.pattern, std::regex::ECMAScript)" in header
    assert header == (ROOT / "kit" / "common" / "never_touch.h").read_text(encoding="utf-8")


def by_pattern(names) -> dict:
    """Whether a committed NEVER_PROPERTIES pattern refuses each name, worked out here pattern by pattern, the case
    counting."""
    import re
    pats = [p for ps in safety.NEVER_PROPERTIES.values() for p in ps]
    return {n: any(re.search(p, n) for p in pats) for n in names}


def test_every_property_of_the_a1_ii_judged_as_the_patterns_say():
    """Opt-in: the a1 II's SDK property list from a probe run in this clone (runs/ILCE-1M2_fw4.00/probe_values/
    properties.json, never committed: the SDK's names are Sony's). Skipped without it, as in CI."""
    from camkit import paths
    props = paths.a1ii_root() / "probe_values" / "properties.json"
    if not props.exists():
        pytest.skip("no probe run of the a1 II in this clone (runs/ILCE-1M2_fw4.00/probe_values/properties.json)")
    import re
    names = [p["name"] for p in json.loads(props.read_text(encoding="utf-8"))]
    unnamed = {n for n in names if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", n)}     # "unknown(0x582)": no name
    patterns = by_pattern(names)
    got = {n: bool(safety.never_property(n)) for n in names}
    assert got == {n: patterns[n] or n in unnamed for n in names}
    assert (sum(patterns[n] for n in names if n not in unnamed), len(names)) == (194, 475)
    assert not any(got[n] for n in CASE_ACCIDENTS if n in got)
    assert set(CASE_ACCIDENTS) | set(TRUE_REFUSALS) <= set(names)          # every name the two lists test is the SDK's


# ---------------------------------------------------------------- a lit row OCR cannot read (fails closed, as drive.py)

def lit_frame(tmp_path, bar=True):
    """A 640 x 480 menu frame with the cursor's orange bar on one row (or none), saved where the reader reads it."""
    a = np.full((480, 640, 3), 24, np.uint8)
    if bar:
        a[212:252, 140:560] = (235, 90, 20)            # the cursor's orange (screen._planes)
    path = tmp_path / "00002_down.png"
    path.write_bytes(b"a frame")
    return SimpleNamespace(image=a, path=path)


class Reader:
    """The "second" vision reader as camkit.vlm.ask_role asks it: answers the menu question with `rows`, or raises
    `fails`; counts the questions."""
    def __init__(self, rows=None, fails=None):
        self.rows, self.fails, self.asked = rows, fails, []

    def __call__(self, name, image, prompt, timeout):
        assert name == "second"
        self.asked.append(prompt)
        if self.fails:
            raise self.fails
        return {"rows": self.rows}


def unread_camera(tmp_path, monkeypatch, reader, kind="submenu", bar=True, ocr_lines=()):
    monkeypatch.setattr(live.ocr, "read", lambda paths, eng=None: {p: list(ocr_lines) for p in paths})
    monkeypatch.setattr(live, "ask_role", reader)
    cam = camera(tmp_path, kind, "")
    cam.frame = lit_frame(tmp_path, bar)
    cam.hdmi = SimpleNamespace(settle=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sent")))
    return cam


def events_of(cam) -> list:
    return [json.loads(l) for l in (cam.run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("key", ["right", "enter", "ms_right", "ms_enter"])
def test_an_unread_lit_row_the_reader_names_never_open_is_refused(tmp_path, monkeypatch, key):
    reader = Reader(rows=[{"label": "Drive Mode", "highlighted": False}, {"label": "Format", "highlighted": True}])
    cam = unread_camera(tmp_path, monkeypatch, reader)
    with pytest.raises(safety.Refused, match="'Format' is never opened"):
        cam.press(key)
    assert cam.link.sent == [] and reader.asked == [live.PROMPTS["menu"]]          # asked once, the menu question
    assert [e["kind"] for e in events_of(cam)] == ["lit_row_by_reader", "press_refused"]


def test_an_unread_lit_row_the_reader_names_as_harmless_opens(tmp_path, monkeypatch):
    reader = Reader(rows=[{"label": "Drive Mode", "highlighted": True}, {"label": "Format", "highlighted": False}])
    cam = unread_camera(tmp_path, monkeypatch, reader)
    with pytest.raises(RuntimeError, match="sent"):                # past the check: the press went out
        cam.press("right")
    assert cam.link.sent == ["right"] and len(reader.asked) == 1
    last = events_of(cam)[-1]
    assert last["kind"] == "lit_row_by_reader" and last["label"] == "Drive Mode"


@pytest.mark.parametrize("reader,said", [
    (Reader(fails=OSError("connection refused")), "the vision reader failed (OSError: connection refused)"),
    (Reader(rows=[{"label": "Drive Mode", "highlighted": False}]), "marked 0 rows"),
    (Reader(rows=[{"label": "A", "highlighted": True}, {"label": "B", "highlighted": True}]), "marked 2 rows"),
    (Reader(rows=[{"label": " ", "highlighted": True}]), "gave the lit row no label"),
    (Reader(rows=None), "marked 0 rows"),
])
def test_an_unread_lit_row_the_reader_cannot_name_is_refused_for_the_owners_hand(tmp_path, monkeypatch, capsys,
                                                                                 reader, said):
    cam = unread_camera(tmp_path, monkeypatch, reader)
    with pytest.raises(safety.Refused, match="the row under the cursor could not be read: the never-open check "
                                             "cannot judge it"):
        cam.press("enter")
    assert cam.link.sent == [] and len(reader.asked) == 1
    last = events_of(cam)[-1]
    assert last["kind"] == "press_refused" and last["why"] == live.UNREAD and said in last["reader"] and last["by_hand"]
    out = capsys.readouterr().out
    assert live.UNREAD in out and "open it on the camera by hand" in out


def test_a_row_ocr_reads_and_a_screen_with_no_bar_never_ask_the_reader(tmp_path, monkeypatch):
    """What happens when OCR reads the lit row is as before, and with no orange bar drawn there is no row to judge."""
    from camkit import ocr
    reader = Reader(fails=AssertionError("the reader was asked"))
    format_line = ocr.Line(text="Format", conf=0.99, x=150, y=220, w=120, h=24)
    cam = unread_camera(tmp_path, monkeypatch, reader, ocr_lines=[format_line])
    with pytest.raises(safety.Refused, match="'Format' is never opened"):
        cam.press("right")
    drive_line = ocr.Line(text="Drive Mode", conf=0.99, x=150, y=220, w=120, h=24)
    cam = unread_camera(tmp_path, monkeypatch, reader, ocr_lines=[drive_line])
    with pytest.raises(RuntimeError, match="sent"):
        cam.press("right")
    cam = unread_camera(tmp_path, monkeypatch, reader, bar=False)
    with pytest.raises(RuntimeError, match="sent"):
        cam.press("right")
    cam = unread_camera(tmp_path, monkeypatch, reader, kind="list")   # a list's Enter chooses an option: not a row
    with pytest.raises(RuntimeError, match="sent"):
        cam.press("enter")
    assert reader.asked == []


def test_an_unread_row_is_asked_of_a_stand_in_when_the_second_reader_will_not_connect(tmp_path, monkeypatch):
    """camkit.vlm.ask_role, through which every question a run asks about a frame goes (proving's ask_second, live's
    reader_label and submenu_labels): the configured "second" reader's server is off (URLError), the next local reader
    that answers takes the role for the run, and the lit row's label comes from it."""
    import urllib.error
    from camkit import vlm
    readers = [{"name": "remote", "url": "http://192.0.2.1/v1", "model": "m"},
               {"name": "omlx", "url": "http://127.0.0.1:8000/v1", "model": "m"}]
    monkeypatch.setattr(vlm, "config", lambda: {"readers": readers})
    monkeypatch.setattr(vlm, "_STANDING_IN", {})
    asked = []

    class Fake:
        def __init__(self, cfg, **override):
            self.name = cfg["name"]

        def ping(self):
            if self.name == "remote":
                raise urllib.error.URLError("connection refused")

        def ask(self, image, prompt):
            asked.append(self.name)
            if self.name == "remote":
                raise urllib.error.URLError("connection refused")
            return {"rows": [{"label": "Drive Mode", "highlighted": True}]}
    monkeypatch.setattr(vlm, "make_reader", Fake)
    frame = lit_frame(tmp_path)
    assert live.reader_label(frame.path) == ("Drive Mode", "")
    assert asked == ["remote", "omlx"] and vlm.standing_in("second") is readers[1]
    assert live.reader_label(frame.path) == ("Drive Mode", "") and asked[-1] == "omlx"     # the stand-in kept


# --allow LABEL on scale_run and prove_run (2026-11-09: the owner allowed the volume and brightness rows in words)
def test_allow_lifts_only_the_named_never_open_row():
    assert safety.never_open("Playback/Monitor. Vol.")
    assert safety.path_refused(["Playback/Monitor. Vol."])
    assert safety.path_refused(["Playback/Monitor. Vol."], allowed=["Playback/Monitor. Vol."]) is None
    assert safety.path_refused(["Voice Memo Play Vol."], allowed=["Playback/Monitor. Vol."])      # another row stays closed
    assert safety.path_refused(["Audio Signal Volume"], allowed=[])


@pytest.mark.parametrize("label", ["Format", "Delete", "Delete Slot1/2", "Initialize", "Reset Network Set.",
                                   "Access Authen. Info", "Wi-Fi Direct Info."])
def test_allow_never_names_the_cards_initialize_or_credentials(label):
    assert safety.allow_refused(label)
    assert safety.path_refused([label], allowed=[label])        # the row stays refused even when named


def test_allow_words_for_the_proof_lines():
    assert safety.allowance([]) == ""
    assert safety.allowance(["Audio Signal Volume", "Voice Memo Play Vol."], "2026-11-09") == (
        "the owner allowed Audio Signal Volume remotely, 2026-11-09; "
        "the owner allowed Voice Memo Play Vol. remotely, 2026-11-09")


def test_provers_take_allow_and_refuse_a_hard_never_row(monkeypatch, capsys):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "provers"))
    import scale_run
    monkeypatch.setattr(sys, "argv", ["scale_run", "--row", "X", "--allow", "Initialize"])
    with pytest.raises(SystemExit, match="Initialize"):
        scale_run.main()
    import prove_run
    monkeypatch.setattr(sys, "argv", ["prove_run", "--rows", "Format", "--allow", "Format"])
    with pytest.raises(SystemExit, match="Format"):
        prove_run.main()
    monkeypatch.setattr(sys, "argv", ["prove_run", "--allow", "Audio Signal Volume"])
    with pytest.raises(SystemExit, match="--rows"):
        prove_run.main()


def test_tagged_adds_the_allowance_without_touching_the_context(tmp_path):
    from proving.base import Tagged
    f = (tmp_path / "p.jsonl").open("w", encoding="utf-8")
    with Tagged(f, None, {"allowance": "the owner allowed X remotely, 2026-11-09"}) as t:
        t.write('{"path": ["X"]}\n')
    r = json.loads((tmp_path / "p.jsonl").read_text(encoding="utf-8"))
    assert r == {"path": ["X"], "allowance": "the owner allowed X remotely, 2026-11-09"}


# ---------------------------------------------------------------- the shooting screen is the guard (decision 21)
# On the shooting screen the body does whatever its owner assigned to a key (the shipped definition's lists for the
# wheel's keys hold Movie Shooting, Wireless Test Flash, FEL Lock, AF On...): no key but MENU goes out there, nor with
# no screen given, unless the caller names that key for the press.

SHOOTING_KEYS = sorted(safety.MENU_INPUTS - safety.SHOOTING_FREE)


@pytest.mark.parametrize("key", SHOOTING_KEYS)
def test_no_key_but_menu_on_the_shooting_screen_unless_the_caller_names_it(key):
    assert safety.shooting_refused(key, "shooting")
    assert safety.shooting_refused(key, "shooting", {key}) == "" and safety.shooting_refused(key, "shooting", key) == ""
    assert safety.shooting_refused(key, "shooting", {"menu", "ms_" + key}), "another key's name names nothing else"
    assert safety.shooting_refused(key, None), "no screen given: nothing says it is not the shooting screen"
    for kind in ("menu", "submenu", "tiles", "dialog", "list", "notice", "unknown"):
        assert safety.shooting_refused(key, kind) == "", kind
    assert safety.shooting_refused("menu", "shooting") == "" and safety.shooting_refused("menu", None) == ""


def sent_lines(log) -> list:
    return [l for l in log.read_text(encoding="utf-8").splitlines() if "press" in l or "dial" in l] if log.exists() else []


@pytest.mark.parametrize("key", ["left", "right", "up", "down", "enter", "ms_left", "ms_enter", "wheel", "rear_r"])
def test_the_link_sends_no_key_but_menu_on_the_shooting_screen(tmp_path, monkeypatch, key):
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    shooting = SimpleNamespace(kind="shooting")
    with fake_link(tmp_path, monkeypatch) as lk:
        with pytest.raises(safety.Refused, match="shooting screen"):
            lk.press(key, screen=shooting)
        with pytest.raises(safety.Refused, match="shooting screen"):
            lk.press(key, screen="shooting", on_shooting={"other"})
        with pytest.raises(safety.Refused, match="none was given"):
            lk.press(key)
        with pytest.raises(safety.Refused, match="shooting screen"):
            lk.call(f"press {key} 60", screen="shooting")              # a raw line is judged the same
        assert lk.press("menu", screen=shooting)["ok"] and lk.press("menu", cleanup=True)["ok"]
        assert lk.press(key, screen=shooting, on_shooting=key)["args"][0] == key       # named for this press
        assert lk.press(key, screen=SimpleNamespace(kind="menu"))["args"][0] == key    # a menu is no shooting screen
    assert sum(f"press {key} " in l for l in sent_lines(log)) == 2


def test_a_dial_on_the_shooting_screen_needs_its_name_and_any_dial_a_screen(tmp_path, monkeypatch):
    """On the shooting screen a dial changes the live exposure, which no settings file holds."""
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    with fake_link(tmp_path, monkeypatch) as lk:
        with pytest.raises(safety.Refused, match="shooting screen"):
            lk.dial("front", 1, screen="shooting")
        with pytest.raises(safety.Refused, match="none was given"):
            lk.dial("front", 1)
        assert lk.dial("front", 1, screen=SimpleNamespace(kind="dialog"))["ok"]
        assert lk.dial("front", -1, screen="shooting", on_shooting="front")["ok"]
    sent = sent_lines(log)
    assert sum("dial front 1" in l for l in sent) == 1 and sum("dial front -1" in l for l in sent) == 1


def test_naming_c4_for_the_shooting_screen_never_sends_it(tmp_path, monkeypatch):
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    with fake_link(tmp_path, monkeypatch) as lk, pytest.raises(safety.Refused, match="C4 refused"):
        lk.press("c4", allow={"c4"}, screen="shooting", on_shooting={"c4"})
    assert not any("c4" in l for l in sent_lines(log))


def test_live_camera_hands_the_keys_named_for_the_shooting_screen_to_the_link(tmp_path):
    cam = camera(tmp_path, "shooting", "")
    cam.hdmi = SimpleNamespace(settle=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sent")))
    with pytest.raises(RuntimeError, match="sent"):
        cam.press("ms_left", on_shooting="ms_left")
    assert cam.link.sent == ["ms_left"] and cam.link.judged == [(cam.screen, "ms_left")]


def test_live_camera_on_the_shooting_screen_is_refused_at_the_link_unless_named(tmp_path, monkeypatch):
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    with fake_link(tmp_path, monkeypatch) as lk:
        cam = camera(tmp_path, "shooting", "")
        cam.link = lk
        cam.hdmi = SimpleNamespace(settle=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sent")))
        for key in ("right", "down", "ms_up"):
            with pytest.raises(safety.Refused, match="shooting screen"):
                cam.press(key)
        with pytest.raises(RuntimeError, match="sent"):
            cam.press("ms_up", on_shooting={"ms_up"})
    assert sent_lines(log) and all("ms_up" in l for l in sent_lines(log))


def black_camera(tmp_path, monkeypatch, osd):
    """A LiveCamera whose screen reads as no known kind on a black frame (HDMI blanked), the camera's own picture of the
    screen reading as `osd` ("" when it cannot be read); returns it and the questions asked of that picture."""
    asked = []
    monkeypatch.setattr(live, "osd_kind", lambda link: asked.append(link) or osd)
    cam = camera(tmp_path, "unknown", "")
    cam.frame = SimpleNamespace(image=np.zeros((480, 640, 3), np.uint8), path=tmp_path / "00003_down.png")
    cam.hdmi = SimpleNamespace(settle=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sent")))
    return cam, asked


def test_a_black_frame_is_judged_on_the_cameras_own_picture(tmp_path, monkeypatch):
    cam, asked = black_camera(tmp_path, monkeypatch, "shooting")
    with pytest.raises(RuntimeError, match="sent"):
        cam.press("down")
    assert cam.link.judged == [("shooting", frozenset())] and len(asked) == 1        # the link refuses it there
    cam, asked = black_camera(tmp_path, monkeypatch, "menu")       # any other reading keeps the screen read last
    with pytest.raises(RuntimeError, match="sent"):
        cam.press("down")
    assert cam.link.judged == [(cam.screen, frozenset())]
    cam, asked = black_camera(tmp_path, monkeypatch, "")           # a picture that cannot be read: unseen, MENU only
    with pytest.raises(safety.Refused, match="could not be read"):
        cam.press("down")
    assert cam.link.sent == [] and events_of(cam)[-1]["kind"] == "press_refused"
    with pytest.raises(RuntimeError, match="sent"):
        cam.press("menu")
    assert cam.link.sent == ["menu"] and len(asked) == 1, "MENU asks no picture"
    with fake_link(tmp_path, monkeypatch) as lk:                  # the real link then refuses the key
        cam, _ = black_camera(tmp_path, monkeypatch, "shooting")
        cam.link = lk
        with pytest.raises(safety.Refused, match="shooting screen"):
            cam.press("down")


def test_a_frame_with_a_picture_or_a_screen_read_asks_the_camera_nothing(tmp_path, monkeypatch):
    cam, asked = black_camera(tmp_path, monkeypatch, "")
    cam.frame.image[:] = 90                                        # a picture: the frame itself is read
    with pytest.raises(RuntimeError, match="sent"):
        cam.press("down")
    cam, more = black_camera(tmp_path, monkeypatch, "")
    cam.screen = SimpleNamespace(kind="dialog")                    # a screen the reader knows, however dark
    with pytest.raises(RuntimeError, match="sent"):
        cam.press("down")
    assert asked == [] and more == []


def stale_camera(tmp_path, lk):
    """A LiveCamera on the real link `lk`, its screen read last a menu page, the link's count kept at that read. Returns
    it and the tags of the frames grabbed."""
    grabbed = []
    cam = camera(tmp_path, "menu", "")
    cam.link = lk
    cam.hdmi = SimpleNamespace(grab=lambda tag, save=True: grabbed.append(tag) or SimpleNamespace(
                                   image=None, path=tmp_path / f"{len(grabbed):05d}_{tag}.png"),
                               settle=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sent")))
    cam._seen = lk.moves
    return cam, grabbed


def test_a_screen_moved_behind_the_cameras_back_is_read_afresh_before_a_press(tmp_path, monkeypatch):
    """A download with the menu closed moves the screen without the LiveCamera seeing it: the next Down is judged on a
    screen grabbed afresh, the shooting screen here, and refused there. With nothing sent since the last read nothing is
    grabbed, and MENU is never held up by a grab."""
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    monkeypatch.setattr(live.screen, "read", lambda f: SimpleNamespace(kind="shooting", focus=None))
    with fake_link(tmp_path, monkeypatch) as lk:
        cam, grabbed = stale_camera(tmp_path, lk)
        with pytest.raises(RuntimeError, match="sent"):            # judged on the menu read last: it goes
            cam.press("down")
        assert grabbed == [] and lk.moves == 1
        cam._seen = lk.moves                                      # as the press's own read keeps it
        lk.download("after")                                      # the menu closes; the camera saw nothing of it
        with pytest.raises(RuntimeError, match="sent"):            # MENU: no grab, judged on no screen
            cam.press("menu")
        assert grabbed == []
        with pytest.raises(safety.Refused, match="shooting screen"):
            cam.press("down")
        assert grabbed == ["stale"] and cam.screen.kind == "shooting" and cam._seen == lk.moves
    assert [e["kind"] for e in events_of(cam)].count("screen_stale") == 1
    assert sum("press down" in l for l in sent_lines(log)) == 1


def test_a_press_through_the_camera_keeps_the_count_it_read_at(tmp_path, monkeypatch):
    """The camera's own press moves the link's count and is read after: the next press needs no grab."""
    reads = iter([SimpleNamespace(kind="dialog", focus=None), SimpleNamespace(kind="list", focus=None)])
    monkeypatch.setattr(live.screen, "read", lambda f: next(reads))
    with fake_link(tmp_path, monkeypatch) as lk:
        cam, grabbed = stale_camera(tmp_path, lk)
        cam.presses = 0
        frame = SimpleNamespace(image=None, path=tmp_path / "00009_down.png")
        cam.hdmi.settle = lambda *a, **k: (frame, True)
        cam.hdmi.timing = {}
        cam.press("down")
        assert cam._seen == lk.moves == 1 and grabbed == []
        cam.press("down")
        assert cam._seen == lk.moves == 2 and grabbed == []


def test_the_cameras_own_picture_is_read_from_a_file_of_this_process_and_removed():
    import os
    asked = []

    def osd(p):
        asked.append(p)
        p.write_bytes(b"not a picture")                # camlink wrote it; the reader cannot read it
        return p
    assert live.osd_kind(SimpleNamespace(osd=osd)) == ""
    assert asked[0].name == f"camkit_osd_{os.getpid()}_press.png" and not asked[0].exists()

    def fails(p):
        raise live.LinkError("no reply within 30 s")
    assert live.osd_kind(SimpleNamespace(osd=fails)) == ""


def test_the_page_scan_hands_each_press_the_screen_it_is_made_on(monkeypatch):
    sys.path.insert(0, str(ROOT / "kit"))
    import page_scan
    got = []
    monkeypatch.setattr(page_scan.screen, "read", lambda f: SimpleNamespace(kind="shooting", seen=f))
    link = SimpleNamespace(press=lambda button, screen=None: got.append((button, screen)))
    eyes = SimpleNamespace(settle=lambda before, tag, **k: (before, True), timing={})
    scan = page_scan.Scan(SimpleNamespace(dir=Path("made-up")), link, eyes, 10)
    scan.press("down", "the frame before", "down")
    assert got == [("down", SimpleNamespace(kind="shooting", seen="the frame before"))]


def test_drive_judges_its_on_shooting_keys_before_anything_connects():
    sys.path.insert(0, str(ROOT / "kit"))
    import drive
    assert drive.on_shooting_refused(["left", "MS_UP", " front", "Down"]) == ""
    assert "without being named" in drive.on_shooting_refused(["menu"])
    assert "never pressed" in drive.on_shooting_refused(["c4"]) and "never pressed" in drive.on_shooting_refused(["help"])
    assert "not a key" in drive.on_shooting_refused(["movie"]) and "not a key" in drive.on_shooting_refused(["fn"])
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "drive.py"), "--path", "Drive Mode", "--on-shooting", "c4"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "never pressed on the shooting screen" in r.stderr


def test_drive_refuses_a_press_that_meets_the_shooting_screen_unless_named():
    sys.path.insert(0, str(ROOT / "kit"))
    import drive
    why = drive.shooting_press_refused("down", "shooting", frozenset())
    assert "shooting screen" in why and "--on-shooting down" in why
    assert drive.shooting_press_refused("down", "shooting", {"down"}) == ""
    assert drive.shooting_press_refused("down", "menu", frozenset()) == ""
    assert drive.shooting_press_refused("menu", "shooting", frozenset()) == ""
    assert "--on-shooting front" in drive.shooting_press_refused("dial.front.1", "shooting", frozenset())
    assert drive.shooting_press_refused("dial.front.1", "shooting", {"front"}) == ""
    assert drive.shooting_press_refused("help", "shooting", {"left"})


def drive_on_shooting(tmp_path, monkeypatch, presses: list, named: list = (), kind: str = "shooting", more=()):
    """drive.py's main() with the camera on the shooting screen all along, or on a screen of `kind` (made up: the menu's
    way to the row, the cursor bar never at a "key@y" row, the session's end); `more`: other arguments. Returns the
    presses and dial turns sent with their keywords, the run's events and the drive.jsonl line."""
    sys.path.insert(0, str(ROOT / "kit"))
    import drive
    run = Run("kit2_drive", root=tmp_path)
    sent = []

    class Link:
        def __init__(self, r):
            self.run = r

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def press(self, key, **kw):
            sent.append(("link", key, kw))

        def download(self, tag):
            return tmp_path / f"{tag}.DAT"

    class Cam:
        frame = SimpleNamespace(path=tmp_path / "00001_shooting.png", image=None)

        def read(self):
            return SimpleNamespace(kind=kind)

        def press(self, key, **kw):
            sent.append(("cam", key, kw))

        def dial(self, name, steps, **kw):
            sent.append(("cam", f"dial {name} {steps}", kw))

        def refresh(self, tag):
            return self.read()
    ending = SimpleNamespace(after=tmp_path / "after.DAT", changes=[], uploaded=False)
    for name, value in (("check_readers", lambda: None), ("load_scan", lambda scan: ([], {})),
                        ("Run", lambda name: run),
                        ("eyes_from_config", lambda r: SimpleNamespace(attach=lambda link: None, grab=lambda save=False: None,
                                                                       close=lambda: None)),
                        ("screen", SimpleNamespace(read=lambda f: SimpleNamespace(kind="shooting"))),
                        ("wait_for", lambda *a, **k: None), ("Link", Link),
                        ("LiveCamera", lambda link, eyes, run, may_open=(): Cam()),
                        ("find_position", lambda cam, cycle, model: 0), ("go_to", lambda *a: True),
                        ("enter_any", lambda cam, path, i: None), ("bar_at", lambda cam, y: False),
                        ("screen_text", lambda cam, grip: ""), ("highlighted", lambda image, path: ""),
                        ("time", SimpleNamespace(sleep=lambda s: None)),
                        ("close_for_restore", lambda cam, link: sent.append(("closed",))),
                        ("session", SimpleNamespace(ended=lambda link, before, show=30: ending,
                                                    put_back=lambda link, e, before: e)),
                        ("restore_checked", lambda r, e, before: True)):
        monkeypatch.setattr(drive, name, value)
    argv = ["drive.py", "--path", "Drive Mode"] + [x for p in presses for x in ("--press", p)]
    monkeypatch.setattr(sys, "argv", argv + [x for k in named for x in ("--on-shooting", k)] + list(more))
    drive.main()
    events = [json.loads(l) for l in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()] \
        if (run.dir / "events.jsonl").exists() else []
    line = json.loads((run.dir / "drive.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    return [s for s in sent if s[0] == "cam"], events, line


@pytest.mark.parametrize("press", ["down@200", "left", "ms_up:.*"])
def test_drive_sends_nothing_but_menu_on_the_shooting_screen_unnamed(tmp_path, monkeypatch, capsys, press):
    pressed, events, line = drive_on_shooting(tmp_path, monkeypatch, [press])
    assert pressed == [("cam", "menu", {})] and line["completed"] is False and "on_shooting" not in line
    assert "the shooting screen" in capsys.readouterr().out and not any(e["kind"] == "on_shooting_press" for e in events)


def test_drive_presses_a_named_key_on_the_shooting_screen_and_says_whose_word(tmp_path, monkeypatch, capsys):
    """--on-shooting names the key: the cursor loop's presses and a plain press go, each marked for the link, the
    owner's word said in the console, the run's events.jsonl and drive.jsonl."""
    pressed, events, line = drive_on_shooting(tmp_path, monkeypatch, ["down@200"], named=["Down"])
    assert pressed == [("cam", "menu", {})] + [("cam", "down", {"on_shooting": frozenset({"down"})})] * 8
    assert line["on_shooting"] == ["down"] and line["completed"] is False          # the bar never reached its row
    assert sum(e["kind"] == "on_shooting_press" for e in events) == 8
    assert any(e["kind"] == "on_shooting_allowed" and e["keys"] == ["down"] for e in events)
    assert "the owner's word (--on-shooting down)" in capsys.readouterr().out
    pressed, _, line = drive_on_shooting(tmp_path, monkeypatch, ["left", "up"], named=["left"])
    assert pressed == [("cam", "menu", {}), ("cam", "left", {"on_shooting": frozenset({"left"})})]
    assert line["screens"][0]["on_shooting"] is True and line["completed"] is False     # Up was not named


def test_a_frame_moved_and_put_back_by_named_keys_goes_out_both_ways(tmp_path, monkeypatch):
    """The camera trial of 2026-11-10: MENU closes the menu, then ms_left and ms_right, both named, on the shooting
    screen, nothing lit there. Both go out and both are recorded: the put-back the operator named is never stranded by
    the refusal of a Right whose row cannot be read, since the shooting screen has no row to open."""
    pressed, events, line = drive_on_shooting(tmp_path, monkeypatch, ["menu", "ms_left", "ms_right"],
                                              named=["ms_left", "ms_right"])
    assert pressed == [("cam", "menu", {}), ("cam", "menu", {}),
                       ("cam", "ms_left", {"on_shooting": frozenset({"ms_left"})}),
                       ("cam", "ms_right", {"on_shooting": frozenset({"ms_right"})})]
    assert line["completed"] is True and [sc.get("on_shooting", False) for sc in line["screens"][:3]] == [False, True, True]
    assert sum(e["kind"] == "on_shooting_press" for e in events) == 2


def test_a_named_right_goes_on_the_shooting_screen_and_an_unnamed_one_does_not(tmp_path, monkeypatch, capsys):
    pressed, _, line = drive_on_shooting(tmp_path, monkeypatch, ["right"], named=["right"])
    assert pressed == [("cam", "menu", {}), ("cam", "right", {"on_shooting": frozenset({"right"})})]
    assert line["completed"] is True
    pressed, _, line = drive_on_shooting(tmp_path, monkeypatch, ["ms_right"], named=["ms_left"])
    assert pressed == [("cam", "menu", {})] and line["completed"] is False
    assert "--on-shooting ms_right" in capsys.readouterr().out


def test_the_naming_lifts_only_the_unread_row_refusals_and_only_on_the_shooting_screen():
    """press_refused: a named Right or Enter on the shooting screen is judged by the naming (no row there to open);
    unnamed, or on a menu page or an unknown screen whose lit row cannot be read, the older refusal stands; a named
    Enter still meets the Initialize and confirmation checks."""
    sys.path.insert(0, str(ROOT / "kit"))
    import drive
    for key in ("right", "ms_right", "enter", "ms_enter"):
        assert drive.press_refused(key, "", "", "shooting", on_shooting={key}) == "", key
        assert drive.press_refused(key, "", "", "shooting", on_shooting={"left"}), key
        assert drive.press_refused(key, "", "", "menu", on_shooting={key}), key
        assert drive.press_refused(key, "", "Made-up Words", "unknown", on_shooting={key}), key
    assert "row Right would open is unknown" in drive.press_refused("right", "", "", "menu", on_shooting={"right"})
    assert "initialize" in drive.press_refused("enter", "", "Initialize", "shooting", on_shooting={"enter"})
    assert "confirmation" in drive.press_refused("enter", "", "Execute? OK", "shooting", on_shooting={"enter"})
    assert drive.press_decision("enter!:.*", "enter", "", "x", "shooting", on_shooting={"enter"}) == ("", False)


def test_drive_turns_a_dial_on_the_shooting_screen_only_when_named(tmp_path, monkeypatch):
    """On the shooting screen a dial changes the live exposure: dial.front.1 is refused there unless --on-shooting names
    the dial, and then LiveCamera.dial is handed the name for the link."""
    pressed, _, line = drive_on_shooting(tmp_path, monkeypatch, ["dial.front.1:.*"])
    assert pressed == [("cam", "menu", {})] and line["completed"] is False
    pressed, events, line = drive_on_shooting(tmp_path, monkeypatch, ["dial.front.1:.*"], named=["front"])
    assert pressed == [("cam", "menu", {}), ("cam", "dial front 1", {"on_shooting": frozenset({"front"})})]
    assert line["screens"][0]["on_shooting"] is True and any(e["kind"] == "on_shooting_press" for e in events)


def test_drive_marks_on_shooting_only_a_named_key(tmp_path, monkeypatch):
    """A key that goes out on another screen, named or not, is not marked; nor is MENU, which needs no naming."""
    _, _, line = drive_on_shooting(tmp_path, monkeypatch, ["left", "menu"], named=["left"], kind="dialog")
    assert [("on_shooting" in sc) for sc in line["screens"][:2]] == [False, False]
    _, _, line = drive_on_shooting(tmp_path, monkeypatch, ["menu"])
    assert "on_shooting" not in line["screens"][0]


def test_drive_sends_c4set_and_c4reset_only_with_the_owners_word(tmp_path, monkeypatch, capsys):
    """c4set and c4reset are go-aheads an owner gives for their own body: refused before anything connects unless
    --c4-press names them, and the word is said in the console, the run's events.jsonl and drive.jsonl. Help (guarded
    Help) needs none."""
    sys.path.insert(0, str(ROOT / "kit"))
    import drive
    assert drive.c4_presses_refused(["c4set:Custom 1", "help"], ["c4set"]) == ""
    assert "--c4-press c4set" in drive.c4_presses_refused(["c4set:Custom 1"], [])
    assert "--c4-press c4reset" in drive.c4_presses_refused(["right", "c4reset:Look"], ["c4set"])
    assert drive.c4_presses_refused(["help", "enter:OK"], []) == ""
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "drive.py"), "--path", "Focus Area", "--press", "c4set:Custom"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "only with your owner's word for this run, --c4-press c4set" in r.stderr
    monkeypatch.setattr(drive, "c4set_refused", lambda kind, text: "")          # the screen check: Focus Area, Custom lit
    pressed, events, line = drive_on_shooting(tmp_path, monkeypatch, ["c4set:.*"], kind="dialog",
                                              more=["--c4-press", "c4set"])
    assert pressed == [("cam", "menu", {}), ("cam", "c4", {"allow": {"c4"}})]
    assert line["c4_allowed"] == ["c4set"] and line["screens"][0]["c4_allowed"] is True
    assert any(e["kind"] == "c4_allowed" for e in events) and any(e["kind"] == "c4_press" for e in events)
    assert "the owner's word (--c4-press c4set)" in capsys.readouterr().out


def test_the_notice_ok_of_to_shooting_goes_out_judged_on_the_notice(tmp_path, monkeypatch):
    """proving.nav.to_shooting: an information notice that refuses MENU takes OK, a cleanup press sent straight through
    the link: it carries the screen read (the notice), so the link's guard lets it out."""
    sys.path.insert(0, str(ROOT / "kit"))
    from camkit.link import LinkError
    from proving import nav
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    kinds = iter(["notice", "shooting"])
    monkeypatch.setattr(nav.screen, "read", lambda f: SimpleNamespace(kind=next(kinds)))
    monkeypatch.setattr(nav, "run_tmp_png", lambda f: tmp_path / "notice.png")
    monkeypatch.setattr(nav.ocr, "read", lambda paths, eng=None: {p: [] for p in paths})
    monkeypatch.setattr(nav.ocr, "text_in", lambda lines, box: "This operation or setting not available.")
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    with fake_link(tmp_path, monkeypatch) as lk:
        real = lk.press

        def press(key, **kw):
            if key == "menu":
                raise LinkError("press menu 60: button not accepted")
            return real(key, **kw)
        lk.press = press
        nav.to_shooting(lk, SimpleNamespace(grab=lambda save=False: SimpleNamespace(image=None)), "the test", tries=1)
    assert sum("press enter 60" in l for l in sent_lines(log)) == 1


def test_live_camera_hands_a_dial_the_black_frame_judgement(tmp_path, monkeypatch):
    """A dial on a black frame read as no known screen is judged on the camera's own picture, as a press is: the link
    gets "shooting" when that picture reads as the shooting screen, and refuses the dial there unless it is named."""
    turned = []
    cam, asked = black_camera(tmp_path, monkeypatch, "shooting")
    cam.link = SimpleNamespace(dial=lambda name, steps, screen=None, on_shooting=frozenset():
                               turned.append((name, steps, screen, on_shooting)))
    cam.hdmi.grab = lambda tag, save=True: SimpleNamespace(image=np.full((480, 640, 3), 90, np.uint8),
                                                           path=tmp_path / "00004_dial.png")
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    monkeypatch.setattr(live.screen, "read", lambda f: SimpleNamespace(kind="dialog", focus=None))
    cam.dial("front", 1, on_shooting="front")
    assert turned == [("front", 1, "shooting", "front")] and len(asked) == 1
    with fake_link(tmp_path, monkeypatch) as lk:
        cam, _ = black_camera(tmp_path, monkeypatch, "shooting")
        cam.link = lk
        with pytest.raises(safety.Refused, match="shooting screen"):
            cam.dial("front", 1)
        cam, _ = black_camera(tmp_path, monkeypatch, "")
        cam.link = lk
        with pytest.raises(safety.Refused, match="could not be read"):
            cam.dial("front", 1, on_shooting="front")


# ---------------------------------------------------------------- decision 8: no allowance opens identity rows

IDENTITY_ROWS = ["Language", "USB Connection Mode", "NTSC/PAL Selector", "Area/Date/Time Setting", "Date/Time Setup",
                 "Wi-Fi Connect", "Device Name", "Bluetooth Function", "Airplane Mode", "USB LUN Setting"]


@pytest.mark.parametrize("label", IDENTITY_ROWS)
def test_no_allowance_opens_the_cameras_identity_its_connections_or_its_region(label):
    assert safety.identity_row(label) and safety.never_lifted(label)
    why = safety.allow_refused(label)
    assert why and "0008" in why and "no --allow opens it" in why
    assert safety.path_refused([label], allowed=[label])
    assert safety.path_refused(["Setup", label], allowed=["Setup", label])
    assert live.open_refused(label, {label})
    assert safety.screen_refused(f"{label} MENU OK", allow=[label])


def test_the_rows_an_owner_may_still_allow_stay_allowed():
    for label in ("Audio Signal Volume", "Playback/Monitor. Vol.", "Monitor Brightness", "Auto Power OFF Temp.",
                  "Camera Set. Memory", "Reg. Custom Shoot Set", "Add Item", "Create New Folder", "Shutter When Pwr OFF"):
        assert safety.allow_refused(label) is None, label
    assert safety.path_refused(["Audio Signal Volume"], allowed=["Audio Signal Volume"]) is None
    assert live.open_refused("Audio Signal Volume  3", {"Audio Signal Volume"}) == ""


@pytest.mark.parametrize("args", [["--path", "Language", "--allow", "Language"],
                                  ["--path", "Setup", "--allow", "USB Connection Mode"],
                                  ["--path", "Network", "--path", "Device Name", "--allow", "Device Name"]])
def test_drive_refuses_an_identity_row_however_it_is_allowed(args):
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "drive.py"), *args], capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "no --allow opens it" in r.stderr and "0008" in r.stderr


def test_the_provers_allow_refuses_an_identity_row(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "provers"))
    import prove_run
    import scale_run
    monkeypatch.setattr(sys, "argv", ["prove_run", "--rows", "Language", "--allow", "Language"])
    with pytest.raises(SystemExit, match="0008"):
        prove_run.main()
    monkeypatch.setattr(sys, "argv", ["scale_run", "--row", "X", "--allow", "NTSC/PAL Selector"])
    with pytest.raises(SystemExit, match="0008"):
        scale_run.main()


# ---------------------------------------------------------------- C4 when the camera's mode cannot be read
# camlink answers get with "unknown property NAME" both for a property the body does not list and for a listed one
# whose read fails (kit/link/camlink.cpp cmdGet): whether it is listed is learnt from props, once per open link.

LISTED = json.dumps([{"name": "CameraOperatingMode", "current": 1}, {"name": "FNumber", "current": 800}])


@pytest.mark.parametrize("answer", [None, {"ok": True}, {"ok": True, "current": "2"}, {"ok": True, "current": None},
                                    {"ok": True, "current": True}])
def test_c4_refused_when_a_listed_mode_cannot_be_read(tmp_path, monkeypatch, answer):
    """The body lists CameraOperatingMode, and get gives no integer mode: the read failed (camlink's "unknown property",
    answer None here), or the answer holds none. C4 is refused whatever the words."""
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    monkeypatch.setenv("FAKE_CAMLINK_PROPS", LISTED)
    monkeypatch.setenv("FAKE_CAMLINK_GET", json.dumps({"CameraOperatingMode": answer} if answer else {}))
    with fake_link(tmp_path, monkeypatch) as lk, pytest.raises(safety.Refused, match="lists its operating mode but did "
                                                                                    "not give it"):
        lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"))
    assert not any("press c4" in l for l in sent_lines(log))


def test_c4_refused_when_the_question_gets_no_reply(tmp_path, monkeypatch):
    """camlink gone mid-question (here it exits on get) on a body that lists the mode."""
    monkeypatch.setenv("FAKE_CAMLINK_PROPS", LISTED)
    monkeypatch.setenv("FAKE_CAMLINK_EXIT", "get")
    lk = fake_link(tmp_path, monkeypatch).open()
    try:
        with pytest.raises(safety.Refused, match="a link in trouble"):
            lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"))
    finally:
        lk.close()


@pytest.mark.parametrize("fails", ["FAKE_CAMLINK_PROPS_FAIL", "FAKE_CAMLINK_EXIT"])
def test_c4_refused_when_props_cannot_be_read(tmp_path, monkeypatch, fails):
    """props answered with camlink's error ("GetDeviceProperties failed"), or camlink gone on it: whether the body lists
    the mode is not known, and C4 is refused; nothing is kept, so the next C4 asks again."""
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    monkeypatch.setenv(fails, "props" if fails == "FAKE_CAMLINK_EXIT" else "1")
    lk = fake_link(tmp_path, monkeypatch).open()
    try:
        with pytest.raises(safety.Refused, match="could not be read .props"):
            lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"))
        assert lk._mode_listed is None
    finally:
        lk.close()
    assert not any("press c4" in l for l in sent_lines(log))


def test_c4_goes_on_the_screen_alone_for_a_body_that_does_not_list_the_mode(tmp_path, monkeypatch):
    """props lists no CameraOperatingMode: the screen decides alone (decision 7), and props is asked once a link."""
    monkeypatch.setenv("FAKE_CAMLINK_PROPS", json.dumps([{"name": "FNumber", "current": 800}]))
    monkeypatch.delenv("FAKE_CAMLINK_GET", raising=False)
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"))["ok"]
        assert lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="dialog"))["ok"]
        events = [json.loads(l) for l in (lk.run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    cmds = [e["cmd"] for e in events if e["kind"] == "cmd"]
    assert cmds.count("props") == 1 and not any(c.startswith("get ") for c in cmds)


def test_c4_goes_on_a_listed_mode_that_is_not_playback(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CAMLINK_PROPS", json.dumps([{"name": "CrDeviceProperty_CameraOperatingMode"}]))
    monkeypatch.setenv("FAKE_CAMLINK_GET", json.dumps({"CameraOperatingMode": {"current": 1}}))       # Record
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"))["ok"]


def test_the_mode_question_logs_no_property_value(tmp_path, monkeypatch):
    """props holds the body's serial number and the photographer's and copyright texts: the question C4's check asks
    keeps only the count and whether the mode is listed in the run's log, no value and no other name; Link.props(),
    for its own callers, still logs its reply whole."""
    made_up = [{"name": "CameraOperatingMode", "current": 1}, {"name": "SerialNumber", "text": "MADE-UP-SERIAL-42"},
               {"name": "SetPhotographer", "text": "Made-up Person"}, {"name": "SetCopyright", "text": "Made-up Rights"}]
    monkeypatch.setenv("FAKE_CAMLINK_PROPS", json.dumps(made_up))
    monkeypatch.setenv("FAKE_CAMLINK_GET", json.dumps({"CameraOperatingMode": {"current": 1}}))
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"))["ok"]
        asked = [json.loads(l) for l in (lk.run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        assert lk.props() == made_up
        later = [json.loads(l) for l in (lk.run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    line = next(e for e in asked if e["kind"] == "cmd" and e["cmd"] == "props")
    assert {k: v for k, v in line["reply"].items() if k != "id"} == {"ok": True, "count": 4, "mode_listed": True}
    text = json.dumps(asked)
    assert not any(word in text for word in ("MADE-UP-SERIAL-42", "Made-up Person", "Made-up Rights", "SerialNumber",
                                             "SetPhotographer", "SetCopyright"))
    whole = [e for e in later if e["kind"] == "cmd" and e["cmd"] == "props"][-1]
    assert whole["reply"]["props"] == made_up, "Link.props() logs its own reply as before"
