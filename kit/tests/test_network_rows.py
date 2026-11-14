"""The Wi-Fi and Bluetooth settings and the address screens (decision 8, as it stands since 2026-11-13): a class of the
never-open list that no --allow, approved motion decision, may_open or vouched Enter opens, and that only a dated
owner decision naming the row ({"lifts": "network", "date", "rows", "why"} in the reviewed scope) opens, for a run
given --network, which asks local readers only: the walk and the provers a setting, drive.py an address screen too.
Such a row is looked at only (up, down, MENU) unless the decision names options to choose ("options"); a screen
inside it that names identity or credentials gets MENU alone, no reader, and its text withheld; an address screen,
the same from the start. Nothing here talks to a camera, a reader or a network; every address is a placeholder
kit/tools/check_public.py lets through.
"""
import contextlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, crawl, live, safety  # noqa: E402
from camkit.runs import Run  # noqa: E402

from conftest import TEST_CAMERA  # noqa: E402

DAY = "2026-11-13"
DECISION = {"date": DAY, "lifts": "network", "why": "the owner: map as much as we can",
            "rows": ["Bluetooth Function", "Wi-Fi Frequency Band", "Display Wi-Fi Info."]}
# the a1 II's owner's decision of 2026-10-30 as its shape is: a dated decision naming a row to keep it by hand, with no
# "lifts"; approved_rows (decision 2's motion rows) reads every dated decision, so it names Bluetooth Rmt Ctrl too
KEEP_BY_HAND = {"date": "2026-10-30", "rows": ["Bluetooth Rmt Ctrl"], "why": "connection settings stay by hand"}
# the values the page model and the definition know for the rows (runner.network_values): a menu row's bar carries one
VALUES = {"Bluetooth Function": ["On", "Off"], "Wi-Fi Frequency Band": ["2.4GHz", "5GHz"],
          "Bluetooth Rmt Ctrl": ["On", "Off"], "Wi-Fi Connect": ["On", "Off"], "Wired LAN Connect": ["On", "Off"]}
# a Wi-Fi or Bluetooth setting whose options a decision may name (Wi-Fi Connect, Bluetooth Rmt Ctrl and Airplane Mode
# never: their choice joins an access point, opens Pairing or drops the links), as a LiveCamera finds it lit
BTF = {"row": "Bluetooth Function", "lit": "Bluetooth Function  On", "words": "Bluetooth Function On Off"}


def decided(*decisions) -> dict:
    rows, refusals = safety.network_decided({"decisions": list(decisions)})
    assert refusals == [], refusals
    return rows


# ---------------------------------------------------------------- a decision lifts only the rows it names

def test_a_decision_lifts_only_the_rows_it_names():
    rows = decided(DECISION)
    assert rows == {"Bluetooth Function": DAY, "Wi-Fi Frequency Band": DAY, "Display Wi-Fi Info.": DAY}
    assert safety.path_refused(["Bluetooth Function"], network=rows) is None
    assert safety.path_refused(["Network", "Wi-Fi Frequency Band"], network=rows) is None
    for other in ("Bluetooth Rmt Ctrl", "Airplane Mode", "Wi-Fi Connect", "Disp Device Address"):
        assert safety.path_refused([other], network=rows), other
        assert live.open_refused(other, network=rows, screens=True), other
    # the lit bar carries the row's value after its label: one of the row's known values; with none known at all, a
    # short tail naming nothing (safety.unknown_tail)
    assert live.open_refused("Bluetooth Function  On", network=rows, values=VALUES) == ""
    assert live.open_refused("Bluetooth Function", network=rows) == ""
    assert live.open_refused("Bluetooth Function  On", network=rows)                     # no value known, no labels
    assert live.open_refused("Bluetooth Function  On", network=rows, labels=set()) == ""  # a short tail, no other label
    assert live.open_refused("Bluetooth Function  On Off Auto", network=rows, labels=set())   # three words: refused
    assert live.open_refused("Bluetooth Function  Maybe", network=rows, values={"Bluetooth Function": []},
                             labels=set()) == ""
    assert live.open_refused("Bluetooth Function  Maybe", network=rows, labels={"Bluetooth Function Maybe Not"})
    assert live.open_refused("Wi‑Fi Frequency Band 2.4GHz", network=rows, values=VALUES) == ""   # a no-break hyphen
    assert live.open_refused("Bluetooth Functional  On", network=rows, values=VALUES)
    assert live.open_refused("Bluetooth Function  Maybe", network=rows, values=VALUES)
    assert live.open_refused("Bluetooth Rmt Ctrl  Off", network=rows, values=VALUES)
    # nothing else lifts the class, the decision's rows included
    assert live.open_refused("Bluetooth Function  On", {"Bluetooth Function"})
    assert safety.path_refused(["Bluetooth Function"], {"Bluetooth Function"}, allowed=["Bluetooth Function"])
    assert safety.screen_refused("Bluetooth Function On MENU OK", allow=["Bluetooth Function"])


def test_an_address_screen_never_lifts_for_the_walk_or_the_provers():
    rows = decided(DECISION, {**DECISION, "rows": ["Display Wired LAN Info.", "Disp Device Address"]})
    for screen in ("Display Wi-Fi Info.", "Display Wired LAN Info.", "Disp Device Address"):
        assert safety.address_screen(screen) and screen in rows
        assert not safety.network_lifted(screen, rows) and safety.network_lifted(screen, rows, screens=True)
        assert safety.path_refused([screen], network=rows)                    # proving.jobs, scale_run, set_twins
        assert live.open_refused(screen, network=rows)                        # LiveCamera without screens
        assert live.open_refused(screen, network=rows, screens=True) == ""    # drive.py alone
        assert not crawl.network_open({"label": screen, "never_open": safety.never_open(screen)}, rows)


@pytest.mark.parametrize("decision", [
    KEEP_BY_HAND,
    {**DECISION, "lifts": None}, {k: v for k, v in DECISION.items() if k != "lifts"},
    {**DECISION, "lifts": "Network"}, {**DECISION, "lifts": "identity"},
    {**DECISION, "date": "someday"}, {**DECISION, "date": "2026-13-45"}, {**DECISION, "date": 20261113},
    {**DECISION, "date": "2999-01-01"},                                               # a day still to come
    {**DECISION, "why": ""}, {k: v for k, v in DECISION.items() if k != "why"},
    {**DECISION, "rows": []}, {**DECISION, "rows": "Bluetooth Function"},
])
def test_a_decision_without_lifts_or_a_day_lifts_nothing(decision):
    rows, refusals = safety.network_decided({"decisions": [decision]})
    assert rows == {}
    assert bool(refusals) == (decision.get("lifts") == "network"), refusals     # a malformed network decision is said
    for label in ("Bluetooth Function", "Bluetooth Rmt Ctrl", "Wi-Fi Frequency Band"):
        assert safety.path_refused([label], network=rows) and live.open_refused(f"{label}  On", network=rows)


def test_the_owners_keep_by_hand_decision_opens_nothing():
    """The 2026-10-30 decision names Bluetooth Rmt Ctrl to keep it by hand: approved_rows takes it in (it reads every
    dated decision), and still no check opens the row, nor does prove_run's may_open, which keeps only motion rows."""
    scope = {"decisions": [KEEP_BY_HAND]}
    approved = safety.approved_rows(scope)
    assert approved == {"Bluetooth Rmt Ctrl"} and safety.network_decided(scope) == ({}, [])
    assert safety.path_refused(["Bluetooth Rmt Ctrl"], approved)
    assert live.open_refused("Bluetooth Rmt Ctrl  Off", approved)
    assert not safety.owner_may_approve(safety.never_open("Bluetooth Rmt Ctrl"))


def test_a_decision_that_says_what_it_lifts_is_no_motion_approval():
    """approved_rows (decision 2's dated approvals) leaves out every decision with "lifts", so a network decision never
    un-asks a row of the scope's ask_user, nor lifts a motion row it happens to name."""
    scope = {"decisions": [KEEP_BY_HAND, {**DECISION, "rows": ["Bluetooth Function", "SteadyShot"]},
                           {"date": DAY, "lifts": "anything", "rows": ["Pre-AF"], "why": "x"}]}
    assert safety.approved_rows(scope) == {"Bluetooth Rmt Ctrl"}
    assert safety.path_refused(["SteadyShot"], safety.approved_rows(scope))


# What no decision opens, whatever it names: credentials, the camera's identity and connections, actions, the serial
# number, Initialize's kin
NEVER_DECIDED = ["Wi-Fi Direct Info.", "Access Authen. Info", "Access Authen. Settings", "Wi-Fi Direct Settings",
                 "Access Point Set.", "SSID/PW Reset", "WPS Push", "Pairing", "Display Serial Number",
                 "Reset Network Set.", "Reset Transfer Status", "Import Root Certificate", "Select on Cam & Send",
                 "Copyright Info", "Save/Load FTP Settings", "Initialize", "Format", "Camera Settings Reset"]
# names that open nothing because they name no row of the class: a group, a path, a name the list does not know
VAGUE = ["Wi-Fi", "Bluetooth", "Network > Bluetooth Function", "Bluetooth Function > On", "Remote Shoot Setting", ""]


@pytest.mark.parametrize("label", NEVER_DECIDED)
def test_what_no_decision_opens_is_refused_when_one_names_it(label):
    rows, refusals = safety.network_decided({"decisions": [{**DECISION, "rows": ["Bluetooth Function", label]}]})
    assert rows == {"Bluetooth Function": DAY}
    assert len(refusals) == 1 and repr(label) in refusals[0], refusals
    # and on every path, even with a set of rows that names it by hand
    forced = {label: DAY}
    assert safety.never_open(label) and not safety.never_open(label).startswith(safety.NETWORK)
    assert not safety.network_lifted(label, forced) and not safety.network_lifted(label, forced, screens=True)
    assert safety.path_refused([label], {label}, network=forced)            # (--allow is its own matter, as before)
    assert safety.path_refused(["Network", label], network=forced)
    assert live.open_refused(label, network=forced, screens=True)
    assert safety.screen_refused(f"{label} MENU OK")
    assert not crawl.network_open({"label": label, "never_open": None}, forced)


@pytest.mark.parametrize("label", VAGUE)
def test_a_vague_name_opens_nothing(label):
    rows, refusals = safety.network_decided({"decisions": [{**DECISION, "rows": [label]}]})
    assert rows == {} and len(refusals) == 1


# Readings that hold a row of the class and the words of another: never_open names the other class, which no network
# decision lifts, and no other allowance lifts it either (the class's words keep it from them)
MIXED = {"Bluetooth Function Password": "credentials", "Wi-Fi Connect Pairing": "by hand only",
         "Airplane Mode Reset": "action", "Bluetooth Rmt Ctrl Volume": "by hand only",
         "SteadyShot Bluetooth Function": safety.MOTION, "Wi-Fi Frequency Band Language": "by hand only",
         "Display Wi-Fi Info. Copyright": "by hand only"}
ALL_ROWS = {"Bluetooth Function": DAY, "Wi-Fi Connect": DAY, "Airplane Mode": DAY, "Bluetooth Rmt Ctrl": DAY,
            "Wi-Fi Frequency Band": DAY, "Display Wi-Fi Info.": DAY}


@pytest.mark.parametrize("label,cls", MIXED.items())
def test_the_class_is_named_only_when_no_other_class_matches(label, cls):
    assert decided({**DECISION, "rows": list(ALL_ROWS)}) == ALL_ROWS
    why = safety.never_open(label)
    assert why.startswith(cls) and not why.startswith(safety.NETWORK), why
    assert safety.network_words(label)
    assert not safety.network_lifted(label, ALL_ROWS, screens=True)
    assert safety.path_refused([label], {label}, allowed=[label], network=ALL_ROWS)
    assert live.open_refused(label, {label}, network=ALL_ROWS, screens=True)
    assert safety.allow_refused(label)
    assert safety.screen_refused(f"{label} OK", allow=[label])


def test_a_row_of_the_class_with_a_card_word_never_lifts():
    """never_open names the class (no other class matches), but never_lifted names the card word: no decision opens it."""
    label = "Wi-Fi Frequency Band Format"
    assert safety.never_open(label).startswith(safety.NETWORK) and safety.never_lifted(label)
    assert not safety.network_lifted(label, ALL_ROWS, screens=True)
    assert live.open_refused(label, network=ALL_ROWS, screens=True)


# ---------------------------------------------------------------- what an address screen run shows

def test_address_fields_keep_the_field_names_and_withhold_every_value():
    from camkit import ocr
    lines = ["Display Wi-Fi Info.", "MAC Address", "00:11:22:33:44:55", "IP Address: 192.0.2.10", "lP Address",
             "Subnet Mask", "255.255.255.0", "Default Gateway 192.0.2.1", "IPv6 Link-local Address", "fe80::1",
             "SSID", "DIRECT-madeup", "Device Name", "ILCE-1M2-made-up", "Disp Device Address",
             ocr.Line(text="Device Address", conf=0.9, x=0, y=0, w=10, h=10),
             ocr.Line(text="00:11:22:33:44:55", conf=0.9, x=0, y=0, w=10, h=10), "MENU", ""]
    names, withheld = safety.address_fields(lines)
    assert names == ["MAC Address", "IP Address", "Subnet Mask", "Default Gateway", "IPv6 Link-local Address", "SSID",
                     "Device Name", "Device Address"]
    shown = json.dumps([names, withheld])
    for value in ("00:11", "192.0.2", "255.255", "fe80", "DIRECT", "made-up", "ILCE", "Display"):
        assert value not in shown, value
    # kept whole: MAC Address, lP Address, Subnet Mask, IPv6 Link-local Address, SSID, Device Name, Device Address;
    # every other line withheld, a field name with a value after it on its line among them
    assert withheld == 18 - 7
    assert safety.address_fields([]) == ([], 0)


LOCAL = {"name": "local", "url": "http://127.0.0.1:8000/v1", "model": "m"}
NOT_LOCAL = [{"name": "claude", "kind": "anthropic", "model": "m"},
             {"name": "hosted", "url": "https://api.example.com/v1", "model": "m", "api_key_env": "MADE_UP_KEY"},
             {"name": "keyless", "url": "http://203.0.113.5:8000/v1", "model": "m"},          # a public address
             {"name": "doc", "url": "http://192.0.2.1/v1", "model": "m"},
             {"name": "named", "url": "http://gpu-box:8000/v1", "model": "m"},                # a name: cannot tell
             {"name": "lan-with-key", "url": "http://192.168.1.100:8080/v1", "model": "m", "api_key_env": "K"},
             {"name": "nourl", "model": "m"}]


@pytest.mark.parametrize("cfg,local", [(LOCAL, True), ({**LOCAL, "url": "http://localhost:11434/v1"}, True),
                                       ({**LOCAL, "url": "http://[::1]:8000/v1"}, True),
                                       ({**LOCAL, "url": "http://192.168.1.100:8080/v1"}, True)]
                         + [(c, False) for c in NOT_LOCAL])
def test_a_local_reader_is_one_on_this_computer_or_the_owners_network(cfg, local):
    from camkit import vlm
    assert vlm.local_reader(cfg) is local


def test_local_only_asks_no_reader_that_is_not_local_and_held_asks_none(monkeypatch):
    from camkit import vlm
    made = []

    class Fake:
        def __init__(self, cfg, **override):
            made.append(cfg["name"])

        def ask(self, image, prompt):
            return {"rows": [{"label": "Drive Mode", "highlighted": True}]}

        def ping(self):
            pass
    monkeypatch.setattr(vlm, "make_reader", Fake)
    monkeypatch.setattr(vlm, "LOCAL_ONLY", True)
    for other in NOT_LOCAL:
        monkeypatch.setattr(vlm, "config", lambda other=other: {"readers": [other, LOCAL]})
        with pytest.raises(vlm.NoReader, match="not a local reader"):
            vlm.ask_role("second", b"a frame", vlm.PROMPTS["menu"], 5)
        assert made == []                                   # no reader built, nothing sent, the cache not read
    assert vlm.ask_role("third", b"a frame", vlm.PROMPTS["menu"], 5)["rows"]   # a local reader is asked as ever
    assert made == ["local"]
    monkeypatch.setattr(vlm, "HELD", "a screen naming identity or credentials is open")
    with pytest.raises(vlm.NoReader, match="no reader is asked"):
        vlm.ask_role("third", b"a frame", vlm.PROMPTS["menu"], 5)
    assert made == ["local"]
    monkeypatch.setattr(vlm, "HELD", None)
    monkeypatch.setattr(vlm, "LOCAL_ONLY", False)
    vlm.ask_role("second", b"a frame", vlm.PROMPTS["menu"], 5)          # without it, the configured second as ever
    assert made == ["local", NOT_LOCAL[-1]["name"]]


def test_local_only_brings_in_no_stand_in_that_is_not_local(monkeypatch):
    from camkit import vlm
    pinged = []

    class Fake:
        def __init__(self, cfg, **override):
            self.name = cfg["name"]

        def ping(self):
            pinged.append(self.name)
    monkeypatch.setattr(vlm, "make_reader", Fake)
    monkeypatch.setattr(vlm, "config", lambda: {"readers": [LOCAL, NOT_LOCAL[2], NOT_LOCAL[4], {**LOCAL, "name": "lan",
                                                                                         "url": "http://192.168.1.50/v1"}]})
    monkeypatch.setattr(vlm, "LOCAL_ONLY", True)
    assert vlm.stand_in("second", LOCAL)["name"] == "lan" and pinged == ["lan"]      # no tiny request to the others


def test_the_start_check_of_a_network_run_asks_local_readers_only(monkeypatch):
    """With LOCAL_ONLY the start check asks no reader that is not local, and a local one that answered stands in for a
    role whose reader is not local; with none, the run stops before the link opens."""
    from camkit import vlm
    asked = []

    def ask_checks(cfgs, image, timeout=None, roles=None):
        asked.extend(c["name"] for c in cfgs)
        return [vlm.Check(c["name"], vlm.kind_of(c), "m", vlm.paid(c), tuple((roles or {}).get(c["name"], ())),
                          asked=True, ok=True, seconds=0.1) for c in cfgs]
    monkeypatch.setattr(vlm, "ask_checks", ask_checks)
    monkeypatch.setattr(vlm, "check_picture", lambda: b"picture")
    monkeypatch.setattr(vlm, "LOCAL_ONLY", True)
    hosted = NOT_LOCAL[1]
    monkeypatch.setattr(vlm, "config", lambda: {"readers": [hosted, LOCAL], "roles": {"second": "hosted",
                                                                                     "third": "local"}})
    checks = vlm.start_check()
    assert asked == ["local"] and next(c for c in checks if c.name == "hosted").not_asked == vlm.NOT_LOCAL
    stand_ins, why = vlm.verdict(checks)
    assert why == "" and stand_ins["second"]["name"] == "local"
    asked.clear()
    monkeypatch.setattr(vlm, "config", lambda: {"readers": [hosted], "roles": {"second": "hosted"}})
    stand_ins, why = vlm.verdict(vlm.start_check())
    assert asked == [] and "not a local reader" in why


# ---------------------------------------------------------------- LiveCamera: the press check and the address lock

class Presses:
    def __init__(self):
        self.sent = []

    def press(self, key, hold_ms=60, allow=frozenset(), cleanup=False, screen=None, on_shooting=frozenset()):
        self.sent.append(key)

    def dial(self, name, steps, screen=None, on_shooting=frozenset()):
        self.sent.append(f"dial {name}")


PAGE = "the page the row is opened from"


def camera(tmp_path, network=(), screens=False, options=None, values=None, page="submenu"):
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.link, cam.run, cam.may_open = Presses(), Run("net", root=tmp_path), frozenset()
    cam.network, cam.screens, cam.options, cam.values = dict(network), screens, dict(options or {}), dict(values or {})
    cam.network_open = cam.address_open = cam.identity_open = None
    cam.screen = SimpleNamespace(kind=page, focus="rows", where=PAGE)
    cam.frame = SimpleNamespace(image=None, path=tmp_path / "00001_down.png")
    cam.hdmi = SimpleNamespace(settle=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sent")))
    return cam


def events(cam) -> list:
    return [json.loads(x) for x in (cam.run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_the_press_check_opens_a_decided_setting_and_refuses_the_rest(tmp_path, monkeypatch):
    rows = decided(DECISION)
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Bluetooth Function  On")
    cam = camera(tmp_path, rows, values=VALUES)
    with pytest.raises(RuntimeError, match="sent"):
        cam.press("right")
    assert cam.link.sent == ["right"] and cam.network_open["row"] == "Bluetooth Function" and cam.address_open is None
    for lit in ("Bluetooth Rmt Ctrl  Off", "Display Wi-Fi Info.", "Bluetooth Function  Maybe"):
        monkeypatch.setattr(live, "lit_text", lambda image, path, lit=lit: lit)       # not named; an address screen,
        cam = camera(tmp_path, rows, values=VALUES)                                   # no screens; no value of its own
        with pytest.raises(safety.Refused, match="never opened"):
            cam.press("right")
        assert cam.link.sent == [] and cam.network_open is None
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Bluetooth Function  On")
    cam = camera(tmp_path)                                                   # no --network
    with pytest.raises(safety.Refused, match="--network"):
        cam.press("enter")


class InsideCamera:
    """The settle that follows a press, as LiveCamera.press takes it: the frame after it reads as `kind` at the place
    `where` (screen.read gives both), its text is `words` (live.text_of). Two screens are at the same position
    (screen.same_position) when they are at the same place: the page a row is opened from is at PAGE."""
    def __init__(self, tmp_path, monkeypatch, kind="list", words="Bluetooth Rmt Ctrl On Off", where="inside"):
        self.kind, self.words, self.where, self.n, self.tmp = kind, words, where, 1, tmp_path
        monkeypatch.setattr(live.screen, "read", lambda f: SimpleNamespace(kind=self.kind, focus="rows",
                                                                          where=self.where))
        monkeypatch.setattr(live, "text_of", lambda cam: self.words)
        monkeypatch.setattr(live.screen, "same_position",
                            lambda a, b: getattr(a, "where", None) is not None and a.where == getattr(b, "where", None))
        monkeypatch.setattr(live.screen, "same_state", lambda a, b: False)

    def shows(self, kind, where):
        """What the frame after the next press (or read) is: a screen of `kind` at `where`."""
        self.kind, self.where = kind, where

    def settle(self, before, tag, **kw):
        self.n += 1
        return SimpleNamespace(image=None, path=self.tmp / f"{self.n:05d}_{tag}.png"), True

    def grab(self, tag, save=True):
        return SimpleNamespace(image=None, path=self.tmp / f"{self.n:05d}_{tag}.png")

    timing = {}


def inside_camera(tmp_path, monkeypatch, options=None, kind="list", words="Bluetooth Rmt Ctrl On Off", where="inside",
                  row="Bluetooth Rmt Ctrl", lit="Bluetooth Rmt Ctrl  Off", page="submenu", link=None):
    """A LiveCamera on a menu page (PAGE, of kind `page`), the decided row `row` lit (`lit`), whose Right opens what
    reads as `kind` at `where` (the row's list by default)."""
    rows = decided({**DECISION, "rows": [row]})
    cam = camera(tmp_path, rows, options=options, values=VALUES, page=page)
    if link is not None:
        cam.link = link
    cam.hdmi = InsideCamera(tmp_path, monkeypatch, kind, words, where)
    cam.presses, cam._seen = 0, cam._moves()
    monkeypatch.setattr(live, "lit_text", lambda image, path: lit)
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    cam.press("right")
    return cam


def test_a_network_row_is_looked_at_only_unless_the_decision_names_options(tmp_path, monkeypatch):
    cam = inside_camera(tmp_path, monkeypatch)
    assert cam.network_open["row"] == "Bluetooth Rmt Ctrl" and cam.identity_open is None
    for key in ("down", "up", "ms_down"):                                    # its options are read
        cam.press(key)
    for key in ("enter", "ms_enter", "right", "left", "ms_right", "wheel", "c4"):
        with pytest.raises(safety.Refused, match="look only|could choose or commit|whatever a decision names"):
            cam.press(key, allow={"c4"})
    with pytest.raises(safety.Refused, match="no dial"):
        cam.dial("front", 1)
    assert cam.link.sent == ["right", "down", "up", "ms_down"]
    cam.hdmi.shows("submenu", PAGE)                                          # MENU: back on the page it was opened on
    cam.press("menu")
    assert cam.network_open is None and events(cam)[-1]["kind"] == "network_row_left"
    assert cam.link.sent[-1] == "menu"


# ---------------------------------------------------------------- D1: the lock ends only on MENU and the page it left

WIRED = {"row": "Wired LAN Connect", "lit": "Wired LAN Connect", "words": "Wired LAN Connect On Off"}


def test_a_camera_slow_to_draw_the_list_keeps_the_lock(tmp_path, monkeypatch):
    """Right on a decided row whose choice is never made (Wired LAN Connect); the camera is slow, so the frame after
    the press still shows the page it was opened from, at the same place: the lock holds (no MENU has gone out). Down
    draws the list, and Enter on Off is refused there, a screen no row check judges."""
    cam = inside_camera(tmp_path, monkeypatch, kind="menu", where=PAGE, page="menu", **WIRED)
    assert cam.network_open is not None and cam.network_open["row"] == "Wired LAN Connect"
    cam.hdmi.shows("list", "inside")
    cam.press("down")
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Off")
    with pytest.raises(safety.Refused, match="whatever a decision names"):
        cam.press("enter")
    assert cam.link.sent == ["right", "down"] and cam.network_open is not None


def test_a_list_misread_as_a_menu_page_keeps_the_lock(tmp_path, monkeypatch):
    """Right opens the list; after a Down the list is misread as a menu page, at the very place the row was opened
    from: no MENU has gone out, so the lock holds, and Enter on Off is refused."""
    cam = inside_camera(tmp_path, monkeypatch, **WIRED)
    cam.hdmi.shows("menu", PAGE)
    cam.press("down")
    assert cam.network_open is not None
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Off")
    for key in ("enter", "right", "ms_enter"):
        with pytest.raises(safety.Refused):
            cam.press(key)
    assert cam.link.sent == ["right", "down"]


@pytest.mark.parametrize("kind,where,left", [
    ("submenu", PAGE, True),            # MENU from the list lands on the page it was opened from, at the same place
    ("shooting", "shooting", True),     # MENU closed the menu
    ("menu", "another page", False),    # MENU landed on another page: still locked
    ("tiles", "tiles", False),          # the Main tiles: still locked
    ("list", "inside", False),          # the camera ignored MENU: still the list
])
def test_menu_ends_the_lock_only_on_the_page_it_was_opened_from_or_the_shooting_screen(tmp_path, monkeypatch, kind,
                                                                                       where, left):
    cam = inside_camera(tmp_path, monkeypatch, **WIRED)
    cam.hdmi.shows(kind, where)
    cam.press("menu")
    assert (cam.network_open is None) is left
    if not left:
        with pytest.raises(safety.Refused):
            cam.press("right")                       # still looked at only: no row opens from here
        cam.hdmi.shows("shooting", "shooting")
        cam.press("menu")                            # another MENU closes the menu: the lock ends there
        assert cam.network_open is None
    assert cam.link.sent[0] == "right" and "right" not in cam.link.sent[1:]


def lit_on(monkeypatch, text):
    """What the lit bar reads from now on (live.lit_text)."""
    monkeypatch.setattr(live, "lit_text", lambda image, path: text)


@pytest.mark.parametrize("after_ok,left", [("Bluetooth Function  Off", True),   # the page, its bar back on the row
                                            ("Off", False)])                     # the page, but an option lit
def test_an_enter_on_a_named_option_ends_the_lock_on_the_page_it_brings_back(tmp_path, monkeypatch, after_ok, left):
    cam = inside_camera(tmp_path, monkeypatch, options={"Bluetooth Function": ["Off"]}, **BTF)
    lit_on(monkeypatch, "Off")

    def ok_then_page(*a, **k):                       # the frame after OK: the page the row was opened from
        lit_on(monkeypatch, after_ok)
        cam.hdmi.shows("submenu", PAGE)
        return InsideCamera.settle(cam.hdmi, *a, **k)
    monkeypatch.setattr(cam.hdmi, "settle", ok_then_page)
    cam.press("enter")
    assert (cam.network_open is None) is left and cam.link.sent == ["right", "enter"]


def test_an_enter_whose_list_is_slow_to_close_keeps_the_lock_until_a_new_menu(tmp_path, monkeypatch):
    """The closing evidence is spent on the read right after the key: OK on a list slow to close (the list read after
    it) keeps the lock, and the page read later ends nothing; a MENU then, onto the page with its bar on the row, does."""
    cam = inside_camera(tmp_path, monkeypatch, options={"Bluetooth Function": ["Off"]}, **BTF)
    lit_on(monkeypatch, "Off")
    cam.hdmi.shows("list", "inside")
    cam.press("enter")
    assert cam.network_open is not None and not cam.network_open["closing"]
    cam.hdmi.shows("submenu", PAGE)
    lit_on(monkeypatch, "Bluetooth Function  Off")
    cam.refresh("later")
    assert cam.network_open is not None              # no MENU since: the evidence was spent
    cam.press("menu")
    assert cam.network_open is None


def test_a_menu_the_camera_ignored_then_a_down_onto_what_reads_as_the_page_keeps_the_lock(tmp_path, monkeypatch):
    """The reviewer's sequence: Right on "Wired LAN Connect On" opens its list; MENU is ignored (the list stays); a Down
    lands on a frame where the popup over the dimmed page reads as that page, even with the row's text lit: the MENU's
    evidence was spent on the list read after it, so the lock holds, and Enter on Off is refused."""
    cam = inside_camera(tmp_path, monkeypatch, row="Wired LAN Connect", lit="Wired LAN Connect  On",
                        words="Wired LAN Connect On Off")
    assert cam.network_open is not None
    lit_on(monkeypatch, "Off")
    cam.hdmi.shows("list", "inside")
    cam.press("menu")                                # ignored by the camera
    assert cam.network_open is not None
    cam.hdmi.shows("submenu", PAGE)                  # the popup reads as the page
    lit_on(monkeypatch, "Wired LAN Connect  On")     # the worst case: its bar read as the row
    cam.press("down")
    assert cam.network_open is not None
    lit_on(monkeypatch, "Off")
    with pytest.raises(safety.Refused, match="whatever a decision names"):
        cam.press("enter")
    assert cam.link.sent == ["right", "menu", "down"]


def test_a_menu_that_only_closed_a_notice_inside_the_row_keeps_the_lock(tmp_path, monkeypatch):
    """Right opens a notice inside the row; MENU closes it onto the row's list, which reads as the page the row was
    opened from (same_position): its lit bar reads an option, not the row, so the lock holds; Enter on Off is refused."""
    cam = inside_camera(tmp_path, monkeypatch, kind="notice", where="inside", row="Wired LAN Connect",
                        lit="Wired LAN Connect  On", words="This function is currently disabled. OK")
    cam.hdmi.shows("submenu", PAGE)
    lit_on(monkeypatch, "Off")
    cam.press("menu")
    assert cam.network_open is not None
    with pytest.raises(safety.Refused, match="whatever a decision names"):
        cam.press("enter")
    lit_on(monkeypatch, "")                          # a bar that cannot be read: still locked after a MENU
    cam.press("menu")
    assert cam.network_open is not None
    assert cam.link.sent == ["right", "menu", "menu"]


def test_a_screen_that_cannot_be_compared_keeps_the_lock(tmp_path, monkeypatch):
    cam = inside_camera(tmp_path, monkeypatch, **WIRED)
    cam.hdmi.shows("submenu", PAGE)

    def cannot(a, b):
        raise ValueError("no picture to compare")
    monkeypatch.setattr(live.screen, "same_position", cannot)
    cam.press("menu")                                # closing set by the MENU, the comparison raising
    assert cam.network_open is not None


def test_a_menu_sent_past_the_camera_counts_through_the_links_count(tmp_path, monkeypatch):
    """A cleanup MENU sent straight through the link (a runner's close) is counted by the link (Link.menus): once the
    page is read again, the lock ends; with no MENU counted, the same page read again keeps it."""
    link = Presses()
    link.menus = 0
    cam = inside_camera(tmp_path, monkeypatch, link=link, **WIRED)
    cam.hdmi.shows("submenu", PAGE)
    cam.refresh("again")
    assert cam.network_open is not None              # the page, but no MENU: a slow list, or a misread
    link.menus += 1                                  # link.press("menu", cleanup=True), past the camera
    cam.refresh("after-cleanup")
    assert cam.network_open is None


def test_a_cancel_after_an_error_ends_the_lock_once_the_page_is_back(tmp_path, monkeypatch):
    """cancel_to_menu (after a STOP or an error) sends its MENU presses straight through the link, as cleanup presses:
    each counts as a MENU gone out, so the lock ends once the page the row was opened from is back; a link that
    counts nothing (this fake) is no matter."""
    cam = inside_camera(tmp_path, monkeypatch, **WIRED)
    cam.hdmi.shows("submenu", PAGE)
    cam.cancel_to_menu()
    assert cam.network_open is None and cam.link.sent[0] == "right" and "menu" in cam.link.sent


def test_the_link_counts_every_menu_it_sends(tmp_path, monkeypatch):
    """Link.menus: every MENU press that goes out, a cleanup's among them (the fake camlink of test_guards)."""
    from camkit import link as L
    monkeypatch.delenv("CAMSET_USB", raising=False)
    fake = [sys.executable, "-X", "utf8", str(Path(__file__).resolve().parent / "fake_camlink.py")]
    with L.Link(Run("lk", root=tmp_path), ip="192.0.2.10", binary=fake, catch_signals=False) as lk:
        lk.press("down", screen="menu")
        lk.press("menu", cleanup=True)
        lk.press("menu")
        assert lk.menus == 2 and lk.moves == 3
        real = lk._reply
        monkeypatch.setattr(lk, "_reply", lambda timeout, want=None: (real(timeout, want=want),
                                                                     {"ok": False, "error": "button not accepted"})[1])
        with pytest.raises(L.LinkError, match="not accepted"):
            lk.press("menu")                         # a MENU the camera did not take counts none
        assert lk.menus == 2 and lk.moves == 4


NOTICE_TEXTS = {"plain": "This operation or setting not available.", "identity": "Connect to DIRECT-madeup? OK"}


@pytest.mark.parametrize("local_only,text,ok", [(False, "plain", True), (False, "identity", False),
                                                (True, "plain", False), (True, "identity", False)])
def test_to_shootings_ok_on_a_notice_never_goes_on_a_network_run_nor_on_identity(tmp_path, monkeypatch, capsys,
                                                                                local_only, text, ok):
    """proving.nav.to_shooting: an information notice that refuses MENU takes OK straight through the link, past any
    network row's lock; never on a --network run (camkit.vlm.LOCAL_ONLY: its text is not even read, nor printed), nor on
    a notice naming identity or credentials ("Connect to <SSID>?"): then it waits, failing closed."""
    from camkit import vlm
    from camkit.link import Link, LinkError
    from proving import nav
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    monkeypatch.delenv("CAMSET_USB", raising=False)
    monkeypatch.setattr(vlm, "LOCAL_ONLY", local_only)
    kinds = iter(["notice", "shooting"])
    monkeypatch.setattr(nav.screen, "read", lambda f: SimpleNamespace(kind=next(kinds)))
    monkeypatch.setattr(nav, "run_tmp_png", lambda f: tmp_path / "notice.png")
    read = []
    monkeypatch.setattr(nav.ocr, "read", lambda paths, eng=None: read.append(paths) or {p: [] for p in paths})
    monkeypatch.setattr(nav.ocr, "text_in", lambda lines, box: NOTICE_TEXTS[text])
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    fake = [sys.executable, "-X", "utf8", str(Path(__file__).resolve().parent / "fake_camlink.py")]
    with Link(Run("nav", root=tmp_path), ip="192.0.2.10", binary=fake, catch_signals=False) as lk:
        real = lk.press

        def press(key, **kw):
            if key == "menu":
                raise LinkError("press menu 60: button not accepted")
            return real(key, **kw)
        lk.press = press
        nav.to_shooting(lk, SimpleNamespace(grab=lambda save=False: SimpleNamespace(image=None)), "the test", tries=1)
    sent = [x for x in log.read_text(encoding="utf-8").splitlines() if "press" in x] if log.exists() else []
    assert sum("press enter" in x for x in sent) == (1 if ok else 0)
    out = capsys.readouterr().out
    assert ("DIRECT-madeup" not in out) and (bool(read) is not local_only)
    if local_only:
        assert "not available" not in out and "its text withheld" in out


@pytest.mark.parametrize("lit,goes", [("Off", True), (" Off ", True), ("OFF", True), ("On", False), ("", False),
                                      ("0ff", False), ("Off Off", False)])
def test_a_named_option_is_chosen_only_when_the_lit_bar_reads_it(tmp_path, monkeypatch, lit, goes):
    cam = inside_camera(tmp_path, monkeypatch, options={"Bluetooth Function": ["Off"]}, **BTF)
    monkeypatch.setattr(live, "lit_text", lambda image, path: lit)
    if goes:
        cam.press("enter")
        assert cam.link.sent == ["right", "enter"]
    else:
        with pytest.raises(safety.Refused):
            cam.press("enter")
        assert cam.link.sent == ["right"]
    with pytest.raises(safety.Refused):
        cam.press("right")                       # a named option opens no Right, nor a dial


def test_a_screen_naming_identity_inside_a_network_row_gets_menu_alone_and_no_reader(tmp_path, monkeypatch):
    from camkit import vlm
    cam = inside_camera(tmp_path, monkeypatch, options={"Bluetooth Function": ["On"]}, kind="unknown",
                        **{**BTF, "words": "Pairing Searching for the device... Cancel"})
    assert cam.identity_open and vlm.HELD
    assert not any("Pairing" in json.dumps(e) for e in events(cam))         # the log names the frame, not the text
    monkeypatch.setattr(live, "lit_text", lambda image, path: "On")
    for key in ("down", "enter", "up"):
        with pytest.raises(safety.Refused, match="no key but MENU"):
            cam.press(key)
    with pytest.raises(vlm.NoReader):
        vlm.ask_role("second", b"a frame", "a question", 5)
    cam.hdmi.shows("menu", "another page")                                  # MENU, but another page: still held
    cam.press("menu")
    assert cam.identity_open and cam.network_open is not None and vlm.HELD
    with pytest.raises(safety.Refused, match="no key but MENU"):
        cam.press("down")
    cam.hdmi.shows("submenu", PAGE)                                          # MENU again: the page it was opened on,
    lit_on(monkeypatch, "Bluetooth Function  On")                            # its bar on the row
    cam.press("menu")
    assert cam.identity_open is None and cam.network_open is None and vlm.HELD is None


def test_once_an_address_screen_opens_only_menu_goes_out(tmp_path, monkeypatch):
    from camkit import vlm
    rows = decided(DECISION)
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Display Wi-Fi Info.")
    cam = camera(tmp_path, rows, screens=True)
    with pytest.raises(RuntimeError, match="sent"):                          # the press went out, then the settle
        cam.press("right")
    assert cam.address_open == "00001_down.png" and events(cam)[-1]["kind"] == "address_screen_opened"
    assert vlm.HELD                                                          # no reader is asked on it
    cam.screen = SimpleNamespace(kind="unknown")                             # whatever the screen reads as
    for key in ("down", "up", "enter", "right", "left", "ms_enter", "wheel"):
        with pytest.raises(safety.Refused, match="no key but MENU"):
            cam.press(key)
    with pytest.raises(safety.Refused, match="no dial"):
        cam.dial("front", 1)
    assert cam.link.sent == ["right"] and events(cam)[-1]["kind"] == "press_refused"
    with pytest.raises(RuntimeError, match="sent"):
        cam.press("menu")
    assert cam.link.sent == ["right", "menu"]


# ---------------------------------------------------------------- the walk (camkit.crawl.visit_row)

class RowCamera:
    """One menu row whose Right opens a notice, and MENU back: enough for visit_row to open a row or skip it."""
    def __init__(self):
        self.where, self.presses, self.keys = "row", 0, []

    def press(self, key):
        self.presses += 1
        self.keys.append(key)
        self.where = {"right": "notice", "menu": "row"}.get(key, self.where)

    def read(self):
        return SimpleNamespace(kind="menu" if self.where == "row" else "notice", signature=self.where, struct=None,
                               bits=None, row=0)


NETWORK_REASON = safety.never_open("Bluetooth Function")


@pytest.mark.parametrize("row,network,opened", [
    ({"label": "Bluetooth Function", "never_open": NETWORK_REASON}, {"Bluetooth Function": DAY}, True),
    ({"label": "Bluetooth Function"}, {"Bluetooth Function": DAY}, True),                  # a live read, no reason
    ({"label": "Bluetooth Function", "never_open": NETWORK_REASON,                          # page_model's readings
      "readings": {"label": {"ocr": "Bluetooth Function", "vlm": "Bluetooth Function"}}}, {"Bluetooth Function": DAY},
     True),
    ({"label": "Bluetooth Function", "never_open": NETWORK_REASON}, {}, False),             # no --network
    ({"label": "Bluetooth Function", "never_open": NETWORK_REASON}, {"Wi-Fi Connect": DAY}, False),   # not named
    # a page model built before the class: its stored reason fails closed
    ({"label": "Bluetooth Function", "never_open": "by hand only: bluetooth function"}, {"Bluetooth Function": DAY},
     False),
    # a reading kept beside the label of another class (submenu_labels' readings): fails closed
    ({"label": "Bluetooth Function", "never_open": NETWORK_REASON, "readings": ["Bluetooth Function Password"]},
     {"Bluetooth Function": DAY}, False),
    ({"label": "Display Wi-Fi Info.", "never_open": safety.never_open("Display Wi-Fi Info.")},
     {"Display Wi-Fi Info.": DAY}, False),                                                  # an address screen
    ({"label": "Access Authen. Info", "never_open": safety.never_open("Access Authen. Info")},
     {"Access Authen. Info": DAY}, False),
])
def test_the_walk_opens_a_decided_setting_and_skips_the_rest(row, network, opened):
    cam = RowCamera()
    r = crawl.visit_row(cam, cam.read(), {"page": "Network > Bluetooth"}, 0, row, network=network)
    if opened:            # a notice is no list to look at: left unwalked, MENU back
        assert r.outcome.startswith("network row: a notice screen") and cam.keys == ["right", "menu"]
    else:
        assert r.outcome.startswith("skipped: ") and cam.keys == []


class CarouselCamera:
    """A row whose Right opens a two-option carousel, each option drawing a second axis's marks and Right opening a
    panel (as Drive Mode's): MENU back to the row. Counts every key."""
    def __init__(self):
        self.where, self.option, self.presses, self.keys = "row", 0, 0, []

    def press(self, key):
        self.presses += 1
        self.keys.append(key)
        if self.where == "row" and key == "right":
            self.where = "dialog"
        elif self.where == "dialog" and key in ("down", "up"):
            self.option = 1 - self.option
        elif key == "menu":
            self.where = "row"

    def read(self):
        import numpy as np
        dialog = self.where == "dialog"
        return SimpleNamespace(kind="dialog" if dialog else "menu", signature=f"{self.where}{self.option}", row=0,
                               at_start=self.option == 0, at_end=self.option == 1, scroll=None, count=2 if dialog else None,
                               glyphs={"side_right": True, "sub_box": True} if dialog else {}, field=None, focus="rows",
                               slots=[], struct=(self.where, self.option), bits=np.zeros(0, np.uint8))


@pytest.mark.parametrize("panels", [False, True])
def test_the_walk_never_commits_inside_a_network_row(panels):
    """A carousel a network decision opens is walked by Down round its options alone: no second axis, no panel (a Right
    there commits the option, 2026-10-28), with --panels too. The same carousel on a row of no class gets its axes
    walked, Right and Left."""
    labels = lambda cam: ("p", [])           # noqa: E731
    cam = CarouselCamera()
    row = {"label": "Bluetooth Rmt Ctrl", "never_open": safety.never_open("Bluetooth Rmt Ctrl")}
    r = crawl.visit_row(cam, cam.read(), {"page": "Network > Bluetooth"}, 0, row, labels, panels=panels,
                        network={"Bluetooth Rmt Ctrl": DAY})
    assert r.outcome.startswith("walked (network row") and cam.keys.count("right") == 1 and "left" not in cam.keys
    assert set(cam.keys) <= {"right", "down", "up", "menu"} and cam.keys[0] == "right" and cam.keys[-1] == "menu"
    cam = CarouselCamera()
    crawl.visit_row(cam, cam.read(), {"page": "Shooting > Drive"}, 0, {"label": "Drive Mode", "never_open": None},
                    labels, panels=panels)
    assert cam.keys.count("right") > 1                                # the other row's axes: more Rights


# ---------------------------------------------------------------- the reviewed scope and the runners

@pytest.fixture
def scope_file(own_runs, monkeypatch):
    """The camera's reviewed scope, where the kit reads it (proving.base.PASS1 in the test's own runs), written by the
    test: write(decisions) -> its path."""
    from proving import base
    pass1 = own_runs / TEST_CAMERA / "kit2_pass1"
    monkeypatch.setattr(base, "PASS1", pass1)

    def write(*decisions, exclude=None):
        pass1.mkdir(parents=True, exist_ok=True)
        f = pass1 / "pass2_scope_draft.json"
        f.write_text(json.dumps({"prove": [], "exclude": exclude or {}, "decisions": list(decisions)}), encoding="utf-8")
        return f
    return write


def test_the_runners_read_the_decisions_from_the_reviewed_scope(scope_file, capsys, tmp_path):
    import runner
    with pytest.raises(SystemExit, match="no reviewed scope"):
        runner.network_decided_or_exit()
    scope_file(KEEP_BY_HAND)
    with pytest.raises(SystemExit, match="no dated owner decision"):
        runner.network_decided_or_exit()
    scope_file(KEEP_BY_HAND, {**DECISION, "rows": ["Bluetooth Function", "Access Authen. Info", "Wi-Fi"]})
    with pytest.raises(SystemExit, match="Access Authen. Info") as e:
        runner.network_decided_or_exit()
    assert "'Wi-Fi'" in str(e.value) and "nothing was sent" in str(e.value)
    from camkit import vlm
    assert vlm.LOCAL_ONLY is False
    scope_file(KEEP_BY_HAND, {**DECISION, "options": {"Bluetooth Function": ["Off"]}})
    run = Run("net", root=tmp_path)
    rows, options, words = runner.network_decided_or_exit(run)
    assert rows == {"Bluetooth Function": DAY, "Wi-Fi Frequency Band": DAY, "Display Wi-Fi Info.": DAY}
    assert options == {"Bluetooth Function": ["Off"]} and vlm.LOCAL_ONLY is True      # local readers only from here
    assert words.startswith(f"the owner decided on {DAY} that the kit may open Bluetooth Function remotely and choose "
                            "Off; ")
    assert "Wi-Fi Frequency Band remotely, to look only" in words
    out = capsys.readouterr().out
    assert "Display Wi-Fi Info., 2026-11-13 (address screen; an address screen: only drive.py opens it" in out
    assert "Wi-Fi Frequency Band, 2026-11-13 (Wi-Fi or Bluetooth setting; to look only)" in out
    assert "(Wi-Fi or Bluetooth setting; may choose Off)" in out
    logged = [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert logged[-1]["kind"] == "network_decided" and logged[-1]["rows"] == rows
    assert logged[-1]["options"] == options


@pytest.mark.parametrize("bad,said", [
    ({"Pairing": ["On"]}, "a row it does not name"), ({"Bluetooth Function": "On"}, "not a list of option names"),
    ({"Bluetooth Function": []}, "not a list"), ({"Bluetooth Function": [""]}, "not a list"),
    (["Bluetooth Function"], "is not an object"), ({"Display Wi-Fi Info.": ["On"]}, "an address screen"),
])
def test_a_decisions_options_name_only_its_own_rows_and_lists(bad, said):
    rows, refusals = safety.network_decided({"decisions": [{**DECISION, "options": bad}]})
    assert len(refusals) == 1 and said in refusals[0], refusals
    assert safety.network_options({"decisions": [{**DECISION, "options": bad}]}) == {}


def test_prove_run_takes_network_with_rows_only_and_never_an_address_screen(scope_file, monkeypatch):
    import prove_run
    monkeypatch.setattr(sys, "argv", ["prove_run", "--network"])
    with pytest.raises(SystemExit, match="--rows"):
        prove_run.main()
    monkeypatch.setattr(sys, "argv", ["prove_run", "--network", "--rows", "Bluetooth Function", "--help-text"])
    with pytest.raises(SystemExit, match="list options only"):
        prove_run.main()
    scope_file(DECISION)
    with pytest.raises(SystemExit, match="to look only"):          # no option named: a proof would choose one
        prove_run.network_rows_or_exit(["Network > Bluetooth Function"])
    scope_file({**DECISION, "options": {"Bluetooth Function": ["Off", "On"]}})
    named, chosen, words = prove_run.network_rows_or_exit(["Network > Bluetooth Function"])
    assert named == {"Bluetooth Function": DAY} and chosen == {"Bluetooth Function": ["Off", "On"]}
    assert words == f"the owner decided on {DAY} that the kit may open Bluetooth Function remotely and choose Off, On"
    for rows in (["Display Wi-Fi Info."], ["Drive Mode"], ["Bluetooth Rmt Ctrl"]):
        with pytest.raises(SystemExit, match="none of the rows"):
            prove_run.network_rows_or_exit(rows)
    scope_file({**DECISION, "rows": ["Bluetooth Function", "Pairing"]})
    with pytest.raises(SystemExit, match="Pairing"):
        prove_run.network_rows_or_exit(["Bluetooth Function"])


def test_prove_run_proves_only_the_named_options_of_a_network_list(capsys):
    import prove_run
    named = {"Bluetooth Function": DAY}
    job = {"path": ["Bluetooth Function"], "kind": "list", "labels": ["On", "Off"]}
    got = prove_run.network_jobs_or_exit([dict(job), {"path": ["Drive Mode"], "kind": "list", "labels": ["A", "B"]}],
                                         named, {"Bluetooth Function": ["off"]})
    assert got[0]["choose"] == [1] and got[0]["network_row"] == "Bluetooth Function" and "choose" not in got[1]
    assert prove_run.planned(got[0]) == {1}
    assert "by hand: On" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="does not list among its options"):
        prove_run.network_jobs_or_exit([dict(job)], named, {"Bluetooth Function": ["Maybe"]})
    with pytest.raises(SystemExit, match="only as a list of options"):
        prove_run.network_jobs_or_exit([{**job, "kind": "dialog"}], named, {"Bluetooth Function": ["Off"]})
    with pytest.raises(SystemExit, match="only as a list of options"):
        prove_run.network_jobs_or_exit([{"path": ["Bluetooth Function"], "kind": "axis", "option": "x",
                                         "values": ["a", "b"]}], named, {"Bluetooth Function": ["Off"]})


class ListCamera:
    """prove_row's camera for a two-option list (On, Off) opened from its row, the cursor where which_option says:
    the press keys, and, after Enter, a notice when `notice` is given (its OCR lines), else the row again."""
    def __init__(self, tmp_path, notice=None):
        self.where, self.option, self.keys, self.notice, self.tmp = "row", 1, [], notice, tmp_path
        self.frame = SimpleNamespace(path=tmp_path / "00001.png", image=None)

    def press(self, key, **kw):
        self.keys.append(key)
        if key == "right":
            self.where = "list"
        elif key in ("down", "up") and self.where == "list":
            self.option = 1 - self.option
        elif key == "enter":
            self.where = "notice" if self.notice else "row"
        elif key == "menu":
            self.where = "row"

    def read(self):
        return SimpleNamespace(kind={"row": "submenu", "list": "list", "notice": "notice"}[self.where])


def test_prove_row_chooses_only_named_options_and_withholds_an_identity_notice(tmp_path, monkeypatch):
    """A network row's proof chooses only the options its decision names; a row whose saved option is not among them is
    left for the session's upload (RestoreAfter); a notice after OK naming identity keeps its field names alone."""
    import prove_run as P
    from camkit import ocr
    from proving.base import RestoreAfter
    run = Run("pass2", root=tmp_path)
    for name, value in (("place", lambda cam: "here"), ("same_place", lambda a, b: True), ("to_row", lambda *a: None),
                        ("which_option", lambda cam, job: cam.option), ("vlm_option", lambda cam: "Off"),
                        ("bar_text", lambda cam: "Off"), ("after_download", lambda cam, done: None),
                        ("finish_attempt", lambda *a, **k: None)):
        monkeypatch.setattr(P, name, value)
    monkeypatch.setattr(P.camset, "read", lambda p: SimpleNamespace())
    monkeypatch.setattr(P.camset, "diff", lambda a, b: [])
    lines = [ocr.Line(text=t, conf=0.9, x=0, y=0, w=10, h=10) for t in ("Pairing", "SSID", "DIRECT-madeup", "OK")]
    monkeypatch.setattr(P.ocr, "read", lambda paths, eng=None: {p: lines for p in paths})
    link = SimpleNamespace(download=lambda tag: tmp_path / f"{tag}.DAT")
    job = {"path": ["Bluetooth Function"], "kind": "list", "labels": ["On", "Off"], "choose": [0],
           "network_row": "Bluetooth Function"}
    out = io.StringIO()
    cam = ListCamera(tmp_path, notice=True)
    with pytest.raises(RestoreAfter, match=P.NETWORK_RESTORE):
        P.prove_row(cam, link, run, job, tmp_path / "base.DAT", out)          # saved Off (1), named On (0) alone
    proofs = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [p["label"] for p in proofs] == ["On"] and cam.keys.count("enter") == 1
    assert proofs[0]["notice"]["fields"] == ["SSID"] and "text" not in proofs[0]["notice"]
    assert "DIRECT" not in out.getvalue() and "Pairing" not in out.getvalue()
    assert proofs[0]["network"] == safety.LIFT_IDENTITY             # no class given: kept as an identity row's
    out = io.StringIO()
    cam = ListCamera(tmp_path)
    with pytest.raises(RestoreAfter, match=P.NETWORK_RESTORE):        # both named: the session's upload, as ever
        P.prove_row(cam, link, run, {**job, "choose": [0, 1], "network_class": safety.LIFT_NETWORK},
                    tmp_path / "base.DAT", out)
    lines = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [x["label"] for x in lines] == ["On", "Off"] and {x["network"] for x in lines} == {safety.LIFT_NETWORK}


def test_the_jobs_take_a_decided_setting_and_keep_the_scopes_exclusions(scope_file, monkeypatch):
    """proving.jobs: a decided setting passes the never-open check with NETWORK set, an address screen never, and a row
    the reviewed scope excludes stays out of the proofs whatever is decided."""
    from proving import base, jobs
    f = scope_file(DECISION, {**DECISION, "rows": ["Bluetooth Rmt Ctrl"]},
                   exclude={"connection, by hand only": ["Bluetooth Rmt Ctrl"]})
    options = [{"index": 0, "label": "On", "frame": "f0"}, {"index": 1, "label": "Off", "frame": "f1"}]
    the_map = f.parent / "map_all.json"
    the_map.write_text(json.dumps({"rows": [{"path": [p], "kind": "list", "options": options} for p in
                                            ("Bluetooth Function", "Display Wi-Fi Info.", "Bluetooth Rmt Ctrl",
                                             "Drive Mode")]}), encoding="utf-8")
    monkeypatch.setattr(base, "MAP", the_map)
    monkeypatch.setattr(jobs, "NETWORK", {})
    assert [j["path"] for j in jobs.jobs()] == [["Drive Mode"]]
    rows = decided(DECISION, {**DECISION, "rows": ["Bluetooth Rmt Ctrl"]})
    monkeypatch.setattr(jobs, "NETWORK", {r: d for r, d in rows.items() if not safety.address_screen(r)})
    assert [j["path"] for j in jobs.jobs()] == [["Bluetooth Function"], ["Drive Mode"]]


def test_the_walk_takes_settings_only(scope_file, tmp_path):
    import crawl_run
    scope_file({**DECISION, "rows": ["Display Wi-Fi Info."]})
    with pytest.raises(SystemExit, match="only address screens"):
        crawl_run.network_settings_or_exit(Run("net", root=tmp_path))
    scope_file(DECISION)
    assert crawl_run.network_settings_or_exit(Run("net", root=tmp_path)) == {"Bluetooth Function": DAY,
                                                                               "Wi-Fi Frequency Band": DAY}


def test_the_help_walk_reads_a_network_rows_guide_with_by_hand_rows(monkeypatch):
    """help_run --by-hand-rows reads the In-Camera Guide of the class's rows as of the other by-hand rows (the row is
    not opened); Access Authen. stays passed over."""
    import help_run
    lit = {"label": ""}
    for name, value in (("same_position", lambda a, b: True), ("help_refused", lambda kind, image: ""),
                        ("highlighted", lambda image, path: lit["label"]),
                        ("guide", lambda cam, label: {"title": "t", "text": "help", "frames": []})):
        monkeypatch.setattr(help_run, name, value)
    cam = SimpleNamespace(press=lambda key: None, read=lambda: SimpleNamespace(kind="menu"),
                          frame=SimpleNamespace(image=None, path=Path("00001.png")))
    cycle = [{"kind": "menu", "page": "P", "row": 0, "screen": "s0"}]
    for label, by_hand, read in (("Bluetooth Rmt Ctrl", True, True), ("Bluetooth Rmt Ctrl", False, False),
                                 ("Display Wi-Fi Info.", True, True), ("Access Authen. Info", True, False)):
        lit["label"] = label
        out = io.StringIO()
        help_run.walk(cam, cycle, {"P": {"breadcrumb": "Network > Bluetooth", "rows": [{"label": label}]}}, set(), out,
                      SimpleNamespace(by_hand_rows=by_hand, context="Stills", limit=0))
        assert bool(out.getvalue()) == read, (label, by_hand)


# ---------------------------------------------------------------- drive.py

DRIVE = ROOT / "kit" / "drive.py"


def drive(*args):
    return subprocess.run([sys.executable, str(DRIVE), *args], capture_output=True, text=True, timeout=60)


def test_drive_refuses_a_network_row_without_network():
    for args in (["--path", "Bluetooth Function"], ["--path", "Network", "--path", "Wi-Fi Frequency Band"],
                 ["--path", "Display Wi-Fi Info.", "--press", "right"],
                 ["--path", "Bluetooth Function", "--allow", "Bluetooth Function"]):
        r = drive(*args)
        assert r.returncode != 0 and "0008" in r.stderr and "no --allow opens it" in r.stderr, (args, r.stderr)
        assert "--network" in r.stderr


def test_drive_refuses_network_with_no_decision(scope_file):
    r = drive("--network", "--path", "Bluetooth Function")
    assert r.returncode != 0 and "no reviewed scope" in r.stderr and "nothing was sent" in r.stderr
    scope_file(KEEP_BY_HAND)
    r = drive("--network", "--path", "Bluetooth Function")
    assert r.returncode != 0 and "no dated owner decision" in r.stderr
    scope_file({**DECISION, "rows": ["Wi-Fi Connect"]})            # a decision, but not for this row
    r = drive("--network", "--path", "Bluetooth Function")
    assert r.returncode != 0 and "no --allow opens it" in r.stderr


@pytest.mark.parametrize("named", ["Access Authen. Info", "Wi-Fi Direct Info.", "Display Serial Number", "WPS Push"])
def test_drive_stops_on_a_decision_naming_what_none_opens(scope_file, named):
    scope_file({**DECISION, "rows": ["Bluetooth Function", named]})
    r = drive("--network", "--path", "Bluetooth Function")
    assert r.returncode != 0 and repr(named) in r.stderr and "nothing was sent" in r.stderr, r.stderr


def test_drive_opens_an_address_screen_only_as_the_last_label(scope_file):
    scope_file({**DECISION, "rows": ["Display Wi-Fi Info.", "Disp Device Address"]})
    for args in (["--path", "Display Wi-Fi Info.", "--path", "Something"],
                 ["--path", "Display Wi-Fi Info.", "--path", "Disp Device Address"]):
        r = drive("--network", *args)
        assert r.returncode != 0 and "only as the last label of --path" in r.stderr, r.stderr


def test_drive_judges_the_lit_row_with_the_decisions_rows():
    import drive as D
    rows = decided(DECISION)
    assert D.press_refused("right", "Bluetooth Function  On", "", "submenu", network=rows, values=VALUES) == ""
    assert D.press_refused("right", "Bluetooth Function  On", "", "submenu", network=rows)         # no labels: no tail
    assert D.press_refused("right", "Bluetooth Function  On", "", "submenu", network=rows, labels=set()) == ""
    assert D.press_refused("right", f"Bluetooth Function  {IP}", "", "submenu", network=rows, labels=set())
    assert D.press_refused("right", "Bluetooth Rmt Ctrl  Off", "", "submenu", network=rows, values=VALUES)
    assert D.press_refused("right", "Display Wi-Fi Info.", "", "submenu", network=rows)
    assert D.press_refused("right", "Display Wi-Fi Info.", "", "submenu", network=rows, screens=True) == ""
    assert D.press_refused("right", "Bluetooth Function  On", "", "submenu", allow=["Bluetooth Function"])
    # a vouched Enter never on a screen that names the class, whatever is decided
    why, _ = D.press_decision("enter!:.*", "enter", "", "Bluetooth Function On Off", "unknown", network=rows)
    assert "never vouched" in why
    assert D.camera_network(rows, None) == {"Bluetooth Function": DAY, "Wi-Fi Frequency Band": DAY}
    assert D.camera_network(rows, "Display Wi-Fi Info.") == rows


MAC, IP = "00:11:22:33:44:55", "192.0.2.10"           # check_public's placeholders: never a real address


def drive_address(tmp_path, monkeypatch, scope_file, presses: list, path=("Display Wi-Fi Info.",)):
    """drive.py's main() on a made-up camera: the path's row lit on a submenu page until a Right or an Enter goes out,
    then a screen that reads as no known kind and shows a MAC and an IP address. Returns (the keys pressed, the console,
    drive.jsonl's line, the run's events)."""
    return drive_fake(tmp_path, monkeypatch, scope_file, presses, path, {**DECISION, "rows": ["Display Wi-Fi Info."]},
                      ["Display Wi-Fi Info.", "MAC Address", MAC, "IP Address", IP, "OK"], "unknown",
                      page_lit="Display Wi-Fi Info.", open_lit="")


def drive_fake(tmp_path, monkeypatch, scope_file, presses: list, path, decision, open_lines, open_kind, page_lit,
               open_lit, page_kind="submenu", slow=False, misread=(), misread_lit=False, menu_does="page",
               page_lines=None, own="", model=None, shooting_lines=None, changes=(), definition=None, reach=True,
               exits=None, end_raises=None):
    """drive.py's main() on a made-up camera, no LiveCamera under it: the path's row lit (page_lit) on a page of
    page_kind until a Right or an Enter goes out, then a screen of open_kind showing open_lines, its lit bar open_lit;
    MENU, or Enter there, brings the page back, at the place it was (drive.same_position: the same kind at the same
    place; drive.same_state alike). slow: the press that opens the row still shows the page after it (a camera slow to
    draw); misread: the keys after which the open screen reads as the page, at its very place, its bar still reading
    open_lit (page_lit with misread_lit, the worst case). menu_does, inside the row: "page" (MENU closes it), "ignored"
    (the camera ignores MENU), "list-as-page" (MENU closes a notice onto the row's list, which reads as the page, its
    bar on an option). page_lines: the page's lines (by default two group names and the lit row); own: the kind the
    camera's own picture of the screen reads as (drive.osd_kind); model: the page scan's page model; shooting_lines: MENU
    inside the row closes the menu onto the shooting screen, which shows these lines (its status line); changes: the
    records the session's end finds differing; definition: the camera's definition (camkit.definitions.active); reach:
    whether the scan reaches the path's first label (crawl_run.go_to); exits: a list that takes the exit status main()
    exits with, where it exits (else the exit is raised); end_raises: what the session's end raises (the link gone).
    A read without a press (the wait's) finds the open screen drawn, a slow camera's included. Returns (the keys
    pressed, the console, drive.jsonl's line, the run's events)."""
    import drive as D
    from camkit import definitions, vlm
    scope_file(decision)
    if definition is not None:
        target = tmp_path / "drive_definition.json"
        target.write_text(json.dumps(definition), encoding="utf-8")
        monkeypatch.setattr(definitions, "active", lambda required=False: target)
    run = Run("kit2_drive", root=tmp_path)
    sent, state = [], {"open": False, "shown": False, "misread": False, "shoot": False}
    lines = {True: list(open_lines), False: list(page_lines or ["Bluetooth", "Wi-Fi", page_lit])}   # the page, its row lit

    def now_lines():
        return list(shooting_lines) if state["shoot"] else list(lines[state["shown"]])

    class Link:
        def __init__(self, r):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def press(self, key, **kw):
            sent.append(("link", key))

        def download(self, tag):
            return tmp_path / f"{tag}.DAT"

    class Cam:
        @property
        def frame(self):
            return SimpleNamespace(path=tmp_path / ("00009_right.png" if state["open"] else "00001_down.png"), image=None)

        def read(self):
            if state["shoot"]:
                return SimpleNamespace(kind="shooting", where="shooting")
            if state["misread"] or not state["shown"]:
                return SimpleNamespace(kind=page_kind, where=PAGE)
            return SimpleNamespace(kind=open_kind, where="inside")

        def press(self, key, **kw):
            sent.append(("cam", key))
            was = state["open"]
            if key == "menu" and was and menu_does == "ignored":
                return
            if key == "menu" and was and shooting_lines is not None:
                state.update(open=False, shown=False, misread=False, shoot=True)
                return
            if key in ("right", "enter"):
                state["open"] = not state["open"] if key == "enter" else True
            if key == "menu" and state["open"] and menu_does == "page":
                state["open"] = False
            state["shown"] = was if (slow and state["open"] and not was) else state["open"]
            state["misread"] = state["open"] and (key in misread or (key == "menu" and menu_does == "list-as-page"))

        def dial(self, name, steps, **kw):
            sent.append(("cam", f"dial {name}"))

        def refresh(self, tag):
            state["shown"] = state["shown"] or (state["open"] and not state["misread"])    # drawn by now
            return self.read()
    seen = {"run": run}

    def camera(link, eyes, r, **kw):
        seen["camera"] = kw
        return Cam()
    ending = SimpleNamespace(after=tmp_path / "after.DAT", changes=list(changes), uploaded=False)

    def ended(link, before, show=30, **kw):
        if end_raises is not None:
            raise end_raises
        seen.update(ended={"show": show, **kw})
        return ending
    for name, value in (("check_readers", lambda: seen.setdefault("local_only", vlm.LOCAL_ONLY)),
                        ("load_scan", lambda scan: ([], model or {})), ("Run", lambda name: run),
                        ("eyes_from_config", lambda r: SimpleNamespace(attach=lambda link: None, grab=lambda save=False: None,
                                                                       close=lambda: None)),
                        ("screen", SimpleNamespace(read=lambda f: SimpleNamespace(kind="shooting"))),
                        ("wait_for", lambda *a, **k: None), ("Link", Link),
                        ("LiveCamera", camera),
                        ("find_position", lambda cam, cycle, model: 0),
                        ("go_to", lambda *a, **k: True if reach else None),
                        ("enter_any", lambda cam, path, i: None), ("bar_at", lambda cam, y: False),
                        ("screen_text", lambda cam, grip: " ".join(now_lines())),
                        ("screen_lines", lambda cam, grip: now_lines()),
                        ("highlighted", lambda image, path: "" if state["shoot"] else page_lit if not state["shown"] or
                         (state["misread"] and misread_lit) else open_lit),
                        ("same_position", lambda a, b: a.kind == b.kind and a.where == b.where),
                        ("same_state", lambda a, b: a.kind == b.kind and a.where == b.where),
                        ("osd_kind", lambda link: own),
                        ("network_values", lambda rows, model: {r: v for r, v in VALUES.items() if r in rows}),
                        ("time", SimpleNamespace(sleep=lambda s: None)),
                        ("close_for_restore", lambda cam, link: sent.append(("closed",))),
                        ("session", SimpleNamespace(ended=ended, put_back=lambda link, e, before: e)),
                        ("restore_checked", lambda r, e, before, **kw: seen.update(checked=kw) or True)):
        monkeypatch.setattr(D, name, value)
    argv = ["drive.py", "--network", *[x for p in path for x in ("--path", p)], *[x for p in presses for x in ("--press", p)]]
    monkeypatch.setattr(sys, "argv", argv)
    try:
        D.main()
    except SystemExit as e:
        if exits is None:
            raise
        exits.append(e.code)
    line = json.loads((run.dir / "drive.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    logged = (run.dir / "events.jsonl").read_text(encoding="utf-8")
    return [s[1] for s in sent if s[0] == "cam"], seen, line, logged


def test_drive_sends_no_key_but_menu_once_an_address_screen_is_open(tmp_path, monkeypatch, scope_file, capsys):
    from camkit import vlm
    pressed, seen, line, logged = drive_address(tmp_path, monkeypatch, scope_file, ["right", "down", "menu"])
    out = capsys.readouterr().out
    assert pressed == ["menu", "right"] and line["completed"] is False          # Down refused, nothing after it
    assert "down refused: a row was opened on this address run" in out
    assert seen["local_only"] is True and vlm.LOCAL_ONLY is True               # set before the link opened
    assert seen["camera"]["screens"] is True and seen["camera"]["network"] == {"Display Wi-Fi Info.": DAY}
    assert line["address_screen"] == "Display Wi-Fi Info." and line["network"] == {"Display Wi-Fi Info.": DAY}
    assert line["screens"][0]["fields"] == ["Display Wi-Fi Info.", "MAC Address", "IP Address"]   # the decided row
    assert "text" not in line["screens"][0]
    for where in (out, json.dumps(line), logged):
        assert MAC not in where and IP not in where
    assert '"address_screen_opened"' in logged and '"press_refused"' in logged
    pressed, _, line, _ = drive_address(tmp_path, monkeypatch, scope_file, ["right", "menu"])
    assert pressed == ["menu", "right", "menu"] and line["completed"] is True
    assert all("text" not in s for s in line["screens"])
    out = capsys.readouterr().out
    assert MAC not in out and IP not in out


def test_drive_withholds_the_quoted_texts_of_an_address_runs_refusals():
    import drive as D
    assert D.withheld(f"the screen does not match 'X': '{MAC} {IP}'") == "the screen does not match '(withheld)': '(withheld)'"
    assert D.withheld('confirmation text: execute on "IP Address 192.0.2.10"') == "confirmation text: execute on '(withheld)'"


RMT = {**DECISION, "rows": ["Bluetooth Function"]}
RMT_LIST = ["Bluetooth Function", "On", "Off"]


def drive_rmt(tmp_path, monkeypatch, scope_file, presses, decision=RMT, open_lit="Off", open_kind="list",
              open_lines=RMT_LIST):
    """drive_fake on Bluetooth Function, a setting whose options a decision may name."""
    return drive_fake(tmp_path, monkeypatch, scope_file, presses, ("Bluetooth Function",), decision, open_lines,
                      open_kind, page_lit="Bluetooth Function  On", open_lit=open_lit)


def test_drive_looks_at_a_network_row_and_chooses_nothing_the_decision_does_not_name(tmp_path, monkeypatch, scope_file,
                                                                                    capsys):
    from camkit import vlm
    pressed, seen, line, _ = drive_rmt(tmp_path, monkeypatch, scope_file, ["right", "down", "up", "enter:Off"])
    assert pressed == ["menu", "right", "down", "up"] and line["completed"] is False
    assert "to look only" in capsys.readouterr().out and vlm.LOCAL_ONLY is True
    assert seen["camera"]["options"] == {} and seen["camera"]["screens"] is False
    # its own list: its title a row label, never its text, nor which option is lit (2026-11-14: no text kept at all)
    assert "text" not in line["screens"][0] and line["screens"][0]["fields"] == ["Bluetooth Function"]
    for refused in (["right", "right"], ["right", "left"], ["right", "dial.front.1:.*"], ["right", "help"],
                    ["right", "ms_enter:Off"]):
        pressed, _, line, _ = drive_rmt(tmp_path, monkeypatch, scope_file, refused)
        assert pressed == ["menu", "right"] and line["completed"] is False, refused


@pytest.mark.parametrize("lit,goes", [("Off", True), ("On", False), ("", False), ("Of", False)])
def test_drive_chooses_only_an_option_the_decision_names(tmp_path, monkeypatch, scope_file, lit, goes):
    decision = {**RMT, "options": {"Bluetooth Function": ["Off"]}}
    pressed, seen, line, logged = drive_rmt(tmp_path, monkeypatch, scope_file, ["right", "enter:.", "down"],
                                            decision=decision, open_lit=lit)
    assert seen["camera"]["options"] == {"Bluetooth Function": ["Off"]}
    if goes:          # Enter chose Off, the page is back, the row is left: Down on the page goes as ever
        assert pressed == ["menu", "right", "enter", "down"] and line["completed"] is True
        assert '"network_row_left"' in logged
    else:
        assert pressed == ["menu", "right"] and line["completed"] is False


def test_drive_leaves_a_network_row_only_after_menu_or_a_named_enter_on_the_page_it_left(monkeypatch):
    """drive.network_left: the press just sent was a MENU or an Enter on a named option (closing) AND the screen read
    now is the shooting screen, or the page the row was opened from (same_position) with its lit bar on the row itself;
    never a screen's kind alone, never a bar that reads an option or nothing."""
    import drive as D
    monkeypatch.setattr(D, "same_position", lambda a, b: a.kind == b.kind and a.where == b.where)
    page, row = SimpleNamespace(kind="menu", where=PAGE), "Wired LAN Connect"
    for now, closing, lit, left in ((SimpleNamespace(kind="menu", where=PAGE), True, "Wired LAN Connect  On", True),
                                    (SimpleNamespace(kind="shooting", where="x"), True, "", True),
                                    (SimpleNamespace(kind="menu", where=PAGE), False, "Wired LAN Connect", False),
                                    (SimpleNamespace(kind="shooting", where="x"), False, "", False),
                                    (SimpleNamespace(kind="menu", where=PAGE), True, "Off", False),   # a popup's bar
                                    (SimpleNamespace(kind="menu", where=PAGE), True, "", False),      # unreadable
                                    (SimpleNamespace(kind="menu", where=PAGE), True, "Wired LAN Connected", False),
                                    (SimpleNamespace(kind="menu", where="another page"), True, row, False),
                                    (SimpleNamespace(kind="tiles", where="tiles"), True, row, False),
                                    (SimpleNamespace(kind="submenu", where="inside"), True, row, False)):
        assert D.network_left(now, page, closing, lit, row) is left, (now, closing, lit)
    monkeypatch.setattr(D, "same_position", lambda a, b: (_ for _ in ()).throw(ValueError("no screen")))
    assert D.network_left(SimpleNamespace(kind="menu"), page, True, row, row) is False    # cannot compare: no way out


WIRED_DRIVE = {"path": ("Wired LAN Connect",), "decision": {**DECISION, "rows": ["Wired LAN Connect"]},
               "open_lines": ["Wired LAN Connect", "On", "Off"], "open_kind": "list", "page_lit": "Wired LAN Connect",
               "open_lit": "Off", "page_kind": "menu"}


@pytest.mark.parametrize("how", [{"slow": True}, {"misread": ("down",)}])
def test_drive_keeps_the_lock_on_a_slow_camera_and_a_list_misread_as_the_page(tmp_path, monkeypatch, scope_file, how):
    """Right on Wired LAN Connect, whose choice is never made; the camera is slow (the frame after the Right still
    reads as the menu page it was opened from), or the list is misread as that page after a Down: no MENU went out, so
    the row stays open, and Enter on Off is refused. drive.py on its own: no LiveCamera under it."""
    pressed, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "down", "enter:."], **WIRED_DRIVE,
                                          **how)
    assert pressed == ["menu", "right", "down"] and line["completed"] is False
    assert '"network_row_opened"' in logged and '"network_row_left"' not in logged


def test_drive_leaves_the_row_when_menu_brings_back_its_page(tmp_path, monkeypatch, scope_file):
    """MENU after the slow Right and a Down: the page it was opened from is back, so the row is left, and a Down on the
    page goes out as ever."""
    pressed, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "down", "menu", "down"],
                                          **WIRED_DRIVE, slow=True)
    assert pressed == ["menu", "right", "down", "menu", "down"] and line["completed"] is True
    assert '"network_row_left"' in logged


def test_drive_keeps_the_lock_after_a_menu_the_camera_ignored(tmp_path, monkeypatch, scope_file):
    """The reviewer's sequence, drive.py on its own: Right on "Wired LAN Connect On" opens its list; MENU is ignored
    (the list stays); a Down lands on a frame where the popup reads as the page, even its bar read as the row: the
    MENU's evidence was spent on the list read after it, so the row stays open, and Enter on Off is refused."""
    pressed, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "menu", "down", "enter:."],
                                          **{**WIRED_DRIVE, "page_lit": "Wired LAN Connect  On"}, menu_does="ignored",
                                          misread=("down",), misread_lit=True)
    assert pressed == ["menu", "right", "menu", "down"] and line["completed"] is False
    assert '"network_row_left"' not in logged


def test_drive_keeps_the_lock_after_a_menu_that_only_closed_a_notice_inside_the_row(tmp_path, monkeypatch, scope_file):
    """Right opens a notice inside the row; MENU closes it onto the row's list, which reads as the page (same place)
    with its bar on an option: the row stays open, and Enter on Off is refused."""
    pressed, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "menu", "enter:."],
                                          **{**WIRED_DRIVE, "open_kind": "notice",
                                             "open_lines": ["This function is currently disabled.", "OK"]},
                                          menu_does="list-as-page")
    assert pressed == ["menu", "right", "menu"] and line["completed"] is False
    assert '"network_row_left"' not in logged


def test_drive_sends_menu_alone_on_a_screen_naming_identity_and_shows_no_text(tmp_path, monkeypatch, scope_file, capsys):
    words = ["Pairing", "Searching for the device...", "Device Name", "ILCE-made-up", "Cancel"]
    decision = {**RMT, "options": {"Bluetooth Function": ["On"]}}
    pressed, _, line, logged = drive_rmt(tmp_path, monkeypatch, scope_file, ["right", "enter:."], decision=decision,
                                         open_lit="On", open_kind="notice", open_lines=words)
    out = capsys.readouterr().out
    assert pressed == ["menu", "right"] and line["completed"] is False
    assert "no key but MENU" in out and '"identity_screen"' in logged
    assert line["screens"][0]["fields"] == ["Device Name"] and "text" not in line["screens"][0]
    for where in (out, json.dumps(line), logged):
        assert "Searching" not in where and "ILCE-made-up" not in where
    pressed, _, line, _ = drive_rmt(tmp_path, monkeypatch, scope_file, ["right", "menu"], decision=decision,
                                    open_lit="On", open_kind="notice", open_lines=words)
    assert pressed == ["menu", "right", "menu"] and line["completed"] is True


def test_drive_shows_a_screen_inside_a_network_row_only_when_it_is_a_kind_it_knows():
    assert safety.network_withheld("list", "Bluetooth Rmt Ctrl On Off") is None
    assert safety.network_withheld("unknown", "Bluetooth Rmt Ctrl On Off")
    assert safety.network_withheld("notice", "Connected to DIRECT-madeup")
    assert safety.network_withheld("notice", "This function is currently disabled.") is None


# ---------------------------------------------------------------- the lift, pinned

def test_the_lift_re_checks_each_decided_row():
    """network_lifted takes only a row a decision may name (network_refused): a group's name ("Bluetooth", "Wi-Fi") as
    decided lifts nothing, though the lit row starts with it."""
    assert not safety.network_lifted("Bluetooth Function  On", {"Bluetooth": DAY}, values=VALUES)
    assert not safety.network_lifted("Wi-Fi Connect On", {"Wi-Fi": DAY}, values=VALUES)
    assert not safety.network_lifted("Bluetooth Function", {"Bluetooth": DAY}, screens=True)


def test_the_lift_refuses_a_lit_text_holding_an_address_screen():
    assert not safety.network_lifted("Bluetooth Function Device Address", {"Bluetooth Function": DAY})
    assert not safety.network_lifted("Bluetooth Function Device Address", {"Bluetooth Function": DAY},
                                     values={"Bluetooth Function": ["Device Address"]})


@pytest.mark.parametrize("lit,lifted", [
    ("Wi-Fi Connect", True), ("Wi-Fi Connect  On", True), ("Wi-Fi Connect Off.", True), ("> Wi-Fi Connect Off", True),
    ("Wi-Fi Connect Settings", False), ("No Wi-Fi Connect", False), ("No Wi-Fi Connect On", False),
    ("Wi-Fi Connected", False), ("Wi-Fi Connect On Off", False), ("S Wi-Fi Connect", False),
])
def test_the_lift_takes_the_row_and_one_of_its_values_and_nothing_else(lit, lifted):
    """What follows the label is nothing or one of the row's own values; no short first word is dropped (clean_label
    does that for the other guards, so "No Wi-Fi Connect" read as "Wi-Fi Connect" there): an icon read as a letter in
    front of the label refuses, failing closed."""
    assert safety.network_lifted(lit, {"Wi-Fi Connect": DAY}, values=VALUES) is lifted


def test_a_decision_is_dated_today_or_before():
    import datetime
    today = datetime.date.today()
    assert safety._valid_day(today.isoformat()) and safety._valid_day("2026-11-13")
    assert not safety._valid_day((today + datetime.timedelta(days=1)).isoformat())
    rows, refusals = safety.network_decided({"decisions": [{**DECISION, "date": "2999-01-01"}]})
    assert rows == {} and "today or before" in refusals[0]


@pytest.mark.parametrize("text", ["Pairing", "Searching for the device...", "SSID: DIRECT-madeup", "Access Point",
                                  "Device Name ILCE-made-up", "Enter the password", "PIN", "WPS", "Connecting...",
                                  "Awaiting connection", "MAC Address", "Connected to DIRECT-madeup",
                                  "Connect to DIRECT-madeup?"])
def test_identity_words_on_a_screen_inside_a_network_row(text):
    assert safety.identity_screen(text) and safety.network_withheld("notice", text)


@pytest.mark.parametrize("text", ["Bluetooth Rmt Ctrl On Off", "Wi-Fi Frequency Band 2.4GHz 5GHz",
                                  "Airplane Mode On Off", "This function is currently disabled. OK"])
def test_a_network_rows_own_list_names_no_identity(text):
    assert safety.identity_screen(text) is None


# ---------------------------------------------------------------- identity and connection rows (decision 8, 2026-11-13)

# The identity and connection rows seen opened and left with MENU over the LAN link on the a1 II without harm, look-only
# (decision 8): (when, what Right opened). A row is liftable only once so seen: safety._IDENTITY_LIFTABLE holds these
# and nothing else (test_only_rows_seen_opened_over_the_link_are_liftable), each entry naming when it was seen
IDENTITY_SEEN = {
    "Wired LAN Connect": ("2026-11-13/14", "a list of two; the link held"),
    "Wake On LAN": ("2026-11-13/14", "a list of two"),
    "Remote Shoot Function": ("2026-11-13/14", "a submenu"),
    "Cnct. while Power OFF": ("2026-11-13/14", "a notice while greyed"),
    "Manage Paired Device": ("2026-11-13", "a screen; MENU returned to the page"),
    "Display FTP Result": ("2026-11-13/14", "an information screen"),
}
IDENTITY_LOOK = list(IDENTITY_SEEN)
# the identity rows no decision opens (2026-11-13, a review): opening one may itself start or end a connection or act,
# and nobody has yet seen on the camera what Right does there (look-only governs the presses after the opening); Server
# Setting holds the FTP login (credentials); Edit Device Name opens a keyboard and the device's name, held by no file.
# Since 2026-11-14 also IP Address Setting, whose opening and MENU dropped the wired LAN link, and the region and USB rows
# nobody has seen opened over the link
NOT_LIFTED = {"Smartphone Connection": "start or end a connection", "Cloud Connection": "start or end a connection",
              "Cloud Information": "start or end a connection", "Network Streaming": "start or end a connection",
              "USB Streaming": "start or end a connection", "Tethering Connection": "start or end a connection",
              "Tethering Disconnection": "start or end a connection", "FTP Function": "start or end a connection",
              "Server Setting": "login", "Edit Device Name": "keyboard",
              "IP Address Setting": "dropped the link", "LANIP Address Setting": "dropped the link",
              "USB Connection Mode": "not yet seen opened", "USB LUN Setting": "not yet seen opened",
              "USB Power Supply": "not yet seen opened", "Language": "not yet seen opened",
              "NTSC/PAL Selector": "not yet seen opened", "Area/Date/Time Setting": "not yet seen opened",
              "Date/Time Setup": "not yet seen opened"}


def test_only_rows_seen_opened_over_the_link_are_liftable():
    """safety._IDENTITY_LIFTABLE is exactly the rows seen opened over the link (IDENTITY_SEEN): each pattern names one
    of them and every one is named, so a row added there without being recorded here as seen fails; and each entry in
    safety.py carries the day it was seen beside it."""
    import inspect
    for rx in safety._IDENTITY_LIFTABLE:
        named = [label for label in IDENTITY_SEEN if any(re.search(rx, r) for r in safety.readings(label))]
        assert len(named) == 1, (rx, named)
    assert {label for label in IDENTITY_SEEN if safety.identity_liftable(label)} == set(IDENTITY_SEEN)
    assert all(safety.lift_class(label) == safety.LIFT_IDENTITY for label in IDENTITY_SEEN)
    source = inspect.getsource(safety)
    block = source[source.index("\n_IDENTITY_LIFTABLE = [") + 1:]
    block = block[:block.index("\n]")]
    entries = [line for line in block.splitlines()[1:] if line.strip() and not line.strip().startswith("#")]
    assert len(entries) == len(safety._IDENTITY_LIFTABLE), entries
    for line in entries:
        assert re.search(r"#\s*seen 20\d\d-\d\d-\d\d", line), f"no day it was seen beside: {line.strip()}"


def test_a_scope_naming_ip_address_setting_stops_drive_before_anything_connects(scope_file):
    """The owner's dated decision of 2026-11-13 names IP Address Setting; since 2026-11-14 no decision opens it: drive.py
    given --network stops before the link opens (no run folder's drive.jsonl is written), saying why."""
    scope_file({**DECISION, "rows": ["Bluetooth Function", "IP Address Setting"]})
    r = drive("--network", "--path", "IP Address Setting")
    assert r.returncode != 0 and "nothing was sent to the camera" in r.stderr, r.stderr
    assert "dropped the link" in r.stderr and "no decision opens it" in r.stderr, r.stderr
    scope_file({**DECISION, "rows": ["Language"]})
    r = drive("--network", "--path", "Language")
    assert r.returncode != 0 and "not yet seen opened" in r.stderr and "nothing was sent" in r.stderr, r.stderr


@pytest.mark.parametrize("label,said", NOT_LIFTED.items())
def test_a_row_whose_opening_may_act_opens_by_no_decision(label, said):
    assert safety.lift_class(label) is None and safety.never_open(label) and safety.never_lifted(label)
    rows, refusals = safety.network_decided({"decisions": [{**DECISION, "rows": ["Bluetooth Function", label]}]})
    assert rows == {"Bluetooth Function": DAY} and len(refusals) == 1 and said in refusals[0], refusals
    forced = {label: DAY}                                    # even a set of rows that names it by hand
    assert not safety.network_lifted(label, forced) and safety.path_refused([label], network=forced)
    assert live.open_refused(label, network=forced, screens=True)
    assert not crawl.network_open({"label": label, "never_open": safety.never_open(label)}, forced)


@pytest.mark.parametrize("label", ["Wired LAN Connect Access Point", "Smartphone Pairing", "Wake On LAN Pairing",
                                   "IP Address Setting SSID", "Remote Shoot Function WPS", "Manage Paired Device Copyright"])
def test_a_liftable_row_read_beside_a_row_that_stays_closed_lifts_nothing(label):
    """identity_liftable judges every reading for the identity rows that stay closed (_IDENTITY_FIXED_RE) too: a
    liftable row's words beside a closed row's words lift nothing."""
    assert safety.lift_class(label) is None
    assert not safety.network_lifted(label, {label.rsplit(" ", 1)[0]: DAY}, screens=True)


@pytest.mark.parametrize("bad,said", [
    (["Password"], "credentials"), (["SSID"], "no decision lets"), (["PIN"], "no decision lets"),
    (["Pairing"], "no decision lets"), (["Initialize"], "no decision lets"), (["A"], "one character"),
    (["0"], "one character"), (["OK"], "button"), (["Enter"], "button"), (["Execute"], "button"), (["Yes"], "button"),
    (["Cancel"], "button"), (["Set"], "button"), (["Done"], "button"), (["On", " ok "], "button"),
])
def test_a_decisions_options_are_screened(bad, said):
    scope = {"decisions": [{**DECISION, "rows": ["Bluetooth Function"], "options": {"Bluetooth Function": bad}}]}
    rows, refusals = safety.network_decided(scope)
    assert rows == {"Bluetooth Function": DAY} and len(refusals) == 1 and said in refusals[0], refusals
    assert safety.network_options(scope) == {}
    good = {"decisions": [{**DECISION, "rows": ["Bluetooth Function", "Wake On LAN"],
                           "options": {"Bluetooth Function": ["On", "Off"], "Wake On LAN": ["Enable", "Disable"]}}]}
    assert safety.network_decided(good)[1] == [] and safety.network_options(good)["Wake On LAN"] == ["Enable", "Disable"]


# Wi-Fi and Bluetooth settings a decision opens to look at, whose options it never lets the kit choose: Wi-Fi Connect's
# On joins the access point, Bluetooth Rmt Ctrl's On opens the Pairing screen, Airplane Mode drops the Wi-Fi and
# Bluetooth links (the a1 II's notes), a Wi-Fi Frequency Band change can drop a link over Wi-Fi (2026-11-14); also as a
# reader returns them
NEVER_CHOSEN = ["Wi-Fi Connect", "Wi-Fl Connect", "WiFi Connect", "Bluetooth Rmt Ctrl", "Bluetoth Rnt Ctrl",
                "Bluetooth Remote Control", "Airplane Mode", "Wi-Fi Frequency Band", "Wi-Fl Freq. Band",
                "WiFi Frequency Band"]


@pytest.mark.parametrize("label", NEVER_CHOSEN)
def test_a_setting_whose_choice_connects_pairs_or_drops_a_link_is_looked_at_only(label):
    assert safety.never_choose(label)
    assert "whatever a decision names" in safety.look_refused("enter", "On", label, ["On"])
    assert safety.look_refused("down", "", label, ["On"]) == ""
    if safety.network_refused(label) is None:            # the row as the camera writes it (or a slip of it)
        scope = {"decisions": [{**DECISION, "rows": [label], "options": {label: ["On"]}}]}
        rows, refusals = safety.network_decided(scope)
        assert rows == {label: DAY} and len(refusals) == 1 and "drops the link" in refusals[0], refusals
        assert safety.network_options(scope) == {}


@pytest.mark.parametrize("label", IDENTITY_LOOK)
def test_an_identity_row_opens_to_look_only_where_a_decision_names_it(label):
    assert safety.lift_class(label) == safety.LIFT_IDENTITY
    # without a decision, refused everywhere as before (identity: no allowance at all)
    assert safety.identity_row(label) and safety.never_lifted(label) and "no --allow opens it" in safety.allow_refused(label)
    assert safety.path_refused([label], {label}, allowed=[label]) and live.open_refused(label, {label})
    assert safety.path_refused([label], network={"Bluetooth Function": DAY})          # a decision naming another row
    rows = decided({**DECISION, "rows": [label]})
    assert rows == {label: DAY}
    assert safety.path_refused([label], network=rows) is None and live.open_refused(label, network=rows) == ""
    assert crawl.network_open({"label": label, "never_open": safety.never_open(label)}, rows)
    # choosing: only Wake On LAN of these may have an option named; never the rest, whatever a decision says
    scope = {"decisions": [{**DECISION, "rows": [label], "options": {label: ["On"]}}]}
    if label == "Wake On LAN":
        assert safety.network_options(scope) == {label: ["On"]} and safety.look_refused("enter", "On", label, ["On"]) == ""
    else:
        assert safety.never_choose(label) and safety.network_options(scope) == {}
        assert "drops the link" in safety.network_decided(scope)[1][0]
        assert "whatever a decision names" in safety.look_refused("enter", "On", label, ["On"])


def test_an_identity_rows_screen_gets_menu_alone_on_credentials_a_keyboard_or_a_connection():
    cls = safety.LIFT_IDENTITY
    assert safety.inside_menu_only(cls, "list", "Wired LAN Connect On Off") is None
    assert safety.inside_menu_only(cls, "submenu", "IP Address Setting IP Address 192.0.2.10") is None
    for kind, text in (("unknown", "A B C D E F G Done"), ("fields", "Device Name"), ("notice", "Password"),
                       ("list", "SSID DIRECT-madeup"), ("notice", "Connecting..."), ("notice", "PIN 0000")):
        assert safety.inside_menu_only(cls, kind, text), (kind, text)
    assert safety.inside_menu_only(safety.LIFT_ADDRESS, "list", "anything")
    assert safety.inside_menu_only(safety.LIFT_NETWORK, "list", "Bluetooth Rmt Ctrl On Off") is None
    assert safety.inside_menu_only(safety.LIFT_NETWORK, "notice", "Pairing")


def test_a_page_models_label_is_kept_whole_only_when_it_looks_like_a_label_alone(monkeypatch, tmp_path):
    """runner.known_labels: the definition's labels, and a page model's only where they carry no value read glued on
    (a colon, an address or a number, identity words, a defined label with more after it)."""
    import runner
    from camkit import definitions
    target = tmp_path / "def.json"
    target.write_text(json.dumps({"menu": [{"label": "IP Address Setting"}, {"label": "Edit Device Name"},
                                           {"label": "Wi-Fi Connect"}], "settings": []}), encoding="utf-8")
    monkeypatch.setattr(definitions, "active", lambda required=False: target)
    model = {"p": {"rows": [{"label": x} for x in ("Drive Mode", "IP Address Setting", f"IP Address: {IP}",
                                                    "Edit Device Name ILCE-made-up", "Wi-Fi Connect On",
                                                    "Device Name ILCE", "SSID DIRECT-madeup", "Network Option",
                                                    "Subnet 255.255.255.0", "Bluetooth Function")]}}
    assert runner.known_labels(model) == {"IP Address Setting", "Edit Device Name", "Wi-Fi Connect", "Drive Mode",
                                          "Network Option", "Bluetooth Function"}
    names, hidden = safety.screen_fields(["Edit Device Name ILCE-made-up", "Network Option"], runner.known_labels(model))
    assert names == ["Network Option"] and hidden == 1


def test_screen_fields_keep_whole_row_labels_and_withhold_values():
    names, hidden = safety.screen_fields(["IP Address Setting", "IP Address Setting  Manual", "IP Address", IP,
                                          "Edit Device Name", "ILCE-made-up"], {"IP Address Setting", "Edit Device Name"})
    assert names == ["IP Address Setting", "IP Address", "Edit Device Name"] and hidden == 3


def test_drive_shows_an_identity_rows_screens_as_field_names_and_chooses_nothing(tmp_path, monkeypatch, scope_file,
                                                                                capsys):
    # a made-up submenu of Remote Shoot Function showing an address, to see that no value of it is kept
    row = "Remote Shoot Function"
    lines = [row, "IP Address", IP, "Subnet Mask", "255.255.255.0"]
    pressed, seen, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "down", "enter:."],
                                             (row,), {**DECISION, "rows": [row]},
                                             lines, "submenu", page_lit=row, open_lit="IP Address")
    out = capsys.readouterr().out
    assert pressed == ["menu", "right", "down"] and line["completed"] is False        # Enter: never chosen there
    assert '"lifted_from": "identity or connection row"' in logged
    assert all("text" not in s for s in line["screens"])
    assert line["screens"][0]["fields"] == [row, "IP Address", "Subnet Mask"]
    for where in (out, json.dumps(line), logged):
        assert IP not in where and "255.255" not in where
    # an entry screen inside it (a keyboard, or an address in boxes): read as no known kind, MENU alone
    pressed, _, line, _ = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "down"], (row,),
                                     {**DECISION, "rows": [row]}, ["1", "2", IP, "Done"],
                                     "unknown", page_lit=row, open_lit="1")
    assert pressed == ["menu", "right"] and line["completed"] is False                # a keyboard: MENU alone
    assert IP not in json.dumps(line)


def test_the_walk_opens_a_decided_identity_row_to_look_only():
    cam = RowCamera()
    row = {"label": "Wired LAN Connect", "never_open": safety.never_open("Wired LAN Connect")}
    r = crawl.visit_row(cam, cam.read(), {"page": "Network > Wired LAN"}, 0, row, network={"Wired LAN Connect": DAY})
    assert r.outcome.startswith("network row") and cam.keys == ["right", "menu"]
    cam = RowCamera()
    other = crawl.visit_row(cam, cam.read(), {"page": "x"}, 0, row, network={"Bluetooth Function": DAY})
    assert other.outcome.startswith("skipped") and cam.keys == []


# ---------------------------------------------------------------- D2: a --network run's frames go to local readers only

HOSTED = {"name": "hosted", "url": "https://api.example.com/v1", "model": "m", "api_key_env": "MADE_UP_KEY"}


@pytest.fixture
def built(tmp_path, monkeypatch):
    """camkit.vlm's readers recorded where they are built (vlm.Reader, camkit.claude_reader.ClaudeReader), asking
    nothing: (the names built, write(readers, roles) for private/config.json, the questions asked {name: [frames]})."""
    import camkit
    from camkit import claude_reader, vlm
    names, asked = [], {}

    class Fake:
        def __init__(self, name=None, model="m", **kw):
            names.append(name)
            self.name, self.model = name, model

        def ask(self, image, prompt):
            asked.setdefault(self.name, []).append(image)
            return {"selected": "On", "text": "help", "title": "t", "rows": []}

        answer = ask

        def ping(self):
            pass
    monkeypatch.setattr(vlm, "Reader", Fake)
    monkeypatch.setattr(claude_reader, "ClaudeReader", Fake)
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(camkit, "CONFIG", cfg)

    def write(readers, roles=None):
        cfg.write_text(json.dumps({"readers": readers, **({"roles": roles} if roles else {})}), encoding="utf-8")
    return names, write, asked


def marked(folder: Path, mark: bool = True) -> Path:
    """A run folder, marked as a --network run's (camkit.vlm.LOCAL_MARKER) unless mark is False, with shots/."""
    from camkit import vlm
    (folder / "shots").mkdir(parents=True, exist_ok=True)
    if mark:
        vlm.mark_local_only(folder)
    return folder


def shots(folder: Path, *names):
    for n in names:
        (folder / "shots" / n).write_bytes(n.encode())


def test_a_network_run_marks_its_folder_and_the_mark_sets_local_only(scope_file, tmp_path):
    import runner
    from camkit import vlm
    scope_file(DECISION)
    run = Run("net", root=tmp_path)
    runner.network_decided_or_exit(run)
    assert (run.dir / vlm.LOCAL_MARKER).is_file()
    vlm.forget()
    other = Run("plain", root=tmp_path)
    runner.log_network_decided(other, {"Bluetooth Function": DAY})          # drive.py and prove_run.py log it so
    assert (other.dir / vlm.LOCAL_MARKER).is_file()
    assert vlm.local_only_runs(tmp_path / "nothing-here") == [] and vlm.LOCAL_ONLY is False
    assert vlm.local_only_runs(run.dir / "shots" / "00001_down.png") == [run.dir.resolve()] and vlm.LOCAL_ONLY is True


def test_make_reader_builds_no_reader_that_is_not_local_while_local_only(built, monkeypatch):
    from camkit import vlm
    names, _, _ = built
    for cfg in NOT_LOCAL[:5]:
        assert vlm.make_reader(cfg)                  # without LOCAL_ONLY: built as ever
    names.clear()
    monkeypatch.setattr(vlm, "LOCAL_ONLY", True)
    for cfg in NOT_LOCAL:
        with pytest.raises(vlm.NoReader, match="not a local reader"):
            vlm.make_reader(cfg)
        with pytest.raises(vlm.NoReader):
            vlm.ask_named_reader(cfg, b"a frame", "a question", None)
    assert names == []
    vlm.make_reader(LOCAL)
    assert names == ["local"]
    monkeypatch.setattr(vlm, "HELD", "an address screen is open")
    with pytest.raises(vlm.NoReader, match="no reader is asked"):
        vlm.make_reader(LOCAL)
    assert names == ["local"]


def test_pass1_labels_reads_a_network_runs_frames_with_a_local_reader_only(built, tmp_path, monkeypatch):
    import pass1_labels
    from camkit import vlm
    names, write, asked = built
    rows = [{"label": "Bluetooth Rmt Ctrl", "kind": "list", "frames": ["00002_down.png", "00003_down.png"],
             "network": safety.LIFT_NETWORK},
            {"label": "Wired LAN Connect", "kind": "list", "frames": ["00005_down.png"], "network": safety.LIFT_IDENTITY},
            {"label": "Drive Mode", "kind": "list", "frames": ["00007_down.png"]}]
    read = []

    def frames(paths):
        read.extend(p.name for p in paths)
        return {}, {}
    monkeypatch.setattr(pass1_labels, "read_frames", frames)
    monkeypatch.setattr(pass1_labels, "load", lambda p: SimpleNamespace(image=None))
    monkeypatch.setattr(pass1_labels, "screen", SimpleNamespace(read=lambda f: SimpleNamespace(kind="list", bar=None)))
    for name, mark in (("plain", False), ("net", True)):
        folder = marked(tmp_path / name, mark)
        (folder / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        shots(folder, "00002_down.png", "00003_down.png", "00005_down.png", "00007_down.png")
    monkeypatch.setattr(sys, "argv", ["pass1_labels.py", str(tmp_path / "plain")])
    write([HOSTED, LOCAL], {"second": "hosted"})
    pass1_labels.main()                              # no mark: the configured second reader, as ever
    assert names == ["hosted"] and vlm.LOCAL_ONLY is False
    names.clear()
    read.clear()
    monkeypatch.setattr(sys, "argv", ["pass1_labels.py", str(tmp_path / "net")])
    with pytest.raises(SystemExit, match="not a local reader"):
        pass1_labels.main()
    assert names == [] and read == [] and vlm.LOCAL_ONLY is True        # nothing built, no frame read
    write([HOSTED, LOCAL], {"second": "local"})
    pass1_labels.main()
    assert names == ["local"] and "00005_down.png" not in read
    lines = [json.loads(x) for x in (tmp_path / "net" / "options.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["frame"] for x in lines] == ["00002_down.png", "00003_down.png", "00007_down.png"]
    assert [x.get("network") for x in lines] == [safety.LIFT_NETWORK, safety.LIFT_NETWORK, None]
    assert b"00005_down.png" not in asked.get("local", [])


def test_tiebreak_asks_a_local_third_reader_only_and_never_about_an_identity_row(built, tmp_path, monkeypatch):
    import tiebreak
    from camkit import vlm
    names, write, asked = built
    folder = marked(tmp_path / "net")
    shots(folder, "00002_down.png", "00005_down.png", "00007_down.png")
    recs = [{"frame": f, "path": [p], "index": 0, "kind": "list", "agreed": False, "ocr": "On", "vlm": {"selected": "0n"},
             **({"network": n} if n else {})}
            for f, p, n in (("00002_down.png", "Bluetooth Rmt Ctrl", safety.LIFT_NETWORK),
                            ("00005_down.png", "Wake On LAN", safety.LIFT_IDENTITY), ("00007_down.png", "Drive Mode", None))]
    (folder / "options.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["tiebreak.py", str(folder)])
    write([LOCAL, HOSTED], {"second": "local", "third": "hosted"})
    with pytest.raises(SystemExit, match="not a local reader"):
        tiebreak.main()
    assert names == [] and vlm.LOCAL_ONLY is True and not (folder / "tiebreak.jsonl").exists()
    write([LOCAL, {**LOCAL, "name": "lan", "url": "http://192.168.1.50/v1"}], {"second": "local", "third": "lan"})
    tiebreak.main()
    done = [json.loads(x)["frame"] for x in (folder / "tiebreak.jsonl").read_text(encoding="utf-8").splitlines()]
    assert names == ["lan"] and done == ["00002_down.png", "00007_down.png"]


def test_page_model_asks_a_local_reader_only_about_a_marked_scan(built, tmp_path, monkeypatch):
    import page_model
    names, write, _ = built
    folder = marked(tmp_path / "scan")

    def alive(cfg):
        raise AssertionError("a request went to the reader")
    monkeypatch.setattr(page_model, "alive", alive)
    write([HOSTED, LOCAL], {"second": "hosted"})
    with pytest.raises(SystemExit, match="not a local reader"):
        page_model.vlm_read_pages(folder)
    with pytest.raises(SystemExit, match="not a local reader"):
        page_model.vlm_read_pages(folder, "hosted")
    assert names == []
    (folder / "scan_rekeyed.json").write_text(json.dumps([{"kind": "menu", "page": "p", "frame": "00001_down.png"}]),
                                             encoding="utf-8")
    shots(folder, "00001_down.png")
    monkeypatch.setattr(page_model, "alive", lambda cfg: True)
    page_model.vlm_read_pages(folder, "local")
    assert names == ["local"]


def test_help_reads_builds_local_readers_only_for_a_marked_help_run(built, tmp_path, monkeypatch):
    import help_reads
    names, write, _ = built
    monkeypatch.setattr(help_reads, "RUN", marked(tmp_path / "kit2_help"))
    write([HOSTED, LOCAL])
    help_reads.main()
    assert names == ["local"]
    names.clear()
    write([HOSTED])
    with pytest.raises(SystemExit, match="no local reader"):
        help_reads.main()
    assert names == []


def test_reread_proofs_asks_a_local_reader_only_and_never_about_an_identity_proof(built, tmp_path, monkeypatch):
    from tools import reread_proofs
    names, write, asked = built
    folder = marked(tmp_path / "kit2_pass2")
    shots(folder, "00002_down.png", "00005_down.png")
    proofs = [{"kind": "list", "chosen_frame": "00002_down.png", "path": ["Bluetooth Rmt Ctrl"], "label": "Off",
               "network": safety.LIFT_NETWORK, "changes": []},
              {"kind": "list", "chosen_frame": "00005_down.png", "path": ["Wake On LAN"], "label": "Enable",
               "network": safety.LIFT_IDENTITY, "changes": []}]
    (folder / "proofs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in proofs), encoding="utf-8")
    write([HOSTED, LOCAL], {"second": "hosted"})
    with pytest.raises(SystemExit, match="not a local reader"):
        reread_proofs.main([str(folder)])
    with pytest.raises(SystemExit, match="not a local reader"):
        reread_proofs.main([str(folder), "--reader", "hosted"])
    assert names == []
    reread_proofs.main([str(folder), "--reader", "local"])
    got = [json.loads(x)["frame"] for x in (folder / "readings.jsonl").read_text(encoding="utf-8").splitlines()]
    assert got == ["00002_down.png"] and set(names) == {"local"}


def test_reader_census_asks_local_readers_only_about_marked_runs(built, tmp_path, monkeypatch):
    from tools import reader_census
    from camkit import frames, vlm
    names, write, _ = built
    folder = marked(tmp_path / "TEST-CAM_fw9.99" / "kit2_pass2")
    shots(folder, "00002_down.png", "00005_down.png")
    proofs = [{"kind": "list", "chosen_frame": f, "path": [p], "label": "Off", "shown": "0ff", "network": n}
              for f, p, n in (("00002_down.png", "Bluetooth Rmt Ctrl", safety.LIFT_NETWORK),
                              ("00005_down.png", "Wake On LAN", safety.LIFT_IDENTITY))]
    (folder / "proofs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in proofs), encoding="utf-8")
    write([HOSTED, LOCAL], {"second": "hosted", "third": "local"})
    with pytest.raises(SystemExit, match="no reader named is local"):
        reader_census.main([str(folder), "--questions", "--reader", "hosted", "--minutes", "0",
                            "--cache", str(tmp_path / "answers")])
    assert names == [] and vlm.LOCAL_ONLY is True
    vlm.forget()
    asked = []

    def ask(frame, prompt, timeout):                 # what camkit.reading.ask does: the second reader, by ask_role
        asked.append(frame.path.name)
        with contextlib.suppress(vlm.NoReader):
            vlm.ask_role("second", b"frame", prompt, timeout)
        return SimpleNamespace(answer=None)
    monkeypatch.setattr(reader_census.reading, "ask", ask)          # "0ff" for "Off": a reading the rule doubts
    monkeypatch.setattr(frames, "load", lambda p: SimpleNamespace(path=p))
    assert reader_census.main([str(folder), "--ask", "--cache", str(tmp_path / "answers")]) == 0
    assert vlm.LOCAL_ONLY is True and asked == ["00002_down.png"] and names == []
    assert reader_census.identity_line(proofs[1]) and not reader_census.identity_line(proofs[0])
    assert not reader_census.identity_line({"kind": "list"})


def test_the_crawl_and_the_proofs_write_the_class_a_decision_lifted_the_row_from():
    import crawl_run
    cam = RowCamera()
    row = {"label": "Wired LAN Connect", "never_open": safety.never_open("Wired LAN Connect")}
    r = crawl.visit_row(cam, cam.read(), {"page": "Network > Wired LAN"}, 0, row, network={"Wired LAN Connect": DAY})
    assert r.network == safety.LIFT_IDENTITY and crawl_run.summary(r)["network"] == safety.LIFT_IDENTITY
    other = RowCamera()
    plain = crawl.visit_row(other, other.read(), {"page": "x"}, 0, {"label": "Drive Mode"})
    assert plain.network == "" and "network" not in crawl_run.summary(plain)


# ---------------------------------------------------------------- the look-only session of 2026-11-13: its defects

# a made-up definition in the shapes docs/DATA_CONTRACTS.md gives: a row path that names an option of its row ("Subject
# Pick > Madeup Option > Depth Level", as "Recognition Target > Auto > Car/Train"), and one with its under_option
# ("Profile Pick > PQ1 > Gamma Row", as "Picture Profile > PP1 > Gamma"). "Madeup Option" is also the value the made-up
# camera shows for IP Address Setting
OPTION = "Madeup Option"
MADE_UP_DEFINITION = {
    "menu": [{"tab": "Network", "group": "Wired LAN", "label": "IP Address Setting"},
             {"tab": "Network", "group": "Wired LAN", "label": "Display Wired LAN Info."},
             {"tab": "Network", "group": "FTP Transfer", "label": "FTP Transfer Func."},
             {"tab": "Focus", "group": "Subject", "label": "Subject Pick"}],
    "settings": [{"name": "Subject Pick", "row": ["Subject Pick"], "values": [[0, OPTION], [1, "Other Choice"]]},
                 {"name": "Depth", "row": ["Subject Pick", OPTION, "Depth Level"], "values": [[0, "1"], [1, "2"]]},
                 {"name": "Gamma", "row": ["Profile Pick", "PQ1", "Gamma Row"], "under_option": "PQ1", "values": []},
                 # a value that is also a field name an address screen shows (safety.ADDRESS_FIELDS)
                 {"name": "Target", "row": ["Transfer Target"], "values": [[0, "Server"], [1, "Phone"]]},
                 {"name": "Unplaced", "values": [[0, "IP Address Setting"]]}]}     # a My Menu item's shape: on no row


@pytest.fixture
def made_up_definition(tmp_path, monkeypatch):
    """The camera's definition is MADE_UP_DEFINITION (camkit.definitions.active)."""
    from camkit import definitions
    target = tmp_path / "made_up_definition.json"
    target.write_text(json.dumps(MADE_UP_DEFINITION), encoding="utf-8")
    monkeypatch.setattr(definitions, "active", lambda required=False: target)
    return target


def test_the_known_labels_are_row_labels_never_an_option_or_a_value(made_up_definition):
    """runner.row_labels leaves out an option a row path names (the row's own setting's value names, or the setting's
    under_option); runner.known_values holds every value name of a setting placed on a row and the page model's value
    column; runner.known_labels holds none of those."""
    import runner
    doc = json.loads(made_up_definition.read_text(encoding="utf-8"))
    assert runner.row_labels(doc) == {"IP Address Setting", "Display Wired LAN Info.", "FTP Transfer Func.",
                                      "Subject Pick", "Depth Level", "Profile Pick", "Gamma Row", "Transfer Target"}
    model = {"p": {"breadcrumb": "Network > Wired LAN",
                   "rows": [{"label": "IP Address Setting", "value": "Automatic",
                             "readings": {"label": {}, "value": {"vlm": "Automatic", "ocr": "Autornatic"}}},
                            {"label": "Wake Up Row", "value": None},
                            {"label": "Other Choice", "value": None},           # a row label read that is a value
                            {"label": "Wake Up Row", "value": "Depth Level"}]}}  # and a value that is a row label
    told = runner.known_values(model)
    assert {OPTION, "Other Choice", "1", "2", "PQ1", "Automatic", "Autornatic", "Depth Level"} <= told
    assert "IP Address Setting" not in told                    # a value of a setting on no row only
    labels = runner.known_labels(model)
    assert OPTION not in labels and "PQ1" not in labels and "Automatic" not in labels
    assert "Other Choice" not in labels and "Depth Level" not in labels      # a value, though some path's row label
    assert {"IP Address Setting", "Gamma Row", "Wake Up Row"} <= labels
    assert runner.known_groups(model) == {"Wired LAN", "FTP Transfer", "Subject"}


def test_screen_fields_never_keep_a_known_value_even_one_named_a_label():
    names, hidden = safety.screen_fields([OPTION, "IP Address Setting", "IP Address", IP],
                                         labels={OPTION, "IP Address Setting"}, values={OPTION})
    assert names == ["IP Address Setting", "IP Address"] and hidden == 2
    assert safety.address_fields(["Automatic", "IP Address", IP], values={"automatic"}) == (["IP Address"], 2)
    assert safety.address_fields(["IP Address"], values={"IP Address"}) == ([], 1)      # failing closed


@pytest.mark.parametrize("where", ["address screen", "page after MENU"])
def test_drive_keeps_no_value_named_as_an_option_on_an_address_screen_or_the_page_after_menu(
        tmp_path, monkeypatch, scope_file, made_up_definition, capsys, where):
    """The leak of 2026-11-13, with made-up names: the value the camera shows for IP Address Setting is a word a row
    path of the definition names as an option. On Display Wired LAN Info. and on the Wired LAN page after MENU, what is
    printed, drive.jsonl and the run's events keep the row labels and field names, never that word; nor "Server", a value
    of Transfer Target that is also a field name an address screen shows (drive passes the known values to
    safety.screen_fields)."""
    page = ["Wired LAN", "IP Address Setting", OPTION, "Display Wired LAN Info.", "Server"]
    info = ["Display Wired LAN Info.", "IP Address", IP, OPTION, "Server"]
    pressed, _, line, logged = drive_fake(
        tmp_path, monkeypatch, scope_file, ["right", "menu"], ("Display Wired LAN Info.",),
        {**DECISION, "rows": ["Display Wired LAN Info."]}, info if where == "address screen" else ["IP Address", IP],
        "unknown", page_lit="Display Wired LAN Info.", open_lit="", page_kind="menu",
        page_lines=page if where == "page after MENU" else ["Wired LAN", "Display Wired LAN Info."])
    out = capsys.readouterr().out
    assert pressed == ["menu", "right", "menu"] and line["completed"] is True
    assert all("text" not in s for s in line["screens"])
    fields = [f for s in line["screens"] for f in s["fields"]]
    assert "IP Address" in fields and "Display Wired LAN Info." in fields
    if where == "page after MENU":
        assert "IP Address Setting" in fields                   # a row label: kept
    assert "Server" not in fields
    for said in (out, json.dumps(line), logged):
        assert OPTION not in said and IP not in said


def test_a_page_models_label_with_a_value_glued_on_is_no_label(tmp_path, monkeypatch):
    """runner.label_alone: a row's label read with one of its known values glued on, with a space or none, an icon's
    letter or two before it or not, is no label alone ("Wi-Fi ConnectOn", "GAirplane Mode On"), whether the row's
    label is the definition's or one the page model read; a longer label that only starts like one is kept."""
    import runner
    from camkit import definitions
    target = tmp_path / "def.json"
    target.write_text(json.dumps({"menu": [{"label": "Airplane Mode"}, {"label": "Wi-Fi Connect"}], "settings": []}),
                      encoding="utf-8")
    monkeypatch.setattr(definitions, "active", lambda required=False: target)
    glued = ["Wi-Fi ConnectOn", "Wi-Fi ConnectOff", "GAirplane Mode On", "G Airplane Mode Off", "AirPlane ModeOn",
             "SBluetooth FunctionOn"]
    model = {"p": {"rows": [{"label": "Airplane Mode", "value": "On", "readings": {"value": {"vlm": "Off"}}},
                            {"label": "Wi-Fi Connect", "value": "Off", "readings": {"value": {"vlm": "On"}}},
                            {"label": "Bluetooth Function", "value": "On"}, {"label": "Wi-Fi Connection Info"},
                            *({"label": x} for x in glued)]}}
    labels = runner.known_labels(model)
    assert not set(glued) & labels, set(glued) & labels
    assert {"Airplane Mode", "Wi-Fi Connect", "Bluetooth Function", "Wi-Fi Connection Info"} <= labels
    names, hidden = safety.screen_fields(["Wi-Fi ConnectOn", "Airplane Mode"], labels, runner.known_values(model))
    assert names == ["Airplane Mode"] and hidden == 1


def read_on(group, *texts) -> list:
    """runner.network_readings' entries for one page-model row: every reading of it, on a page of `group`."""
    return [{"group": group, "readings": list(texts)}]


# The page icon glued on was first seen on the a1 II's IP Address Setting ("LANIP Address Setting", 2026-11-13), which no
# decision opens since 2026-11-14 (its opening dropped the link): Wired LAN Connect, a row of the same page that a
# decision opens, stands in for it in the tests below
def test_a_row_read_with_its_icon_glued_on_lifts_only_where_another_reader_read_the_row():
    """The Wired LAN page's icon read as letters glued to the label ("LANWired LAN Connect"): the lift takes it for
    Wired LAN Connect only where the page model keeps, for the same row, a reading that is the row exactly, every
    reading of it is of the row's class, and what the reading adds is a word of the page's own group name, glued on, of
    at most safety.ICON_MAX letters (safety.lifted_readings, glued_icon)."""
    rows = decided({**DECISION, "rows": ["Wired LAN Connect"]})
    values = {"Wired LAN Connect": ["On", "Off"]}
    two = {"Wired LAN Connect": read_on("Wired LAN", "LANWired LAN Connect", "LAN Wired LAN Connect",
                                         "Wired LAN Connect")}
    lift = lambda lit, readings: safety.network_lifted_row(lit, rows, values=values, readings=readings)  # noqa: E731
    assert lift("LANWired LAN Connect", two) == "Wired LAN Connect"
    assert lift("LANWired LAN Connect  On", two) == "Wired LAN Connect"
    assert lift("LANWired LAN Connect  Elsewhere", two) is None                   # no value of its own
    assert lift("LANWired LAN Connect", None) is None                              # no second reading
    assert lift("LAN Wired LAN Connect", two) is None                              # a word in front: no icon
    assert lift("LANWired LAN Connect", {"Wired LAN Connect": [["LANWired LAN Connect", "Wired LAN Connect"]]}) \
        is None                                                                     # no page group known
    assert lift("LANWired LAN Connect", {"Wired LAN Connect": read_on("Wi-Fi", "LANWired LAN Connect",
                                                                        "Wired LAN Connect")}) is None   # not its group
    assert lift("LANWired LAN Connect", {"Wired LAN Connect": read_on("Wired LAN", "LANWired LAN Connect",
                                                                        "Wired LAN Conect")}) is None  # differs
    assert lift("LANWired LAN Connect", {"Wired LAN Connect": read_on(
        "Wired LAN", "LANWired LAN Connect", "Wired LAN Connect", "Wired LAN Connect Password")}) is None   # credentials
    assert lift("LANWired LAN Connect", {"Wired LAN Connect": read_on(
        "Wired LAN", "LANWired LAN Connect", "Wired LAN Connect", "Wired LAN Connect Reset")}) is None  # an action
    assert lift("WiredWired LAN Connect", {"Wired LAN Connect": read_on(
        "Wired LAN", "WiredWired LAN Connect", "Wired LAN Connect")}) is None      # a word of 5 letters: no icon
    assert lift("LANWired LAN Connecl", {"Wired LAN Connect": read_on(
        "Wired LAN", "LANWired LAN Connecl", "Wired LAN Connect")}) is None        # not the row itself after the icon
    for lit in ("LAN Access Point Set.", "LANAccess Point Set."):
        assert lift(lit, {"Wired LAN Connect": read_on("Wired LAN", lit, "Wired LAN Connect")}) is None
    # nothing else of the lift moves: the row itself, and its value, as before
    assert lift("Wired LAN Connect  Off", None) == "Wired LAN Connect"


@pytest.mark.parametrize("lit,row,group", [
    ("WPSWired LAN Connect", "Wired LAN Connect", "Wired LAN"), ("PWWi-Fi Connect", "Wi-Fi Connect", "Wi-Fi"),
    ("NoWi-Fi Connect", "Wi-Fi Connect", "Wi-Fi"), ("DelBluetooth Function", "Bluetooth Function", "Bluetooth"),
    ("PinManage Paired Device", "Manage Paired Device", "Bluetooth"),
    ("OffAirplane Mode", "Airplane Mode", "Network Option"),
    # the same words where the page's group held them: never_open or identity_screen refuses them alone
    ("WPSWired LAN Connect", "Wired LAN Connect", "WPS Wired LAN"), ("PWWi-Fi Connect", "Wi-Fi Connect", "PW Wi-Fi"),
    ("PinManage Paired Device", "Manage Paired Device", "Pin Bluetooth"),
    ("CopyWi-Fi Connect", "Wi-Fi Connect", "Copy Wi-Fi"),        # an action's name: never_open alone names it
])
def test_a_word_glued_on_is_no_icon_unless_it_is_the_pages_group_and_harmless(lit, row, group):
    """What the review of 2026-11-14 found lifting: a real word glued on (WPS, PW, No, Del, Pin, Off), whose
    word-boundary patterns never fire on glued text. Each is refused: no word of the row's page's group, or one that
    never_open or identity_screen names alone."""
    rows = decided({**DECISION, "rows": [row]})
    assert safety.network_lifted_row(lit, rows, values=VALUES, readings={row: read_on(group, lit, row)}) is None
    assert safety.glued_icon(lit[:-len(row)], row, group)


def test_an_icon_that_sets_the_row_in_another_class_is_no_icon():
    """glued_icon: the label read with the glued word set apart must keep the row's class. A made-up row of the Wi-Fi
    class whose glued word "USB" would read, set apart, as USB Power (an identity row): no icon, though "USB" names
    nothing alone and is a word of the made-up group."""
    row = "Power Supply Wi-Fi Connect"
    assert safety.lift_class(row) == safety.LIFT_NETWORK and not safety.never_open("usb")
    assert safety.identity_screen("usb") is None and "class" in safety.glued_icon("USB", row, "USB Wi-Fi")
    assert safety.lifted_readings(row, {row: read_on("USB Wi-Fi", "USBPower Supply Wi-Fi Connect", row)}) == {
        safety.plain(row)}
    assert safety.glued_icon("lan", "IP Address Setting", "Wired LAN") is None


def test_a_row_opened_through_its_icon_glued_on_is_left_on_its_page_and_the_next_row_opens(tmp_path, monkeypatch):
    """The lock ends where the page the row was opened from is back with its bar on the row as the reading with its
    icon glued on that opened it ("LANWired LAN Connect" still reads so after MENU: safety.bar_on_row); then the next
    row opens. Without that reading kept, the lock stayed and the crawl stopped at the next Right (the review of
    2026-11-14)."""
    rows = decided({**DECISION, "rows": ["Wired LAN Connect"]})
    readings = {"Wired LAN Connect": read_on("Wired LAN", "LANWired LAN Connect", "Wired LAN Connect")}
    cam = camera(tmp_path, rows, values={"Wired LAN Connect": ["On"]}, page="menu")
    cam.readings = readings
    cam.hdmi = InsideCamera(tmp_path, monkeypatch, "list", "On Off", "inside")
    cam.presses, cam._seen = 0, cam._moves()
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    lit_on(monkeypatch, "LANWired LAN Connect  On")
    cam.press("right")
    assert cam.network_open["row"] == "Wired LAN Connect"
    cam.hdmi.shows("menu", PAGE)                     # MENU: the page, its bar on the glued reading
    cam.press("menu")
    assert cam.network_open is None and events(cam)[-1]["kind"] == "network_row_left"
    cam.press("right")                               # the next row (here the same) opens as ever
    assert cam.link.sent == ["right", "menu", "right"] and cam.network_open is not None
    assert safety.bar_on_row("LANWired LAN Connect  On", "Wired LAN Connect", readings)
    assert not safety.bar_on_row("LANWired LAN Connect  On", "Wired LAN Connect")
    assert not safety.bar_on_row("On", "Wired LAN Connect", readings)


def test_drive_leaves_a_row_opened_through_its_icon_glued_on_and_opens_the_next(tmp_path, monkeypatch, scope_file):
    """drive.py on its own: Right on "LANWired LAN Connect" (the page model's row holds "Wired LAN Connect" too, on
    the Wired LAN page), MENU back to the page with that bar, Right again: the lock had ended."""
    model = {"p": {"breadcrumb": "Network > Wired LAN", "rows": [
        {"label": "LANWired LAN Connect", "readings": {"label": {"ocr": "LANWired LAN Connect",
                                                                  "vlm": "Wired LAN Connect"}}}]}}
    pressed, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "menu", "right"],
                                          ("Wired LAN Connect",), {**DECISION, "rows": ["Wired LAN Connect"]},
                                          ["On", "Off"], "list", page_lit="LANWired LAN Connect",
                                          open_lit="On", page_kind="menu", model=model)
    assert pressed == ["menu", "right", "menu", "right"] and line["completed"] is True
    assert logged.count('"network_row_opened"') == 2 and '"network_row_left"' in logged


def test_the_runners_give_the_page_models_readings_and_values_to_the_lift(tmp_path, monkeypatch):
    import runner
    row = {"label": "LANWired LAN Connect", "value": "On",
           "readings": {"label": {"ocr": "LANWired LAN Connect", "ocr2": "LAN Wired LAN Connect",
                                  "vlm": "Wired LAN Connect"}, "value": {"vlm": "On"}},
           "never_open": safety.never_open("LANWired LAN Connect")}
    model = {"p": {"breadcrumb": "Network > Wired LAN", "rows": [row, {"label": "IP Address Setting", "value": "Automatic"}]}}
    decided_rows = {"Wired LAN Connect": DAY}
    readings = runner.network_readings(decided_rows, model)
    assert readings == {"Wired LAN Connect": read_on("Wired LAN", "LANWired LAN Connect", "LANWired LAN Connect",
                                                      "LAN Wired LAN Connect", "Wired LAN Connect")}
    values = runner.network_values(decided_rows, model)
    assert values == {"Wired LAN Connect": ["On"]}
    # the camera's own press check opens it, and the walk takes the page model's row
    monkeypatch.setattr(live, "lit_text", lambda image, path: "LANWired LAN Connect  On")
    cam = camera(tmp_path, decided_rows, values=values, page="menu")
    cam.readings = readings
    with pytest.raises(RuntimeError, match="sent"):
        cam.press("right")
    assert cam.link.sent == ["right"] and cam.network_open["row"] == "Wired LAN Connect"
    cam = camera(tmp_path, decided_rows, values=values, page="menu")                 # no readings: refused
    with pytest.raises(safety.Refused, match="never opened"):
        cam.press("right")
    assert crawl.network_open(row, decided_rows, "Wired LAN")
    assert not crawl.network_open(row, decided_rows)                              # no page group: no icon
    assert not crawl.network_open({**row, "readings": {"label": {"ocr": "LANWired LAN Connect"}}}, decided_rows,
                                  "Wired LAN")
    # the walk takes the group off the page's breadcrumb
    cam = RowCamera()
    r = crawl.visit_row(cam, cam.read(), model["p"], 0, row, network=decided_rows)
    assert r.network == safety.LIFT_IDENTITY and cam.keys == ["right", "menu"]


def test_a_group_one_letter_from_a_never_open_one_is_refused_before_any_press():
    """safety.group_refused: the page model's "FTP Transter" is "FTP Transfer" (an action) but for one letter; a group
    name one letter from a never-open group name the kit knows (known) is refused too; the real group names are not."""
    assert safety.never_open("FTP Transter") is None
    assert "ftp transfer" in safety.group_refused("FTP Transter") and "one letter" in safety.group_refused("FTP Transter")
    assert safety.group_refused("FTP Transfer") == safety.never_open("FTP Transfer")
    assert safety.group_refused("FTP Transfr")                                      # a letter dropped
    assert safety.group_refused("Streamlng") is None and safety.group_refused("Streamlng", ["Streaming"])
    for name in ("Wired LAN", "Wi-Fi", "Bluetooth", "Network Option", "Cnct./Remote Sht.", "File", "Edit", "Media",
                 "Shooting Mode", "Image Quality/Rec", "Setup Option", "Touch Operation", "Zoom", "Flash"):
        assert safety.group_refused(name, ["Streaming", "FTP Transfer", "Accessibility", "Delete"]) is None, name
    # only a name of safety.GROUP_MIN letters and digits or more is compared one letter apart
    assert safety.GROUP_MIN == 5
    assert safety.group_refused("Sent") is None                                     # "send" but for a letter: short
    assert safety.group_refused("Delet")                                            # five letters, "delete" less one
    # the one-letter comparison is made on every reading, its slips undone: "Forrnal" is "formal", "format" less one
    assert safety.never_open("Forrnal") is None and "format" in safety.group_refused("Forrnal")


class ColumnCamera:
    """One tab of a menu (Network), each of its groups one page of `rows` rows, as the tab column, the group column and
    the rows show it: Left from the rows goes to the group column, Left again to the tab column, Right back; Up and Down
    in the group column light another group (ignored, `stuck`, or two groups at once, `skip`, for the keys named), Right
    there steps into the lit group's first row; Down and Up in the rows step a row (onto the next group's page at a
    page's end, the last group's onto the first's). The lit bar in the group column reads the group's name as the camera
    draws it (`drawn`); after a key named in `misfocus` the screen reads as the rows (focus "rows") though the cursor is
    in the group column, its lit bar reading `misfocus[key]`. Every Right in the group column is kept with what it lit."""
    def __init__(self, drawn, at=0, stuck=(), rows=2, skip=(), misfocus=None):
        self.drawn, self.focus, self.group, self.row, self.keys, self.rights = drawn, "groups", at, 0, [], []
        self.stuck, self.skip, self.misfocus, self.misread = list(stuck), list(skip), dict(misfocus or {}), None
        self.may_open, self.rows = frozenset(), rows
        self.frame = SimpleNamespace(image=None, path=Path("00001_menu.png"))

    def press(self, key):
        self.keys.append(key)
        self.misread = self.misfocus.pop(key, None)
        if self.focus == "tabs":
            if key == "right":
                self.focus = "groups"
        elif self.focus == "groups":
            if key in self.stuck:
                self.stuck.remove(key)
            elif key in ("up", "down"):
                step = 2 if key in self.skip else 1
                self.skip = [k for k in self.skip if k != key]
                self.group = max(0, min(len(self.drawn) - 1, self.group + (step if key == "down" else -step)))
            elif key == "right":
                self.rights.append(self.drawn[self.group])
                self.focus, self.row = "rows", 0
            elif key == "left":
                self.focus = "tabs"
        elif key == "left":
            self.focus = "groups"
        elif key in ("up", "down"):
            at = self.group * self.rows + self.row + (1 if key == "down" else -1)
            self.group, self.row = divmod(at % (self.rows * len(self.drawn)), self.rows)

    def read(self):
        focus = "rows" if self.misread is not None else self.focus
        return SimpleNamespace(kind="menu", focus=focus, where=(focus, self.group, self.row))

    def lit(self):
        if self.misread is not None:
            return self.misread
        return self.drawn[self.group] if self.focus == "groups" else f"{self.drawn[self.group]} row {self.row}"


def columns(monkeypatch, scanned, drawn, at=0, stuck=(), rows=2, skip=(), misfocus=None):
    """A ColumnCamera, and the page scan's cycle and page model of its tab as the scan read the group names
    (`scanned`), crawl_run's seams faked on it."""
    import crawl_run
    cam = ColumnCamera(drawn, at, stuck, rows, skip, misfocus)
    cycle = [{"kind": "menu", "page": f"p{g}", "row": r,
              "screen": SimpleNamespace(kind="menu", focus="rows", where=("rows", g, r))}
             for g in range(len(scanned)) for r in range(rows)]
    model = {f"p{g}": {"breadcrumb": f"Network > {n}", "rows": [{"label": f"{n} row {r}"} for r in range(rows)]}
             for g, n in enumerate(scanned)}
    monkeypatch.setattr(crawl_run, "same_position", lambda a, b: a.where == b.where)
    monkeypatch.setattr(crawl_run, "lit_text", lambda image, path: cam.lit())
    monkeypatch.setattr(crawl_run, "menu_text", lambda c: "Network 7/9")
    return cam, cycle, model


def test_from_the_group_column_navigation_steps_into_a_group_it_may_enter(monkeypatch):
    """The menu reopens with the cursor in the group column on the group a jump was refused on ("FTP Transfer", which
    the scan read as "FTP Transter"): find_position goes Up to the nearest group it may enter and Right there, never on
    the refused one, and go_to goes on by the scan to a row on another page."""
    import crawl_run
    scanned = ["Wi-Fi", "FTP Transter", "Wired LAN"]
    cam, cycle, model = columns(monkeypatch, scanned, ["Wi-Fi", "FTP Transfer", "Wired LAN"], at=1)
    j = crawl_run.find_position(cam, cycle, model)
    assert j == 0 and cam.keys == ["up", "right"] and cam.rights == ["Wi-Fi"]
    assert crawl_run.go_to(cam, cycle, model, j, "Wired LAN row 0") == 4
    assert cam.rights == ["Wi-Fi"] and len(cam.keys) == 4 and set(cam.keys[2:]) <= {"up", "down"}
    # the menu reopens in the column on a group it may enter: Right at once
    cam, cycle, model = columns(monkeypatch, scanned, ["Wi-Fi", "FTP Transfer", "Wired LAN"], at=2)
    assert crawl_run.find_position(cam, cycle, model) == 4 and cam.keys == ["right"]


def test_from_the_group_column_nothing_is_pressed_where_every_group_is_refused(monkeypatch):
    """Every group of the tab is one the column never enters: find_position presses nothing (the caller's MENU closes
    the menu); and where the Up meant for a group it may enter is not taken, so the refused group is still lit, no
    Right goes out."""
    import crawl_run
    refused = ["FTP Transter", "Creators' Cloud", "Streaming"]
    cam, cycle, model = columns(monkeypatch, refused, ["FTP Transfer", "Creators' Cloud", "Streaming"], at=0)
    assert crawl_run.find_position(cam, cycle, model) is None and cam.keys == [] and cam.focus == "groups"
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "FTP Transter"], ["Wi-Fi", "FTP Transfer"], at=1, stuck=["up"])
    assert crawl_run.find_position(cam, cycle, model) is None and cam.keys == ["up"] and cam.rights == []


def test_from_the_group_column_the_lit_group_and_the_focus_are_judged_before_the_right(monkeypatch):
    """from_groups sends its Right only where the lit bar, read just before it, names the very group it went to (judged
    whole: group_near) and no group the column never enters (safety.group_refused, on the page model's name and on the
    bar as read), and the screen still reads as the group column."""
    import crawl_run
    # the page model's name ("Creators' Clond") passes, the bar read there ("Creators' Cloud") does not: no Right
    cam, cycle, model = columns(monkeypatch, ["FTP Transter", "Creators' Clond"], ["FTP Transfer", "Creators' Cloud"])
    assert crawl_run.find_position(cam, cycle, model) is None and cam.keys == ["down"] and cam.rights == []
    # the same where the menu reopened on that group: it is stepped off, not entered
    cam, cycle, model = columns(monkeypatch, ["Creators' Clond", "Wi-Fi"], ["Creators' Cloud", "Wi-Fi"])
    assert crawl_run.find_position(cam, cycle, model) == 2 and cam.keys == ["down", "right"] and cam.rights == ["Wi-Fi"]
    # an Up that moved two groups lands on another group than the one meant, harmless or not: no Right
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "Bluetooth", "FTP Transter"], ["Wi-Fi", "Bluetooth", "FTP Transfer"],
                                at=2, skip=["up"])
    assert crawl_run.find_position(cam, cycle, model) is None and cam.keys == ["up"] and cam.rights == []
    # after the Up the screen reads as a page of rows: no Right, whatever its bar reads
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "FTP Transter"], ["Wi-Fi", "FTP Transfer"], at=1,
                                misfocus={"up": "Wi-Fi"})
    assert crawl_run.find_position(cam, cycle, model) is None and cam.keys == ["up"] and cam.rights == []
    # the focus read as the group column on a page of rows: the lit row's text names no group ("File Format  RAW" is no
    # "File"), so nothing is pressed
    cam, cycle, model = columns(monkeypatch, ["File", "Media"], ["File Format  RAW", "Media"])
    assert crawl_run.find_position(cam, cycle, model) is None and cam.keys == []


def test_a_lit_group_is_named_whole_and_by_one_group_only():
    import crawl_run
    names = ["File", "Media Option", "FTP Transter"]
    assert crawl_run.group_near("File", names) == 0 and crawl_run.group_near("File Format  RAW", names) is None
    assert crawl_run.group_near("FTP Transfer", names) == 2 and crawl_run.group_near("DFTP Transfer", names) is None
    assert crawl_run.group_near("Media Optlon", names) == 1
    assert crawl_run.group_near("Fil", names) is None                         # one letter off a short name: none
    assert crawl_run.group_near("Media Optin", ["Media Option", "Media Opton"]) is None     # two groups: none


def test_jump_sends_no_right_where_the_lit_group_reads_as_one_never_entered(monkeypatch):
    """crawl_run.jump: its last Right goes out only where the lit group, as read there, is no group the column never
    enters (group_closed), whatever the page model read ("Creators' Clond" for "Creators' Cloud")."""
    import crawl_run
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "Creators' Clond"], ["Wi-Fi", "Creators' Cloud"])
    cam.focus = "rows"
    assert crawl_run.jump(cam, cycle, crawl_run.page_groups(cycle, model), 2, model) is None
    assert cam.keys == ["left", "left", "right", "down"] and cam.rights == []
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "Bluetooth"], ["Wi-Fi", "Bluetooth"])
    cam.focus = "rows"
    assert crawl_run.jump(cam, cycle, crawl_run.page_groups(cycle, model), 2, model) == 2 and cam.rights == ["Bluetooth"]


def test_a_network_runs_navigation_prints_no_text_it_read(monkeypatch, capsys):
    """On a --network run (the camera given a decision's rows) from_groups and jump print the length of what they read
    off the screen, never the text, which may hold a device's name or an address."""
    import crawl_run
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "Bluetooth"], [f"ILCE-made-up {IP}", "Bluetooth"])
    cam.network = {"Bluetooth Function": DAY}
    assert crawl_run.find_position(cam, cycle, model) is None
    out = capsys.readouterr().out
    assert "withheld" in out and IP not in out and "ILCE-made-up" not in out
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "Bluetooth"], ["Wi-Fi", "FTP Transfr"])
    cam.focus, cam.network = "rows", {"Bluetooth Function": DAY}
    assert crawl_run.jump(cam, cycle, crawl_run.page_groups(cycle, model), 2, model) is None and cam.rights == []
    out = capsys.readouterr().out
    assert "withheld" in out and "FTP Transfr" not in out
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "Bluetooth"], [f"ILCE-made-up {IP}", "Bluetooth"])
    assert crawl_run.find_position(cam, cycle, model) is None
    assert "ILCE-made-up" in capsys.readouterr().out                        # without --network, as ever


def test_go_to_walks_rather_than_jump_into_a_group_read_one_letter_off(monkeypatch):
    """go_to's jump by the columns is refused before any press when the target's group, as the scan read it, is one
    letter from a never-open name: the rows are walked to, Down by Down."""
    import crawl_run
    scanned = ["Wi-Fi", "Bluetooth", "FTP Transter", "Wired LAN"]
    cam, cycle, model = columns(monkeypatch, scanned, scanned, at=0, rows=6)
    cam.focus = "rows"
    monkeypatch.setattr(crawl_run, "jump", lambda *a, **k: pytest.fail("jumped by the columns"))
    assert crawl_run.go_to(cam, cycle, model, 0, "FTP Transter row 1") == 13
    assert cam.keys == ["up"] * 11 and cam.rights == []
    # the same walk to a group it may jump into goes by the columns (jump), as ever
    jumped = []
    monkeypatch.setattr(crawl_run, "jump", lambda cam, cycle, groups, target, model: jumped.append(target) or target)
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "Bluetooth", "Network Option", "Wired LAN"],
                                ["Wi-Fi", "Bluetooth", "Network Option", "Wired LAN"], at=0, rows=6)
    cam.focus = "rows"
    assert crawl_run.go_to(cam, cycle, model, 0, "Network Option row 1") == 13 and jumped == [13] and cam.keys == []


def test_a_rows_own_screen_read_as_the_shooting_screen_keeps_menu_alone(tmp_path, monkeypatch):
    """Right on Manage Paired Device opens what reads as the shooting screen: no MENU has gone out, so it is the row's
    own screen misread. It is judged as no known kind (MENU alone, no reader); a MENU after which the same screen still
    reads so leaves nothing; one after which another frame reads as the shooting screen ends the row only when the
    camera's own picture says so too (live.osd_kind)."""
    from camkit import vlm
    cam = inside_camera(tmp_path, monkeypatch, kind="shooting", where="inside", row="Manage Paired Device",
                        lit="Manage Paired Device", words="Manage Paired Device Made-up Phone")
    assert cam.network_open["suspect"] is not None and cam.identity_open and vlm.HELD
    assert [e["kind"] for e in events(cam)][-2:] == ["shooting_inside", "identity_screen"]
    with pytest.raises(safety.Refused, match="no key but MENU"):
        cam.press("down")
    monkeypatch.setattr(live.screen, "same_state", lambda a, b: a.where == b.where and a.kind == b.kind)
    monkeypatch.setattr(live, "osd_kind", lambda link: "shooting")
    cam.press("menu")                                    # the same screen, still read as the shooting screen
    assert cam.network_open is not None and cam.identity_open
    cam.hdmi.shows("shooting", "shooting")
    monkeypatch.setattr(live, "osd_kind", lambda link: "")
    cam.press("menu")                                    # another frame, but the camera's own picture cannot say
    assert cam.network_open is not None
    monkeypatch.setattr(live, "osd_kind", lambda link: "shooting")
    cam.press("menu")
    assert cam.network_open is None and cam.identity_open is None and vlm.HELD is None
    assert cam.link.sent == ["right", "menu", "menu", "menu"]


def test_a_shooting_screen_after_a_menu_inside_a_row_whose_screen_read_right_ends_it_as_before(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "osd_kind", lambda link: pytest.fail("the camera's own picture asked"))
    cam = inside_camera(tmp_path, monkeypatch, **WIRED)
    assert cam.network_open.get("suspect") is None and cam.identity_open is None
    cam.hdmi.shows("shooting", "shooting")
    cam.press("menu")
    assert cam.network_open is None


def test_drive_sends_menu_alone_on_a_rows_screen_read_as_the_shooting_screen(tmp_path, monkeypatch, scope_file, capsys):
    """drive.py on its own: Right on Manage Paired Device opens what reads as the shooting screen. Down is refused (MENU
    alone), and a MENU the camera ignores, the screen still read so, leaves nothing, whatever the camera's own picture
    reads."""
    import drive as D
    paired = {"path": ("Manage Paired Device",), "decision": {**DECISION, "rows": ["Manage Paired Device"]},
              "open_lines": ["Manage Paired Device", "Made-up Phone"], "open_kind": "shooting",
              "page_lit": "Manage Paired Device", "open_lit": "", "page_kind": "menu"}
    pressed, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "down"], **paired)
    out = capsys.readouterr().out
    assert pressed == ["menu", "right"] and line["completed"] is False and "no key but MENU" in out
    assert '"shooting_inside"' in logged and "Made-up Phone" not in out + json.dumps(line)
    pressed, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "menu", "down"], **paired,
                                          menu_does="ignored", own="shooting")
    assert pressed == ["menu", "right", "menu"] and line["completed"] is False
    assert '"network_row_left"' not in logged
    page, suspect = SimpleNamespace(kind="menu", where=PAGE), SimpleNamespace(kind="shooting", where="inside")
    real = SimpleNamespace(kind="shooting", where="shooting")
    monkeypatch.setattr(D, "same_state", lambda a, b: a.where == b.where)
    row = "Manage Paired Device"
    assert D.network_left(real, page, True, "", row) is True                         # no suspect: as before
    assert D.network_left(real, page, True, "", row, suspect, lambda: "shooting") is True
    assert D.network_left(real, page, True, "", row, suspect, lambda: "") is False
    assert D.network_left(real, page, True, "", row, suspect, None) is False
    assert D.network_left(suspect, page, True, "", row, suspect, lambda: "shooting") is False


def test_drive_marks_a_rows_screen_read_as_the_shooting_screen_at_the_wait_too(tmp_path, monkeypatch, scope_file):
    """A camera slow to draw: the frame after Right on Bluetooth Function still shows the page, and the frame read after
    the wait reads as the shooting screen, the row still open. That screen is the row's own, misread: kept as its field
    names alone, never its text (a Wi-Fi or Bluetooth setting's own screen read as the shooting screen would otherwise
    be shown whole)."""
    pressed, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right"], ("Bluetooth Function",), RMT,
                                          ["Bluetooth Function", "On", "Off"], "shooting",
                                          page_lit="Bluetooth Function  On", open_lit="", slow=True)
    assert pressed == ["menu", "right"] and line["completed"] is True
    wait = line["screens"][-1]
    assert wait["after"] == "wait" and wait["kind"] == "shooting" and "text" not in wait and "fields" in wait
    assert '"shooting_inside"' in logged and '"key": "wait"' in logged


def test_a_screen_of_no_known_kind_inside_any_lifted_row_gets_menu_alone_and_field_names():
    """No kind "info" is added (the information screens, Display Wired LAN Info., Display FTP Result, cannot be told
    from a keyboard or an entry screen without the camera's frames): a screen read as no known kind inside a row a
    decision opened, of any class, gets MENU alone, and drive.py keeps its field names and whole row labels alone."""
    import drive as D
    for cls in (safety.LIFT_NETWORK, safety.LIFT_IDENTITY, safety.LIFT_ADDRESS):
        assert safety.inside_menu_only(cls, "unknown", "Bluetooth Function On Off"), cls
    assert safety.inside_menu_only(safety.LIFT_NETWORK, "list", "Bluetooth Function On Off") is None
    assert D.network_shown("unknown", "Server Result: made-up", {"class": safety.LIFT_NETWORK}, False, True)


def test_drive_keeps_display_ftp_results_field_names_alone(tmp_path, monkeypatch, scope_file, capsys):
    lines = ["Display FTP Result", "Server", "made-up.example", "Result: 3 sent"]
    pressed, _, line, _ = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "down"], ("Display FTP Result",),
                                     {**DECISION, "rows": ["Display FTP Result"]}, lines, "unknown",
                                     page_lit="Display FTP Result", open_lit="", page_kind="menu")
    out = capsys.readouterr().out
    assert pressed == ["menu", "right"] and line["completed"] is False                # MENU alone on it
    assert line["screens"][0]["fields"] == ["Display FTP Result", "Server"] and "text" not in line["screens"][0]
    for said in (out, json.dumps(line)):
        assert "made-up.example" not in said and "3 sent" not in said


# the row labels and their values the kit knows, as runner.known_labels and runner.row_values give them (made up but for
# the a1 II's own row names); "Account Info", "Forrnat Media" ("rn" read for "m") and "Update Firmware" are made-up
# labels whose words name identity, a card action (only with the slip undone) and a confirmation
NOTICE_LABELS = {"Airplane Mode", "Wired LAN Connect", "Account Info", "Forrnat Media", "Update Firmware"}
NOTICE_VALUES = {"Airplane Mode": ["On", "Off"], "Wired LAN Connect": ["On", "Off"], "Account Info": ["Set"],
                 "Forrnat Media": ["Slot 1"], "Update Firmware": ["Ready"]}
FOLLOWS = "This operation or setting not available as follows"


@pytest.mark.parametrize("text,kept", [
    ("This function is currently disabled. OK", "This function is currently disabled."),
    ("This function is currently disabled.", "This function is currently disabled."),
    ("This operation or setting not available.  ● OK", "This operation or setting not available."),
    (f"{FOLLOWS} Airplane Mode On OK", f"{FOLLOWS} Airplane Mode"),          # a known label and one of its values:
    #                                                                           the label alone, never its state
    (f"{FOLLOWS} Airplane Mode OK", f"{FOLLOWS} Airplane Mode"),             # a known label alone
    (f"{FOLLOWS} Airplane Mode Maybe", FOLLOWS),                              # no value of its own: the sentence alone
    (f"{FOLLOWS} {IP}", FOLLOWS),                                             # an address: the sentence alone
    (f"{FOLLOWS} {MAC}", FOLLOWS),
    (f"{FOLLOWS} ILCE-made-up", FOLLOWS),                                     # a device's name
    (f"{FOLLOWS} DIRECT-madeup", FOLLOWS),                                    # an SSID-like string
    (f"{FOLLOWS} someone@example.com", FOLLOWS),                              # an e-mail address
    ("Connected to DIRECT-madeup. Cannot be executed. OK", ""),                 # names a connection: nothing
    (f"{FOLLOWS} Wired LAN Connect On", ""),                                  # names an identity row: nothing
    (f"{FOLLOWS} SSID madeup", ""),
    (f"{FOLLOWS} Account Info Set", ""),                                      # identity_screen alone names it
    (f"{FOLLOWS} Forrnat Media Slot 1", ""),                                  # never_lifted alone, slips undone
    (f"{FOLLOWS} Update Firmware Ready", ""),                                 # a confirmation's word after it
    ("Something else happened. OK", ""),                                      # a shape the kit does not know
    ("Reset the setting? Cancel OK", ""),
    ("", ""),
])
def test_a_notice_is_kept_only_in_a_shape_the_kit_knows_naming_no_identity(text, kept):
    """safety.notice_kept: a notice the kit knows, and from a blocker notice what it names after "as follows" only where
    that is a row label the kit knows, alone or with one of that row's known values; an address, a device's name, an
    SSID or an e-mail address there keeps the fixed sentence alone; identity, a card action or a confirmation anywhere
    keeps nothing."""
    assert safety.notice_kept(text, NOTICE_LABELS, NOTICE_VALUES) == kept
    if kept.startswith(FOLLOWS) and kept != FOLLOWS:
        assert safety.notice_kept(text) == FOLLOWS                          # no labels known: the sentence alone


def test_crawl_run_gives_the_walk_its_known_labels_and_values_for_the_notices(monkeypatch):
    """crawl_run.crawl_from_menu: on a --network walk the notices are read with camkit.live.text_of and judged by the
    row labels and values the kit knows (runner.known_labels, runner.row_values); without --network none is read."""
    import crawl_run
    got = {}
    monkeypatch.setattr(crawl_run, "crawl", lambda cam, cycle, model, **kw: got.update(kw) or SimpleNamespace(
        stopped="", presses=0, rows=[], recoveries=[]))
    monkeypatch.setattr(crawl_run, "same_position", lambda a, b: True)
    cam = SimpleNamespace(press=lambda key: None, read=lambda: SimpleNamespace(kind="menu"))
    link = SimpleNamespace(press=lambda key, cleanup=False: None)
    model = {"p": {"breadcrumb": "Network > Network Option", "rows": [{"label": "Airplane Mode", "value": "On"}]}}
    crawl_run.crawl_from_menu(cam, link, [{"screen": None}], model, None, io.StringIO(), network={"Bluetooth Function": DAY})
    read, labels, values = got["notices"]
    assert read is crawl_run.text_of and "Airplane Mode" in labels and values["Airplane Mode"] == {"On"}
    got.clear()
    crawl_run.crawl_from_menu(cam, link, [{"screen": None}], model, None, io.StringIO())
    assert got["notices"] is None


def test_the_crawl_keeps_a_greyed_network_settings_notice_and_nothing_else():
    """camkit.crawl.visit_row: a Wi-Fi or Bluetooth setting a decision opened that answers Right with a notice keeps the
    notice's text where safety.notice_kept takes it; an identity row's notice, one naming identity, one in a shape the
    kit does not know, or a walk given no way to read text, keeps none (crawl_run.summary writes it as "notice")."""
    import crawl_run
    row = {"label": "Bluetooth Function", "never_open": NETWORK_REASON}
    wired = {"label": "Wired LAN Connect", "never_open": safety.never_open("Wired LAN Connect")}
    disabled = "This function is currently disabled. OK"
    for r, network, text, notice in (
            (row, {"Bluetooth Function": DAY}, disabled, "This function is currently disabled."),
            (row, {"Bluetooth Function": DAY}, f"{FOLLOWS} Airplane Mode On", f"{FOLLOWS} Airplane Mode"),
            (row, {"Bluetooth Function": DAY}, f"{FOLLOWS} {IP}", FOLLOWS),
            (row, {"Bluetooth Function": DAY}, "Connected to DIRECT-madeup. Cannot be executed.", ""),
            (row, {"Bluetooth Function": DAY}, "Something else happened.", ""),
            (wired, {"Wired LAN Connect": DAY}, disabled, ""),
            (row, {"Bluetooth Function": DAY}, None, "")):
        cam = RowCamera()
        got = crawl.visit_row(cam, cam.read(), {"page": "Network > Bluetooth"}, 0, r, network=network,
                              notices=None if text is None else ((lambda c, t=text: t), NOTICE_LABELS, NOTICE_VALUES))
        assert got.outcome.startswith("network row: a notice screen") and got.notice == notice, (r["label"], text)
        assert crawl_run.summary(got).get("notice", "") == notice
        assert cam.keys == ["right", "menu"]


# ---------------------------------------------------------------- the second look of 2026-11-14: nothing read is kept

# made-up value words and a made-up shooting status line: none may reach the console, drive.jsonl, the run's events or
# the walk's rows.jsonl on a --network run. "Zephyr" and "Quokka" are the made-up definition's two values of Bluetooth
# Function; "Marmot" and "Wombat-77" are values the kit knows nowhere
KNOWN_A, KNOWN_B, UNKNOWN, UNKNOWN2 = "Zephyr", "Quokka", "Marmot", "Wombat-77"
STATUS = ["1/8000", "F2.8", "ISO 12800", "+1.7"]
BT_DEFINITION = {"menu": [{"tab": "Network", "group": "Bluetooth", "label": "Bluetooth Function"},
                          {"tab": "Network", "group": "Network Option", "label": "Airplane Mode"}],
                 "settings": [{"name": "BT", "row": ["Bluetooth Function"], "values": [[0, KNOWN_A], [1, KNOWN_B]]}]}
# the same with the made-up states the definition gives Airplane Mode, one of which a blocker notice names
ENGAGED = "Engaged"
STATE_DEFINITION = {**BT_DEFINITION, "settings": [*BT_DEFINITION["settings"],
                                                  {"name": "AM", "row": ["Airplane Mode"],
                                                   "values": [[0, ENGAGED], [1, "Idle"]]}]}


@pytest.fixture
def bt_definition(tmp_path, monkeypatch):
    """The camera's definition is BT_DEFINITION (camkit.definitions.active)."""
    from camkit import definitions
    target = tmp_path / "bt_definition.json"
    target.write_text(json.dumps(BT_DEFINITION), encoding="utf-8")
    monkeypatch.setattr(definitions, "active", lambda required=False: target)
    return target


def nowhere(said, *words):
    for where in said:
        for w in words:
            assert w not in where, (w, where[:400])


@pytest.mark.parametrize("screen", ["list", "notice", "page after MENU", "shooting screen after MENU"])
def test_a_network_run_prints_and_keeps_no_screens_text_from_its_start_to_its_end(tmp_path, monkeypatch, scope_file,
                                                                                  bt_definition, capsys, screen):
    """The second look of 2026-11-14, with made-up values: drive.py printed and kept a list's lines, a greyed row's
    blocker with its state, the page after MENU and, after MENU from a notice, the shooting screen's status line. Now
    every screen of a --network run is kept as safety.kept_screen keeps it: the row labels and field names, a list's
    option names where the definition gives them for its row (never which is lit), a notice as notice_kept keeps it,
    the count withheld, and the shooting screen as its kind alone."""
    page = ["Bluetooth", "Bluetooth Function", f"Airplane Mode  {UNKNOWN}", UNKNOWN2]
    kw = {"page_lit": "Bluetooth Function", "open_lit": KNOWN_B, "page_kind": "submenu", "page_lines": page}
    presses = ["right", "down", "menu"]
    if screen == "list":
        opened, kind = ["Bluetooth Function", KNOWN_A, KNOWN_B, UNKNOWN2], "list"
    elif screen == "notice":
        opened, kind = [FOLLOWS, f"Airplane Mode {UNKNOWN}", "OK"], "notice"
        presses = ["right", "menu"]
    else:
        opened, kind = ["Bluetooth Function", KNOWN_A, KNOWN_B], "list"
    if screen == "shooting screen after MENU":
        kw["shooting_lines"] = STATUS
    pressed, seen, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, presses, ("Bluetooth Function",), RMT,
                                             opened, kind, **kw)
    out = capsys.readouterr().out
    assert line["completed"] is True and all("text" not in s for s in line["screens"])
    said = (out, json.dumps(line), logged)
    nowhere(said, UNKNOWN, UNKNOWN2, *STATUS)
    first = line["screens"][0]
    if screen == "list":
        # the definition's two names for the row: kept as its options, in the screen's order, the lit one unmarked
        assert first["options"] == [KNOWN_A, KNOWN_B] and first["fields"] == ["Bluetooth Function"]
        assert first["withheld"] == 1 and "lit" not in json.dumps(first)
    elif screen == "notice":
        assert first["notice"] == FOLLOWS and "Airplane Mode" not in first["notice"]      # its value is no known one
    elif screen == "page after MENU":
        last = line["screens"][-1]
        # its row label kept; the group's name (no row label), the row with its value beside it and a value withheld
        assert last["kind"] == "submenu" and last["fields"] == ["Bluetooth Function"] and last["withheld"] == 3
    else:
        shot = [s for s in line["screens"] if s["kind"] == "shooting"]
        assert shot and all(s["fields"] == [] and s["withheld"] == len(STATUS) for s in shot)
        assert '"network_row_left"' in logged
    # the run's folder is owner-only (item 7): on POSIX, folders 0700 and files 0600
    import os
    import stat
    if os.name == "posix":
        run_dir = seen["run"].dir
        for p in [run_dir, *run_dir.rglob("*")]:
            assert not stat.S_IMODE(p.stat().st_mode) & 0o077, p


def test_without_the_definitions_names_a_list_keeps_no_option_and_without_network_the_text_as_ever(
        tmp_path, monkeypatch, scope_file, capsys):
    """No definition: the list's option names are no known names, so none is kept; and a run without --network keeps a
    screen's text as ever (drive.network_shown)."""
    import drive as D
    pressed, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "menu"], ("Bluetooth Function",),
                                          RMT, ["Bluetooth Function", KNOWN_A, KNOWN_B], "list",
                                          page_lit="Bluetooth Function", open_lit=KNOWN_A)
    assert "options" not in line["screens"][0] and line["screens"][0]["withheld"] == 2
    nowhere((capsys.readouterr().out, json.dumps(line), logged), KNOWN_A, KNOWN_B)
    assert D.network_shown("menu", "anything", None, False, False) is False
    assert D.network_shown("menu", "anything", None, False, True) is True
    assert D.network_shown("shooting", "", None, True, False) is True


def test_kept_screen_keeps_kinds_labels_fields_known_options_and_notices_alone():
    labels, values = {"Bluetooth Function", "Airplane Mode"}, {KNOWN_A, KNOWN_B, "On", "Off"}
    by_row = {"Airplane Mode": {"On", "Off"}}
    k = safety.kept_screen
    assert k("shooting", STATUS, labels, values) == {"fields": [], "withheld": 4}
    # its kind alone, a line that reads as a row label or a field name among it
    assert k("shooting", ["Airplane Mode", "IP Address", *STATUS], labels, values) == {"fields": [], "withheld": 6}
    # a list: the row's known names, two or more on the screen, never one alone (the lit one, on a short window)
    got = k("list", ["Bluetooth Function", KNOWN_A, KNOWN_B, UNKNOWN], labels, values, [KNOWN_A, KNOWN_B])
    assert got == {"fields": ["Bluetooth Function"], "options": [KNOWN_A, KNOWN_B], "withheld": 1}
    # a set short of the row's whole set (OCR missed the lit line, a window of a longer list): the count alone
    got = k("list", ["Bluetooth Function", KNOWN_A, KNOWN_B], labels, values, [KNOWN_A, KNOWN_B, "Third"])
    assert "options" not in got and got["option_count"] == 2 and KNOWN_A not in json.dumps(got)
    assert "options" not in k("list", ["Bluetooth Function", KNOWN_A], labels, values, [KNOWN_A, KNOWN_B])
    # a carousel draws the lit option alone, a side list a window centred on it: never their options
    for kind in ("dialog", "sidelist"):
        assert "options" not in k(kind, [KNOWN_A, KNOWN_B], labels, values, [KNOWN_A, KNOWN_B]), kind
    # a notice: what notice_kept keeps, its lines counted
    got = k("notice", [FOLLOWS, "Airplane Mode On", "OK"], labels, values, (), by_row)
    assert got["notice"] == f"{FOLLOWS} Airplane Mode" and got["withheld"] == 2      # the blocker's line and the OK
    assert "On" not in got["notice"].split() and safety.blocker_known("Airplane Mode On", labels, by_row) == "Airplane Mode"
    assert safety.blocker_known("Airplane Mode Maybe", labels, by_row) is None
    got = k("notice", [FOLLOWS, f"Airplane Mode {UNKNOWN}"], labels, values, (), by_row)
    assert got["notice"] == FOLLOWS and got["withheld"] == 1 and UNKNOWN not in json.dumps(got)
    said = safety.kept_said({"fields": ["A"], "options": ["B", "C"], "notice": "N", "withheld": 3})
    assert said == "fields ['A'], options ['B', 'C'], notice 'N', 3 lines withheld"
    assert safety.kept_said({"fields": [], "option_count": 2, "withheld": 2}) == "fields [], 2 options, 2 lines withheld"
    assert "screen withheld" in safety.kept_said({"blanked": True})


class LapCamera:
    """A page of rows labelled by the page model, Down from one to the next; Right on a row named in `refuse` raises
    safety.Refused before anything goes out (the camera's own check), on one named in `opens` opens a list whose Down
    raises safety.Refused (a refusal after a press), on any other opens a notice; MENU back to the row."""
    def __init__(self, n, refuse=(), opens=(), locked=()):
        self.n, self.row, self.where, self.keys, self.presses = n, 0, "row", [], 0
        self.refuse, self.opens, self.locked = set(refuse), set(opens), set(locked)

    def press(self, key):
        if key == "right" and self.where == "row" and self.row in self.refuse:
            raise safety.RowRefused("right: the lit row reads 'Wombat-77 Setting', never opened (by hand only)")
        if key == "right" and self.where == "row" and self.row in self.locked:
            raise safety.Refused("right: a row a network decision opened ('Wombat-77') is still open: look only")
        if key == "down" and self.where == "list":
            raise safety.Refused("down: could choose an option inside 'Wombat-77'")
        self.keys.append(key)
        self.presses += 1
        if key == "right":
            self.where = "list" if self.row in self.opens else "notice"
        elif key == "menu":
            self.where = "row"
        elif key == "down":
            self.row += 1

    def read(self):
        return SimpleNamespace(kind={"row": "menu", "notice": "notice", "list": "list"}[self.where],
                               signature=(self.where, self.row), struct=None, bits=None, row=self.row, glyphs={},
                               at_end=None, at_start=None, scroll=None)


def lap(n):
    cycle = [{"page": "p", "row": i, "kind": "menu", "signature": ("row", i)} for i in range(n)]
    model = {"p": {"breadcrumb": "Shooting > Made-up", "page": "p", "rows": [{"label": f"Row {i}"} for i in range(n)]}}
    return cycle, model


def test_a_row_whose_opening_is_refused_before_any_press_is_skipped_and_the_lap_goes_on():
    """camkit.crawl.visit_row: a Right the camera refuses before it goes out skips that row ("skipped: refused (...)",
    the reason's quoted texts withheld), and the crawl goes on to the next row."""
    cam = LapCamera(3, refuse={1})
    cycle, model = lap(3)
    out = crawl.crawl(cam, cycle, model)
    assert out.stopped == "" and [r.outcome for r in out.rows] == ["notice", out.rows[1].outcome, "notice"]
    assert out.rows[1].outcome.startswith("skipped: refused (") and "Wombat" not in out.rows[1].outcome
    assert "'(withheld)'" in out.rows[1].outcome and out.rows[1].presses == 0
    assert cam.keys == ["right", "menu", "down", "down", "right", "menu"]       # no Right went out on row 1
    assert out.presses == 6
    # a refusal that is not about the row (a lock still on): the lap is cancelled, never every later row skipped
    cam = LapCamera(3, locked={1})
    with pytest.raises(safety.Refused, match="still open"):
        crawl.crawl(cam, cycle, model)
    assert cam.keys == ["right", "menu", "down"]
    # and a row refusal while the camera says a decided row is still open: raised too
    cam = LapCamera(3, refuse={1})
    cam.network_open = {"row": "Bluetooth Function"}
    with pytest.raises(safety.RowRefused):
        crawl.crawl(cam, cycle, model)


def test_a_refusal_after_a_press_on_a_row_cancels_the_lap():
    """A refusal inside the row's walk (after its Right) is raised, never taken for an incomplete walk: an ordinary
    row's, and a row a network decision opened to look at."""
    cam = LapCamera(2, opens={0})
    cycle, model = lap(2)
    with pytest.raises(safety.Refused, match="could choose"):
        crawl.crawl(cam, cycle, model)
    assert cam.keys == ["right"]
    cam = LapCamera(2, opens={0})
    model["p"]["breadcrumb"] = "Network > Bluetooth"
    model["p"]["rows"][0] = {"label": "Bluetooth Function", "never_open": NETWORK_REASON}
    with pytest.raises(safety.Refused, match="could choose"):
        crawl.crawl(cam, cycle, model, network={"Bluetooth Function": DAY})
    assert cam.keys == ["right"]


def crawl_main(tmp_path, monkeypatch, raised, restored=True, network=None, argv=(), complete=True, log=None):
    """crawl_run.main() with its seams faked: crawl_from_menu raises `raised` (or returns `complete`); the restore's
    check says `restored`. Returns (the exit status, the console); `log` collects the keywords the session's end and the
    restore's check were given."""
    import crawl_run as C
    run = Run("kit2_crawl", root=tmp_path)
    log = [] if log is None else log

    def crawl_from_menu(*a, **k):
        if raised is not None:
            raise raised
        return complete
    for name, value in (("load_scan", lambda scan: ([], {})), ("Run", lambda name: run),
                        ("network_settings_or_exit", lambda r: network or {}), ("check_readers", lambda: None),
                        ("eyes_from_config", lambda r: SimpleNamespace(attach=lambda link: None, close=lambda: None,
                                                                       grab=lambda save=False: None)),
                        ("Link", lambda r: contextlib.nullcontext(SimpleNamespace(download=lambda tag: tmp_path / "b.DAT",
                                                                                  press=lambda *a, **k: None))),
                        ("screen", SimpleNamespace(read=lambda f: SimpleNamespace(kind="shooting"))),
                        ("wait_for", lambda *a, **k: None), ("time", SimpleNamespace(sleep=lambda s: None)),
                        ("LiveCamera", lambda *a, **k: SimpleNamespace()), ("crawl_from_menu", crawl_from_menu),
                        ("close_for_restore", lambda cam, link: None),
                        ("end_session", lambda *a, **k: log.append(("end", {x: k[x] for x in k if x != "reach"}))
                         or SimpleNamespace(after=None, changes=[], uploaded=False)),
                        ("restore_checked", lambda r, e, before, **kw: log.append(("check", kw)) or restored),
                        ("network_values", lambda n, m: {}), ("label_readings", lambda m: set()),
                        ("network_readings", lambda n, m: {})):
        monkeypatch.setattr(C, name, value)
    monkeypatch.setattr(sys, "argv", ["crawl_run.py", *argv])
    out = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out):
        try:
            C.main()
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()


def test_crawl_run_exits_refused_when_a_refusal_stops_the_lap_and_a_chain_stops_there(tmp_path, monkeypatch):
    """A refusal that stops the lap: the start file restored and checked, then EXIT_REFUSED (7), never 0; anything else
    that stops it short (an error, the lap off the scan, lost, its start label not reached) EXIT_INCOMPLETE (8); a STOP
    and a lap ended as asked 0; an unchecked restore EXIT_UNRESTORED (4) as ever. On a --network run the error's quoted
    texts are withheld, and the session's end and the restore's check say the records by key alone."""
    from camkit.link import LinkError, StopRequested
    from exit_status import EXIT_INCOMPLETE, EXIT_REFUSED, EXIT_UNRESTORED
    refusal = safety.Refused("right: the lit row reads 'Wombat-77 Setting'")
    code, out = crawl_main(tmp_path, monkeypatch, refusal)
    assert code == EXIT_REFUSED == 7 and "stopped by a refusal" in out
    assert crawl_main(tmp_path, monkeypatch, refusal, restored=False)[0] == EXIT_UNRESTORED
    log = []
    assert crawl_main(tmp_path, monkeypatch, None, log=log)[0] == 0
    assert log == [("end", {}), ("check", {})]                                   # without --network, values as ever
    for failure in (RuntimeError("the camera went away"), LinkError("no answer")):
        code, out = crawl_main(tmp_path, monkeypatch, failure)
        assert code == EXIT_INCOMPLETE == 8 and "stopped short" in out, failure
    assert crawl_main(tmp_path, monkeypatch, None, complete=False)[0] == EXIT_INCOMPLETE
    assert crawl_main(tmp_path, monkeypatch, StopRequested("STOP"))[0] == 0
    assert crawl_main(tmp_path, monkeypatch, RuntimeError("x"), restored=False)[0] == EXIT_UNRESTORED
    log = []
    code, out = crawl_main(tmp_path, monkeypatch, refusal, network={"Bluetooth Function": DAY}, argv=["--network"],
                           log=log)
    assert code == EXIT_REFUSED and "Wombat" not in out and "'(withheld)'" in out
    assert log == [("end", {"show": 0, "keys": True}), ("check", {"show": 0, "keys": True})]


def test_crawl_from_menu_says_whether_the_lap_ended_as_asked(monkeypatch, capsys):
    """crawl_run.crawl_from_menu: True for a complete lap, --limit reached or a STOP; False for a menu on a screen the
    scan does not know, a start label not reached (its own message), or a crawl stopped off the scan or lost."""
    import crawl_run
    from camkit.link import StopRequested
    cam = SimpleNamespace(press=lambda key: None, read=lambda: SimpleNamespace(kind="menu", focus="rows"),
                          cancel_to_menu=lambda: None)
    link = SimpleNamespace(press=lambda key, cleanup=False: None)
    monkeypatch.setattr(crawl_run, "same_position", lambda a, b: True)

    def lap(stopped=None, raised=None):
        def fake(cam, cycle, model, **kw):
            if raised:
                raise raised
            return SimpleNamespace(stopped=stopped, presses=0, rows=[], recoveries=[])
        monkeypatch.setattr(crawl_run, "crawl", fake)
        return crawl_run.crawl_from_menu(cam, link, [{"screen": None}], {}, None, io.StringIO())
    assert lap("") is True and lap("row limit (3) reached") is True and lap("stop requested") is True
    assert lap(raised=StopRequested("STOP")) is True
    assert lap("position 4: lost") is False and lap("position 4: the screen is not the one the scan recorded here") is False
    monkeypatch.setattr(crawl_run, "go_to", lambda *a, **k: None)
    assert crawl_run.crawl_from_menu(cam, link, [{"screen": None}], {}, None, io.StringIO(), "Drive Mode") is False
    assert "the start label 'Drive Mode' could not be reached by the scan" in capsys.readouterr().out
    monkeypatch.setattr(crawl_run, "same_position", lambda a, b: False)
    unknown = [{"screen": None, "kind": "menu", "page": "p", "row": 0}]      # a scan position the menu does not show
    assert crawl_run.crawl_from_menu(cam, link, unknown, {}, None, io.StringIO()) is False
    assert "a screen the scan does not know" in capsys.readouterr().out


@pytest.mark.parametrize("status,said", [(7, "a refusal stopped the step"), (8, "the step stopped short")])
def test_the_chain_stops_after_a_step_that_exits_refused_and_uploads_its_end_file(tmp_path, monkeypatch, status, said):
    """kit/tools/chain.py: status 7 (EXIT_REFUSED) and 8 (EXIT_INCOMPLETE) stop the chain as status 4 does, and the end
    file still goes up."""
    from tools import chain
    end = tmp_path / "owner.DAT"
    end.write_bytes(b"x")
    f = tmp_path / "c.toml"
    f.write_text('name = "c"\n[[step]]\ntitle = "one"\nrun = ["kit/crawl_run.py"]\n[[step]]\ntitle = "two"\n'
                 'run = ["kit/crawl_run.py"]\n[[step]]\ntitle = "three"\nrun = ["kit/crawl_run.py"]\n', encoding="utf-8")
    ran = []

    def step(s, env, out):
        ran.append(s.get("title") or ("upload", Path(s.get("upload")).name))
        return status if s.get("title") == "two" else 0
    monkeypatch.setattr(chain, "run_step", step)
    monkeypatch.setattr(chain.paths, "run_root", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["chain.py", str(f), "--end", str(end), "--stop", str(tmp_path / "STOP_CHAIN")])
    with contextlib.redirect_stdout(io.StringIO()) as out:
        chain.main()
    assert ran == ["one", "two", ("upload", "owner.DAT")] and said in out.getvalue()


def test_a_network_walk_keeps_only_the_labels_it_knows_in_rows_jsonl_and_the_console(monkeypatch, capsys):
    """crawl_run.crawl_from_menu on a --network walk: a row's label is kept where it is a row label the kit knows, or
    the decided row a lifted row was opened as; a label read with a value glued on, a live page's reading holding a
    device's name, and an outcome's or a note's quoted texts are withheld, in rows.jsonl and on the console."""
    import crawl_run
    from camkit.crawl import RowResult, SubCrawl

    def fake_crawl(cam, cycle, model, **kw):
        sub = SubCrawl(rows=[RowResult("p > s", 0, f"Device Name ILCE-{UNKNOWN}", "notice"),
                             RowResult("p > s", 1, "Airplane Mode", "notice")], stopped=f"lost at '{UNKNOWN2}'")
        for r in (RowResult("p", 0, "Bluetooth Function", "notice", network=safety.LIFT_NETWORK,
                            decided="Bluetooth Function"),
                  RowResult("p", 1, f"Wi-Fi Connect{UNKNOWN}", f"incomplete: '{UNKNOWN2}'"),
                  RowResult("p", 2, "LANWired LAN Connect", "walked (network row, looked at only)",
                            network=safety.LIFT_IDENTITY, decided="Wired LAN Connect"),
                  RowResult("p", 3, "Airplane Mode", "submenu crawled", walk=sub)):
            kw["on_row"](r)
        return SimpleNamespace(stopped=f"position 3: lost at '{UNKNOWN2}'", presses=0, rows=[], recoveries=[])
    monkeypatch.setattr(crawl_run, "crawl", fake_crawl)
    monkeypatch.setattr(crawl_run, "same_position", lambda a, b: True)
    cam = SimpleNamespace(press=lambda key: None, read=lambda: SimpleNamespace(kind="menu"))
    link = SimpleNamespace(press=lambda key, cleanup=False: None)
    model = {"p": {"breadcrumb": "Network > Network Option", "rows": [{"label": "Airplane Mode", "value": "On"},
                                                                      {"label": "Bluetooth Function"}]}}
    results = io.StringIO()
    crawl_run.crawl_from_menu(cam, link, [{"screen": None}], model, None, results,
                              network={"Bluetooth Function": DAY, "Wired LAN Connect": DAY})
    rows = [json.loads(x) for x in results.getvalue().splitlines()]
    assert [r["label"] for r in rows] == ["Bluetooth Function", "(withheld)", "Wired LAN Connect", "Airplane Mode"]
    assert [r["label"] for r in rows[3]["submenu"]] == ["(withheld)", "Airplane Mode"]
    nowhere((results.getvalue(), capsys.readouterr().out), UNKNOWN, UNKNOWN2, "ILCE")
    # without --network the summary is as ever
    results = io.StringIO()
    crawl_run.crawl_from_menu(cam, link, [{"screen": None}], model, None, results)
    assert UNKNOWN in results.getvalue()


# ---------------------------------------------------------------- a row found by its readings, gone to and opened (item 2)

def test_go_to_finds_a_row_by_any_of_its_readings_or_its_icon_glued_on(monkeypatch, capsys):
    """crawl_run.go_to: where the page model's label is OCR's "LANWired LAN Connect", --path "Wired LAN Connect" finds
    the row by the vision reader's reading, or by the Wired LAN page's icon glued on (safety.glued_icon); never by a
    word set before it, an icon that is no word of its page's group, or one naming what the never-open list holds."""
    import crawl_run

    def find(group, row, label="Wired LAN Connect", bar=None, twice=False):
        """go_to on a made-up tab; `bar`: what the lit bar reads on the row gone to (its page model label by default);
        twice: another row of another page reads as the label too."""
        cam, cycle, model = columns(monkeypatch, ["Wi-Fi", group], ["Wi-Fi", group])
        cam.focus = "rows"
        model["p1"]["rows"][1] = row
        if twice:
            model["p0"]["rows"][0] = row
        real = cam.lit
        cam.lit = lambda: (bar or row["label"]) if (cam.focus, cam.group, cam.row) == ("rows", 1, 1) else real()
        return crawl_run.go_to(cam, cycle, model, 0, label)
    both = {"label": "LANWired LAN Connect", "readings": {"label": {"ocr": "LANWired LAN Connect",
                                                                     "vlm": "Wired LAN Connect"}}}
    assert find("Wired LAN", both) == 3                                          # its bar, the icon glued on: the row
    assert find("Wired LAN", both, bar="LANWired LAN Connect  On") == 3
    assert find("Wi-Fi Option", both, bar="Wired LAN Connect  On") == 3  # a reader read it exactly
    assert find("Wi-Fi Option", both) is None                                    # but its bar reads no such row
    assert "its bar does not read it" in capsys.readouterr().out
    ocr_only = {"label": "LANWired LAN Connect", "readings": {"label": {"ocr": "LANWired LAN Connect"}}}
    assert find("Wired LAN", ocr_only, bar="Wired LAN Connect") == 3            # the icon of its own page, glued on
    assert find("Wired LAN", ocr_only) is None                                   # no reader read the row: no bar is
    capsys.readouterr()
    for group, row in (("Wi-Fi Option", ocr_only),                               # no word of the page's group
                       ("Wired LAN", {"label": "LAN Wired LAN Connect"}),       # a word set before it
                       ("WPS Wired LAN", {"label": "WPSWired LAN Connect"}),    # never_open names it alone
                       ("Wired LAN", {"label": "LANWired LAN Connecl"})):       # not the row after the icon
        assert find(group, row, bar="Wired LAN Connect") is None, (group, row)
        assert "no row labelled 'Wired LAN Connect'" in capsys.readouterr().out
    # exactly one row may read so: two rows of two pages, none is gone to
    assert find("Wired LAN", both, twice=True) is None and "2 rows read as it" in capsys.readouterr().out
    # the old rule first, as ever: a prefix of one or two letters, no check of the bar on arrival
    assert find("Wired LAN", {"label": "SDrive Mode"}, "Drive Mode", bar="something else") == 3
    assert crawl_run.row_named(both, "Wired LAN Connect", "") and not crawl_run.row_named(ocr_only, "Wired LAN Connect", "")


def test_drive_refuses_the_glued_label_as_a_path_before_anything_connects(scope_file):
    """(b): the decided label is the path; the glued reading as a --path label is refused before anything connects."""
    scope_file({**DECISION, "rows": ["Wired LAN Connect"]})
    r = drive("--network", "--path", "LANWired LAN Connect")
    assert r.returncode != 0 and "'LANWired LAN Connect'" in r.stderr and "no --allow opens it" in r.stderr, r.stderr


def test_row_values_gather_every_reading_of_a_page_model_row(made_up_definition):
    """runner.row_values and network_values: the value shown beside OCR's "LANIP Address Setting" counts for the vision
    reader's "IP Address Setting"; the definition's own values as before."""
    import runner
    model = {"p": {"breadcrumb": "Network > Wired LAN", "rows": [
        {"label": "LANIP Address Setting", "value": UNKNOWN,
         "readings": {"label": {"ocr": "LANIP Address Setting", "vlm": "IP Address Setting"}, "value": {"vlm": UNKNOWN2}}}]}}
    got = runner.row_values(model)
    assert got["IP Address Setting"] == {UNKNOWN, UNKNOWN2} == got["LANIP Address Setting"]
    assert runner.network_values({"IP Address Setting": DAY}, model) == {"IP Address Setting": sorted({UNKNOWN, UNKNOWN2})}
    assert runner.defined_values()["Subject Pick"] == {OPTION, "Other Choice"}
    assert "IP Address Setting" not in runner.defined_values()                # the page model's values: never


@pytest.mark.parametrize("tail,lifts", [
    ("", True), ("Manual", True), ("Auto IP", True), ("Static", True),
    ("Auto IP Now", False),                         # three words
    (IP, False), ("10.0", False), (MAC, False),     # an address's shape
    ("Format", False), ("Password", False),         # the never-open list
    ("Copy", False), ("Send", False),               # an action's name, which only never_open names here
    ("SSID", False), ("Pairing", False), ("Connecting", False),       # identity
])
def test_a_decided_row_with_no_known_value_takes_a_short_tail_naming_nothing(tail, lifts):
    """safety.network_lifted_row: with no value known for the row at all, what follows the label may be at most two
    words naming nothing never-open, of identity or credentials, with no address shape (unknown_tail); where values are
    known, only one of them, as before."""
    rows = decided({**DECISION, "rows": ["Wired LAN Connect"]})
    lit = f"Wired LAN Connect  {tail}".strip()
    lift = lambda **kw: safety.network_lifted_row(lit, rows, labels={"Drive Mode"}, **kw) == "Wired LAN Connect"  # noqa: E731
    assert lift(values={}) is lifts and lift(values={"Wired LAN Connect": []}) is lifts
    if tail:
        assert not lift(values={"Wired LAN Connect": ["On"]})
        assert safety.network_lifted_row(lit, rows, values={}) is None                  # no labels given: no tail


def test_drive_opens_a_decided_row_with_a_value_none_knew(tmp_path, monkeypatch, scope_file):
    """drive.py on its own: Right on "LANWired LAN Connect  Manual" opens Wired LAN Connect where the page model's
    row holds that reading and the vision reader's, and nothing knew Manual as its value (no value of the row known)."""
    monkeypatch.delitem(VALUES, "Wired LAN Connect")
    model = {"p": {"breadcrumb": "Network > Wired LAN", "rows": [
        {"label": "LANWired LAN Connect", "readings": {"label": {"ocr": "LANWired LAN Connect",
                                                                  "vlm": "Wired LAN Connect"}}}]}}
    pressed, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "menu"], ("Wired LAN Connect",),
                                          {**DECISION, "rows": ["Wired LAN Connect"]}, ["Automatic", "Manual"],
                                          "list", page_lit="LANWired LAN Connect  Manual", open_lit="Manual",
                                          page_kind="menu", model=model)
    assert '"network_row_opened"' in logged, logged


# ---------------------------------------------------------------- the lit group read, never guessed (item 4)

def test_the_jump_reads_an_unread_lit_group_again_and_never_guesses(monkeypatch):
    """crawl_run.jump: a lit group that cannot be read is read again once after a short settle, then on the camera's own
    picture of its screen (osd_lit); where none names it, nothing more is pressed (the row is not reached), where before
    it was taken as the first group and Downs went out."""
    import crawl_run
    monkeypatch.setattr(crawl_run.time, "sleep", lambda s: None)

    def jumped(reads, osd=""):
        cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "Bluetooth", "Wired LAN"], ["Wi-Fi", "Bluetooth", "Wired LAN"],
                                    at=1)
        cam.focus = "rows"
        seen = list(reads)
        real = cam.lit
        cam.lit = lambda: seen.pop(0) if seen else real()
        cam.refresh = lambda tag: cam.keys.append(f"refresh:{tag}")
        monkeypatch.setattr(crawl_run, "osd_lit", lambda c: osd)
        return crawl_run.jump(cam, cycle, crawl_run.page_groups(cycle, model), 5, model), cam
    j, cam = jumped([""])                                        # read on the second look
    assert j == 4 and cam.keys == ["left", "left", "right", "refresh:group-again", "down", "right"]
    j, cam = jumped(["", ""], osd="Bluetooth")                  # the camera's own picture names it
    assert j == 4 and cam.keys == ["left", "left", "right", "refresh:group-again", "down", "right"]
    j, cam = jumped(["", "", "", "", ""], osd="")               # none names it: nothing more
    assert j is None and cam.keys == ["left", "left", "right", "refresh:group-again"]
    j, cam = jumped(["", "", "", "", ""], osd=f"ILCE-made-up {IP}")
    assert j is None and cam.keys == ["left", "left", "right", "refresh:group-again"]


def test_from_the_group_column_an_unread_lit_group_gets_a_second_look(monkeypatch):
    import crawl_run
    monkeypatch.setattr(crawl_run.time, "sleep", lambda s: None)
    monkeypatch.setattr(crawl_run, "osd_lit", lambda c: "")
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "Wired LAN"], ["Wi-Fi", "Wired LAN"], at=1)
    seen = [""]
    real = cam.lit
    cam.lit = lambda: seen.pop(0) if seen else real()
    assert crawl_run.find_position(cam, cycle, model) == 2 and cam.keys == ["right"]


# ---------------------------------------------------------------- short labels and Wi-Fi Frequency Band (items 5, 6)

def test_a_one_or_two_character_label_is_no_label_unless_the_definition_has_it(tmp_path, monkeypatch):
    import runner
    from camkit import definitions
    target = tmp_path / "def.json"
    target.write_text(json.dumps({"menu": [{"label": "AF"}, {"label": "Drive Mode"}], "settings": []}), encoding="utf-8")
    monkeypatch.setattr(definitions, "active", lambda required=False: target)
    model = {"p": {"rows": [{"label": x} for x in ("B", "Q7", "AF", "Drive Mode", "Zoom")]}}
    labels = runner.known_labels(model)
    assert {"AF", "Drive Mode", "Zoom"} <= labels and not {"B", "Q7"} & labels
    # a label of a letter or two is kept only on the page it is a row of (2026-11-14: screen_fields' page)
    names, hidden = safety.screen_fields(["B", "AF", "Drive Mode", "Q7"], labels, page=["AF", "Drive Mode"])
    assert names == ["AF", "Drive Mode"] and hidden == 2
    names, hidden = safety.screen_fields(["B", "AF", "Drive Mode", "Q7"], labels)
    assert names == ["Drive Mode"] and hidden == 3


def test_wi_fi_frequency_band_is_never_chosen():
    for label in ("Wi-Fi Frequency Band", "Wi-Fl Freq. Band", "Wi‑Fi Frequency Band"):
        assert safety.never_choose(label), label
        assert "whatever a decision names" in safety.look_refused("enter", "5GHz", label, ["5GHz"])
    scope = {"decisions": [{**DECISION, "rows": ["Wi-Fi Frequency Band"], "options": {"Wi-Fi Frequency Band": ["5GHz"]}}]}
    rows, refusals = safety.network_decided(scope)
    assert rows == {"Wi-Fi Frequency Band": DAY} and "drops the link" in refusals[0] and safety.network_options(scope) == {}
    assert safety.network_lifted("Wi-Fi Frequency Band 5GHz", rows, values=VALUES)        # still opened, to look


# ---------------------------------------------------------------- a private run's folder (items 7, 8)

@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_a_private_run_is_owner_only_from_its_creation_to_its_end(tmp_path):
    """camkit.runs.Run(private=True): the folders 0700, every file the run then writes 0600 (events, a file opened, one
    runner.write_text writes, one a child process writes), whatever was there before tightened; seal() at the end
    takes the eyes' polling target away and fixes and says what another user could read."""
    import os
    import stat
    import runner
    from camkit import runs
    old = tmp_path / "kit2_drive" / "shots" / "00001_old.png"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"x")
    os.chmod(old, 0o644)
    os.chmod(old.parent, 0o755)
    run = Run("kit2_drive", root=tmp_path, private=True)
    mode = lambda p: stat.S_IMODE(p.stat().st_mode)              # noqa: E731
    assert run.private and runs.UMASK_FLOOR == 0o077
    assert mode(run.dir) == mode(run.shots) == mode(run.dat) == 0o700 and mode(old) == 0o600
    run.log("x", a=1)
    with open(run.dir / "drive.jsonl", "a", encoding="utf-8") as f:
        f.write("{}\n")
    runner.write_json(run.dir / "made.json", {})
    subprocess.run([sys.executable, "-c", f"open({str(run.dat / '00002_before.DAT')!r}, 'wb').write(b'x')"], check=True)
    (run.dir / "_live.png").write_bytes(b"frame")
    for name in ("events.jsonl", "drive.jsonl", "made.json"):
        assert mode(run.dir / name) == 0o600, name
    assert mode(run.dat / "00002_before.DAT") == 0o600
    loose = run.shots / "00003_loose.png"
    loose.write_bytes(b"x")
    os.chmod(loose, 0o644)
    with contextlib.redirect_stdout(io.StringIO()) as out:
        fixed = run.seal()
    assert fixed == ["shots/00003_loose.png"] and mode(loose) == 0o600 and "readable by other users" in out.getvalue()
    assert not (run.dir / "_live.png").exists()
    assert '"private_modes_fixed"' in (run.dir / "events.jsonl").read_text(encoding="utf-8")
    plain = Run("kit2_other", root=tmp_path)
    assert not plain.private and plain.seal() == []


def test_the_eyes_take_their_polling_target_away_and_the_viewer_never_links_it(tmp_path):
    """camkit.frames: the OSD eyes' _live.png (and camlink's .part) at the top of the run's folder goes when they close,
    on every run; kit/tools/proof_viewer.py's frame() never links it, marked or not."""
    from camkit import frames
    from tools import proof_viewer as pv
    run = Run("kit2_x", root=tmp_path)
    for eyes in (frames.OsdFeed(run), frames.OsdSource(SimpleNamespace(), run)):
        eyes.live.write_bytes(b"frame")
        eyes.live.with_name("_live.png.part").write_bytes(b"part")
        eyes.close()
        assert not eyes.live.exists() and not eyes.live.with_name("_live.png.part").exists()
    (run.dir / "_live.png").write_bytes(b"frame")
    (run.shots / "00001_x.png").write_bytes(b"frame")
    old = pv.RUN_ROOT
    pv.RUN_ROOT = tmp_path
    try:
        assert pv.frame(run.dir, "_live.png", tmp_path) is None
        assert pv.frame(run.dir, "00001_x.png", tmp_path) is not None
    finally:
        pv.RUN_ROOT = old


def prove_network(tmp_path, monkeypatch, saved, choose, notice=None, expect=None):
    """prove_run.prove_row on a two-option network list (On, Off) saved on option `saved`, the decision naming `choose`;
    each download differs from the start in one record, its values made up. notice: the OCR lines of a notice after each
    OK; expect: the exception the proof ends with (RestoreAfter by default). Returns (the proofs, the exception's text);
    the console is the caller's (capsys)."""
    import prove_run as P
    from camkit import ocr
    from proving.base import RestoreAfter
    run = Run("pass2", root=tmp_path)
    for name, value in (("place", lambda cam: "here"), ("same_place", lambda a, b: True), ("to_row", lambda *a: None),
                        ("which_option", lambda cam, job: cam.option), ("vlm_option", lambda cam: f"Off {UNKNOWN}"),
                        ("bar_text", lambda cam: "Off"), ("after_download", lambda cam, done: None),
                        ("finish_attempt", lambda *a, **k: None)):
        monkeypatch.setattr(P, name, value)
    monkeypatch.setattr(P.camset, "read", lambda p: SimpleNamespace())
    monkeypatch.setattr(P.camset, "diff", lambda a, b: [SimpleNamespace(key="global:0x0123", before=UNKNOWN,
                                                                        after=UNKNOWN2)])
    lines = [ocr.Line(text=t, conf=0.9, x=0, y=0, w=10, h=10) for t in notice or ()]
    monkeypatch.setattr(P.ocr, "read", lambda paths, eng=None: {p: lines for p in paths})
    link = SimpleNamespace(download=lambda tag: tmp_path / f"{tag}.DAT")
    job = {"path": ["Bluetooth Function"], "kind": "list", "labels": ["On", "Off"], "choose": choose,
           "network_row": "Bluetooth Function", "network_class": safety.LIFT_NETWORK}
    out = io.StringIO()
    cam = ListCamera(tmp_path, notice=bool(notice))
    cam.option = saved
    with pytest.raises(expect or RestoreAfter) as e:    # every network row: the session's upload of the start file
        P.prove_row(cam, link, run, job, tmp_path / "base.DAT", out)
    return [json.loads(x) for x in out.getvalue().splitlines()], str(e.value)


def test_prove_row_on_a_network_row_tells_nothing_of_the_saved_option(tmp_path, monkeypatch, capsys):
    """prove_run.prove_row inside a Wi-Fi or Bluetooth setting a decision opened: the named options proved in their own
    order whatever the row was saved on (never the saved one last), the loop saying "proof i of N" alone, the records
    said by key after it, never a value, and every such row ending with the session's upload of the start file, one text
    for all; the console the same whichever option was saved. An option read under the cursor is kept only where it is
    one of the map's own names. The proofs' diffs against the start file tell it by nature, in proofs.jsonl alone."""
    import prove_run as P
    seen = {}
    for saved in (0, 1):
        proofs, why = prove_network(tmp_path, monkeypatch, saved, [0, 1])
        said = capsys.readouterr().out
        seen[saved] = (said, [p["label"] for p in proofs], why)
        assert [p["label"] for p in proofs] == ["On", "Off"]                   # their own order, never saved-last
        assert all(p["vlm"] == "(withheld)" and p["shown"] == "Off" for p in proofs)
        assert "proof 1 of 2" in said and "proof 2 of 2" in said and "records ['global:0x0123']" in said
        assert "proving 2 named option(s) ['On', 'Off']; the saved value withheld" in said
        assert "no change" not in said and "->" not in said and "saved value 'O" not in said
        nowhere((said,), UNKNOWN, UNKNOWN2)
        assert why == f"Bluetooth Function: {P.NETWORK_RESTORE}"
    assert seen[0] == seen[1]                                                   # nothing said tells the two apart


def test_a_network_rows_failure_names_no_option_by_its_index(tmp_path, monkeypatch, capsys):
    """After a refused proof the last OK "chose" the saved option: a list that then opens on another names neither by
    its index on a network row (the failure would tell the saved option); elsewhere as ever."""
    from proving.base import Failed
    _, why = prove_network(tmp_path, monkeypatch, 1, [0, 1], notice=[FOLLOWS, "OK"], expect=Failed)
    assert "did not open on the option the last OK chose" in why and not any(c.isdigit() for c in why), why


def test_a_proof_sessions_end_says_the_records_by_key_alone_on_a_network_run(tmp_path, monkeypatch):
    """prove_run.end_rows, the session's end main() calls: show=0 and keys on a --network run (the decided rows main()
    gives proving.jobs.NETWORK), as ever otherwise."""
    import prove_run as P
    from proving import jobs
    got = []
    monkeypatch.setattr(P, "end_session", lambda link, eyes, start, why, reach=None, **kw: got.append(kw) or "ended")
    monkeypatch.setattr(jobs, "NETWORK", {"Bluetooth Function": DAY})
    assert P.end_rows(None, None, tmp_path / "start.DAT", None) == "ended"
    monkeypatch.setattr(jobs, "NETWORK", {})
    assert P.end_rows(None, None, tmp_path / "start.DAT", None) == "ended"
    assert P.end_rows(None, None, tmp_path / "start.DAT", None, True) == "ended"
    assert got == [{"show": 0, "keys": True}, {}, {"show": 0, "keys": True}]
    src = Path(P.__file__).read_text(encoding="utf-8")
    assert "ending = end_rows(link, eyes, start, reach)" in src and "ending = end_session(" not in src


def test_prove_row_keeps_a_network_rows_notice_in_its_proofs_alone(tmp_path, monkeypatch, capsys):
    """A notice after OK inside a network row: kept in proofs.jsonl as safety.kept_screen keeps it (here the blocker's
    sentence alone, its row's value being none the kit knows), never its text, and said nowhere."""
    proofs, _ = prove_network(tmp_path, monkeypatch, 1, [0], notice=[FOLLOWS, f"Airplane Mode {UNKNOWN}", "OK"])
    said = capsys.readouterr().out
    assert [p["label"] for p in proofs] == ["On"]
    assert all(p["notice"]["notice"] == FOLLOWS and "text" not in p["notice"] for p in proofs)
    assert "notice" not in said and "withheld (" not in said
    nowhere((said, json.dumps([p["notice"] for p in proofs])), UNKNOWN)


# ---------------------------------------------------------------- the review of 7fc07bd: what it found still said

def test_the_sessions_end_says_the_records_by_key_alone_where_values_are_withheld(tmp_path, monkeypatch, capsys):
    """camkit.session.ended and verify_restore with show=0 and keys (runner.VALUES_WITHHELD, every --network and --owner
    run): the count and the records' keys, never a value; without keys, the values as ever."""
    from camkit import session
    changes = [SimpleNamespace(key="global:0x0123", before=UNKNOWN, after=UNKNOWN2),
               SimpleNamespace(key="set1:0x0456", before=b"\x01", after=b"\x02")]
    monkeypatch.setattr(session, "compared", lambda start, after, say=None: list(changes))
    link = SimpleNamespace(download=lambda tag: tmp_path / f"{tag}.DAT")
    got = session.ended(link, tmp_path / "start.DAT", show=0, keys=True)
    said = capsys.readouterr().out
    assert got.changes == changes and "2 records differ" in said and "global:0x0123, set1:0x0456" in said
    nowhere((said,), UNKNOWN, UNKNOWN2, "->")
    session.ended(link, tmp_path / "start.DAT")
    assert UNKNOWN in capsys.readouterr().out                                    # as ever without keys
    monkeypatch.setattr(session.time, "sleep", lambda s: None)
    n = session.verify_restore(SimpleNamespace(), tmp_path / "start.DAT", link_class=lambda run: contextlib.nullcontext(link),
                               show=0, keys=True)
    said = capsys.readouterr().out
    assert n == 2 and "global:0x0123" in said
    nowhere((said,), UNKNOWN, UNKNOWN2)
    import runner
    assert runner.values_withheld(True) == {"show": 0, "keys": True} and runner.values_withheld(False) == {}
    assert runner.changes_kept(changes, False) == [{"key": "global:0x0123"}, {"key": "set1:0x0456"}]
    assert runner.changes_kept(changes[:1], True) == [{"key": "global:0x0123", "before": UNKNOWN, "after": UNKNOWN2}]


def test_drive_says_and_keeps_the_records_by_key_alone_on_a_network_run(tmp_path, monkeypatch, scope_file, capsys):
    """drive.py on a --network run: the session's end and the restore's check are given show=0 and keys, and
    drive.jsonl keeps the records that differ by key alone, never a before or an after."""
    change = SimpleNamespace(key="global:0x0123", before=UNKNOWN, after=UNKNOWN2)
    pressed, seen, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "menu"], ("Bluetooth Function",),
                                             RMT, ["Bluetooth Function", "On", "Off"], "list",
                                             page_lit="Bluetooth Function", open_lit="On", changes=[change])
    assert seen["ended"] == {"show": 0, "keys": True} and seen["checked"] == {"show": 0, "keys": True}
    assert line["changes"] == [{"key": "global:0x0123"}]
    nowhere((json.dumps(line), logged, capsys.readouterr().out), UNKNOWN, UNKNOWN2)


def test_prove_run_puts_its_start_file_back_saying_the_records_by_key_alone_on_a_network_run(tmp_path, monkeypatch):
    """prove_run.put_start_back on a --network run: the restore's check is given show=0 and keys."""
    import prove_run as P
    got = []
    monkeypatch.setattr(P, "Link", lambda run: contextlib.nullcontext(SimpleNamespace(
        download=lambda tag: tmp_path / f"{tag}.DAT", press=lambda *a, **k: None, upload=lambda f: "uploaded")))
    monkeypatch.setattr(P, "to_shooting", lambda *a, **k: None)
    monkeypatch.setattr(P.screen, "read", lambda f: SimpleNamespace(kind="shooting"))
    monkeypatch.setattr(P.camset, "read", lambda f: SimpleNamespace())
    monkeypatch.setattr(P.camset, "diff", lambda a, b: [SimpleNamespace(key="global:0x0123", before=UNKNOWN, after=UNKNOWN2)])
    monkeypatch.setattr(P, "verify_restore", lambda run, ref, **kw: got.append(kw) or 0)
    eyes = SimpleNamespace(attach=lambda link: None, grab=lambda save=False: None)
    with contextlib.redirect_stdout(io.StringIO()) as out:
        assert P.put_start_back(SimpleNamespace(), eyes, tmp_path / "start.DAT", True)
        assert P.put_start_back(SimpleNamespace(), eyes, tmp_path / "start.DAT")
    assert got == [{"show": 0, "keys": True}, {}] and UNKNOWN not in out.getvalue()


def test_a_blocker_notice_keeps_its_rows_label_never_its_state_in_drive(tmp_path, monkeypatch, scope_file, capsys):
    """drive.py: a greyed row's blocker notice ("... not available as follows Airplane Mode Engaged", Engaged one of the
    values the definition gives Airplane Mode) keeps the blocking row's label, never its state."""
    pressed, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "menu"], ("Bluetooth Function",),
                                          RMT, [FOLLOWS, f"Airplane Mode {ENGAGED}", "OK"], "notice",
                                          page_lit="Bluetooth Function", open_lit="OK", definition=STATE_DEFINITION)
    assert line["screens"][0]["notice"] == f"{FOLLOWS} Airplane Mode"
    nowhere((capsys.readouterr().out, json.dumps(line), logged), ENGAGED)


def test_drive_keeps_a_lists_options_only_as_the_definitions_whole_set(tmp_path, monkeypatch, scope_file, capsys):
    """drive.py: a list's option names are the definition's for the row (never the page model's, which hold the value
    the camera showed at the scan), kept only where the screen shows that whole set; a set short of it keeps the count
    alone."""
    model = {"p": {"breadcrumb": "Network > Bluetooth", "rows": [{"label": "Bluetooth Function", "value": UNKNOWN}]}}
    for lines, kept in ((["Bluetooth Function", KNOWN_A, KNOWN_B], {"options": [KNOWN_A, KNOWN_B]}),
                        (["Bluetooth Function", KNOWN_A], {"option_count": 1})):
        pressed, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "menu"],
                                              ("Bluetooth Function",), RMT, lines, "list", page_lit="Bluetooth Function",
                                              open_lit=KNOWN_A, model=model, definition=BT_DEFINITION)
        first = line["screens"][0]
        assert {k: first[k] for k in ("options", "option_count") if k in first} == kept, first
        nowhere((capsys.readouterr().out, json.dumps(line), logged), UNKNOWN)
        if "option_count" in kept:
            assert KNOWN_A not in json.dumps(line)


def test_a_refusal_that_is_no_rows_own_stops_the_walk_on_the_camera(tmp_path, monkeypatch):
    """The reviewer's probe, on camkit.live.LiveCamera: a decided row's look-only lock still on, the walk's Right on the
    next row ("Drive Mode") is refused by the lock (safety.Refused), never skipped as the row's own refusal; a lit row
    the run may not open (safety.RowRefused) is skipped, nothing sent."""
    cam = inside_camera(tmp_path, monkeypatch, **WIRED)
    assert cam.network_open is not None
    sent = list(cam.link.sent)
    with pytest.raises(safety.Refused) as e:
        crawl.visit_row(cam, cam.read(), {"page": "Shooting > Drive"}, 1, {"label": "Drive Mode"})
    assert not isinstance(e.value, safety.RowRefused) and cam.link.sent == sent
    cam = camera(tmp_path, page="menu")
    cam.presses, cam._seen = 0, cam._moves()
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Format")
    r = crawl.visit_row(cam, cam.read(), {"page": "Shooting > Media"}, 0, {"label": "Drive Mode"})
    assert r.outcome.startswith("skipped: refused (") and cam.link.sent == []
    with pytest.raises(safety.RowRefused):
        cam.press("right")
    # a lit row no reader can read is the row's own refusal too (LiveCamera.unread_row)
    monkeypatch.setattr(live, "reader_label", lambda path: ("", "no row marked"))
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    with pytest.raises(safety.RowRefused):
        cam.unread_row("right")


def test_the_jump_sends_no_right_on_a_group_it_did_not_read_after_its_moves(monkeypatch):
    """crawl_run.jump: after the Downs in the group column, the group reached must be read as the one meant; one that
    cannot be read (nor on a second look or the camera's own picture) gets no Right."""
    import crawl_run
    monkeypatch.setattr(crawl_run.time, "sleep", lambda s: None)
    monkeypatch.setattr(crawl_run, "osd_lit", lambda c: "")
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "Bluetooth", "Wired LAN"], ["Wi-Fi", "Bluetooth", "Wired LAN"])
    cam.focus = "rows"
    real = cam.lit
    cam.lit = lambda: "" if (cam.focus, cam.group) == ("groups", 2) else real()
    assert crawl_run.jump(cam, cycle, crawl_run.page_groups(cycle, model), 5, model) is None
    assert cam.rights == [] and cam.keys == ["left", "left", "right", "down", "down"]


def test_a_tail_none_knows_makes_no_other_label_and_the_rows_own_readings_are_its_own():
    """safety.network_lifted_row with no value known: the lit bar with its tail is no other label the kit knows, nor
    the start of one (other_label); the readings the page model keeps of the decided row itself are no other label."""
    rows = decided({**DECISION, "rows": ["Wi-Fi Connect"]})
    labels = {"Wi-Fi Connect", "Wi-Fi Connect Settings", "Drive Mode"}
    lift = lambda lit, **kw: safety.network_lifted_row(lit, rows, values={}, labels=labels, **kw)   # noqa: E731
    assert lift("Wi-Fi Connect On") == "Wi-Fi Connect"
    assert lift("Wi-Fi Connect Settings") is None and lift("Wi-Fi Connect Sett") is None
    assert safety.other_label("Wi-Fi Connect Sett", labels, {"wi-fi connect"}) == "Wi-Fi Connect Settings"
    # a bar that begins with another, longer label, a value after it: that row's, never the decided row's
    for lit in ("Wi-Fi Connect Settings On", "Wi-Fi Connect Settings  Auto"):
        assert safety.network_lifted_row(lit, rows, values={"Wi-Fi Connect": []},
                                         labels={"Wi-Fi Connect", "Wi-Fi Connect Settings"}) is None, lit
    assert safety.network_lifted_row("Wi-Fi Connect Auto", rows, values={"Wi-Fi Connect": []},
                                     labels={"Wi-Fi Connect", "Wi-Fi Connect Settings"}) == "Wi-Fi Connect"
    rows = decided({**DECISION, "rows": ["Wired LAN Connect"]})
    own = {"Wired LAN Connect": read_on("Wired LAN", "Wired LAN Connect", "Wired LAN Connect Manual")}
    labels = {"Wired LAN Connect", "Wired LAN Connect Manual"}
    assert safety.network_lifted_row("Wired LAN Connect  Manual", rows, values={}, labels=labels) is None
    assert safety.network_lifted_row("Wired LAN Connect  Manual", rows, values={}, labels=labels,
                                     readings=own) == "Wired LAN Connect"


def test_runner_label_readings_holds_every_label_and_reading(made_up_definition):
    import runner
    model = {"p": {"rows": [{"label": "LANIP Address Setting", "readings": {"label": {"vlm": "IP Address Setting"}}}]}}
    got = runner.label_readings(model)
    assert {"LANIP Address Setting", "IP Address Setting", "Subject Pick", "Depth Level"} <= got


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_tighten_never_follows_a_symbolic_link_out_of_the_run(tmp_path):
    """camkit.runs.Run.tighten: a symbolic link in a private run's folder is left as it is, and the file it names, out
    of the run, keeps its mode."""
    import os
    import stat
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    os.chmod(outside, 0o644)
    run = Run("kit2_link", root=tmp_path / "runs")
    (run.dir / "link.txt").symlink_to(outside)
    run.make_private()
    assert stat.S_IMODE(outside.stat().st_mode) == 0o644 and run.seal() == []


def test_find_row_says_no_bar_text_on_a_network_or_owner_run(monkeypatch, capsys):
    """proving.nav.find_row: the closest reading it goes to is said as withheld on a run asking local readers only
    (camkit.vlm.LOCAL_ONLY: --network, --owner), as read otherwise."""
    from camkit import vlm
    from proving import nav
    cam = SimpleNamespace(read=lambda: SimpleNamespace(kind="submenu"), press=lambda key: None)
    monkeypatch.setattr(nav, "at_label", lambda cam, kind, label: False)
    monkeypatch.setattr(nav, "same_state", lambda a, b: True)
    monkeypatch.setattr(nav, "closest_row", lambda texts, label: 0)
    monkeypatch.setattr(nav, "bar_text", lambda cam: f"Row {UNKNOWN}")
    for local, shown in ((True, False), (False, True)):
        monkeypatch.setattr(vlm, "LOCAL_ONLY", local)
        assert nav.find_row(cam, "Row") is True
        said = capsys.readouterr().out
        assert "row 'Row' reads" in said and (UNKNOWN in said) is shown, local


# ---------------------------------------------------------------- the third look of 2026-11-14: what it showed to mend

# The Network tab's groups as a page scan stores them: the scan read Cnct./Remote Sht.'s icon glyph as "[" and FTP
# Transfer one letter off ("FTP Transter"); the group column's lit bar shows them otherwise, glyph and all
THIRD_SCANNED = ["Wi-Fi", "[Cnct./Remote Sht.", "FTP Transter", "Wired LAN"]


@pytest.mark.parametrize("drawn", ["[Cnct./Remote Sht.", "0Cnct./Remote Sht.", "(Cnct./Remote Sht."])
def test_the_jump_reads_the_lit_group_whole_whatever_glyph_the_bar_draws(monkeypatch, drawn):
    """crawl_run.jump judges the group column's lit bar as from_groups does (group_near: its letters and digits, whole,
    equal or one letter apart, exactly one group): a bar read with another icon glyph than the scan stored, or with a
    glyph where the scan read none, is the same group, where group_shown, wanting the scan's text, read none and the
    jump pressed nothing more (item 1)."""
    import crawl_run
    monkeypatch.setattr(crawl_run.time, "sleep", lambda s: None)
    monkeypatch.setattr(crawl_run, "osd_lit", lambda c: "")
    shown = ["Wi-Fi", drawn, "FTP Transfer", "Wired LAN"]
    # the column opens on the group of the page the jump left (Cnct./Remote Sht.), and steps down to Wired LAN
    cam, cycle, model = columns(monkeypatch, THIRD_SCANNED, shown, at=1)
    cam.focus = "rows"
    assert crawl_run.jump(cam, cycle, crawl_run.page_groups(cycle, model), 6, model) == 6
    assert cam.keys == ["left", "left", "right", "down", "down", "right"] and cam.rights == ["Wired LAN"]
    # it opens on FTP Transfer (the scan's "FTP Transter") and steps up to the glyph-drawn group: Right into it
    cam, cycle, model = columns(monkeypatch, THIRD_SCANNED, shown, at=2)
    cam.focus = "rows"
    assert crawl_run.jump(cam, cycle, crawl_run.page_groups(cycle, model), 2, model) == 2
    assert cam.keys == ["left", "left", "right", "up", "right"] and cam.rights == [drawn]
    assert crawl_run.lit_group(cam, THIRD_SCANNED, lambda: drawn) == 1


def test_the_jump_still_refuses_what_it_cannot_tell_and_rechecks_the_column_before_its_right(monkeypatch):
    """jump, judging the bar whole: a bar naming no group of the tab, or two, presses nothing more; a group the column
    never enters is refused on the lit text (group_refused); and the screen read as the rows after the Downs gets no
    Right (the kind and focus checked again just before it, as from_groups does)."""
    import crawl_run
    monkeypatch.setattr(crawl_run.time, "sleep", lambda s: None)
    monkeypatch.setattr(crawl_run, "osd_lit", lambda c: "")
    for drawn in ("Cnct./Remote Sht. Wi-Fi", "Remote"):
        cam, cycle, model = columns(monkeypatch, THIRD_SCANNED, ["Wi-Fi", drawn, "FTP Transfer", "Wired LAN"], at=1)
        cam.focus = "rows"
        assert crawl_run.jump(cam, cycle, crawl_run.page_groups(cycle, model), 6, model) is None
        assert "down" not in cam.keys and cam.rights == []
    # the target group drawn as the never-open action it is one letter from: no Right
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "[Cnct./Remote Sht.", "Wired LAN"],
                                ["Wi-Fi", "(Cnct./Remote Sht.", "FTP Transfer"], at=1)
    cam.focus = "rows"
    assert crawl_run.jump(cam, cycle, crawl_run.page_groups(cycle, model), 4, model) is None and cam.rights == []
    # after the Down the screen reads as a page of rows, its bar the very group meant: no Right
    cam, cycle, model = columns(monkeypatch, THIRD_SCANNED, ["Wi-Fi", "(Cnct./Remote Sht.", "FTP Transfer", "Wired LAN"],
                                at=2, misfocus={"down": "Wired LAN"})
    cam.focus = "rows"
    assert crawl_run.jump(cam, cycle, crawl_run.page_groups(cycle, model), 6, model) is None
    assert cam.keys == ["left", "left", "right", "down"] and cam.rights == []


def test_the_crawl_steps_out_of_the_group_column_the_menu_reopened_in(monkeypatch, capsys):
    """crawl_run.crawl_from_menu finds where the menu opened as find_position does (item 2): a menu reopened with the
    cursor in the group column, on the group a refused jump left it on, is stepped into a group it may enter
    (from_groups) and the lap crawls from there, where before the crawl stopped at once (a screen the scan does not
    know, exit status 8)."""
    import crawl_run
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "FTP Transter", "Wired LAN"], ["Wi-Fi", "FTP Transfer", "Wired LAN"],
                                at=1)
    link = SimpleNamespace(press=lambda key, cleanup=False: cam.keys.append(f"link {key}"))
    began = []

    def fake(cam, cycle, model, **kw):
        began.append(cycle[0]["page"])
        return SimpleNamespace(stopped="", presses=0, rows=[], recoveries=[])
    monkeypatch.setattr(crawl_run, "crawl", fake)
    assert crawl_run.crawl_from_menu(cam, link, cycle, model, None, io.StringIO()) is True
    assert began == ["p0"] and cam.rights == ["Wi-Fi"] and cam.keys[:3] == ["menu", "up", "right"]
    assert "a screen the scan does not know" not in capsys.readouterr().out
    # every group of the tab refused: nothing pressed in the column, the lap not begun (the run exits 8, as before)
    cam, cycle, model = columns(monkeypatch, ["FTP Transter"], ["FTP Transfer"], at=0)
    link = SimpleNamespace(press=lambda key, cleanup=False: None)
    assert crawl_run.crawl_from_menu(cam, link, cycle, model, None, io.StringIO()) is False and cam.rights == []


# The Wired LAN page's IP Address Setting as the a1 II's page scan stored it (2026-11-14), in made-up text of the same
# shape, Wired LAN Connect standing in for it (no decision opens IP Address Setting since 2026-11-14): its icon read as
# three capitals, set apart by a space in one OCR reading and glued on in the other, the vision reader's reading the
# label exactly; its value one word. The lit bar, read live with the row lit, shows the icon with a letter misread and
# set apart by a space, or with a letter dropped and glued on, then the label and the value
ICON_VALUE = "Madeup"
ICON_ROW = {"label": "LANWired LAN Connect", "value": ICON_VALUE,
            "readings": {"label": {"ocr": "LAN Wired LAN Connect", "ocr2": "LANWired LAN Connect",
                                   "vlm": "Wired LAN Connect"},
                         "value": {"ocr": ICON_VALUE, "ocr2": ICON_VALUE, "vlm": ICON_VALUE}}}
ICON_BARS = [f"LAH Wired LAN Connect {ICON_VALUE}", f"LAWired LAN Connect {ICON_VALUE}"]
ICON_LABEL = "Wired LAN Connect"


def icon_model(row=None, group="Wired LAN"):
    return {"p": {"breadcrumb": f"Network > {group}", "rows": [{"label": "IP Address Setting"}, row or ICON_ROW]}}


def icon_checks(model, known_value=True):
    """(the decided rows, values, readings, labels) for Wired LAN Connect on the page model `model`, as kit/drive.py
    and kit/crawl_run.py give them to the checks (runner.network_values, network_readings, label_readings); with no
    value known for the row where known_value is False."""
    import runner
    rows = decided({**DECISION, "rows": [ICON_LABEL]})
    values = runner.network_values(rows, model) if known_value else {}
    return rows, values, runner.network_readings(rows, model), runner.label_readings(model)


@pytest.mark.parametrize("bar", ICON_BARS)
@pytest.mark.parametrize("known_value", [True, False])
def test_a_row_opens_on_its_live_bar_its_icon_read_otherwise(tmp_path, monkeypatch, bar, known_value):
    """Item 3 (seen on IP Address Setting, Wired LAN Connect standing in): the lit bar of the row, read live, shows the
    page's icon with a letter misread and set apart, or a letter dropped and glued on, which no reading of the page
    model holds. go_to's arrival check, drive.py's press check, LiveCamera's opening and its release after MENU take it
    for the row (safety.bar_heads, icon_slip), with its value known or not, where before each refused it."""
    import crawl_run
    import drive as D
    model = icon_model()
    rows, values, readings, labels = icon_checks(model, known_value)
    assert [readings[ICON_LABEL][0]["group"]] == ["Wired LAN"] and (values.get(ICON_LABEL) == [ICON_VALUE]) is known_value
    # go_to: found by the vision reader's reading, its arrival judged on the live bar
    cam, cycle, gmodel = columns(monkeypatch, ["Wi-Fi", "Wired LAN"], ["Wi-Fi", "Wired LAN"])
    cam.focus = "rows"
    gmodel["p1"]["rows"][1] = ICON_ROW
    real = cam.lit
    cam.lit = lambda: bar if (cam.focus, cam.group, cam.row) == ("rows", 1, 1) else real()
    assert crawl_run.go_to(cam, cycle, gmodel, 0, ICON_LABEL) == 3
    # drive.py's press check
    assert D.press_refused("right", bar, "", "menu", network=rows, values=values, readings=readings, labels=labels) == ""
    assert safety.network_lifted_row(bar, rows, False, values, readings, labels) == ICON_LABEL
    # LiveCamera: its opening, then MENU back on the page with the bar on the row ends the lock
    cam = camera(tmp_path, rows, values=values, page="menu")
    cam.readings, cam.labels = readings, labels
    cam.hdmi = InsideCamera(tmp_path, monkeypatch, "list", "On Off", "inside")
    cam.presses, cam._seen = 0, cam._moves()
    monkeypatch.setattr(live, "lit_text", lambda image, path: bar)
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    cam.press("right")
    assert cam.network_open is not None and cam.network_open["row"] == ICON_LABEL
    cam.hdmi.shows("menu", PAGE)
    cam.press("menu")
    assert cam.network_open is None and events(cam)[-1]["kind"] == "network_row_left"
    # drive.py's own release: MENU, then the page it was opened from with the bar on the row
    page = SimpleNamespace(kind="menu", where=PAGE)
    monkeypatch.setattr(D, "same_position", lambda a, b: a.where == b.where)
    assert D.network_left(page, page, True, bar, ICON_LABEL, readings=readings, labels=labels)


def test_the_live_icon_keeps_every_condition_of_the_glued_one():
    """What icon_slip and bar_heads take is only the row's own icon as the page model read it glued on (a word of its
    page's group, every reading of the row of its class, a reader reading the label exactly), read with one letter
    misread, dropped or put in, naming nothing, forming no other label the kit knows; and only where the labels are
    given."""
    model = icon_model()
    rows, values, readings, labels = icon_checks(model)

    def lift(bar, readings=readings, labels=labels):
        return safety.network_lifted_row(bar, rows, False, values, readings, labels) == ICON_LABEL
    assert all(lift(bar) for bar in ICON_BARS)
    for bar in (f"LXY Wired LAN Connect {ICON_VALUE}",          # two letters off the icon
                f"No Wired LAN Connect {ICON_VALUE}",           # a word set before the label, no icon of it
                f"L Wired LAN Connect {ICON_VALUE}",            # a single letter
                "LAH Wired LAN Connect Other",                  # a value it does not know, its values known
                f"LAH Wired LAN Connects {ICON_VALUE}",         # not the label after the icon
                f"LAHH Wired LAN Connect {ICON_VALUE}"):        # two letters put in
        assert not lift(bar), bar
    assert not lift(ICON_BARS[0], labels=None) and not safety.bar_on_row(ICON_BARS[0], ICON_LABEL, readings)
    assert safety.bar_on_row(ICON_BARS[0], ICON_LABEL, readings, labels)

    def unknown(bar):
        """the row lifted with no value of it known: a short tail naming nothing takes the value's place"""
        return safety.network_lifted_row(bar, rows, False, {}, readings, labels) == ICON_LABEL
    # nothing alphanumeric right after the label (bar_heads): "Connects" is no Wired LAN Connect and a value
    assert unknown("LAN Wired LAN Connect") and unknown(f"LAH Wired LAN Connect {ICON_VALUE}")
    assert not unknown("LAN Wired LAN Connects") and not unknown(f"LAH Wired LAN Connects {ICON_VALUE}")
    assert not safety.bar_on_row("LAN Wired LAN Connects", ICON_LABEL, readings, labels)
    # exactly one space between the icon and the label, the icon one word: a letter set apart is no icon
    for bar in ("l an Wired LAN Connect", f"l an Wired LAN Connect {ICON_VALUE}", f"la n Wired LAN Connect {ICON_VALUE}"):
        assert not unknown(bar) and not lift(bar) and not safety.bar_on_row(bar, ICON_LABEL, readings, labels), bar
    # each of icon_slip's two class checks on its own (made-up rows of a Wi-Fi or Bluetooth setting): the prefix set
    # apart before the label forms an identity row that stays closed ("access Point": Access Point), glued on it does
    # not; glued on, the prefix forms one ("wpS": WPS), set apart it does not
    assert safety.lift_class("Point Wi-Fi Connect") == safety.lift_class("S Bluetooth Function") == safety.LIFT_NETWORK
    assert safety.lift_class("access Point Wi-Fi Connect") is None and safety.lift_class("wpS Bluetooth Function") is None
    assert safety.lift_class("wp S Bluetooth Function") == safety.LIFT_NETWORK
    assert not safety.icon_slip("access", "Point Wi-Fi Connect", {"access"})
    assert not safety.icon_slip("wp", "S Bluetooth Function", {"wps"})
    # another label the kit knows formed by the bar: refused
    assert not lift(ICON_BARS[0], labels=labels | {"LAH Wired LAN Connect"})
    # the icon the page model never read glued on (only set apart), nor on a page of a group naming no such word, nor
    # with a reading of the row of another class beside it: no icon of the row at all
    spaced = {**ICON_ROW, "label": "Wired LAN Connect",
              "readings": {"label": {"ocr": "LAN Wired LAN Connect", "vlm": "Wired LAN Connect"}}}
    other = {**ICON_ROW, "readings": {"label": {**ICON_ROW["readings"]["label"], "ocr3": "Format"}}}
    for m in (icon_model(spaced), icon_model(group="Wi-Fi Option"), icon_model(other)):
        _, _, r, lab = icon_checks(m)
        assert safety.row_icons(ICON_LABEL, r) == set() and not lift(ICON_BARS[0], readings=r, labels=lab), m
    assert safety.row_icons(ICON_LABEL, readings) == {"lan"}
    # the icon read with a letter misread may name nothing the never-open list or identity holds
    assert safety.icon_slip("pip", ICON_LABEL, {"pin"}) and not safety.icon_slip("pin", ICON_LABEL, {"pip"})
    assert not safety.icon_slip("la", ICON_LABEL, {"wi"}) and not safety.icon_slip("wo", ICON_LABEL, {"wi"})   # a short icon
    # no word before the label of a row whose page model read no icon: "No Wi-Fi Connect" as ever
    wifi = decided({**DECISION, "rows": ["Wi-Fi Connect"]})
    assert safety.network_lifted_row("No Wi-Fi Connect On", wifi, values=VALUES, labels=set()) is None


def test_drive_says_the_row_it_could_not_reach_and_exits_incomplete(tmp_path, monkeypatch, scope_file, capsys):
    """Items 4 and 7: a --network run whose first --path label the scan does not reach sends none of its presses,
    names the decided row as the run was given it (its own argument, where before it said "could not reach
    '(withheld)'"), restores its start file and, once that checks out, exits EXIT_INCOMPLETE (8), where before it exited
    0; nothing it read off the screen is said."""
    import runner
    exits = []
    pressed, seen, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "menu"], (ICON_LABEL,),
                                             {**DECISION, "rows": [ICON_LABEL]}, ["On", "Off"], "list",
                                             page_lit=f"LAH Wired LAN Connect {UNKNOWN}", open_lit="Off",
                                             page_kind="menu", reach=False, exits=exits)
    out = capsys.readouterr().out
    assert exits == [runner.EXIT_INCOMPLETE] == [8] and pressed == ["menu"] and line["completed"] is False
    assert f"could not reach {ICON_LABEL!r} by the scan" in out and "'(withheld)'" not in out
    assert "exit status 8" in out and "checked" in seen and line["screens"] == []
    nowhere((out, json.dumps(line), logged), UNKNOWN)
    # reached, the same run ends 0, as ever
    exits = []
    drive_fake(tmp_path, monkeypatch, scope_file, ["menu"], (ICON_LABEL,), {**DECISION, "rows": [ICON_LABEL]}, ["On"], "list",
               page_lit="Wired LAN Connect", open_lit="On", page_kind="menu", exits=exits)
    assert exits == []


# the polling target's path as the link's command quotes it, a placeholder home folder (2026-11-14: the closing lines
# printed the real one)
FRAME_PATH = '"/Users/you/camset/runs/TEST-CAM_fw9.99/kit2_drive/_live.png"'
LINK_GONE = f"osd {FRAME_PATH}: camera link exited"


def test_a_private_runs_closing_lines_withhold_what_its_first_error_line_withholds(monkeypatch, capsys):
    """2026-11-14: a --network run's first error line withheld the OSD frame's path, a quoted argument of the link's
    command, and its closing lines printed it whole, home folder and all. camkit.live.close, runner.close_for_restore,
    runner.restoring and runner.end_session withhold an error's quoted texts on a --network or --owner run; on any other
    run they print it as before."""
    import runner
    from camkit.link import LinkError

    def gone(*a, **k):
        raise LinkError(LINK_GONE)

    def cam_of(**kw):
        return SimpleNamespace(cancel_to_menu=gone, refresh=lambda tag: SimpleNamespace(kind="unknown"), read=gone, **kw)
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    link = SimpleNamespace(press=lambda *a, **k: None)
    for cam, hidden in ((cam_of(network={"Bluetooth Function": DAY}), True), (cam_of(owner={"Format": {}}), True),
                        (cam_of(network={}, owner={}), False)):
        with pytest.raises(SystemExit):
            live.close(cam, link)                        # each try's line, then it gives up
        out = capsys.readouterr().out
        assert out.count("closing: ") == 8 and ("/Users/you" in out) is not hidden and ("'(withheld)'" in out) is hidden
        # close_for_restore: the close gives up and the last screen cannot be read (the link gone): no restore, exit 4
        monkeypatch.setattr(runner, "close", lambda c, lk: (_ for _ in ()).throw(SystemExit("could not get back")))
        with pytest.raises(SystemExit) as e:
            runner.close_for_restore(cam, link)
        out = capsys.readouterr().out
        assert e.value.code == runner.EXIT_UNRESTORED and "cannot be read" in out and "did not finish" in out
        assert ("/Users/you" in out) is not hidden and ("'(withheld)'" in out) is hidden, out
        monkeypatch.setattr(runner, "close", gone)    # the close fails outright: said, and the restore goes on
        runner.close_for_restore(cam, link)
        out = capsys.readouterr().out
        assert "restoring all the same" in out and ("/Users/you" in out) is not hidden, out
    for withhold in (True, False):
        with pytest.raises(SystemExit) as e, runner.restoring("the restore", withhold=withhold):
            gone()
        out = capsys.readouterr().out
        assert e.value.code == runner.EXIT_UNRESTORED and ("/Users/you" in out) is not withhold, out
    # end_session: keys (a --network or --owner run, values_withheld) withholds its reach's error too
    monkeypatch.setattr(runner.session, "finish", lambda *a, **k: "finished")
    for kw, hidden in ((runner.values_withheld(True), True), ({}, False)):
        assert runner.end_session(link, None, Path("start.DAT"), "the end", reach=gone, **kw) == "finished"
        out = capsys.readouterr().out
        assert "restoring all the same" in out and ("/Users/you" in out) is not hidden, out


def test_drive_keeps_a_result_line_when_its_restore_does_not_finish(tmp_path, monkeypatch, scope_file, capsys):
    """2026-11-14: drive.py's unrestored exit (status 4) left drive.jsonl empty. It keeps a result line saying the run
    did not finish and was not restored, with what it was asked and no screen at all; its closing lines withhold the
    link's quoted path as its first error line does."""
    import drive as D
    import runner
    from camkit.link import LinkError
    exits = []
    _, _, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "menu"], ("Bluetooth Function",),
                                    RMT, RMT_LIST, "list", page_lit="Bluetooth Function  On", open_lit="Off",
                                    exits=exits, end_raises=LinkError(LINK_GONE))
    out = capsys.readouterr().out
    assert exits == [runner.EXIT_UNRESTORED] == [4]
    assert line["restore"] == "not finished" and line["outcome"] == D.UNFINISHED and line["after"] is None
    assert line["path"] == ["Bluetooth Function"] and line["network"] == {"Bluetooth Function": DAY}
    assert "screens" not in line and "changes" not in line and line["before"].endswith(".DAT")
    assert "did not finish" in out and "'(withheld)'" in out
    for where in (out, json.dumps(line), logged):
        assert "/Users/you" not in where


def test_the_navigation_says_no_length_of_what_it_withholds(monkeypatch, capsys):
    """Item 6: on a --network or --owner run crawl_run.said prints nothing of a text read off the screen, not even its
    length (which can tell a row's options apart); without either, the text as before."""
    import crawl_run
    text = f"Wi-Fi Connect {UNKNOWN}"
    for cam in (SimpleNamespace(network={"Wi-Fi Connect": DAY}), SimpleNamespace(owner={"Format": {}}),
                SimpleNamespace(network={"Wi-Fi Connect": DAY}, owner={})):
        assert crawl_run.said(cam, text) == crawl_run.TEXT_WITHHELD
        assert not any(ch.isdigit() for ch in crawl_run.said(cam, text)) and "characters" not in crawl_run.said(cam, text)
    assert crawl_run.said(SimpleNamespace(network={}, owner={}), text) == repr(text)
    cam, cycle, model = columns(monkeypatch, ["Wi-Fi", "Bluetooth"], [f"ILCE-made-up {IP}", "Bluetooth"])
    cam.owner = {"Format": {}}
    assert crawl_run.find_position(cam, cycle, model) is None
    out = capsys.readouterr().out
    assert "withheld" in out and "characters" not in out and "ILCE-made-up" not in out


def test_a_withheld_screen_keeps_a_letter_or_two_only_as_a_row_label_of_its_own_page(tmp_path, monkeypatch, scope_file):
    """Item 6: the definition has a row labelled "B" (a Picture Profile's Color Depth row, made up here); a withheld
    screen keeps a line of a letter or two only where it is a row label of the scan page shown (drive.page_labels, the
    page model's rows of that page: safety.screen_fields' page), never because the definition has it somewhere."""
    import drive as D
    labels = {"B", "Drive Mode", "Bluetooth Function"}
    assert safety.screen_fields(["B", "Drive Mode"], labels)[0] == ["Drive Mode"]
    assert safety.screen_fields(["B", "Drive Mode"], labels, page=["B", "Drive Mode"])[0] == ["B", "Drive Mode"]
    assert safety.kept_screen("menu", ["B", "Drive Mode"], labels)["fields"] == ["Drive Mode"]
    assert safety.kept_screen("menu", ["B", "Drive Mode"], labels, page=["B"])["fields"] == ["B", "Drive Mode"]
    assert safety.screen_fields(["B"], set(), page=["B"])[0] == []        # on the page, but no label the kit knows
    # drive.page_labels: the page model's row labels of the scan page the screen is, none elsewhere
    cycle = [{"page": "p1", "screen": SimpleNamespace(where="one")}, {"page": "p2", "screen": SimpleNamespace(where="two")}]
    model = {"p1": {"rows": [{"label": "B"}, {"label": "Drive Mode"}]}, "p2": {"rows": [{"label": "Zoom"}]}}
    monkeypatch.setattr(D, "same_position", lambda a, b: a.where == b.where)
    assert D.page_labels(SimpleNamespace(where="one"), cycle, model) == ["B", "Drive Mode"]
    assert D.page_labels(SimpleNamespace(where="inside"), cycle, model) == []
    # drive.py on its own: a page line "B" the definition names as some other page's row is withheld
    definition = {"menu": [{"tab": "Network", "group": "Bluetooth", "label": "Bluetooth Function"},
                           {"tab": "Exposure/Color", "group": "Color Depth", "label": "B"}], "settings": []}
    pressed, _, line, _ = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "menu"], ("Bluetooth Function",),
                                     DECISION, ["On", "Off"], "list", page_lit="Bluetooth Function  On", open_lit="On",
                                     page_lines=["B", "Bluetooth", "Bluetooth Function"], definition=definition)
    page_screens = [s for s in line["screens"] if s["kind"] == "submenu"]
    assert page_screens and all("B" not in s["fields"] for s in page_screens), line["screens"]
    assert all("Bluetooth Function" in s["fields"] for s in page_screens)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_a_tool_writes_owner_only_into_a_folder_a_network_run_marked(own_runs, monkeypatch):
    """Item 5: kit/pass1_labels.py wrote options.jsonl 0644 into a run folder the --network run had sealed owner-only.
    A tool that writes into a run folder carrying the LOCAL_ONLY (or NO_READER) marker makes the process write
    owner-only and the folder owner-only (camkit.runs.private_if_marked, Run.make_private's helpers): options.jsonl
    0600, one left from before tightened too; a folder without the marker as ever."""
    import os
    import stat

    import pass1_labels
    from camkit import runs, vlm
    run = Run("kit2_net", root=own_runs / TEST_CAMERA)
    (run.dir / "rows.jsonl").write_text(json.dumps({"label": "Drive Mode", "frames": []}) + "\n", encoding="utf-8")
    vlm.mark_local_only(run.dir)
    (run.dir / "options.jsonl").write_text("", encoding="utf-8")
    os.chmod(run.dir / "options.jsonl", 0o644)
    os.chmod(run.dir, 0o755)
    for name, value in (("readers", lambda stop=False: [{"name": "local"}]), ("role", lambda name: {"parallel": 1}),
                        ("make_reader", lambda cfg, **kw: SimpleNamespace(ask=lambda b, p: {})),
                        ("read_frames", lambda frames: ({}, {}))):
        monkeypatch.setattr(pass1_labels, name, value)
    monkeypatch.setattr(sys, "argv", ["pass1_labels.py", str(run.dir)])
    pass1_labels.main()
    assert stat.S_IMODE((run.dir / "options.jsonl").stat().st_mode) == 0o600
    assert stat.S_IMODE(run.dir.stat().st_mode) == 0o700 and runs.UMASK_FLOOR == 0o077
    # a file written new after it is owner-only too
    (run.dir / "later.json").write_text("{}", encoding="utf-8")
    assert stat.S_IMODE((run.dir / "later.json").stat().st_mode) == 0o600
    # NO_READER marks a folder alike; one with neither is left as it is
    held = Run("kit2_owner", root=own_runs / TEST_CAMERA)
    vlm.mark_no_reader(held.dir)
    plain_run = Run("kit2_plain", root=own_runs / TEST_CAMERA)
    (plain_run.dir / "options.jsonl").write_text("", encoding="utf-8")
    os.chmod(plain_run.dir / "options.jsonl", 0o644)
    assert runs.private_if_marked(held.dir / "shots", plain_run.dir) == [held.dir.resolve()]
    assert stat.S_IMODE((plain_run.dir / "options.jsonl").stat().st_mode) == 0o644
