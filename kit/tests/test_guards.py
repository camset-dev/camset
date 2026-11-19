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

    def press(self, key, hold_ms=60, allow=frozenset(), cleanup=False, screen=None, on_shooting=frozenset(),
              judged=False):
        self.sent.append(key)
        self.judged.append((screen, on_shooting))


def camera(tmp_path, kind, lit, may_open=()):
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.link, cam.run, cam.may_open = Presses(), Run("guards", root=tmp_path), frozenset(may_open)
    cam.screen = SimpleNamespace(kind=kind)
    cam.frame = SimpleNamespace(image=None, path=tmp_path / "00001_down.png")
    return cam


def readable(monkeypatch, text="Shooting 2/40 Drive Mode Single Shooting"):
    """The screen's text as the camera's own Enter check reads it (live.text_of, body_of, title_of): a menu page's, which
    asks nothing, for a test whose made-up frame OCR cannot read (the check refuses a screen it cannot read)."""
    for name in ("text_of", "body_of", "title_of"):
        monkeypatch.setattr(live, name, lambda cam: text)
    unchanged(monkeypatch)


def unchanged(monkeypatch):
    """The screen looked at again just before an Enter (live.look_again) is the one judged: a made-up camera has no
    eyes to grab from."""
    monkeypatch.setattr(live, "look_again", lambda eyes, judged, tag, moved_at=None: ("", None))


@pytest.mark.parametrize("key", ["right", "enter", "ms_right", "ms_enter"])
def test_choke_point_refuses_opening_a_never_open_row(tmp_path, monkeypatch, key):
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Access Authen. Info")
    unchanged(monkeypatch)              # an Enter looks at the screen again first (LiveCamera.look_before)
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
    unchanged(monkeypatch)              # an Enter looks at the screen again first (LiveCamera.look_before)
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Access Authen. Info")
    cam = camera(tmp_path, "submenu", "Access Authen. Info")
    with pytest.raises(safety.Refused, match="never opened"):
        cam.press(key)
    assert cam.link.sent == []
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Drive Mode  Single Shooting")
    readable(monkeypatch)                   # past the camera's own Enter check, which asks a readable screen
    with fake_link(tmp_path, monkeypatch) as lk:
        cam = camera(tmp_path, "submenu", "")
        cam.link = lk
        with pytest.raises(safety.Refused, match="not written as the guards read it"):
            cam.press(key)


def test_choke_point_lets_a_named_row_and_other_presses_through(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Reg. Custom Shoot Set")
    readable(monkeypatch)
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
        assert lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind=kind), judged=lk.moves)["args"] == ["c4", "60", "allowed"]


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
        lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"), judged=lk.moves)
    monkeypatch.setenv("FAKE_CAMLINK_GET", json.dumps({"CameraOperatingMode": {"current": 1}}))       # Record
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"), judged=lk.moves)["ok"]


def test_live_camera_hands_its_screen_to_the_link(tmp_path, monkeypatch):
    """LiveCamera.press, the way every walker presses, gives the link the screen it read last."""
    seen = []
    readable(monkeypatch)                   # C4 meets the camera's check of what the screen asks too
    cam = camera(tmp_path, "menu", "")
    cam.link = SimpleNamespace(press=lambda key, hold_ms=60, allow=frozenset(), screen=None, on_shooting=frozenset(),
                               judged=None:
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
    unchanged(monkeypatch)              # an Enter looks at the screen again first (LiveCamera.look_before)
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
    readable(monkeypatch, "Drive Mode Single Shooting Continuous Shooting")     # a list that asks nothing
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
        # an Enter goes with the camera layer's word that its check judged it (camkit.live), named or not
        def judged():                   # the link's move count now: what the camera layer's check hands it
            return {"judged": lk.moves} if key in safety.ENTER_KEYS else {}
        assert lk.press(key, screen=shooting, on_shooting=key, **judged())["args"][0] == key       # named for this press
        assert lk.press(key, screen=SimpleNamespace(kind="menu"), **judged())["args"][0] == key    # no shooting screen
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


def drive_on_shooting(tmp_path, monkeypatch, presses: list, named: list = (), kind: str = "shooting", more=(),
                      text: str = "", lit: str = ""):
    """drive.py's main() with the camera on the shooting screen all along, or on a screen of `kind` (made up: the menu's
    way to the row, the cursor bar never at a "key@y" row, the session's end), the screen's text `text` and its lit
    text `lit`; `more`: other arguments. Returns the presses and dial turns sent with their keywords (and the camera's
    confirm word, confirm_once, where drive.py gave it for that press), the run's events and the drive.jsonl line."""
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

        def __init__(self):
            self.run = run                  # the run's events.jsonl, where a refused notice is logged

        def read(self):
            return SimpleNamespace(kind=kind)

        def press(self, key, **kw):
            said = {**kw, **({"confirm_once": True} if getattr(self, "confirm_once", False) else {}),
                    **({"answer_once": self.answer_once} if getattr(self, "answer_once", None) else {})}
            sent.append(("cam", key, said))
            self.confirm_once, self.answer_once = False, None

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
                        ("LiveCamera", lambda link, eyes, run, may_open=(), **kw: Cam()),
                        ("find_position", lambda cam, cycle, model: 0), ("go_to", lambda *a: True),
                        ("enter_any", lambda cam, path, i: None), ("bar_at", lambda cam, y: False),
                        ("screen_text", lambda cam, grip: text), ("highlighted", lambda image, path: lit),
                        ("time", SimpleNamespace(sleep=lambda s: None)),
                        ("close_for_restore", lambda cam, link, start: sent.append(("closed",))),
                        ("restore_checked", lambda r, e, before: True)):
        monkeypatch.setattr(drive, name, value)
    import runner
    monkeypatch.setattr(runner.session, "finish", lambda link, before, tag="after", show=30: ending)  # end_session's
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
    the link: judged as the camera judges a notice that has just refused MENU (live.menu_refused_enter: its OK lit and
    alone, no question mark, no confirmation's words), it carries the screen read (the notice) and the camera layer's
    judged word, so the link's guards let it out."""
    sys.path.insert(0, str(ROOT / "kit"))
    from camkit.link import CameraRefused
    from proving import nav
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    kinds = iter(["notice", "shooting"])
    monkeypatch.setattr(nav.screen, "read", lambda f: SimpleNamespace(kind=next(kinds)))
    monkeypatch.setattr(nav, "run_tmp_png", lambda f: tmp_path / "notice.png")
    monkeypatch.setattr(nav.ocr, "read", lambda paths, eng=None: {p: [] for p in paths})
    monkeypatch.setattr(nav.ocr, "text_in", lambda lines, box: "OK" if box == (200, 340, 440, 395)    # its lit OK
                        else "This operation or setting not available.")
    monkeypatch.setattr(live, "lit_found", lambda image, kind=None: ((200, 340, 440, 395), True))     # its lit OK
    monkeypatch.setattr(live, "look_again", lambda eyes, judged, tag, moved_at=None: ("", SimpleNamespace(image=None)))  # unchanged
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    with fake_link(tmp_path, monkeypatch) as lk:
        real = lk.press

        def press(key, **kw):
            if key == "menu":
                raise CameraRefused("press menu 60: button not accepted")      # the camera's own refusal
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
                 "Device Name", "USB LUN Setting", "Wired LAN Connect", "IP Address Setting", "WPS Push",
                 "Access Point Set.", "Pairing", "Manage Paired Device", "Edit Device Name"]


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


# Wi-Fi and Bluetooth rows that no pattern caught though decision 8's Rule line names them, and the screens that show
# the camera's MAC and IP addresses and its Bluetooth device address (a review, 2026-11-13): the a1 II's labels as it
# draws them, then as a reader returns them (a capital I for an l, zeros, "rn" or "n" for "m", 1, l or | for i or l, 8
# for B, a letter dropped, a space dropped or put in, Addr. for Address, Freq. for Frequency, Remote for Rmt, Cyrillic
# and full-width look-alikes, a no-break hyphen or an en dash, a zero-width or no-break space, two spaces, a line
# break, a stop after the label); and Wi-Fi Connect, which a pattern caught only as written before. Since the owner's
# decision of 2026-11-13 (decision 8) they are a class of their own, with Wi-Fi Connect, Bluetooth Function and Airplane
# Mode (identity rows before): no --allow, approved motion decision, may_open or vouched Enter opens them, and only a
# dated decision naming the row does (test_network_rows.py)
NETWORK_ROWS = ["Bluetooth Rmt Ctrl", "Wi-Fi Frequency Band", "Display Wi-Fi Info.", "Display Wired LAN Info.",
                "Disp Device Address", "Wi-Fi Connect", "Bluetooth Function", "Airplane Mode"]
NETWORK_READ_AS = [
    # Bluetooth Rmt Ctrl
    "BIuetooth Rmt Ctrl", "Bluet00th Rmt Ctrl", "Bluetooth Rrnt Ctrl", "Bluetooth Rnt Ctrl", "Bluetoth Rmt Ctrl",
    "8luetooth Rmt Ctrl", "\u0412luetooth Rmt Ctrl", "Bluetooth\u00a0Rmt Ctrl", "Bluetooth Rmt Ctrl.",
    "Bluetooth Remote Ctrl", "Bluetooth Remote Control",
    # Wi-Fi Frequency Band
    "Wi\u2011Fi Frequency Band", "Wi\u2013Fi Frequency Band", "WiFi Frequency Band", "Wi-Fi Frequency B\u0430nd",
    "\uff37\uff49-\uff26\uff49 Frequency Band", "Wi-Fi Frequency\nBand", "Wi-Fl Frequency Band", "Wi-Fi Freq. Band",
    "Wi-Fl Freq. Band", "W1-Fi Frequency Band",
    # Display Wi-Fi Info.
    "Display Wi\u2011Fi Info.", "Display Wi-Fi lnfo.", "Display Wi-Fi Inf0.", "Display Wi\u200b-Fi Info.",
    "Display Wi-FiInfo.", "Display Wi - Fi Info.", "Display Wi-Fl Info.", "Display Wi-F1 Info.", "Display Wi-Fi 1nfo.",
    # Display Wired LAN Info., and a reading that lost "Wired" or a LAN Info. row another body may show
    "Display LAN Info.", "LAN 1nfo.", "Display Wired LAN lnfo.", "Display Wired L\u0410N Info.", "Display Wired LAN\u00a0Info.", "Display Wired LAN  Info.",
    "Display Wired LANInfo.", "Display WiredLAN Info.", "Display Wired IAN Info.", "Display Wired 1AN Info.",
    "Display Wired LAN 1nfo.",
    # Disp Device Address, and a MAC address row another body may show
    "Disp D\u0435vice Address", "Disp Device\u00a0Address", "Disp Device  Address", "Disp Device Address.",
    "Disp Dev1ce Address", "Disp Devlce Address", "Disp Device Addr.", "MAC Address", "MAC Addr.", "Disp MAC Address",
    # Wi-Fi Connect
    "Wi-Fl Connect", "Wi-FiConnect", "Wi-F1 Connect", "Wi - Fi Connect"]


@pytest.mark.parametrize("label", NETWORK_ROWS + NETWORK_READ_AS)
def test_wifi_and_bluetooth_rows_and_the_address_screens_open_by_no_allowance(label):
    why = safety.never_open(label)
    assert why and why.startswith(safety.NETWORK + ":") and not safety.owner_may_approve(why), why
    assert safety.identity_row(label) is None and safety.never_lifted(label) is None         # a class of its own
    assert safety.network_words(label)
    assert safety.path_refused([label]) and safety.path_refused(["Network", label])          # no decision
    assert live.open_refused(label) and safety.screen_refused(f"{label} MENU OK")
    assert safety.path_refused([label], {label})                     # a dated decision without "lifts": approved
    assert "0008" in safety.allow_refused(label) and "no --allow opens it" in safety.allow_refused(label)
    assert safety.path_refused([label], {label}, allowed=[label])
    assert safety.path_refused(["Network", label], allowed=["Network", label])
    assert live.open_refused(label, {label})                         # may_open: drive.py's --allow, a prover's
    assert safety.screen_refused(f"{label} MENU OK", allow=[label])  # a vouched Enter


# Wi-Fi Direct Info. as a reader returns it: credentials (decision 9) however it is spelt, whatever is allowed
CREDENTIAL_READ_AS = ["Wi-Fl Direct Info.", "Wi-FiDirect Info.", "Wi-F1 Direct Info.", "Wi - Fi Direct Info.",
                      "Wi-Fi D1rect Info.", "Wi-Fl Direct Settings"]


@pytest.mark.parametrize("label", CREDENTIAL_READ_AS)
def test_wifi_direct_never_opens_however_a_reader_returns_it(label):
    why = safety.never_open(label)
    assert why and why.startswith("credentials") and not safety.owner_may_approve(why), why
    assert safety.never_lifted(label) and safety.allow_refused(label)
    assert safety.path_refused([label], {label}, allowed=[label]) and live.open_refused(label, {label})
    assert safety.screen_refused(f"{label} MENU OK", allow=[label])


# The body's serial number on screen: never opened whatever is allowed, since every saved frame would hold it
# (2026-11-13). Display Serial Number is an action's row still, as before; Write Serial Number, whether pictures carry
# the number, is walked as before (NETWORK_NEAR_WALKED).
SERIAL_ROWS = ["Display Serial Number", "Disp. Serial Number", "Disp Serial Number", "Displ\u0430y Serial Number",
               "Display Serial\u00a0Number", "Display  Serial Number", "Setup > Setup Option > Display Serial Number"]


@pytest.mark.parametrize("label", SERIAL_ROWS)
def test_the_serial_number_screen_never_opens_whatever_is_allowed(label):
    assert safety.never_open(label) and safety.path_refused([label])                         # no allowance
    assert safety.identity_row(label) and safety.never_lifted(label)                          # an allowance naming it
    assert "0008" in safety.allow_refused(label) and "no --allow opens it" in safety.allow_refused(label)
    assert safety.path_refused([label], allowed=[label]) and live.open_refused(label, {label})
    assert safety.screen_refused(f"{label} MENU OK", allow=[label])


# Rows beside them that the new patterns leave as they were: the Network tab's group names, the other Display rows,
# the remote shooting rows, Write Serial Number, and Bluetooth Rmt Ctrl's help line in the definition (the pattern
# takes "Rmt" or "Remote Ctrl", never "remote commander"); a flicker row another body may draw, since no a1 II label
# but Wi-Fi Frequency Band holds "freq" (a pattern takes Freq. only after Wi-Fi); and the Bluetooth, Wi-Fi and address
# rows already refused, each for its own words still
NETWORK_NEAR_WALKED = ["Wi-Fi", "Bluetooth", "Wired LAN", "Network Option", "Display Media Info.", "HDMI Info. Display",
                       "Display Quality", "Display Rotation", "Display All Info.", "Display as Group", "No Disp. Info.",
                       "Remote Shoot Setting", "Remote Zoom", "Lets a Bluetooth remote commander control the camera.",
                       "Write Serial Number", "Flicker Freq."]
NETWORK_NEAR_REFUSED = {"Bluetooth Function": "network setting or address screen: bluetooth function",
                        "Pairing": "by hand only: pairing", "Manage Paired Device": "by hand only: paired",
                        "Wi-Fi Connect": "network setting or address screen: wi-fi connect",
                        "Wired LAN Connect": "by hand only: wired lan connect", "Wi-Fi Direct Info.": "credentials: wi-fi direct",
                        "IP Address Setting": "by hand only: ip address", "SSID/PW Reset": "action: ssid/pw reset",
                        "Display Serial Number": "action: display serial number"}


@pytest.mark.parametrize("label", NETWORK_NEAR_WALKED)
def test_the_rows_beside_them_are_walked_as_before(label):
    assert safety.never_open(label) is None and safety.never_lifted(label) is None
    assert safety.allow_refused(label) is None and safety.screen_refused(label) is None


@pytest.mark.parametrize("label,why", NETWORK_NEAR_REFUSED.items())
def test_the_rows_beside_them_are_refused_as_before(label, why):
    assert safety.never_open(label) == why


@pytest.mark.parametrize("args", [["--path", "Language", "--allow", "Language"],
                                  ["--path", "Setup", "--allow", "USB Connection Mode"],
                                  ["--path", "Network", "--path", "Device Name", "--allow", "Device Name"],
                                  ["--path", "Network", "--path", "Bluetooth Rmt Ctrl", "--allow", "Bluetooth Rmt Ctrl"],
                                  ["--path", "Network", "--allow", "Display Wired LAN Info."]])
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
        lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"), judged=lk.moves)
    assert not any("press c4" in l for l in sent_lines(log))


def test_c4_refused_when_the_question_gets_no_reply(tmp_path, monkeypatch):
    """camlink gone mid-question (here it exits on get) on a body that lists the mode."""
    monkeypatch.setenv("FAKE_CAMLINK_PROPS", LISTED)
    monkeypatch.setenv("FAKE_CAMLINK_EXIT", "get")
    lk = fake_link(tmp_path, monkeypatch).open()
    try:
        with pytest.raises(safety.Refused, match="a link in trouble"):
            lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"), judged=lk.moves)
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
            lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"), judged=lk.moves)
        assert lk._mode_listed is None
    finally:
        lk.close()
    assert not any("press c4" in l for l in sent_lines(log))


def test_c4_goes_on_the_screen_alone_for_a_body_that_does_not_list_the_mode(tmp_path, monkeypatch):
    """props lists no CameraOperatingMode: the screen decides alone (decision 7), and props is asked once a link."""
    monkeypatch.setenv("FAKE_CAMLINK_PROPS", json.dumps([{"name": "FNumber", "current": 800}]))
    monkeypatch.delenv("FAKE_CAMLINK_GET", raising=False)
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"), judged=lk.moves)["ok"]
        assert lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="dialog"), judged=lk.moves)["ok"]
        events = [json.loads(l) for l in (lk.run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    cmds = [e["cmd"] for e in events if e["kind"] == "cmd"]
    assert cmds.count("props") == 1 and not any(c.startswith("get ") for c in cmds)


def test_c4_goes_on_a_listed_mode_that_is_not_playback(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CAMLINK_PROPS", json.dumps([{"name": "CrDeviceProperty_CameraOperatingMode"}]))
    monkeypatch.setenv("FAKE_CAMLINK_GET", json.dumps({"CameraOperatingMode": {"current": 1}}))       # Record
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"), judged=lk.moves)["ok"]


def test_the_mode_question_logs_no_property_value(tmp_path, monkeypatch):
    """props holds the body's serial number and the photographer's and copyright texts: the question C4's check asks
    keeps only the count and whether the mode is listed in the run's log, no value and no other name; Link.props(),
    for its own callers, still logs its reply whole."""
    made_up = [{"name": "CameraOperatingMode", "current": 1}, {"name": "SerialNumber", "text": "MADE-UP-SERIAL-42"},
               {"name": "SetPhotographer", "text": "Made-up Person"}, {"name": "SetCopyright", "text": "Made-up Rights"}]
    monkeypatch.setenv("FAKE_CAMLINK_PROPS", json.dumps(made_up))
    monkeypatch.setenv("FAKE_CAMLINK_GET", json.dumps({"CameraOperatingMode": {"current": 1}}))
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"), judged=lk.moves)["ok"]
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


# ---------------------------------------------------------------- words OCR runs together or splits (2026-11-14)

def definition_labels() -> list:
    """The a1 II definition's menu labels and every label of its settings' row paths, as written there."""
    doc = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    out = {m.get("label") for m in doc.get("menu") or [] if isinstance(m, dict)}
    out |= {x for s in doc.get("settings") or [] if isinstance(s, dict) for x in s.get("row") or []}
    return sorted(x for x in out if isinstance(x, str) and x.strip())


def run_together(label: str) -> list:
    """Every reading of `label` with one of its spaces dropped, and with all of them dropped."""
    words = label.split(" ")
    out = {label.replace(" ", "")} | {" ".join(words[:i] + [words[i] + words[i + 1]] + words[i + 2:])
                                      for i in range(len(words) - 1)}
    return sorted(out - {label})


def split_apart(label: str) -> list:
    """Every reading of `label` with one space put between two of its letters or digits."""
    return [label[:i] + " " + label[i:] for i in range(1, len(label)) if label[i - 1].isalnum() and label[i].isalnum()]


def test_no_never_open_row_of_the_definition_escapes_with_its_words_run_together_or_split():
    """A reading with one space dropped made an ordinary row of 54 of the a1 II definition's 95 never-open labels (its
    menu's and its settings' rows: actions, credentials, sound and light, identity rows, network settings), in
    drive.py's press check and the camera's own: a pattern with a space in it never matched the words run together.
    Every never-open row of the definition, read with any one of its spaces dropped, with all of them dropped, or with
    one space put inside a word ("Forma t"), is refused by never_open, the camera's open_refused and drive.py's press
    check (safety._glued, and the reading with every space taken out in safety._sources)."""
    import drive
    labels = [x for x in definition_labels() if safety.never_open(x)]
    together = [(x, v) for x in labels for v in run_together(x)]
    apart = [(x, v) for x in labels for v in split_apart(x)]
    assert len(labels) >= 80 and len(together) >= 150 and len(apart) >= 1000
    for label, v in together:
        assert safety.never_open(v), (label, v)
        assert live.open_refused(v) and drive.press_refused("right", v, "", "menu"), (label, v)
    for label, v in apart:
        assert safety.never_open(v) and live.open_refused(v), (label, v)


# the a1 II's ordinary rows whose words, run together, hold a word of the never-open list: none is an action, nor any
# other class of it, for the reading with every space taken out ("fileformat" is no "format": the actions are matched
# whole)
ORDINARY_RUN_TOGETHER = ["Av/Tv Rotate", "Bird: Detailed Settings", "Crop Level", "Delete confirm.",
                         "Delete pressing twice", "File Format", "File Name Format", "Pre-Capture Settings",
                         "Px Proxy File Format", "Rating Set(Custom Key)", "Time Code Format", "Time Code Preset",
                         "User Bit Preset", "Zoom Ring Rotate", "Drive Mode", "Focus Area"]


@pytest.mark.parametrize("label", ORDINARY_RUN_TOGETHER)
def test_an_ordinary_row_holding_a_never_open_word_run_together_stays_ordinary(label):
    assert label in definition_labels()
    assert safety.never_open(label) is None and live.open_refused(label) == ""


def test_each_guard_judges_the_words_run_together_as_it_judges_them_spaced():
    """safety._glued gives every guard pattern with a space in it a copy without: each guard that judges a label or a
    screen judges the words run together as it judges them spaced (one assertion per guard, so that leaving _glued out
    of any one of them fails here), and "WPS Push" run together is WPS ("\\bwps\\b" never matched "wpspush")."""
    assert safety._glued([r"wake on lan", r"wps\s?push", r"delete slot ?1/2", r"copy"]) == [
        r"wake on lan", r"wakeonlan", r"wps\s?push", r"wpspush", r"delete slot ?1/2", r"deleteslot1/2", r"copy"]
    assert safety.never_open("SettingReset") == "action: settingreset"                        # _ACTION_RE
    assert safety.never_open("ScreenReader").startswith("by hand only")                       # _ANYWHERE_RE
    assert safety.identity_row("WakeOnLAN")                                                   # _IDENTITY_RE
    assert safety.never_open("AccessAuthen. Info").startswith("credentials")                  # _CREDENTIALS_RE
    assert safety.never_open("ShutterWhenPwr OFF").startswith(safety.MOTION)                  # _MOTION_RE
    assert safety.network_row("AirplaneMode")                                                 # _NETWORK_SETTINGS_RE
    assert safety.never_open("AirplaneMode").startswith(safety.NETWORK)                       # _NETWORK_RE
    assert safety.lift_class("WakeOnLAN") == safety.LIFT_IDENTITY                             # _IDENTITY_LIFTABLE_RE
    assert safety.lift_class("Wake On LAN Access") == safety.LIFT_IDENTITY
    assert safety.lift_class("Wake On LAN AccessPoint") is None                               # _IDENTITY_FIXED_RE
    assert safety.lift_class("Wake On LAN ScreenReader") is None                              # _OTHER_BY_HAND_RE
    assert safety.never_choose("AirplaneMode")                                                # _NEVER_CHOOSE_RE
    assert "never, whatever is allowed" in safety.never_lifted("AccessAuthen. Info")          # _NEVER_LIFTED_RE
    assert "never, whatever is allowed" in safety.never_lifted("ResetNetwork Set.")           # reset ?network
    assert safety.screen_refused("SettingReset")                                              # _ACTION_ANY_RE
    assert safety.identity_screen("WakeOnLAN")                                                # _IDENTITY_SCREEN_RE
    assert safety.inside_menu_only(safety.LIFT_IDENTITY, "list", "AccessPoint list")          # _SECRET_SCREEN_RE
    assert safety.acts_on_open("CreateNewFolder")                                             # _ACTS_ON_OPEN_RE
    assert safety.link_risk_open("AccessPoint Set.")                                          # _LINK_RISK_OPEN_RE
    assert safety.registers("FaceMemory")                                                     # _REGISTERS_RE
    assert safety.writes_card("CreateNewFolder")                                              # _WRITES_CARD_RE
    assert safety.link_wiping("ResetNetwork Set.")                                            # _LINK_WIPING
    assert any(safety.LINK_WIPING_ENTER.search(r) for r in safety.readings("ResetNetwork Set."))
    assert "settingreset" in safety.profile_reset_dialog(                                     # _NOT_PROFILE_RESET
        "SettingReset? Reset PP1 to the default setting? Enter Cancel", "PP1")
    assert "start or end a connection" in safety.network_refused("FTPFunction")              # _NOT_LIFTED_WHY
    for label in ("WPS Push", "WPSPush"):
        assert safety.identity_row(label) and safety.acts_on_open(label) and safety.link_risk_open(label), label
        assert safety.inside_menu_only(safety.LIFT_IDENTITY, "list", label), label


@pytest.mark.parametrize("split,why", [("Forma t", "action: format"), ("Cop y", "action: copy"),
                                       ("De lete", "action: delete"), ("Initia lize", "action: initialize"),
                                       ("Access Auth en. Info", "credentials: accessauthen"),
                                       ("Scre en Reader", "by hand only: screenreader")])
def test_a_word_split_by_a_space_is_judged_whole(split, why):
    """A word OCR splits ("Forma t") is the word: the reading with every space taken out judges it (it only adds
    refusals: the readings with the space are judged beside it)."""
    assert safety.never_open(split) == why and live.open_refused(split)


def test_a_name_the_run_was_allowed_lifts_its_own_words_run_together_too():
    """screen_refused: a name given with --allow lifts its words on the screen, in the reading with every space taken out
    too (and, as before, nothing else); the row's own words on its own screen likewise (owner_menu_only)."""
    assert safety.screen_refused("Camera Set. Memory  MR 1 2 3")
    assert safety.screen_refused("Camera Set. Memory  MR 1 2 3", allow=("Camera Set. Memory",)) is None
    assert safety.screen_refused("Camera Set. Memory  Format", allow=("Camera Set. Memory",))
    assert safety.owner_menu_only(safety.LIFT_CREDENTIALS, "list", "Access Authen. On Off", "Access Authen.") is None
    assert safety.owner_menu_only(safety.LIFT_CREDENTIALS, "list", "Access Authen. AccessPoint", "Access Authen.")


# ---------------------------------------------------------------- what the run-together view may not permit (2026-11-14)

def one_row(row, **extra) -> dict:
    return {"decisions": [{"lifts": "network", "date": "2026-11-13", "why": "w", "rows": [row], **extra}]}


@pytest.mark.parametrize("row", ["Wired LANConnect", "W ired LAN Connect", "Wake OnLAN", "WakeOn LAN", "Wi-Fi Conn ect",
                                 "AirplaneMode", "RemoteShoot Function", "Cnct.while Power OFF"])
def test_a_network_decision_names_a_row_as_the_camera_writes_it(row):
    """Finding 1: a decision that names a row with its words run together or split was accepted with its options once
    the never-open list read such a name (2026-11-14, a review): never_choose's word boundaries never matched it, so the
    USB row's option would have been chosen. A name that reads otherwise as written than run together or split is
    refused (safety._read_otherwise), and never_choose reads USB and DNS at a word's start."""
    rows, options, refusals = safety._network_decisions(one_row(row, options={row: ["On"]}))
    assert rows == {} and options == {} and "name the row as the camera writes it" in refusals[0], refusals
    assert safety.network_refused(row).startswith("name the row as the camera writes it")


def test_never_choose_reads_usb_and_dns_at_a_words_start():
    """Finding 1: "\\busb\\b" never matched "USBConnection"; never_choose refused the spaced name and passed the glued
    one."""
    for row in ("USBConnection Mode", "USB Connection Mode", "USBLUN Setting", "Primary DNSServer", "DNS1", "USB1"):
        assert safety.never_choose(row), row
    assert safety.look_refused("enter", "PC Remote", "USBConnection Mode", ["PC Remote"])
    for row in ("USB Connection Mode", "USBConnection Mode"):               # no network decision opens either
        rows, _, refusals = safety._network_decisions(one_row(row, options={row: ["PC Remote"]}))
        assert not rows and any("no option of a row naming 'usb'" in r for r in refusals), refusals
    # its class alike, but an option chosen only as written: "remoteshoot" run together is Remote Shoot
    assert "whether no option of it is chosen" in safety.network_refused("Wake On LAN Remoteshoot")


@pytest.mark.parametrize("row", ["Shooting > Shooting Mode > RecallCamera Setting",
                                 "Shooting > Shooting Mode > Re call Camera Setting",
                                 "Shooting > Shooting Mode > Recall Camera Setting"])
def test_no_owner_decision_names_recall_camera_setting_however_it_is_read(row):
    """Finding 1: _LOADS read "recall" with word boundaries, so "RecallCamera Setting" or "Re call Camera Setting" with
    "confirm" was accepted as an action. Each word of _LOADS is read where a word may start, whatever follows it."""
    places = [("Shooting", "Shooting Mode", "Recall Camera Setting")]
    got = safety.owner_decided({"decisions": [{"lifts": "owner", "date": "2026-11-13", "why": "w", "rows": [row],
                                               "confirm": [row]}]}, places)
    assert got["rows"] == {} and "loads settings or a file" in got["refusals"][0]
    for word in ("Download", "Upload", "Reload", "important", "Save/Load Settings", "Save/Load FTP Settings"):
        assert not any(safety._LOADS_RE.search(r) for r in safety.readings(word)), word
    for word in ("Load", "Loading...", "LOADPRESET", "Import Root Certificate", "ImportRoot", "RegisterIPTC Info",
                 "2RegisterIPTC Info", "User1: (No Import)"):
        assert any(safety._LOADS_RE.search(r) for r in safety.readings(word)), word


@pytest.mark.parametrize("label,what", [("DeleteAll", "its class"), ("AccessAuthen.", "its class"),
                                        ("Access Authen. AccessPoint", "whether its opening acts")])
def test_an_owner_decision_names_a_row_as_the_camera_writes_it(label, what):
    """Finding 1 (and 8): an owner decision's row that reads otherwise once its words run together or split (its class,
    or whether its opening acts: "AccessPoint" acts on opening only run together, which made a "confirm" of a
    credentials row acceptable) is refused, whatever its path."""
    places = [("Network", "Network Option", "Access Authen. Settings")]
    entry = f"Network > Network Option > Access Authen. Settings > {label}"
    why, _, _ = safety.owner_row_refused(entry, places)
    assert why.startswith("name the row as the camera writes it") and what in why, why
    assert safety.owner_row_refused("Network > Network Option > Access Authen. Settings > Access Authen.", places)[0] \
        == ""


@pytest.mark.parametrize("label", ["DeleteAll", "De lete All", "DeleteSlot1/2", "FormatSlot 1", "Forma t",
                                   "De lete AII"])
def test_no_allowance_opens_a_card_action_however_its_words_are_read(label):
    """Finding 2: the never-lifted tier read Format and Delete with word boundaries, so "DeleteAll" was opened by a run
    that named it (--allow, a LiveCamera's may_open). Format and Delete are read at a word's start in every reading."""
    import drive
    assert safety.never_lifted(label) and safety.allow_refused(label).startswith("nothing on the cards"), label
    if safety.never_open(label):            # "FormatSlot 1" is no row of the list, run together or spaced
        assert live.open_refused(label, may_open={label})
        assert drive.press_refused("right", label, "", "menu", allow=(label,))
        assert safety.path_refused(["Playback", "Delete", label], allowed=(label,))


GLUED_QUESTIONS = ["Formatthe memory card? Enter Cancel", "Formatthememorycard?EnterCancel", "PressOKToFormat?",
                   "ResetPP1 to the default setting? Enter Cancel", "Deletethis image?DeleteCancel"]


@pytest.mark.parametrize("text", GLUED_QUESTIONS)
def test_enter_on_a_confirmation_read_run_together_needs_confirm(text):
    """Finding 3: confirmation's word boundaries never matched a question OCR ran together, and drive.py's Enter guard
    is a refusal: Enter went out with no --confirm. confirmation_refused judges the text with its CamelCase set apart
    and with every space taken out too; confirmation itself, which permits an armed press, is as it was."""
    import drive
    assert safety.confirmation(text) is None and safety.confirmation_refused(text)
    assert "confirmation text" in drive.press_refused("enter", "Enter", text, "dialog")
    assert drive.press_refused("enter", "Enter", text, "dialog", confirm=True) == ""


@pytest.mark.parametrize("text", ["File Format XAVC HS 8K", "FileFormat RAW", "Time Code Preset",
                                  "Folder Name Standard Form", "This function is currently disabled.", "Complete. OK"])
def test_the_refusal_check_leaves_ordinary_screens_alone(text):
    assert safety.confirmation_refused(text) is None, text


def test_a_seen_step_on_a_question_read_run_together_is_the_final_press():
    """Finding 3: owner_enter's seen step takes the refusal check: a slot's screen whose question OCR ran together is no
    safe step; notice_kept keeps nothing of a notice that reads so."""
    rows = ("Format", safety.LIFT_CARDS, "list", "Slot 1")
    assert safety.owner_enter(*rows, "Slot 1 Slot 2", ["Slot 1"], ["Slot 1"]) == ("", "step")
    assert safety.owner_enter(*rows, "Formatthe memory card Slot 1", ["Slot 1"], ["Slot 1"]) == ("", "final")
    follows = "This operation or setting not available as follows "
    assert safety.notice_kept(follows + "Drive Mode", ["Drive Mode"]) == follows + "Drive Mode"
    assert safety.notice_kept(follows + "ResetAll Settings", ["ResetAll Settings"]) == ""
    assert "reads as a confirmation" in safety.profile_reset_complete("Complete. ResetAll OK", "OK")


class Sent(Exception):
    pass


def asking_camera(tmp_path, monkeypatch, kind, text, lit=None, body=None, lone=""):
    """A LiveCamera on a screen read as `kind` whose whole text is `text`, its text above the footer `body` (the whole
    text when not given) and lit text `lit` (the whole text when not given), a notice's lone OK verdict `lone`
    (live.lone_of: "" when OK is its only button); its link raises Sent, and CameraRefused for MENU."""
    from camkit.link import CameraRefused
    monkeypatch.setattr(live, "lit_text", lambda image, path: text if lit is None else lit)
    monkeypatch.setattr(live, "text_of", lambda cam: text)
    monkeypatch.setattr(live, "body_of", lambda cam: text if body is None else body)
    monkeypatch.setattr(live, "title_of", lambda cam: "")
    monkeypatch.setattr(live, "lone_of", lambda image, path: lone)
    unchanged(monkeypatch)
    cam = camera(tmp_path, kind, text)

    def press(key, *a, **k):
        if key == "menu":
            raise CameraRefused("press menu 60: button not accepted")
        raise Sent(k)
    cam.link = SimpleNamespace(press=press, moves=0, menus=0)
    cam.network, cam.owner, cam.permit, cam.network_open, cam.may_open_exact = frozenset(), {}, None, None, None
    return cam


@pytest.mark.parametrize("text", GLUED_QUESTIONS + ["Format the memory card? Enter Cancel", "Formatting... Execute"])
def test_the_camera_refuses_enter_on_a_confirmation_unless_its_caller_judged_it(tmp_path, monkeypatch, text):
    """Finding 3: LiveCamera made no confirmation check of its own; it now refuses Enter on a notice, or a dialog that
    asks, reading as one, unless the caller judged that press with the check lifted (confirm_once: drive.py's
    --confirm through live.press's confirm) or drive.py allowed it as an owner row's armed press (permit)."""
    kind = "notice" if "?" not in text else "dialog"
    cam = asking_camera(tmp_path, monkeypatch, kind, text)
    with pytest.raises(safety.Refused, match="a notice|question mark"):       # by its shape, before any word
        cam.press("enter")
    cam = asking_camera(tmp_path, monkeypatch, kind, text)
    with pytest.raises(Sent):
        live.press(cam, "enter", confirm=True)
    assert cam.confirm_once is False                    # used up by the press
    cam = asking_camera(tmp_path, monkeypatch, kind, text)
    cam.permit = {"row": "Format", "what": "confirm"}
    with pytest.raises(Sent):
        cam.press("enter")
    cam = asking_camera(tmp_path, monkeypatch, "list", text)
    if "?" in text:                                     # a question mark asks, whatever kind the screen reads as
        with pytest.raises(safety.Refused, match="question mark"):
            cam.press("enter")
    else:
        with pytest.raises(Sent):                       # an option list: its Enter chooses, never confirms
            cam.press("enter")


def definition_carousels() -> list:
    """(title + lit option, lit option) of every option of every row of the a1 II definition, as a carousel shows it."""
    doc = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    return [(f"{s['row'][-1]} {v[1]}", v[1]) for s in doc.get("settings") or [] if s.get("row")
            for v in s.get("values") or [] if isinstance(v, list) and len(v) > 1 and isinstance(v[1], str)]


def test_the_camera_lets_enter_choose_on_every_carousel_whose_title_holds_a_confirmations_word(tmp_path, monkeypatch):
    """A carousel reads as a dialog too (its divider) and asks nothing: the provers choose its options. Every one of the
    a1 II definition's carousels that reads as a confirmation (its title or option holds the word: Delete confirm., File
    Name Format, Custom Key Setting's Delete, File Number's Reset) asks nothing (safety.asks), so the camera lets its
    Enter go."""
    reading = [(t, lit) for t, lit in definition_carousels() if safety.confirmation_refused(t)]
    assert len(reading) >= 30
    for text, lit in reading:
        assert safety.asks(text, lit) is None, (text, lit)
    for text, lit in reading[:: max(1, len(reading) // 8)]:
        with pytest.raises(Sent):
            asking_camera(tmp_path, monkeypatch, "dialog", text, lit).press("enter")
    quoted = 'Delete confirm. "Delete" first "Cancel" first OK'          # an option's name is no Cancel button
    assert safety.asks(quoted, '"Delete" first') is None


@pytest.mark.parametrize("kind,text,lit", [("dialog", "Delete this image Delete Cancel", "Delete"),
                                           ("dialog", "Format Enter", "Enter"),
                                           ("dialog", "Format Slot 1 All data will be deleted. Enter", "Enter"),
                                           ("dialog", "Reset PP1 to the default setting OK", "OK"),
                                           ("dialog", "Delete this image Delete", "Delete"),
                                           ("dialog", "Delete this image Delete Cancel", "Cancel"),
                                           ("dialog", "Slot 1 Execute", "Execute"),
                                           ("dialog", "Format the memory card", ""),
                                           ("unknown", "Delete this image? Delete Cancel", "Delete"),
                                           ("notice", "", "")])
def test_the_camera_refuses_enter_on_a_question_whose_mark_or_button_ocr_missed(tmp_path, monkeypatch, kind, text, lit):
    """Finding B of the second review: a question whose "?" OCR missed, a Cancel unread, a dialog's lit button its only
    sign, a screen read as no known kind, and a notice that reads nothing: the camera's own check refuses Enter on each
    (safety.asks), unless the caller judged that press with the check lifted."""
    with pytest.raises(safety.Refused):
        asking_camera(tmp_path, monkeypatch, kind, text, lit).press("enter")
    with pytest.raises(Sent):
        live.press(asking_camera(tmp_path, monkeypatch, kind, text, lit), "enter", confirm=True)


def test_the_camera_refuses_enter_where_it_cannot_read_the_screen(tmp_path, monkeypatch):
    """confirm_refused: a screen whose text cannot be read is refused, nothing could judge it."""
    cam = asking_camera(tmp_path, monkeypatch, "dialog", "x")
    monkeypatch.setattr(live, "text_of", lambda cam: (_ for _ in ()).throw(RuntimeError("no OCR")))
    with pytest.raises(safety.Refused, match="cannot be read"):
        cam.press("enter")


# ---------------------------------------------------------------- Enter by the screen's shape (2026-11-14, step C1)

FACES = "Clear registered faces? OK Cancel"          # a question holding none of the confirmation words


def test_a_question_holding_no_confirmation_word_was_let_through_and_is_refused_now(tmp_path, monkeypatch):
    """The finding: the words gated nothing they did not name, so "Clear registered faces? OK Cancel" passed the camera's
    check on a notice, a dialog and a screen of no known kind, and drive.py's. Each refuses it now, by its shape."""
    import drive
    assert safety.confirmation_refused(FACES) is None              # no word of the list: the old check let it go
    for kind in ("notice", "dialog", "unknown"):
        for key in ("enter", "ms_enter"):                          # the multi-selector's centre answers it too
            with pytest.raises(safety.Refused):
                asking_camera(tmp_path, monkeypatch, kind, FACES, "OK").press(key)
    with pytest.raises(safety.Refused, match="question mark"):     # and the trash button, which confirms a delete
        asking_camera(tmp_path, monkeypatch, "list", FACES, "OK").press("c4", allow={"c4"})
        assert drive.press_refused("enter", "OK", FACES, kind), kind
        assert safety.enter_refused(kind, FACES, "OK"), kind
    assert drive.press_refused("enter", "OK", FACES, "notice", confirm=True) == ""     # the owner's word lifts it


@pytest.mark.parametrize("kind,text,lit", [
    ("notice", "Speicherkarte formatieren? Ausführen Abbrechen", "Ausführen"),
    ("dialog", "Supprimer toutes les images ? OK Annuler", "OK"),
    ("notice", "¿Borrar todas las imágenes? Aceptar Cancelar", "Aceptar"),
    ("notice", "Effacer la carte Valider Annuler", "Valider"),                 # no mark, no English word: a notice
    ("unknown", "Gerät koppeln Weiter Abbrechen", "Weiter"),                    # no mark: a screen of no known kind
    ("list", "هل تريد حذف كل الصور؟ موافق إلغاء", "موافق"),                     # an Arabic mark on any kind
    ("list", "メモリーカードをフォーマットしますか？ 実行 キャンセル", "実行")])     # a full-width mark on any kind
def test_a_question_in_another_language_is_refused_by_its_shape(tmp_path, monkeypatch, kind, text, lit):
    """A camera not set to English: none of the confirmation words is there to read. The question mark, the notice and
    the screen of no known kind refuse it all the same, at the camera and in drive.py."""
    import drive
    assert safety.confirmation_refused(text) is None
    with pytest.raises(safety.Refused):
        asking_camera(tmp_path, monkeypatch, kind, text, lit).press("enter")
    assert drive.press_refused("enter", lit, text, kind)


@pytest.mark.parametrize("kind", ["dialog", "notice"])
def test_a_two_button_dialog_with_no_question_mark_is_refused(tmp_path, monkeypatch, kind):
    """"Pair this device OK Cancel": no question mark. As a carousel it asks by its buttons (safety.asks: Cancel, the
    pair; English words, honestly); as a notice by its kind. And after a refused MENU a notice with a second button below
    its lit OK, or a line reading Cancel, is no lone OK (safety.lone_ok)."""
    text = "Pair this device OK Cancel"
    with pytest.raises(safety.Refused, match="asks|notice"):
        asking_camera(tmp_path, monkeypatch, kind, text, "OK").press("enter")
    ok, cancel, sentence = ("OK", 300, 352, 40, 30), ("Cancel", 290, 410, 60, 30), ("Pair this device", 100, 120, 400, 30)
    box = (200, 340, 440, 395)
    assert "beside or below" in safety.lone_ok("OK", [sentence, ok, cancel], box)
    assert "beside or below" in safety.lone_ok("OK", [sentence, ok, ("Cancel", 460, 352, 60, 30)], box)
    assert "reads as a button" in safety.lone_ok("OK", [sentence, ("Cancel", 290, 280, 60, 30), ok], box)
    assert safety.lone_ok("OK", [sentence, ok], box) == ""
    assert safety.lone_ok("", [sentence, ok], box) and safety.lone_ok("OK", [sentence, ok], None)


def test_an_unreadable_dialog_gets_no_enter(tmp_path, monkeypatch):
    """A carousel whose lit option and title line read nothing, a screen whose text reads nothing, and one whose reading
    fails: nothing tells what Enter would answer."""
    with pytest.raises(safety.Refused, match="lit text that cannot be read"):
        asking_camera(tmp_path, monkeypatch, "dialog", "Drive Mode", "").press("enter")
    with pytest.raises(safety.Refused, match="nothing on the list screen can be read"):
        asking_camera(tmp_path, monkeypatch, "list", "", "").press("enter")
    cam = asking_camera(tmp_path, monkeypatch, "picker", "x")
    monkeypatch.setattr(live, "body_of", lambda cam: (_ for _ in ()).throw(RuntimeError("no OCR")))
    with pytest.raises(safety.Refused, match="cannot be read"):
        cam.press("enter")
    cam = asking_camera(tmp_path, monkeypatch, "dialog", "Drive Mode", "")       # its title line read instead
    monkeypatch.setattr(live, "title_of", lambda cam: "Single Shooting")
    with pytest.raises(Sent):
        cam.press("enter")


def test_a_lone_ok_notice_takes_enter_right_after_it_refused_menu(tmp_path, monkeypatch):
    """The one way out of an information notice: MENU first (live.leave_notice); where the camera refuses it, the next
    Enter, on that very screen with nothing sent between, goes when OK is plainly its only button and the text reads as
    no confirmation. Without the refused MENU, after another press, on another screen, with a second button or with a
    question mark, no Enter."""
    from camkit.link import CameraRefused
    text = "This operation or setting not available as follows Picture Profile OK"
    cam = asking_camera(tmp_path, monkeypatch, "notice", text, "OK")
    with pytest.raises(safety.Refused, match="a notice"):
        cam.press("enter")                                          # no MENU refused before it
    cam = asking_camera(tmp_path, monkeypatch, "notice", text, "OK")
    with pytest.raises(Sent):
        live.leave_notice(cam)                                      # MENU refused, then the lone OK
    events = [json.loads(l) for l in (cam.run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["kind"] for e in events][-2:] == ["menu_refused", "enter_passed"]
    assert events[-1]["by"] == live.MENU_REFUSED
    for spoil in ("a press between", "another screen", "a second button", "a question mark", "a confirmation"):
        t = text.replace("OK", "OK?") if spoil == "a question mark" else \
            "All data will be deleted OK" if spoil == "a confirmation" else text
        cam = asking_camera(tmp_path, monkeypatch, "notice", t, "OK", lone="a line sits below" if spoil == "a second button" else "")
        with pytest.raises(CameraRefused):
            cam.press("menu")
        if spoil == "a press between":
            cam.link.moves = 1                                      # something went out since the refusal
        if spoil == "another screen":
            cam.screen = SimpleNamespace(kind="notice", signature="other")
            cam.menu_refused["screen"] = SimpleNamespace(kind="notice", signature="one", struct=(1,), bits=np.zeros(0))
        with pytest.raises(safety.Refused):
            cam.press("enter")


def test_each_explicit_way_past_and_only_it(tmp_path, monkeypatch):
    """The ways past the shape check, each named and logged: --confirm (confirm_once, every check lifted), an owner
    decision's armed press (permit), a prover's --allow for its own row (answer_once: the shape lifted, the words still
    refuse), a notice --info-ok names (notice_ok: a lone OK, no question mark, no confirmation's words). Each is used up
    by one press."""
    slots = "MR Memory 1 2 3 M1 M2 M3 M4 MENU OK"                   # memreg's slot screen reads as no known kind
    cam = asking_camera(tmp_path, monkeypatch, "unknown", slots, "")
    with pytest.raises(safety.Refused, match="no known kind|'unknown'"):
        cam.press("enter")
    cam = asking_camera(tmp_path, monkeypatch, "unknown", slots, "")
    cam.answer_once = "--allow 'Camera Set. Memory'"
    with pytest.raises(Sent):
        cam.press("enter")
    assert cam.answer_once is None                                  # used up
    cam = asking_camera(tmp_path, monkeypatch, "unknown", "Format all data will be lost OK", "")
    cam.answer_once = "--allow 'Camera Set. Memory'"
    with pytest.raises(safety.Refused, match="does not answer"):    # the words still refuse under the consent
        cam.press("enter")
    cam = asking_camera(tmp_path, monkeypatch, "unknown", "", "")
    cam.answer_once = "--allow 'Camera Set. Memory'"
    with pytest.raises(safety.Refused, match="'unknown'"):          # nothing read: no consent answers it
        cam.press("enter")
    for way in ("confirm", "permit"):
        cam = asking_camera(tmp_path, monkeypatch, "notice", FACES, "OK")
        if way == "confirm":
            cam.confirm_once = "--confirm"
        else:
            cam.permit = {"row": "Face Memory", "what": "confirm"}
        with pytest.raises(Sent):
            cam.press("enter")
    notice = "You can set different settings for still image mode and movie mode in the next screen. OK"
    with pytest.raises(Sent):
        asking_camera(tmp_path, monkeypatch, "notice", notice, "OK").press("enter", notice_ok="Different Set for Still/Mv")
    with pytest.raises(safety.Refused, match="only one"):
        asking_camera(tmp_path, monkeypatch, "notice", notice, "OK", lone="a line sits below").press(
            "enter", notice_ok="Different Set for Still/Mv")
    with pytest.raises(safety.Refused, match="question mark"):
        asking_camera(tmp_path, monkeypatch, "notice", FACES, "OK").press("enter", notice_ok="Different Set for Still/Mv")
    import drive
    assert "no known kind" in drive.press_refused("enter", "", slots, "unknown", vouched=True) or \
        "'unknown'" in drive.press_refused("enter", "", slots, "unknown", vouched=True)  # a vouch alone: no
    assert drive.press_refused("enter", "", slots, "unknown", vouched=True, consent="--allow 'Camera Set. Memory'") == ""
    assert drive.press_refused("enter", "OK", "", "unknown", consent="--allow 'Camera Set. Memory'")   # nothing read
    assert drive.press_refused("enter", "OK", "Complete. OK", "notice", notice_way=live.MENU_REFUSED, lone="") == ""
    assert drive.press_refused("enter", "OK", "Complete. OK", "notice", notice_way=live.MENU_REFUSED, lone="2 buttons")
    assert drive.press_refused("enter", "OK", "Complete. OK", "notice")


def test_the_shape_check_judges_the_text_above_the_footer_and_every_kind_it_does_not_list(tmp_path, monkeypatch):
    """The footer's help glyph draws a "?" on every menu and option screen: the question mark is judged above it
    (live.body_of). A kind camkit.screen does not list as one whose Enter chooses or opens gets no Enter; the trash
    button meets the question mark and the kind, never the carousel's buttons (Focus Area's SET, a look's Reset)."""
    menu = "Shooting 2/40 Drive Mode Single Shooting Interval Shoot Func."
    with pytest.raises(Sent):
        asking_camera(tmp_path, monkeypatch, "menu", menu + " MENU ? Help", "Drive Mode", body=menu).press("enter")
    with pytest.raises(safety.Refused, match="question mark"):
        asking_camera(tmp_path, monkeypatch, "menu", menu + " Delete? OK", "Drive Mode").press("enter")
    for kind in ("unknown", "notice", "carousel_v2", None, ""):
        assert safety.enter_refused(kind, menu, "x"), kind
    assert safety.enter_refused("look", "Creative Look ST Reset Cancel OK", "", key="c4") == ""
    assert safety.enter_refused("look", "Reset this look? Cancel OK", "", key="c4")
    assert safety.enter_refused("notice", "Delete this image Delete Cancel", "", key="c4")
    # a reading that failed refuses as one; a notice takes Enter only by a named way past AND a lone OK judged
    assert "cannot be read" in safety.enter_refused("list", None, "x")
    assert safety.enter_refused("notice", "Complete. OK", "OK", lone="")                    # a lone OK, no way named
    assert safety.enter_refused("notice", "Complete. OK", "OK", passed=live.MENU_REFUSED)   # a way, the OK unjudged
    assert safety.enter_refused("notice", "Complete. OK", "OK", passed=live.MENU_REFUSED, lone="") == ""
    listed = {"menu", "submenu", "tiles", "shooting", "list", "dialog", "sidelist", "checklist", "checkgrid", "fields",
              "picker", "table", "keyset", "fnmenu", "look", "slider", "wbgrid", "guide", "helppop"}
    assert listed == set(safety.ENTER_KINDS), "a kind added to the list is one more screen Enter goes on: on purpose"


def test_the_link_sends_no_enter_the_camera_layer_did_not_judge(tmp_path, monkeypatch):
    """Nothing bypasses the camera's check: the link refuses an Enter, or the multi-selector's centre, sent without the
    camera layer's word that it judged it (Link.press's judged), a raw command line too; LiveCamera.press gives that word."""
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    with fake_link(tmp_path, monkeypatch) as lk:
        for key in ("enter", "ms_enter"):
            with pytest.raises(safety.Refused, match="judged"):
                lk.press(key, screen=SimpleNamespace(kind="list"))
            with pytest.raises(safety.Refused, match="judged"):
                lk.call(f"press {key} 60", screen="list")
            assert lk.press(key, screen=SimpleNamespace(kind="list"), judged=lk.moves)["args"][0] == key
        assert lk.press("down", screen=SimpleNamespace(kind="list"))["ok"]          # other keys need no word
    assert sum("press enter " in l for l in sent_lines(log)) == 1
    cam = asking_camera(tmp_path, monkeypatch, "list", "Drive Mode Single Shooting", "Single Shooting")
    with pytest.raises(Sent) as got:
        cam.press("enter")
    assert got.value.args[0].get("judged") == cam.link.moves      # the move count it judged the screen at


def test_an_information_notice_after_a_choice_is_left_with_menu_first(tmp_path, monkeypatch):
    """proving.screens.info_notice_ok took an information notice's OK on the words alone. Now MENU goes first
    (live.leave_notice), and OK only where the camera refuses MENU (the camera then judges that lone OK); a screen read
    as a table (Exposure Ctrl Type's information) takes its OK as before, and a notice --info-ok names takes it with the
    run's name for it (LiveCamera.press's notice_ok)."""
    sys.path.insert(0, str(ROOT / "kit"))
    from camkit.link import CameraRefused
    from proving import screens
    monkeypatch.setattr(screens.ocr, "read", lambda paths, eng=None: {p: [] for p in paths})
    monkeypatch.setattr(screens.ocr, "text_in", lambda lines, box: "Enters the state with Flash Effect applied. OK")
    monkeypatch.setattr(screens, "notice_lit", lambda cam: "OK")

    class Cam:
        def __init__(self, kind, refuses=False):
            self.kind, self.refuses, self.pressed = kind, refuses, []
            self.frame = SimpleNamespace(path=tmp_path / "00009_notice.png", image=None)

        def read(self):
            return SimpleNamespace(kind=self.kind)

        def press(self, key, **kw):
            self.pressed.append((key, kw))
            if key == "menu" and self.refuses:
                raise CameraRefused("press menu 60: button not accepted")
    for kind, refuses, pressed, left in (("notice", False, ["menu"], "menu"), ("unknown", False, ["menu"], "menu"),
                                         ("notice", True, ["menu", "enter"], "ok")):
        cam = Cam(kind, refuses)
        assert screens.info_notice_ok(cam, "Sync Terminal")["left_by"] == left
        assert [k for k, _ in cam.pressed] == pressed, (kind, refuses)
    cam = Cam("table")
    assert screens.info_notice_ok(cam, "Exposure Ctrl Type", kinds=("table",))["left_by"] == "ok"
    assert cam.pressed == [("enter", {})]
    cam = Cam("notice")
    screens.info_notice_ok(cam, "Different Set for Still/Mv", kinds=("notice",), named="Different Set for Still/Mv")
    assert cam.pressed == [("enter", {"notice_ok": "Different Set for Still/Mv"})]


NOT_AVAILABLE = "This operation or setting not available as follows Picture Profile OK"


@pytest.mark.parametrize("text,sends,error", [(FACES, False, "refused"),
                                              ("Speicherkarte formatieren Ausführen Abbrechen", False, "refused"),
                                              (NOT_AVAILABLE, True, "refused"), (NOT_AVAILABLE, False, "timeout")])
def test_to_shooting_sends_its_ok_only_where_the_camera_layer_passes_it(tmp_path, monkeypatch, text, sends, error):
    """proving.nav.to_shooting sent its OK on a notice that refused MENU straight through the link, judged by the words
    alone: "Clear registered faces? OK Cancel" got it. It is judged now as the camera judges a notice that has just
    refused MENU (live.menu_refused_enter: no question mark, OK plainly its only button, no confirmation's words), and
    goes with the link's judged word; a question, or a second button, gets no OK and the wait fails closed. A MENU that
    failed otherwise (no reply: it may have gone) is no refusal, and gets no OK either."""
    sys.path.insert(0, str(ROOT / "kit"))
    from camkit.link import CameraRefused, LinkError
    from proving import nav
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    kinds = iter(["notice"] + ["shooting"] * 3)
    monkeypatch.setattr(nav.screen, "read", lambda f: SimpleNamespace(kind=next(kinds, "shooting")))
    monkeypatch.setattr(nav, "run_tmp_png", lambda f: tmp_path / "notice.png")
    words = text.replace(" OK", "").replace(" Ausführen Abbrechen", "")
    lines = [nav.ocr.Line(text=words, conf=0.9, x=40, y=120, w=560, h=30),
             nav.ocr.Line(text="Ausführen" if "Ausführen" in text else "OK", conf=0.9, x=300, y=352, w=40, h=30)]
    if text != NOT_AVAILABLE:                                       # the questions show their second button
        lines.append(nav.ocr.Line(text="Cancel" if text == FACES else "Abbrechen", conf=0.9, x=290, y=410, w=60, h=30))
    monkeypatch.setattr(nav.ocr, "read", lambda paths, eng=None: {p: lines for p in paths})
    monkeypatch.setattr(live, "lit_found", lambda image, kind=None: ((200, 340, 440, 395), True))
    monkeypatch.setattr(live, "look_again", lambda eyes, judged, tag, moved_at=None: ("", SimpleNamespace(image=None)))  # unchanged
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    with fake_link(tmp_path, monkeypatch) as lk:
        real = lk.press

        def press(key, **kw):
            if key == "menu" and error == "refused":
                raise CameraRefused("press menu 60: button not accepted")
            if key == "menu":
                raise LinkError("press menu 60: no reply within 30 s")
            return real(key, **kw)
        lk.press = press
        nav.to_shooting(lk, SimpleNamespace(grab=lambda save=False: SimpleNamespace(image=None)), "the test", tries=1)
    assert sum("press enter 60" in l for l in sent_lines(log)) == (1 if sends else 0)


@pytest.mark.parametrize("label", ["De lete AII", "Dele te AII", "DeIete AII"])
def test_a_split_word_with_a_capital_i_for_an_l_is_judged_whole(label):
    """Finding 4: the reading with every space taken out was made from the folded text alone, never with OCR's capital I
    read as an l, so "De lete AII" escaped Delete All."""
    assert safety.never_open(label) and safety.never_lifted(label), label


@pytest.mark.parametrize("label", ["Pre-AFOn", "PRE-AFON", "pre-afon", "PreAF On", "Pre-AF Off", "RecLamp", "RecLED", "LEDLight", "MonitorVol.",
                                   "Line OutVol.", "FlashFire", "TestShot", "ResetEV Comp.", "ResetCustomHold", "PWReset",
                                   "WPSPIN", "wpspin", "WPS PIN", "ResetNetwork"])
def test_a_word_bounded_at_its_end_is_seen_inside_run_together_words(label):
    """Finding 5: a pattern with a word boundary at its end (lamp, led, vol., fire, test, reset, pw, wps) never matched
    inside run-together text; the a1 II's "Pre-AFOn" (Pre-AF's lit bar, its value glued on) escaped motion. The reading
    with its CamelCase set apart (safety._camel) and "wps pin" catch them, and drive.py's press check with them."""
    import drive
    assert safety.never_open(label) and drive.press_refused("right", label, "", "menu"), label


def test_screen_refused_lifts_an_allowed_name_only_where_it_stands_whole():
    """Finding 6: with two names allowed, the reading with every space taken out gained a space after the first and the
    second lifted nothing; a name lifted part of another word ("Set" in "Reset"); and "Voice Memo" lifted its words out
    of "Voice Memo Play Vol." before the longer name could. A word is lifted only where it lies wholly within a name's
    own text, in that reading's form of the name."""
    both = ("Camera Set. Memory", "Face Memory")
    assert safety.screen_refused("Camera Set. Memory Face Memory", allow=both) is None
    assert "face memory" in safety.screen_refused("Camera Set. Memory Face Memory", allow=both[:1])
    assert safety.screen_refused("Slot 1 Setting Camera Set. Memory",
                                 allow=("Slot 1 Setting", "Camera Set. Memory")) is None
    assert safety.screen_refused("Voice Memo Play Vol. 7", allow=("Voice Memo",))
    for order in (("Voice Memo", "Voice Memo Play Vol."), ("Voice Memo Play Vol.", "Voice Memo")):
        assert safety.screen_refused("Voice Memo Play Vol. 7", allow=order) is None, order
    assert safety.screen_refused("Setting Reset", allow=("Set",))
    assert safety.screen_refused("Video Light Mode", allow=("Light",))
    assert safety.screen_refused("SteadyShot On", allow=("SteadyShot",)) is None
    assert safety.screen_refused("VolumeSettings", allow=("Volume Settings",))      # as before: no space, no name
    assert safety.screen_refused("Volume Settings Beep", allow=("Volume Settings",))


def test_no_allowed_name_hides_another_labels_never_open_word():
    """Finding 6: every name --allow accepts, of the a1 II definition's labels, against every never-open label: the
    label's own never-open word, where it is no part of the name, still refuses the screen; and after a name."""
    labels = definition_labels()
    allowed = [n for n in labels if not safety.allow_refused(n)]
    closed = [x for x in labels if safety.never_open(x)]
    assert len(allowed) > 300 and len(closed) > 80
    for label in closed:
        word = safety.never_open(label).split(": ", 1)[1].rstrip(".")
        for name in allowed:
            forms = [f for f in safety.readings(name) if f.strip()]
            if any(word in f or word.replace(" ", "") in f for f in forms):
                continue                            # the label's word is the name's own
            if not any(f in r for f in forms for r in safety.readings(label)):
                continue                            # the name is nowhere in the label: it covers nothing
            assert safety.screen_refused(label, allow=(name,)), (label, name)
    for name in ("Set", "Light", "Test", "Reset", "Voice Memo", "Memory", "Mode", "Copy", "Reader", "Info"):
        for label in closed:
            word = safety.never_open(label).split(": ", 1)[1].rstrip(".")
            if not any(word in f for f in safety.readings(name)):
                assert safety.screen_refused(f"{name} {label}", allow=(name,)), (name, label)


def test_the_rows_own_label_goes_whole_from_its_screen_and_its_readings_without_a_space_count():
    """Finding 7: a whitespace-free reading was skipped when the fold put a space in (a spacing diaeresis), so a PW after
    a zero-width space read as nothing; and the row's own words went out word by word, taking Access Authen.'s words out
    of "Access Point" beside it. The row's label goes whole, in its readings as written."""
    cred = (safety.LIFT_CREDENTIALS, "list")
    assert safety.owner_menu_only(*cred, "Ax​pw¨", "Access Authen.")
    assert "access point" in safety.owner_menu_only(*cred, "Access Authen. Access Point On Off", "Access Authen.")
    assert safety.owner_menu_only(*cred, "Access Authen. On Off", "Access Authen.") is None
    assert safety.owner_menu_only(*cred, "Access Authen. AccessPoint On", "Access Authen.")
    assert safety.owner_menu_only(*cred, "AccessAuthen. On Off", "Access Authen.")          # run together: as before
    assert safety.owner_menu_only(*cred, "Access Authen. On Off", "AccessAuthen.")          # a name run together
    assert safety.owner_menu_only(safety.LIFT_ACTION, "dialog", "SSID/PW Reset Reset? OK Cancel", "SSID/PW Reset") is None


def test_what_permits_holds_only_where_the_plain_view_says_so_too():
    """Finding 8: a reading of a row's class only once its spaces are taken out vouches for no other reading; arming a
    confirmation needs the action's own word spaced as read; a field name is kept only as read; an armed row arms its
    own family only as written; a lit bar or an owner row opens only what both views read alike."""
    row = "Wired LAN Connect"
    assert safety.row_read_as(row, [row, "LANWired LAN Connect"])
    assert not safety.row_read_as(row, [row, "LANWired LAN Connect", "WiredLAN Connect"])
    entry = {row: [{"group": "Wired LAN", "readings": [row, "LANWired LAN Connect", "WiredLAN Connect"]}]}
    assert safety.lifted_readings(row, entry) == {"wired lan connect"}
    fmt = ("Format", safety.LIFT_CARDS, "confirm", "dialog", "Enter")
    assert safety.arm_refused(*fmt, "Format? All data will be lost. Enter Cancel", True, False) == ""
    assert safety.arm_refused(*fmt, "Forma t? All data will be lost. Enter Cancel", True, False)
    assert safety.address_fields(["Ser ver"]) == ([], 1) and safety.address_fields(["Server"]) == (["Server"], 0)
    assert not safety.armed_wiping("ResetNetwork Set.", "reset network")
    assert safety.armed_wiping("Reset Network Set.", "resetnetwork")
    assert safety.network_lifted_row("USBConnection Mode", {"USB Connection Mode": "2026-11-13"}) is None
    assert safety.owner_lifted_row("DeleteAll", {"DeleteAll": {"class": safety.LIFT_CARDS}}) is None
    for label in ("DeleteAll", "deleteall"):                           # a card action, read run together too
        assert safety.owner_class(label) == safety.LIFT_CARDS, label
    assert safety.glued_icon("lan", "Wake OnLAN", "Wired LAN")          # no icon of a row only read run together
    assert not safety.icon_slip("lam", "Wake OnLAN", {"lan"})


@pytest.mark.parametrize("row,why", [("ServerSetting", "the FTP server's login sits behind it"),
                                     ("SERVERSETTING", "the FTP server's login sits behind it"),
                                     ("Edit DeviceName", "its opening shows a keyboard"),
                                     ("EDIT DEVICENAME", "its opening shows a keyboard"),
                                     ("FTPFunction", "start or end a connection"),
                                     ("ftpfunction", "start or end a connection")])
def test_a_closed_identity_row_run_together_is_refused_for_its_own_reason(row, why):
    """Finding 9: _NOT_LIFTED_WHY reads its rows run together too."""
    assert why in safety.network_refused(row)


# ---------------------------------------------------------------- the second review of 2026-11-14

def test_a_profile_reset_question_is_its_own_only_in_its_readings_spaced_as_read():
    """A1: the question's words in order were looked for in every reading, the CamelCase set apart among them, so
    "theDefault" read as "the Default" permitted the reset; the permission is judged on the readings spaced as read."""
    assert safety.profile_reset_dialog("Reset PP1 to the default setting? Enter Cancel", "PP1") == ""
    assert safety.profile_reset_dialog("Reset PP1 to theDefault setting? Enter Cancel", "PP1")


def test_an_unattended_decision_waives_the_question_only_of_a_never_choose_row_it_names_as_written():
    """A2: waives_question took a never-choose row from "options" alone, read run together ("USBConnection Mode"), so
    the decision was no longer refused whole and its row got "unattended". The row must be one the decision names under
    "rows", written as the camera writes it."""
    places = [("Setup", "Reset/Save Settings", "Setting Reset"), ("Network", "Wired LAN", "Wired LAN Connect")]
    bad = {"lifts": "owner", "date": "2026-11-13", "why": "w", "rows": ["Setup > Reset/Save Settings > Setting Reset"],
           "unattended": True, "link_loss": True, "options": {"USBConnection Mode": ["PC Remote"]}}
    got = safety.owner_decided({"decisions": [bad]}, places)
    assert not safety.waives_question(bad) and got["rows"] == {} and "unattended" in got["refusals"][0]
    row = "Network > Wired LAN > Wired LAN Connect"
    good = {**bad, "rows": [row], "options": {row: ["Off"]}}
    assert safety.waives_question(good) and safety.waives_question(good, places)
    assert not safety.waives_question({**good, "rows": ["Network > Wired LAN > Wired LANConnect"]})
    glued = "Network > Wired LAN > Wired LANConnect"                       # named alike in rows and options
    assert not safety.waives_question({**good, "rows": [glued], "options": {glued: ["Off"]}})
    # given the places, a row owner_row_refused refuses (no top-level place the kit knows) waives nothing either
    elsewhere = [("Setup", "Reset/Save Settings", "Setting Reset")]
    assert safety.waives_question(good) and not safety.waives_question(good, elsewhere)
    assert any("unattended" in r for r in safety.owner_decided({"decisions": [good]}, elsewhere)["refusals"])
    # an action's options are steps, never a never-choose choice: nothing to waive, whatever its name holds
    reset = "Setup > Reset/Save Settings > Setting Reset"
    assert not safety.waives_question({**good, "rows": [reset], "options": {reset: ["USB"]}})
    assert not safety.waives_question({**good, "rows": ["Network > Wired LAN > USB Reset"],
                                       "options": {"Network > Wired LAN > USB Reset": ["On"]}})


def test_an_approval_lifts_a_row_only_where_both_views_read_it_as_motion():
    """A3: never_open gives the first reason any reading matches, so a run-together motion reading came before an
    action read once folded (a Cyrillic е in "Rеset"), and an approval naming that spelling lifted it. The approval
    holds only where the plain view reads motion too (approved_motion), in path_refused and kit/prove_run.py."""
    label = "ShutterWhenPwr OFF Rеset"
    assert safety.never_open(label).startswith(safety.MOTION) and plain_never_open(label).startswith("action")
    assert not safety.approved_motion(label)
    assert safety.path_refused(["Silent Mode Settings", label], approved={"Silent Mode Settings > " + label})
    good = "Shutter When Pwr OFF"
    assert safety.approved_motion(good)
    assert safety.path_refused(["Silent Mode Settings", good], approved={"Silent Mode Settings > " + good}) is None
    assert "safety.approved_motion(" in (ROOT / "kit" / "prove_run.py").read_text(encoding="utf-8")


def plain_never_open(label):
    return safety.plain_view(safety.never_open, label)


def test_an_opening_is_armed_only_where_it_acts_in_both_views():
    """The general pattern of A: arm_refused's "open" took a row whose opening acts only once its words run together
    ("AccessPoint"); in both views it acts, or it opens to look and no opening is armed."""
    row = "Access Authen. AccessPoint"
    assert safety.acts_on_open(row) and not safety.plain_view(safety.acts_on_open, row)
    assert "opens to look" in safety.arm_refused(row, safety.LIFT_CREDENTIALS, "open", "menu", row, "", True, True)
    assert safety.arm_refused("WPS Push", safety.LIFT_FIXED, "open", "menu", "WPS Push", "", True, True) == ""


def test_a_network_decision_compares_the_class_whole():
    """C: a name of a lifted class in both views, but another one in each (a Wi-Fi setting written, an address screen
    with its CamelCase set apart), is refused: the class is compared whole, never as a yes or no."""
    row = "Wi-Fi Connect xLAN Info"
    assert safety.lift_class(row) == safety.LIFT_ADDRESS
    assert safety.plain_view(safety.lift_class, row) == safety.LIFT_NETWORK
    assert "its class" in safety.network_refused(row)


def test_the_camelcase_reading_sets_a_digit_apart_from_its_letters():
    """C: _camel sets a word apart at a letter followed by a digit ("Test1") and a digit followed by a letter
    ("1Test"), so a word bounded at its end is seen there too."""
    assert safety._camel("Test1") == "Test 1" and safety._camel("1Test") == "1 Test"
    assert safety._camel("Slot1/2") == "Slot 1/2" and safety._camel("PP1to") == "PP1 to"
    for label in ("Test1", "1Test"):
        assert safety.never_open(label) == "by hand only: test", label
        assert safety.plain_view(safety.never_open, label) is None, label


def ocr_reads(monkeypatch, *texts):
    """What drive.py's OCR reads on any frame: one line per text, top to bottom (for --confirm's screen_named)."""
    import drive
    from camkit import ocr
    lines = [ocr.Line(text=t, conf=0.9, x=40, y=100 + 40 * i, w=400, h=30) for i, t in enumerate(texts)]
    monkeypatch.setattr(drive.ocr, "read", lambda paths, eng=None: {p: lines for p in paths})


def test_drive_confirm_without_owner_names_one_screen_and_lifts_its_shape_alone(tmp_path, monkeypatch):
    """Fix 2 of the C1 review: --confirm without --owner lifted every check for every Enter of the run. Now it names one
    screen by its whole text and lifts the shape check for one Enter on it (the camera's answer_once, which keeps the
    word list); a second Enter, or one on another screen, is refused."""
    question = "Clear registered faces? OK Cancel"
    ocr_reads(monkeypatch, "Clear registered faces?", "OK", "Cancel")
    pressed, _, line = drive_on_shooting(tmp_path / "a", monkeypatch, ["enter:faces"], kind="dialog",
                                         more=["--confirm", question], text=question, lit="OK")
    assert ("cam", "enter", {"answer_once": "--confirm 'clear registered faces ok cancel'"}) in pressed
    assert line["completed"] is True
    pressed, _, line = drive_on_shooting(tmp_path / "b", monkeypatch, ["enter:faces", "enter:faces"], kind="dialog",
                                         more=["--confirm", question], text=question, lit="OK")
    assert [p[1] for p in pressed].count("enter") == 1 and line["completed"] is False     # once only
    ocr_reads(monkeypatch, "Pair this device?", "OK", "Cancel")
    pressed, _, line = drive_on_shooting(tmp_path / "c", monkeypatch, ["enter:device"], kind="dialog",
                                         more=["--confirm", question], text="Pair this device? OK Cancel", lit="OK")
    assert not any(p[1] == "enter" for p in pressed) and line["completed"] is False   # another screen
    pressed, _, line = drive_on_shooting(tmp_path / "d", monkeypatch, ["enter:faces"], kind="dialog",
                                         text=question, lit="OK")
    assert not any(p[1] == "enter" for p in pressed) and line["completed"] is False   # no --confirm: refused


@pytest.mark.parametrize("args,said", [
    (["--confirm"], "names the one screen it answers"),
    (["--confirm", "Format the memory card? Enter Cancel"], "only the owner route answers"),
    (["--confirm", "Delete this image? Delete Cancel"], "only the owner route answers"),
    (["--confirm", "Clear registered faces? OK Cancel", "--owner"], "takes no screen text")])
def test_drive_confirm_never_lifts_the_confirmation_words(args, said):
    """A format, a delete or a reset goes only by the owner route (--owner --confirm, the row's name typed at the
    terminal): --confirm without it refuses such a screen before anything connects, and names one screen."""
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "drive.py"), "--path", "Drive Mode", *args],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and said in r.stderr, r.stderr


def test_drive_info_ok_takes_a_named_notices_ok_and_no_other(tmp_path, monkeypatch):
    """Fix 2: drive.py --info-ok "ROW=PHRASE" (ROW a --path label) takes the OK of the plain notice it names, so
    --confirm is not needed for one; the camera gets it as notice_ok. A notice it does not name gets no Enter."""
    import drive
    from proving import screens
    notice = "This operation or setting not available as follows Picture Profile OK"
    monkeypatch.setattr(screens, "notice_refused", lambda cam, phrase, words=True: "" if "picture profile" in phrase
                        else "not the notice named")
    monkeypatch.setattr(drive, "lone_of", lambda image, path: "")
    pressed, _, line = drive_on_shooting(tmp_path / "a", monkeypatch, ["enter:not available"], kind="notice",
                                         more=["--info-ok", "Drive Mode=This operation or setting not available as "
                                               "follows Picture Profile"], text=notice, lit="OK")
    assert ("cam", "enter", {"notice_ok": "Drive Mode"}) in pressed and line["completed"] is True
    pressed, _, line = drive_on_shooting(tmp_path / "b", monkeypatch, ["enter:not available"], kind="notice",
                                         more=["--info-ok", "Drive Mode=Something else entirely shown here"],
                                         text=notice, lit="OK")
    assert not any(p[1] == "enter" for p in pressed) and line["completed"] is False


def test_drive_says_the_info_ok_a_refused_notice_needs_and_logs_the_refusal(tmp_path, monkeypatch, capsys):
    """The camera session (2026-11-15): drive.py refused Enter on Different Set for Still/Mv's notice, no --info-ok
    given, without saying the flag that passes it and without an event. It prints the --info-ok (the last --path label
    and the text read) and logs press_refused and the notice not passed."""
    import drive
    notice = "You can set different settings for still image mode and movie mode in the next screen. OK"
    monkeypatch.setattr(drive, "info_ok_text", lambda cam: notice[:-3])
    pressed, events, line = drive_on_shooting(tmp_path, monkeypatch, ["enter:different settings"], kind="notice",
                                              text=notice, lit="OK")
    out = capsys.readouterr().out
    assert not any(p[1] == "enter" for p in pressed) and line["completed"] is False
    assert '--info-ok "Drive Mode=You can set different settings for still image mode' in out, out
    assert "the owner's word" not in out and "naming this screen by its whole text" in out
    assert any(e["kind"] == "press_refused" and e["key"] == "enter" for e in events)
    assert any(e["kind"] == "notice_not_passed" and e["row"] == "Drive Mode" for e in events)


# ---------------------------------------------------------------- White Balance's Cloudy is no cloud row (2026-11-14)

# the a1 II's cloud rows as its definition, its data and its Help Guide write them (the Creators' Cloud group and its
# two rows), another body's, and a value beside one, each refused as written, with its words run together
# ("CloudConnection", "creatorscloud" in lower case) or split ("Clo ud Connection")
CLOUD_ROWS = ["Cloud Connection", "Cloud Information", "Creators' Cloud", "Cloud Connect", "Cloud Upload",
              "C3 Portal/cloud", "Cloud Connection On", "Creators' Cloud Yes", "creatorscloud"]
# White Balance's Cloudy as the camera read it on 2026-11-14 ("White Balance Cloudy", the lit row with its value beside
# its name), alone, with its words run together, and with a word after it that starts with no letter (a 0 there is
# read as an o once the spaces are taken out, deslip, so "Cloudy 0" is refused as "cloudyo")
CLOUDY = ["White Balance Cloudy", "Cloudy", "Cloudy Weather", "Cloudy\nWeather", "White BalanceCloudy",
          "WhiteBalanceCloudy", "CloudyWeather", "Cloudy Weather On", "WB fine-tune A-B (Cloudy, stills)",
          "White Balance Cloudy 2"]


def a1ii_cloud_labels() -> set:
    """Every label holding "cloud" of the a1 II definition's menu, settings' rows and values, and of its Help Guide's
    menu."""
    doc = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    out = set(definition_labels())
    out |= {v[1] for s in doc["settings"] for v in s.get("values") or [] if len(v) > 1 and isinstance(v[1], str)}
    guide = ROOT / "data" / "ILCE-1M2_fw4.00" / "help_guide_menu_ILCE-1M2_fw4.00.jsonl"
    for line in guide.read_text(encoding="utf-8").splitlines():
        out |= {json.loads(line).get(k) for k in ("tab", "group", "item")} if line.strip() else set()
    return {x for x in out if isinstance(x, str) and "cloud" in x.lower()}


def test_the_a1_iis_cloud_labels_are_its_cloud_rows_and_white_balances_cloudy():
    assert a1ii_cloud_labels() == {"Cloud Connection", "Cloud Information", "Creators' Cloud", "Cloudy"}
    assert all(safety.never_open(x) for x in a1ii_cloud_labels() - {"Cloudy"})


@pytest.mark.parametrize("label", CLOUD_ROWS)
def test_every_cloud_row_is_refused_as_written_run_together_or_split(label):
    """A cloud row is by hand only and acts on opening (decision 8), however OCR runs its words together or splits one,
    in every guard that reads it: the "Cloudy" let through is never one of its readings."""
    import drive
    assert safety.plain_view(safety.never_open, label) == "by hand only: cloud"
    for v in [label, *run_together(label), *split_apart(label)]:
        assert safety.never_open(v).startswith("by hand only"), v
        assert live.open_refused(v) and drive.press_refused("right", v, "", "menu"), v
        assert safety.identity_row(v) and safety.never_lifted(v) and safety.allow_refused(v), v
        assert safety.screen_refused(v) and safety.identity_screen(v) and safety.lift_class(v) is None, v
        assert safety.never_choose(v) and safety.acts_on_open(v) and safety.link_risk_open(v), v
        assert "start or end a connection" in safety.network_refused(v), v


@pytest.mark.parametrize("label", CLOUDY)
def test_white_balance_cloudy_is_no_cloud_row(label):
    """2026-11-14, the owner's a1 II: once White Balance > Cloudy was chosen the lit row read "White Balance Cloudy",
    and the next press was refused, "by hand only: cloud". "Cloudy" ending its word, or before "Weather", is no cloud
    row in any guard, in any reading, run together too."""
    import drive
    import runner
    assert safety.never_open(label) is None and live.open_refused(label) == "", label
    assert not drive.press_refused("right", label, "", "menu")
    assert safety.identity_row(label) is None and safety.never_lifted(label) is None
    assert safety.allow_refused(label) is None and safety.screen_refused(label) is None
    assert safety.identity_screen(label) is None and safety.never_choose(label) is None
    assert safety.acts_on_open(label) is None and safety.link_risk_open(label) is None
    assert "connection" not in safety.network_refused(label)
    if " " in label:                    # the --info-ok check reads a word run together on its own (runner.joined)
        assert runner.run_together_refused(label) is None


@pytest.mark.parametrize("label", ["Cloudyconnect", "Cloudy Connection", "Creators' Clo ud Yes", "Creators' Cl oud Yes",
                                   "White Balance Cloudy A1", "White Balance Cloud y", "Cloudy Wireless", "Cloudywifi",
                                   "Cloudyzone", "Cloudy Weath", "Cloudy Xweather"])
def test_cloudy_with_more_letters_after_it_run_together_stays_refused(label):
    """With every space taken out, a "y" and a letter after "cloud" may be a cloud row split by OCR and the next word
    ("creators'cloudyes"), or a letter put in ("Cloudyconnect"): refused, as is White Balance's Cloudy with a word that
    starts with a letter after it, which that reading cannot tell from them, whatever the letter ("Cloudyzone"),
    "Weather" alone whole ("Cloudy Wireless", "Cloudy Weath", "Cloudy Xweather" refused). "Cloud y" reads "cloud" as
    written. The --info-ok check of a row's words run together refuses "Cloudyconnect" too ("cloud" is still on its
    list)."""
    import runner
    assert safety.never_open(label).startswith("by hand only"), label
    assert "cloud" in runner._never_open_words() and runner.run_together_refused("Cloudyconnect")


@pytest.mark.parametrize("label", ["C loud Y", "Clo ud Y1", "C loudy", "C3 Portal/cl oud\nY", "Clo ud ｙ",
                                   "Creators' C loud Y", "Creators' Clou d y.", "CLO UD Y", "Cl0ud y", "C1o ud Y",
                                   "C 1oud Y", "Cl 0 ud Y", "White Balance C loudy", "White Balance Clou dy"])
def test_a_cloud_word_split_with_a_y_after_it_is_refused(label):
    """A cloud row's "Cloud" split by OCR, or slipped, with a "y" after it ("C loud Y"): with its spaces taken out it
    reads "cloudy", which _CLOUD lets through, so _CLOUD_SPLIT judges it as read (refused before the Cloudy fix of
    2026-11-14, and again since), a 1 or a 0 that deslip leaves as it is among them ("C 1oud Y", "Cl 0 ud Y"). White
    Balance's Cloudy read split ("C loudy") is refused with it."""
    import drive
    assert safety.never_open(label).startswith("by hand only"), label
    assert live.open_refused(label) and drive.press_refused("right", label, "", "menu")
    assert safety.identity_row(label) and safety.never_lifted(label) and safety.allow_refused(label)
    assert safety.screen_refused(label) and safety.identity_screen(label) and safety.lift_class(label) is None
    assert safety.never_choose(label) and safety.acts_on_open(label) and safety.link_risk_open(label)
    assert "start or end a connection" in safety.network_refused(label)


def test_the_split_cloud_pattern_takes_its_y_and_a_split_word_is_the_run_together_views():
    """_CLOUD_SPLIT names a split "cloud" only with its "y" (its as-written pattern is judged in the plain view too); a
    split cloud word with no "y" is _CLOUD's, in the reading with every space taken out alone, as a split word always is
    ("Forma t")."""
    assert safety.plain_view(safety.never_open, "C loudy") == "by hand only: c loudy"
    assert safety.never_open("C loud Connection") == "by hand only: cloud"
    assert safety.plain_view(safety.never_open, "C loud Connection") is None


def test_runners_never_open_words_are_the_same_with_the_split_cloud():
    """_CLOUD_SPLIT is its own entry, so runner._never_open_words, which takes a pattern's look-arounds out, still has
    "cloud" from _CLOUD and nothing from _CLOUD_SPLIT."""
    import runner
    words = runner._never_open_words()
    assert "cloud" in words and not any(w.startswith("c\\s") or "[l1|]" in w for w in words)
    assert safety._CLOUD_SPLIT in safety._IDENTITY and safety._CLOUD_SPLIT in safety._NEVER_CHOOSE
    assert safety._CLOUD_SPLIT in safety._ACTS_ON_OPEN


def test_a_y_put_in_after_a_cloud_rows_cloud_passes_the_row_check_but_not_the_group_column():
    """What no pattern tells from White Balance's Cloudy: a "y" OCR puts in after a cloud row's "Cloud" before a sign or
    the end ("Creators' Cloudy", "Cloudy-Connection") passes the row check, as a letter read for another does
    ("Creators' Clond"). The group column still refuses the a1 II's Creators' Cloudy, one letter from its group's
    name."""
    for label in ("Creators' Cloudy", "Cloudy-Connection", "Creators' Clond"):
        assert safety.never_open(label) is None, label
    doc = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    groups = {m.get("group") for m in doc["menu"] if isinstance(m, dict)}
    assert "Creators' Cloud" in groups
    assert "one letter from \"Creators' Cloud\"" in safety.group_refused("Creators' Cloudy", groups)
    assert safety.group_refused("Creators' Clond", groups)


def test_whole_screen_guards_refuse_white_balances_list_read_run_together():
    """A screen's whole text is judged in every reading too: White Balance's list ("Shade Cloudy Incandescent") with its
    spaces taken out holds "cloudyi", a "y" and a letter after "cloud", and is refused, a vouched Enter on it too."""
    import drive
    text = "Shade Cloudy Incandescent"
    assert safety.screen_refused(text) and safety.identity_screen(text)
    assert drive.press_refused("enter", "", text, "dialog", vouched=True)
    assert safety.plain_view(safety.screen_refused, text) is None
