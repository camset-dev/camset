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
    # the lit bar carries the row's value after its label: one of the row's known values, else nothing may follow
    assert live.open_refused("Bluetooth Function  On", network=rows, values=VALUES) == ""
    assert live.open_refused("Bluetooth Function", network=rows) == ""
    assert live.open_refused("Bluetooth Function  On", network=rows)                     # no value known
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
    with pytest.raises(RestoreAfter, match="saved option is not one the decision names"):
        P.prove_row(cam, link, run, job, tmp_path / "base.DAT", out)          # saved Off (1), named On (0) alone
    proofs = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [p["label"] for p in proofs] == ["On"] and cam.keys.count("enter") == 1
    assert proofs[0]["notice"]["fields"] == ["SSID"] and "text" not in proofs[0]["notice"]
    assert "DIRECT" not in out.getvalue() and "Pairing" not in out.getvalue()
    assert proofs[0]["network"] == safety.LIFT_IDENTITY             # no class given: kept as an identity row's
    out = io.StringIO()
    cam = ListCamera(tmp_path)
    P.prove_row(cam, link, run, {**job, "choose": [0, 1], "network_class": safety.LIFT_NETWORK}, tmp_path / "base.DAT",
                out)                                                 # both named: put back by OK
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
    assert D.press_refused("right", "Bluetooth Function  On", "", "submenu", network=rows)     # no value known
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
               open_lit, page_kind="submenu", slow=False, misread=(), misread_lit=False, menu_does="page"):
    """drive.py's main() on a made-up camera, no LiveCamera under it: the path's row lit (page_lit) on a page of
    page_kind until a Right or an Enter goes out, then a screen of open_kind showing open_lines, its lit bar open_lit;
    MENU, or Enter there, brings the page back, at the place it was (drive.same_position: the same kind at the same
    place). slow: the press that opens the row still shows the page after it (a camera slow to draw); misread: the keys
    after which the open screen reads as the page, at its very place, its bar still reading open_lit (page_lit with
    misread_lit, the worst case). menu_does, inside the row: "page" (MENU closes it), "ignored" (the camera ignores
    MENU), "list-as-page" (MENU closes a notice onto the row's list, which reads as the page, its bar on an option).
    Returns (the keys pressed, the console, drive.jsonl's line, the run's events)."""
    import drive as D
    from camkit import vlm
    scope_file(decision)
    run = Run("kit2_drive", root=tmp_path)
    sent, state = [], {"open": False, "shown": False, "misread": False}
    lines = {True: list(open_lines), False: ["Bluetooth", "Wi-Fi", page_lit]}        # the page, its row lit

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
            if state["misread"] or not state["shown"]:
                return SimpleNamespace(kind=page_kind, where=PAGE)
            return SimpleNamespace(kind=open_kind, where="inside")

        def press(self, key, **kw):
            sent.append(("cam", key))
            was = state["open"]
            if key == "menu" and was and menu_does == "ignored":
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
            return self.read()
    seen = {}

    def camera(link, eyes, r, **kw):
        seen["camera"] = kw
        return Cam()
    ending = SimpleNamespace(after=tmp_path / "after.DAT", changes=[], uploaded=False)
    for name, value in (("check_readers", lambda: seen.setdefault("local_only", vlm.LOCAL_ONLY)),
                        ("load_scan", lambda scan: ([], {})), ("Run", lambda name: run),
                        ("eyes_from_config", lambda r: SimpleNamespace(attach=lambda link: None, grab=lambda save=False: None,
                                                                       close=lambda: None)),
                        ("screen", SimpleNamespace(read=lambda f: SimpleNamespace(kind="shooting"))),
                        ("wait_for", lambda *a, **k: None), ("Link", Link),
                        ("LiveCamera", camera),
                        ("find_position", lambda cam, cycle, model: 0), ("go_to", lambda *a: True),
                        ("enter_any", lambda cam, path, i: None), ("bar_at", lambda cam, y: False),
                        ("screen_text", lambda cam, grip: " ".join(lines[state["shown"]])),
                        ("screen_lines", lambda cam, grip: list(lines[state["shown"]])),
                        ("highlighted", lambda image, path: page_lit if not state["shown"] or
                         (state["misread"] and misread_lit) else open_lit),
                        ("same_position", lambda a, b: a.kind == b.kind and a.where == b.where),
                        ("network_values", lambda rows, model: {r: v for r, v in VALUES.items() if r in rows}),
                        ("time", SimpleNamespace(sleep=lambda s: None)),
                        ("close_for_restore", lambda cam, link: sent.append(("closed",))),
                        ("session", SimpleNamespace(ended=lambda link, before, show=30: ending,
                                                    put_back=lambda link, e, before: e)),
                        ("restore_checked", lambda r, e, before: True)):
        monkeypatch.setattr(D, name, value)
    argv = ["drive.py", "--network", *[x for p in path for x in ("--path", p)], *[x for p in presses for x in ("--press", p)]]
    monkeypatch.setattr(sys, "argv", argv)
    D.main()
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
    assert line["screens"][0]["fields"] == ["MAC Address", "IP Address"] and "text" not in line["screens"][0]
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
    assert line["screens"][0]["text"] == " ".join(RMT_LIST)               # its own list, no identity word: shown
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

# the identity, connection and region rows a decision may open: Right on each opens an option list, a submenu or an
# information screen, and starts or ends nothing
IDENTITY_LOOK = ["Wired LAN Connect", "IP Address Setting", "Remote Shoot Function", "Cnct. while Power OFF",
                 "Wake On LAN", "Manage Paired Device", "Display FTP Result", "USB Connection Mode", "USB LUN Setting",
                 "USB Power Supply", "Language", "NTSC/PAL Selector", "Area/Date/Time Setting", "Date/Time Setup"]
# the identity rows no decision opens (2026-11-13, a review): opening one may itself start or end a connection or act,
# and nobody has yet seen on the camera what Right does there (look-only governs the presses after the opening); Server
# Setting holds the FTP login (credentials); Edit Device Name opens a keyboard and the device's name, held by no file
NOT_LIFTED = {"Smartphone Connection": "start or end a connection", "Cloud Connection": "start or end a connection",
              "Cloud Information": "start or end a connection", "Network Streaming": "start or end a connection",
              "USB Streaming": "start or end a connection", "Tethering Connection": "start or end a connection",
              "Tethering Disconnection": "start or end a connection", "FTP Function": "start or end a connection",
              "Server Setting": "login", "Edit Device Name": "keyboard"}


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
    good = {"decisions": [{**DECISION, "rows": ["Bluetooth Function", "Wi-Fi Frequency Band", "Wake On LAN"],
                           "options": {"Bluetooth Function": ["On", "Off"], "Wi-Fi Frequency Band": ["5GHz"],
                                       "Wake On LAN": ["Enable", "Disable"]}}]}
    assert safety.network_decided(good)[1] == [] and safety.network_options(good)["Wi-Fi Frequency Band"] == ["5GHz"]


# Wi-Fi and Bluetooth settings a decision opens to look at, whose options it never lets the kit choose: Wi-Fi Connect's
# On joins the access point, Bluetooth Rmt Ctrl's On opens the Pairing screen, Airplane Mode drops the Wi-Fi and
# Bluetooth links (the a1 II's notes); also as a reader returns them
NEVER_CHOSEN = ["Wi-Fi Connect", "Wi-Fl Connect", "WiFi Connect", "Bluetooth Rmt Ctrl", "Bluetoth Rnt Ctrl",
                "Bluetooth Remote Control", "Airplane Mode"]


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
    lines = ["IP Address Setting", "IP Address", IP, "Subnet Mask", "255.255.255.0"]
    pressed, seen, line, logged = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "down", "enter:."],
                                             ("IP Address Setting",), {**DECISION, "rows": ["IP Address Setting"]},
                                             lines, "submenu", page_lit="IP Address Setting", open_lit="IP Address")
    out = capsys.readouterr().out
    assert pressed == ["menu", "right", "down"] and line["completed"] is False        # Enter: never chosen there
    assert '"lifted_from": "identity or connection row"' in logged
    assert all("text" not in s for s in line["screens"])
    assert line["screens"][0]["fields"] == ["IP Address", "Subnet Mask"]
    for where in (out, json.dumps(line), logged):
        assert IP not in where and "255.255" not in where
    # IP Address Setting's entry screen (a keyboard, or the address in boxes): read as no known kind, MENU alone
    pressed, _, line, _ = drive_fake(tmp_path, monkeypatch, scope_file, ["right", "down"], ("IP Address Setting",),
                                     {**DECISION, "rows": ["IP Address Setting"]}, ["1", "2", IP, "Done"],
                                     "unknown", page_lit="IP Address Setting", open_lit="1")
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
