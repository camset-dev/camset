"""The web page's own script (editor/web/app.js) under node, without a browser: the camera layout's grouping and
folding, where the Menu shows a tab (`menuPlace`, the editor's routes) and how a setting is opened in it
(`openSetting`, and from Compare's record map and the Exposure page), the set a row changes (`rowTarget`), the nested
options (`treeAt`, `treePick`, `treeControls`), Compare's "Open in Edit" and its back button, whose words a help text
is, the My Menu picker, numbers put on their steps, the keyboard (its shortcuts' guard, the focus kept through a
change, Enter and Space on what acts as a button, the menus' keys, Compare's column headers as one Tab stop the arrows
move along, greyed-out toolbar buttons that stay reachable and say why), and how the page holds up when the editor
refuses a page, ends the session or answers out of order. Two tests need no node: every element the script asks
for by id is in the page, and only the status bar, the toast and the editor-closed notice speak up by themselves.

Run: .venv/bin/python -m pytest kit/tests/test_page_script.py -q
kit/tests/page_harness.js loads the whole script as the browser does, in a small made-up DOM with no editor behind
it, then runs each test's script in the same context; the tests stub the page's own drawing and requests by name and
look at the elements the page made. The rows, tabs and menus are made up; nothing talks to the editor or a camera.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "editor" / "web" / "app.js"
HARNESS = Path(__file__).with_name("page_harness.js")

PAGE = ROOT / "editor" / "web" / "index.html"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

# made-up rows and the page's state for them, shared by the tests below; `act` and the page's drawing are stubbed so
# nothing is asked of the editor, and every request the page would send is kept in `sent`
COMMON = """
const sent = [];
const pageAct = act;
act = async (what, body) => { sent.push([what, body]); return { message: "done" }; };
const pageRender = render;
render = () => {};
refresh = async () => {};
drawSide = () => {};
const row = (key, name, extra = {}) => ({ key, name, kind: "shown", label: "one", editable: true, ...extra });
const names = (box) => box.querySelectorAll(".row > .name").map((n) => n.textContent);
const tick = () => new Promise((r) => setTimeout(r, 0));
// the person's last input before the focus moves, as the page tells it (a key, or a tap or a click)
const viaKeys = () => { for (const f of document.listeners.keydown) f({ key: "Tab", shiftKey: false, defaultPrevented: false, preventDefault() {} }); };
const viaPointer = () => { for (const f of document.listeners.pointerdown) f({ target: document.body }); };
state = { rev: 1, file: { editable: true }, prefs: {}, targets: [[0, "Live"], [3, "Memory 1"]], tab_info: [{ name: "Shoot", color: "#123456" }],
  routes: {}, row_hovers: {}, my_menu: { name: "My Menu" } };
"""


def run(tmp_path, code):
    """The page's script loaded, then `code` run beside it; what it printed, as JSON. The test's own names are kept
    in a block, so none of them hides a name of the page's (a script's top-level const would, for the page too)."""
    test = tmp_path / "test.js"
    test.write_text("{" + COMMON + code + "}\n", encoding="utf-8")
    r = subprocess.run(["node", str(HARNESS), str(APP), str(test)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@needs_node
def test_the_pages_script_parses():
    """node --check of the page's whole script, as the editor serves it."""
    r = subprocess.run(["node", "--check", str(APP)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr


@needs_node
def test_the_page_loads_whole_and_asks_for_the_access_code(tmp_path):
    """The script runs from top to bottom in the harness: with no access code given it shows its login, hides the
    app and asks the editor nothing. Each window it opens by name has its section in the page."""
    got = run(tmp_path, """
console.log(JSON.stringify({ login: $("login").hidden, app: $("app").hidden, asked: __fetches.length, view, windows: Object.keys(xp.windows) }));
""")
    assert (got["login"], got["app"], got["asked"]) == (False, True, 0)
    assert got["view"]["page"] == "main" and got["view"]["mode"] == "edit"
    ids = set(re.findall(r'id="([^"]+)"', PAGE.read_text(encoding="utf-8")))
    assert got["windows"] and set(got["windows"]) <= ids, got["windows"]


# a group laid out as on the camera: a heading with two rows under it, a heading with none, the rows only Movie mode's
# menu has, and the settings the definition does not place
LAYOUT = """
const drive = { name: "Drive", color: "#000", rows: [row("k:a", "Alpha"), row("k:b", "Beta", { changed: true, original: "two" }), row("k:c", "Gamma"), row("k:d", "Delta")],
  layout: [{ head: "Speed", depth: 0, path: ["Speed"] }, { key: "k:a", depth: 1 }, { key: "k:b", depth: 1 }, { head: "Empty", depth: 0, path: ["Empty"] },
    { mode: "In Movie mode", name: "Movie" }, { key: "k:c", depth: 0 }, { more: "More settings in this group" }, { key: "k:d", depth: 0 }] };
const other = { name: "Other", rows: [row("k:e", "Epsilon")] };
"""


@needs_node
def test_the_camera_layout_groups_and_folds_its_rows(tmp_path):
    """A tab's groups: the first open the first time, the others' rows made when opened and remembered open; as on
    the camera, a heading over its rows (indented), "In Movie mode" and "More settings in this group" as lines of
    their own, a heading with no row under it left out; a heading folds the rows under it down to the next line as
    shallow, a mode or "More" line ends the fold, and a fold stays across a redraw. With Only edited, a heading stays
    only with a row still under it, and a tab with nothing edited says so. The layout switch shows only when the
    definition places the settings."""
    got = run(tmp_path, LAYOUT + """
view.tab = "Shoot";
const [d1, d2] = drawGroups([drive, other], "Shoot", false);
const lines = d1.querySelector(".grid").children.map((n) => [n.querySelector(".name").textContent, n.className, n.dataset.depth ?? null]);
const before = { second_open: d2.open, second_rows: d2.querySelector(".grid").childElementCount };
d2.open = true; d2.dispatchEvent({ type: "toggle" });
const opened = { rows: names(d2), kept: [...openGroups.get("Shoot")] };
const head = d1.querySelector(".rowhead > .name");
head.click();
const folded = { cls: head.parentElement.classList.contains("folded"), aria: head.getAttribute("aria-expanded"),
  hidden: d1.querySelector(".grid").children.map((n) => n.hidden) };
const [again] = drawGroups([drive, other], "Shoot", false);
const redrawn = again.querySelector(".grid").children.map((n) => n.hidden);
head.click();
const unfolded = d1.querySelector(".grid").children.map((n) => n.hidden);
const sum = d1.querySelector("summary");
view.only = true;
const [h, ...edited] = drawTab([drive, other], { places: true, flat: false });
const onlyEdited = edited.map((d) => [d.dataset.group, d.querySelector(".grid").children.map((n) => n.querySelector(".name").textContent)]);
const none = drawTab([other], { places: false }).map((e) => e.textContent);
console.log(JSON.stringify({ lines, before, opened, folded, redrawn, unfolded, summary: [sum.textContent, sum.style["--c"]],
  head: [h.querySelector("h1").textContent, h.querySelector("h1").style.color, h.querySelectorAll(".layout-switch button").map((b) => [b.textContent, b.classList.contains("on")])],
  onlyEdited, none }));
""")
    assert got["lines"] == [["Speed", "row rowhead", "0"], ["Alpha", "row", "1"], ["Beta", "row changed", "1"],
                            ["In Movie mode", "row rowmore rowmode", "0"], ["Gamma", "row", "0"],
                            ["More settings in this group", "row rowmore", "0"], ["Delta", "row", "0"]]
    assert got["lines"][2][0] == "Beta" and got["before"] == {"second_open": False, "second_rows": 0}
    assert got["opened"] == {"rows": ["Epsilon"], "kept": ["Drive", "Other"]}
    # the heading folds Alpha and Beta; the mode line ends the fold
    assert got["folded"] == {"cls": True, "aria": "false", "hidden": [False, True, True, False, False, False, False]}
    assert got["redrawn"] == got["folded"]["hidden"] and got["unfolded"] == [False] * 7
    assert got["summary"][0].startswith("Drive  (4)1") and got["summary"][1] == "#000"   # its count, and 1 edited
    assert got["head"] == ["Shoot", "#123456", [["As on the camera", True], ["Flat list", False]]]
    assert got["onlyEdited"] == [["Drive", ["Speed", "Beta"]]]
    assert got["none"] == ["Shoot", "No settings match."]


@needs_node
def test_a_tab_without_an_entry_goes_where_the_editor_routes_it(tmp_path):
    """menuPlace: a tab with its own Menu entry is shown there; a tab with none goes where the editor's routes say:
    My Menu's tab to the My Menu page, "Not in the menus" to the first tab when the flat list has no such entry, an
    unlisted tab to the entry that shows it."""
    got = run(tmp_path, """
state.routes = { "Mine": { page: "mymenu" }, "Not in the menus": { page: "tab", tab: "Shoot" }, "Spare": { page: "tab", tab: "Other" } };
console.log(JSON.stringify(["Shoot", "Mine", "Not in the menus", "Spare"].map(menuPlace)));
""")
    assert got == [{"page": "tab", "tab": "Shoot"}, {"page": "mymenu", "tab": None}, {"page": "tab", "tab": "Shoot"},
                   {"page": "tab", "tab": "Other"}]


@needs_node
def test_opening_a_setting_unfolds_its_own_row(tmp_path):
    """openSetting: the page and tab where the Menu shows the setting (its `open_tab` first, then its tab's route),
    the search cleared, the group that shows it (`open_group`, else its own) open, its details unfolded, and its own
    row of the group (not a copy of it in another row's details, earlier on the page) unfolded from under a folded
    heading and brought into view."""
    got = run(tmp_path, LAYOUT + """
const copy = el("div", { class: "row", "data-key": "k:b" });
drawContent = async () => {
  const where = view.page === "tab" ? view.tab : view.page;
  $("content").replaceChildren(el("div", { class: "detail" }, copy), ...drawGroups([other, drive], where, false));
};
const open = async (s) => {
  view.q = "words";
  await openSetting(s);
  const own = document.querySelector('details.grp > .grid > [data-key="' + s.key + '"]');
  return { page: view.page, tab: view.tab, q: view.q, search: $("search").value, groups: [...(openGroups.get(view.page === "tab" ? view.tab : view.page) || [])],
    detail: xp.detail.has(s.key), reveal: xp.reveal, own: own && { hidden: own.hidden, seen: !!own.scrolledTo }, copy: !!copy.scrolledTo };
};
(async () => {
  state.routes = { "Mine": { page: "mymenu" } };
  xp.rowFolds.add(JSON.stringify(["Shoot", "Drive", ["Speed"]]));
  const shoot = await open({ key: "k:b", tab: "Shoot", group: "Drive" });
  const mine = await open({ key: "k:e", tab: "Mine", group: "Other" });
  const off = await open({ key: "k:d", tab: "Shoot", group: "Elsewhere", open_tab: "Not in the menus", open_group: "Drive" });
  state.routes["Not in the menus"] = { page: "tab", tab: "Shoot" };
  const flat = await open({ key: "k:a", tab: "Shoot", group: "Drive", open_tab: "Not in the menus" });
  console.log(JSON.stringify({ shoot, mine, off, flat, unfolded: !xp.rowFolds.has(JSON.stringify(["Shoot", "Drive", ["Speed"]])) }));
})();
""")
    assert got["shoot"] == {"page": "tab", "tab": "Shoot", "q": "", "search": "", "groups": ["Drive"], "detail": True, "reveal": None,
                            "own": {"hidden": False, "seen": True}, "copy": False}
    assert got["unfolded"]          # the folded heading over Beta was unfolded to show it
    assert got["mine"]["page"] == "mymenu" and got["mine"]["groups"] == ["Other"] and got["mine"]["own"] == {"hidden": False, "seen": True}
    assert (got["off"]["page"], got["off"]["tab"], got["off"]["groups"]) == ("tab", "Not in the menus", ["Drive"])
    assert (got["flat"]["page"], got["flat"]["tab"], got["flat"]["groups"]) == ("tab", "Shoot", ["Drive"])


@needs_node
def test_a_row_changes_the_set_it_was_drawn_for(tmp_path):
    """rowTarget: a row drawn for a set of its own (the My Menu page's, the live settings, set 0) changes that set,
    whatever set the page edits; any other row the page's; Revert sends that set."""
    got = run(tmp_path, """
view.target = 3;
(async () => {
  const live = drawRow(row("k:a", "Alpha", { changed: true, original: "two", target: 0 }));
  const page = drawRow(row("k:b", "Beta", { changed: true, original: "two" }));
  for (const r of [live, page]) r.querySelectorAll("button").find((b) => b.textContent === "Revert").click();
  await tick();
  console.log(JSON.stringify({ targets: [rowTarget({ target: 0 }), rowTarget({ target: 2 }), rowTarget({})], sent }));
})();
""")
    assert got["targets"] == [0, 2, 3]
    assert got["sent"] == [["revert", {"target": 0, "key": "k:a"}], ["revert", {"target": 3, "key": "k:b"}]]


TREE = """
const tree = [{ label: "Auto", value: 0 }, { label: "Preset", options: [[1, "Sun", true, "In the sun."], [2, "Shade", false, null]] }, { label: "Manual", value: 9 }];
const options = [[0, "Auto", true, "Chosen by the camera."], [1, "Sun", true, null], [2, "Shade", false, null], [9, "Manual", false, null]];
"""


@needs_node
def test_nested_options_keep_the_main_option_of_the_value(tmp_path):
    """treeAt: the main option that holds the value (its own value or one of its choices), else -1, then the row
    shows its flat list. treePick: choosing a main option keeps the value when it is one of that option's choices,
    else stores its first choice, or its one value. treeControls: the main list on the option of the value (help on
    hover, "not checked" said, but not on the value held now, as the window draws it), and the option's own choices
    under it; a change stores only a new value."""
    got = run(tmp_path, TREE + """
const sets = [];
const r = row("k:w", "Balance", { kind: "choice", value: 2, options, tree });
const [main, sub] = treeControls(r, (b) => sets.push(b)).map((s) => s.querySelector("select"));
const shown = { main: [main.value, main.children.map((o) => [o.textContent, o.title])], sub: [sub.value, sub.children.map((o) => [o.textContent, o.title])] };
main.value = "1"; main.dispatchEvent({ type: "change" });
main.value = "2"; main.dispatchEvent({ type: "change" });
sub.value = "1"; sub.dispatchEvent({ type: "change" });
const single = treeControls({ ...r, value: 0 }, () => {}).length;
const flat = drawRow({ ...r, value: 5 }).querySelectorAll("select").length;
console.log(JSON.stringify({ at: [treeAt(r), treeAt({ ...r, value: 0 }), treeAt({ ...r, value: 9 }), treeAt({ ...r, value: 5 }), treeAt({ value: 1 })],
  pick: [treePick(tree[1], 2), treePick(tree[1], 0), treePick(tree[0], 2), treePick(tree[2], 9)], shown, sets, single, flat }));
""")
    assert got["at"] == [1, 0, 2, -1, -1]
    assert got["pick"] == [2, 1, 0, 9]
    assert got["shown"]["main"] == ["1", [["Auto", "Chosen by the camera."], ["Preset", "Has a choice of its own: Sun, Shade"], ["Manual (not checked)", ""]]]
    assert got["shown"]["sub"] == ["2", [["Sun", "In the sun."], ["Shade", ""]]]
    assert got["sets"] == [{"value": 9}, {"value": 1}]     # Preset again keeps Shade: nothing to store
    assert (got["single"], got["flat"]) == (1, 1)


COMPARE = """
render = () => {};
drawContent = async () => {};
cmp.last = { cols: [{ editable: true, section: 0 }, { editable: true, section: 3 }, { editable: false, section: 3 }] };
const r = (extra) => ({ key: "k:a", tab: "Shoot", group: "Drive", in_sets: true, cells: [{ edited: false }, { edited: true }, null], ...extra });
const edit = async (row, section, only) => {
  view.mode = "compare"; view.only = only; view.target = 0; $("only").checked = only;
  await cmpOpenInEdit(row, section);
  return { target: view.target, mode: view.mode, page: view.page, tab: view.tab, only: view.only, box: $("only").checked, from: cmp.from };
};
const back = () => { const b = cmpBackButton(); return b && b.textContent.includes("Back to Compare"); };
"""


@needs_node
def test_open_in_edit_opens_the_section_that_keeps_the_setting(tmp_path):
    """cmpOpenInEdit: Edit on the setting in the column's set when that set keeps it, else in the live settings (a
    setting the sets do not keep, or a set the file has not); Only edited turned off only when it would hide the
    setting there; the tab where the Menu shows it (`open_tab`)."""
    got = run(tmp_path, COMPARE + """
(async () => {
  const out = {
    memory: await edit(r(), 3, true),
    live_only: await edit(r({ in_sets: false }), 3, true),
    no_such_set: await edit(r(), 5, false),
    off_menu: await edit(r({ open_tab: "Not in the menus" }), 0, false),
  };
  console.log(JSON.stringify(out));
})();
""")
    assert got["memory"] == {"target": 3, "mode": "edit", "page": "tab", "tab": "Shoot", "only": True, "box": True,
                             "from": {"key": "k:a", "tab": "Shoot", "target": 3}}
    assert (got["live_only"]["target"], got["live_only"]["only"], got["live_only"]["box"]) == (0, False, False)
    assert got["no_such_set"]["target"] == 0
    assert got["off_menu"]["tab"] == "Not in the menus" and got["off_menu"]["from"]["tab"] == "Not in the menus"


@needs_node
def test_the_back_to_compare_button_lasts_while_the_setting_is_shown(tmp_path):
    """"← Back to Compare" heads the tab "Open in Edit" opened while that tab is shown in that set, again when the
    person comes back to it, never on another tab, set or page; it takes the page back to Compare on the row it was
    opened from, and is gone after."""
    got = run(tmp_path, COMPARE + """
(async () => {
  await edit(r(), 3, false);
  const out = { shown: back(), drawn: drawTab([], {})[0].firstChild.tagName };
  view.tab = "Other"; out.other_tab = back();
  view.tab = "Shoot"; out.back_again = back();
  view.target = 0; out.other_set = back(); view.target = 3;
  view.page = "main"; out.main = back(); view.page = "tab";
  cmpBackButton().click();
  out.after = { mode: view.mode, goKey: cmp.goKey, from: cmp.from };
  view.mode = "edit"; out.gone = back();
  console.log(JSON.stringify(out));
})();
""")
    assert (got["shown"], got["drawn"]) == (True, "BUTTON")
    assert (got["other_tab"], got["back_again"], got["other_set"], got["main"]) == (None, True, None, None)
    assert got["after"] == {"mode": "compare", "goKey": "k:a", "from": None} and got["gone"] is None


@needs_node
def test_hovers_say_whose_words_the_help_is(tmp_path):
    """A row's details: its help on hover says whose words they are, the camera's own (a help file) or Camset's, in
    the editor's words (`row_hovers`); the name's hover says first where the setting sits on the camera."""
    got = run(tmp_path, """
state.row_hovers = { help: "The camera's own guide", help_own: "Camset's own words", modes: "The shooting modes" };
const own = rowDetail(row("k:a", "Alpha", { help: "Words.", help_from_file: false, modes: "Stills" }));
const camera = rowDetail(row("k:b", "Beta", { help: "Words.", help_from_file: true }));
const name = drawRow(row("k:c", "Gamma", { help: "Words.", place: "Shoot > Page 2" })).querySelector(".name");
console.log(JSON.stringify({ own: own.map((e) => [e.className, e.title]), camera: camera.map((e) => e.title), name: name.title,
  none: drawRow(row("k:d", "Delta")).querySelector(".name").title }));
""")
    assert got["own"] == [["help", "Camset's own words"], ["meta", ""]]
    assert got["camera"] == ["The camera's own guide"]
    assert got["name"] == "Shoot > Page 2\nClick for more about this setting" and got["none"] == ""


MYMENU = """
const j = { name: "Favourites", editable: true, excluded: "The camera keeps some items out.",
  items: [{ code: 11, name: "Alpha", tab: "Shoot" }, { code: 12, name: "Beta", tab: "Exposure", in: { page: 1, item: 2 } }, { code: 13, name: "Gamma" }] };
const pop = $("mymenu");
const list = () => pop.querySelector(".mm-pick-list").children.map((b) => [b.textContent, b.disabled, b.title]);
const type = (q) => { pop.querySelector("input").dispatchEvent({ type: "input", target: { value: q } }); return list(); };
"""


@needs_node
def test_the_my_menu_picker_filters_and_refuses(tmp_path):
    """The My Menu picker: every item a place can hold with its tab, narrowed by name or tab as one types, "No item
    matches." when none does; the items already in My Menu greyed out with where they are; a click puts the item in
    the place and closes the picker. A row's My Menu items: Add when it can be, where it is and Remove when it is,
    greyed out with the reason when the camera has no item for it or the file cannot be edited."""
    got = run(tmp_path, MYMENU + """
(async () => {
  showMyMenuPicker(j, 0, 1, { empty: true, code: 0, name: "Empty" }, el("button"));
  const out = { open: !pop.hidden, head: pop.firstChild.textContent, note: pop.querySelector(".small.weak").textContent, all: list(),
    by_name: type("  GAM "), by_tab: type("expo"), none: type("zzz"), back: type("").length };
  pop.querySelector(".mm-pick-list").children[0].click();
  await tick();
  out.chose = { sent, closed: pop.hidden };
  showMyMenuPicker(j, 1, 0, { code: 12, name: "Beta" }, el("button"));
  out.replace = pop.firstChild.textContent;
  const items = (r) => myMenuItems(r).map((e) => [e.textContent, e.tagName === "BUTTON" ? e.disabled : e.querySelector("button") ? e.querySelector("button").disabled : null, e.title]);
  out.cannot = items(row("k:a", "Alpha", { mymenu_why: "The camera has no My Menu item for this setting." }));
  out.add = items(row("k:a", "Alpha", { menu_code: 5 }));
  out.held = items(row("k:a", "Alpha", { menu_code: 5, mymenu: { page: 2, item: 3 } }));
  state.file.editable = false; state.my_menu.name = "Shelf";
  out.locked = items(row("k:a", "Alpha", { menu_code: 5 }));
  console.log(JSON.stringify(out));
})();
""")
    assert got["open"] and got["head"] == "Add to Favourites 1" and got["note"] == "The camera keeps some items out."
    assert got["all"] == [["Alpha   (Shoot)", False, ""], ["Beta   (in Favourites 1, item 2)", True, "Already in Favourites 1, item 2"],
                          ["Gamma", False, ""]]
    assert [x[0] for x in got["by_name"]] == ["Gamma"] and [x[0] for x in got["by_tab"]] == ["Beta   (in Favourites 1, item 2)"]
    assert got["none"] == [["No item matches.", False, ""]] and got["back"] == 3
    assert got["chose"] == {"sent": [["mymenu_slot", {"page": 0, "item": 1, "code": 0, "do": "set", "to": 11}]], "closed": True}
    assert got["replace"] == "In place of Beta"
    assert got["cannot"] == [["Add to My Menu", True, "The camera has no My Menu item for this setting."]]
    assert got["add"] == [["Add to My Menu", False, ""]]
    assert got["held"] == [["In My Menu: page 2, item 3", None, ""], ["Remove from My Menu", False, ""]]
    assert got["locked"] == [["Add to Shelf", True, ""]]


@needs_node
def test_mapping_text_reaches_expert_mode_only(tmp_path):
    """A row and its details: the mapping team's note, the records, the record id beside the name, the proof badge,
    the stored number and the values no file has held are drawn in Expert mode only,
    whatever the editor sends; the help comes first, and a setting not on this camera's menu says so in plain words.
    The refusals a proof run met (menu_blocked) are evidence, in no definition: the page draws none, whatever it is
    sent."""
    got = run(tmp_path, """
const r = row("k:a", "Alpha", { help: "Words.", note: "Seen in pass 2", records: "Record 0x0123 (global)",
  record_hex: "0x0123", record_id: "0x0123", proof: "Proved on the camera (3/3)", proof_kind: "ok", raw: 7,
  hidden: 2, hidden_words: "2 value(s) not checked on the camera yet are hidden (the window's words)", stored: "sets", not_on_camera: true,
  blocked: [{ label: "One", reason: "Tracking is on" }, { label: "Two", reason: "Tracking is on" }, { label: "Three", reason: "in Movie mode" }] });
const text = () => { const box = drawRow(r); return box.textContent; };
state.prefs = { expert: false, show_proof: true, show_record_ids: true, show_raw: true };
const plainRow = text();
const plainFirst = rowDetail(r)[0].className;
state.prefs = { expert: true, show_proof: false };
const expertRow = text();
state.prefs = { expert: true, show_proof: true };
const badged = text();
console.log(JSON.stringify({ plainRow, plainFirst, expertRow, badged }));
""")
    mapping = ["Seen in pass 2", "Record 0x0123", "0x0123", "Proved on the camera", "raw value",
               "not checked on the camera yet"]
    for t in mapping:
        assert t not in got["plainRow"], t
        assert t in got["expertRow"] or t == "Proved on the camera", t
    assert got["plainFirst"] == "help"
    assert "Not on this camera's menu" in got["plainRow"] and "Not on this camera's menu" in got["expertRow"]
    assert "Not on this camera's menu" not in got["badged"] and "Proved on the camera" in got["badged"]
    assert "Not offered while" not in got["plainRow"] + got["expertRow"]
    assert "Kept in the memories too" in got["plainRow"]


@needs_node
def test_a_number_shown_as_the_definition_says(tmp_path):
    """shown_as: the number box, its range and its step in the shown terms (7500 stored, 75 shown; 9250 is 92.5, never
    rounded away), a typed number stored multiplied back, the tile's list in those terms; without it, as stored."""
    got = run(tmp_path, """
const r = row("k:n", "Knee", { kind: "range", value: 7500, lo: 7500, hi: 10500, step: 250, unit: "%", label: "75 %", shown_as: { divide: 100, decimals: 0 } });
const node = drawRow(r);
const input = node.querySelector("input");
const words = node.querySelector(".more").textContent;
const before = input.value;
input.value = "92.5";
input.dispatchEvent({ type: "change" });
const plain = drawRow(row("k:p", "Plain", { kind: "range", value: 3, lo: 0, hi: 10, step: 1, unit: "ms", label: "3 ms" }));
(async () => {
  await tick();
  console.log(JSON.stringify({ shown: [before, input.getAttribute("min"), input.getAttribute("max"), input.getAttribute("step")], words,
    sent, numbers: [shownNumber(r, 9250), shownNumber({ shown_as: { divide: 10, decimals: 1 } }, 3), storedNumber(r, "75"), storedNumber(r, "x")],
    tile: rangeOptions(r).slice(0, 2), plain: [plain.querySelector("input").value, plain.querySelector(".more").textContent] }));
})();
""")
    assert got["shown"] == ["75", "75", "105", "2.5"]
    assert got["words"] == "%, 75 to 105 in steps of 2.5"
    assert [b.get("value") for _, b in got["sent"]] == [9250], got["sent"]
    assert got["numbers"] == ["92.5", "0.3", 7500, None]
    assert got["tile"] == [[7500, "75 %"], [7750, "77.5 %"]]
    assert got["plain"] == ["3", "ms, 0 to 10"]


@needs_node
def test_sub_choices_beside_the_chosen_option(tmp_path):
    """As on the camera an option's sub-choices are no rows: the owner's details show every choice of the option chosen
    now, in the order sent, each with its control, and an edited one of another option; the group counts them and
    Only edited keeps an owner whose choice is edited. Opening a choice opens its owner's details, its box marked; a
    search's row of a choice links there. In Expert mode a disputed setting says so in place of the proof line; no
    option is marked for where its name came from (a name source is evidence, in no definition), whatever is sent."""
    got = run(tmp_path, """
const sub = (key, name, option, extra = {}) => row(key, name, { option, ...extra });
const owner = row("k:o", "Look", { kind: "choice", value: 1, options: [[0, "A", true, null], [1, "B", true, null]],
  subs: { options: ["A", "B"], now: "B", edited: 1, rows: [sub("k:a1", "A only", "A", { changed: true, original: "two" }), sub("k:a2", "A other", "A"), sub("k:b1", "B first", "B"), sub("k:b2", "B second", "B")] } });
const look = { name: "Looks", color: "#000", beside: true, rows: [owner, row("k:x", "Other")] };
view.tab = "Shoot";
const [d] = drawGroups([look], "Shoot", false);
const drawnRows = d.querySelectorAll("details.grp > .grid > .row").map((n) => n.dataset.key);
const ownerRow = d.querySelector('[data-key="k:o"]');
const subs = ownerRow.querySelectorAll(".subs > .grid > .row").map((n) => n.dataset.key);
const labels = ownerRow.querySelectorAll(".subs > .strong").map((n) => n.textContent);
const controls = ownerRow.querySelectorAll(".subs > .grid > .row .ctl").length;
const count = d.querySelector("summary").textContent;
view.only = true;
const only = onlyEdited([look]).map((g) => [g.name, g.rows.map((r) => r.key), groupCount(g)]);
view.only = false;
drawContent = async () => { $("content").replaceChildren(...drawGroups([look], "Shoot", false)); };
const link = drawRow(row("k:b2", "B second", { beside: { owner: "k:o", name: "Look", option: "B", tab: "Shoot", group: "Looks" } }));
const linkText = link.querySelectorAll(".detail a").map((a) => a.textContent);
state.prefs = { expert: true };
const marked = optionWords({ names: { "1": "Name from one reader" } }, 1, "B", false, null);
const disputed = drawRow(row("k:d", "D", { disputed: "Disputed: left out of the proofs until a mapper decides", proof: "Proved", proof_kind: "ok" })).querySelector(".more").textContent;
state.prefs = {};
const plainMark = optionWords({ names: { "1": "Name from one reader" } }, 1, "B", false, null);
(async () => {
  await openSetting({ key: "k:a2", tab: "Shoot", group: "Looks" });
  const opened = document.querySelector('details.grp > .grid > [data-key="k:o"]');
  const focus = opened.querySelector(".subs .grid.focus [data-key]");
  console.log(JSON.stringify({ drawnRows, subs, labels, controls, count, only, linkText, marked, disputed, plainMark,
    detail: xp.detail.has("k:o"), focus: focus && focus.dataset.key, seen: !!(focus && focus.scrolledTo),
    shownAfter: opened.querySelectorAll(".subs > .grid > .row").map((n) => n.dataset.key) }));
})();
""")
    assert got["drawnRows"] == ["k:o", "k:x"]
    assert got["subs"] == ["k:a1", "k:b1", "k:b2"], "B's two in order, and A's edited one"
    assert got["labels"] == ["For A:", "For B:", "For B:"] and got["controls"] == 3
    assert got["count"].startswith("Looks  (6)")
    assert got["only"] == [["Looks", ["k:o"], 2]]
    assert got["linkText"] == ["Open beside Look > B"]
    assert got["marked"] == ["B", None] and got["plainMark"] == ["B", None]
    assert got["disputed"].startswith("Disputed: left out of the proofs") and "Proved" not in got["disputed"]
    assert got["detail"] and got["focus"] == "k:a2" and got["seen"]
    assert got["shownAfter"] == ["k:a1", "k:a2", "k:b1", "k:b2"]


@needs_node
def test_an_option_opens_its_page(tmp_path):
    """Right on an option (Picture Profile's PP1) opens a whole page of rows: the option is marked "›" with the page's
    count on hover, the owner's details link to the chosen option's page ("Open the PP1 page") and the others', and a
    link opens the page's group (marked "›" in its head), laid out with the page's own headings, the stills and movie
    copies of a parameter side by side."""
    got = run(tmp_path, """
const page = (option, key) => ({ option, count: 3, key, open_tab: "Shoot", open_group: `Profile ${option}`, words: `Open the ${option} page` });
const owner = row("k:o", "Profile", { kind: "choice", value: 1, label: "P1", options: [[0, "Off", true, null], [1, "P1", true, null], [2, "P2", true, null]],
  pages: [page("P1", "k:bl"), page("P2", "k:p2")] });
const color = { name: "Color", color: "#000", beside: true, rows: [owner] };
const p1 = { name: "Profile P1", color: "#000", beside: true, page: "P1",
  rows: [row("k:bl", "Black Level"), row("k:bls", "Black Level (stills)"), row("k:bgr", "Black Gamma Range"), row("k:bgl", "Black Gamma Level")],
  layout: [{ key: "k:bl", depth: 0 }, { key: "k:bls", depth: 0 }, { head: "Black Gamma", depth: 0, path: ["Black Gamma"] }, { key: "k:bgr", depth: 1 }, { key: "k:bgl", depth: 1 }] };
view.tab = "Shoot";
const opts = drawRow(owner).querySelectorAll("option").map((o) => [o.textContent, o.title || null]);
const links = drawRow(owner).querySelectorAll(".pages a").map((a) => a.textContent);
drawContent = async () => { $("content").replaceChildren(...drawGroups([color, p1], "Shoot", false)); };
(async () => {
  try {
    await openSetting({ key: "k:bl", tab: "Shoot", open_tab: "Shoot", open_group: "Profile P1" });
    const g = document.querySelectorAll("details.grp").find((n) => n.dataset.group === "Profile P1");
    console.log(JSON.stringify({ opts, links, open: g.open, head: g.querySelector("summary").textContent,
      lines: g.querySelector(".grid").children.map((n) => [n.querySelector(".name").textContent, n.dataset.depth ?? null]) }));
  } catch (e) { console.log(JSON.stringify({ error: String(e && e.stack) })); }
})();
""")
    assert "error" not in got, got.get("error")
    assert got["opts"][0] == ["Off", None]
    assert got["opts"][1][0] == "P1  ›" and "page of 3 settings" in got["opts"][1][1]
    assert got["links"] == ["Open the P1 page", "P2"]
    assert got["open"] and got["head"].startswith("› Profile P1  (4)")
    assert got["lines"] == [["Black Level", "0"], ["Black Level (stills)", "0"], ["Black Gamma", "0"], ["Black Gamma Range", "1"], ["Black Gamma Level", "1"]]


@needs_node
def test_a_view_only_setting_says_why(tmp_path):
    """A setting the editor sends as view only outside Expert mode (one no menu of the camera writes) has its control
    off and says why under it, in the editor's words, the definition's own reason on hover; a setting that may be
    changed says nothing of the kind."""
    got = run(tmp_path, """
const locked = drawRow(row("k:p", "Black Level", { kind: "choice", value: 0, options: [[0, "0", true, null], [1, "1", true, null]], editable: false,
  locked: "View only: this setting is not on this camera's menu, so no camera writes it.",
  locked_why: "PP7 to PP9 are not on this camera's menu." }));
const line = locked.querySelector("[data-locked]");
const free = drawRow(row("k:f", "Black Level", { kind: "choice", value: 0, options: [[0, "0", true, null], [1, "1", true, null]] }));
console.log(JSON.stringify({ text: line && line.textContent, title: line && line.title, off: locked.querySelector("select").disabled,
  free: !!free.querySelector("[data-locked]"), freeOff: free.querySelector("select").disabled }));
""")
    assert got["text"].startswith("View only: this setting is not on") and got["title"].startswith("PP7 to PP9")
    assert got["off"] is True and (got["free"], got["freeOff"]) == (False, False)


@needs_node
def test_a_copy_says_what_changing_it_changes(tmp_path):
    """A row the editor sends a note for (`copy_note`: a value the camera keeps in more than one record, what changing
    it changes, or that the file is out of step there) shows it under the row in the editor's words, its hover the
    editor's, the control left on; a Main tile says it on hover (`why`); a row without one shows none."""
    got = run(tmp_path, """
const note = "Changing this changes Black Level too, and reverting it reverts them: they held the same value when this file was opened or read, so the editor keeps them together.";
const r = drawRow(row("k:c", "Black Level (stills)", { kind: "choice", value: 0, options: [[0, "0", true, null], [1, "1", true, null]],
  copy_note: note, copy_note_why: "The camera keeps some values in more than one record." }));
const line = r.querySelector("[data-copy-note]");
const plainRow = drawRow(row("k:f", "Black Level", { kind: "choice", value: 0, options: [[0, "0", true, null], [1, "1", true, null]] }));
const tile = drawTile({ caption: "ISO", text: "ISO 100", why: note });
console.log(JSON.stringify({ text: line && line.textContent, title: line && line.title, on: !r.querySelector("select").disabled,
  none: !plainRow.querySelector("[data-copy-note]"), tile: tile.title }));
""")
    assert got["text"].startswith("Changing this changes Black Level too") and got["title"].startswith("The camera keeps some values")
    assert got["on"] is True and got["none"] is True
    assert got["tile"].startswith("ISO 100") and "Changing this changes Black Level too" in got["tile"]


@needs_node
def test_a_copy_reverts_through_the_editor_and_the_sample_says_so(tmp_path):
    """A changed copy's row, its All edits line and its Compare cell offer Revert, as any setting's, and each asks the
    editor, which decides what goes back with it (a copy in step takes its setting back along) or refuses with why. A
    download of the sample, or a file made from it, says that it must never be loaded into a camera, in the editor's
    words (`sample_words`)."""
    got = run(tmp_path, """
const buttons = (n) => n.querySelectorAll("button").map((b) => b.textContent);
const copy = drawRow(row("k:c", "Black Level (stills)", { changed: true, original: "0" }));
const edits = drawChanges([{ where: "Live", name: "Black Level (stills)", was: "0", now: "1", section: 0, id: 2 },
  { where: "Live", name: "Black Level", was: "0", now: "1", section: 0, id: 1 }]);
const table = edits[1].querySelectorAll("tr").map((tr) => buttons(tr).length);
const j = { cols: [{ src: "a", section: 0, name: "A Live", editable: true }], editable: true, rows: [] };
const cellMenu = cmpCellMenu(j, { key: "k:c", in_sets: false, cells: [{ stored: true, edited: true, text: "1" }] }, 0).map((x) => x[0]);
copy.querySelectorAll("button").find((b) => b.textContent === "Revert").click();
let said = null;
downloadAnswer = async (name, body, fallback, words) => { said = words("CAMSET02.DAT"); };
state.file = { issues: 0, sample_words: "This is the editor's sample: never load it into a camera." };
(async () => {
  await tick();
  const asked = sent[sent.length - 1];
  await downloadFile();
  const sample = said;
  state.file = { issues: 0 };
  await downloadFile();
  console.log(JSON.stringify({ copy: buttons(copy), asked, table, cellMenu, sample, plain: said }));
})();
""")
    assert "Revert" in got["copy"] and got["asked"] == ["revert", {"target": 0, "key": "k:c"}]
    assert got["table"][1:] == [1, 1], "All edits: a Revert for each record"
    assert "Revert" in got["cellMenu"]
    assert got["sample"] == "Downloaded CAMSET02.DAT. This is the editor's sample: never load it into a camera."
    assert got["plain"] == "Downloaded CAMSET02.DAT"


@needs_node
def test_what_only_the_cameras_copy_shows_and_putting_back(tmp_path):
    """What the editor marks as only the camera's copy showing (`camera_only`: in the file as opened, not on the camera
    now) is listed under its own heading with the editor's sentence, but not counted among the values flagged: the
    button reads Write anyway with no count, and no all-clear shows. A row the editor offers to put back where the
    camera keeps it (`put_back`, in its words, with what it does on hover) has that button, which asks the editor to
    "restore" it."""
    got = run(tmp_path, """
const base = { summary: [], warnings: [], rev: "r1", leave_on: "", words: { all_clear: "✔ All clear.", camera_only: "2 records of this file differ from what the camera holds now." } };
const theirs = (name) => ({ name, value: "v", reason: "why", kind: "In the file as opened, not on the camera now", kind_line: "line", edited: false, camera_only: true });
drawSend({ ...base, issues: [theirs("A"), theirs("B")] });
const box = $("send");
const out = { buttons: box.querySelectorAll("button").map((b) => b.textContent), texts: box.querySelectorAll("p").map((p) => p.textContent) };
const r = drawRow(row("k:c", "Black Level (stills)", { put_back: "Back in step with Black Level", put_back_why: "Sets this copy to the value Black Level holds now." }));
const put = r.querySelector("[data-put-back]");
put.click();
(async () => {
  await tick();
  console.log(JSON.stringify({ ...out, put: put.textContent, putWhy: put.title, asked: sent[sent.length - 1] }));
})();
""")
    assert "Write anyway" in got["buttons"] and not any("flagged" in b for b in got["buttons"]) and "Revert all flagged" not in got["buttons"]
    assert "2 records of this file differ from what the camera holds now." in got["texts"] and not any("All clear" in t for t in got["texts"])
    assert got["put"] == "Back in step with Black Level" and got["putWhy"] == "Sets this copy to the value Black Level holds now."
    assert got["asked"] == ["restore", {"target": 0, "key": "k:c"}]


@needs_node
def test_the_write_window_lists_each_value_under_what_it_is(tmp_path):
    """The page's Write window lists the values the editor sends under what each is (its heading, the line saying what
    such a value is), in the order sent, with the editor's words over them; its button says it writes them anyway, and
    Revert all flagged is there while one of them is an edit. With none sent, the editor's all-clear and the plain
    Write to camera."""
    got = run(tmp_path, """
const words = { issues: "3 values the camera is not known to take as written.", todo: "What to do: Revert the flagged values.", all_clear: "✔ Every changed value was checked on the camera and is one it takes." };
const issue = (name, kind, edited = true) => ({ name, value: "v", reason: "why", kind, kind_line: kind + " line", edited });
const base = { summary: [], warnings: [], rev: "r1", leave_on: "", words };
drawSend({ ...base, issues: [issue("A", "Not checked on the camera"), issue("B", "Not checked on the camera"), issue("C", "Raw edits")] });
const box = $("send");
const kinds = box.querySelectorAll(".issue-kind").map((n) => [n.textContent, n.title]);
const rows = box.querySelectorAll(".issues tr").map((n) => n.querySelector("td").textContent);
const buttons = box.querySelectorAll("button").map((b) => b.textContent);
const texts = box.querySelectorAll("p").map((p) => p.textContent);
drawSend({ ...base, issues: [issue("D", "Another video system's values", false)] });
const unedited = $("send").querySelectorAll("button").map((b) => b.textContent);
drawSend({ ...base, issues: [] });
const clear = { texts: $("send").querySelectorAll("p").map((p) => p.textContent), buttons: $("send").querySelectorAll("button").map((b) => b.textContent) };
console.log(JSON.stringify({ kinds, rows, buttons, texts, unedited, clear }));
""")
    assert got["kinds"] == [["Not checked on the camera", "Not checked on the camera line"], ["Raw edits", "Raw edits line"]]
    assert got["rows"] == ["A", "B", "C"]
    assert "Write anyway, with 3 flagged" in got["buttons"] and "Revert all flagged" in got["buttons"] and "Write to camera" not in got["buttons"]
    assert "3 values the camera is not known to take as written." in got["texts"] and "What to do: Revert the flagged values." in got["texts"]
    assert not any("experiment" in t or "known to accept" in t for t in got["texts"])
    assert "Revert all flagged" not in got["unedited"] and "Write anyway, with 1 flagged" in got["unedited"]
    assert any("Every changed value was checked on the camera" in t for t in got["clear"]["texts"]) and "Write to camera" in got["clear"]["buttons"]


def test_every_element_the_script_asks_for_is_in_the_page():
    """Each `$("id")` in the script names an element of index.html (but the difference cursor's words, which the
    script makes itself). The windows the script opens by name are checked from the running script, in
    `test_the_page_loads_whole_and_asks_for_the_access_code`."""
    script, page = APP.read_text(encoding="utf-8"), PAGE.read_text(encoding="utf-8")
    ids = set(re.findall(r'id="([^"]+)"', page))
    asked = set(re.findall(r'\$\("([A-Za-z0-9_-]+)"\)', script)) - {"cmp-at"}
    assert asked and asked <= ids, sorted(asked - ids)
    # the window "Edit a file from another firmware" is the desktop app's alone: the page has no section for it
    assert "unchecked" not in ids


@needs_node
def test_shortcuts_send_nothing_from_the_login_or_behind_a_window(tmp_path):
    """Cmd/Ctrl+Z and +Y undo and redo only while the page is in use: not on the login (a request there carries no
    code, which the editor counts as a wrong one), not behind a question or the Write window (the page is inert), not
    while the editor is out of reach, not in a text field; the text size keys work on the login too."""
    got = run(tmp_path, """
const press = (key, extra = {}) => { const ev = { key, metaKey: true, ctrlKey: false, altKey: false, shiftKey: false, defaultPrevented: false,
  preventDefault() { this.defaultPrevented = true; }, ...extra }; for (const f of document.listeners.keydown) f(ev); return ev.defaultPrevented; };
const out = {};
// the keyboard off the code box (on the login's Connect button): a text field keeps its keys
$("code").blur();
out.login = { taken: press("z"), sent: sent.length };
out.font = { taken: press("="), pct: $("font-scale-pct").textContent };
press("0");
$("app").hidden = false; $("app").inert = false; away.since = 0;
press("z"); press("Z", { shiftKey: true }); press("y");
out.inUse = sent.map(([w]) => w);
sent.length = 0;
ask("Write to camera", "Sure?", "Yes"); out.modal = $("app").inert; press("z");
askOpen(false); away.since = 1; press("z");
away.since = 0; document.activeElement = el("input"); press("z");
out.blocked = sent.length;
console.log(JSON.stringify(out));
""")
    assert got["login"] == {"taken": False, "sent": 0}
    assert got["font"] == {"taken": True, "pct": "110%"}
    assert got["inUse"] == ["undo", "redo", "redo"]
    assert got["modal"] is True and got["blocked"] == 0


@needs_node
def test_a_change_keeps_the_keyboard_on_its_control(tmp_path):
    """A list changed from the keyboard: the request goes with the focus kept (it is not let go of), and the row the
    editor answers with, drawn anew in place, takes the focus on the same control, with the new value; a row drawn
    again by the next poll does the same (`redrawRow`), and Main's patch replaces its own rows only, not the grids of
    sub-choices in a row's details. A list tapped or clicked lets go of the focus, so the page is drawn again."""
    got = run(tmp_path, """
const r = row("k:a", "Alpha", { kind: "choice", value: 1, label: "one", options: [[1, "one", true, null], [2, "two", true, null]] });
act = pageAct;
api = async (name, body) => { sent.push([name, body]); return { row: { ...r, value: body.value, label: "two", changed: true }, rows: [{ ...r, value: body.value, label: "two", changed: true }], rev: "r2" }; };
(async () => {
  $("content").replaceChildren(el("div", { class: "grid" }, drawRow(r)));
  const tapped = $("content").querySelector("select");
  viaPointer(); tapped.focus();
  tapped.value = "2"; tapped.dispatchEvent({ type: "change" });
  await tick(); await tick();
  const letGo = document.activeElement === document.body;
  sent.length = 0;
  $("content").replaceChildren(el("div", { class: "grid" }, drawRow(r)));
  const old = $("content").querySelector("select");
  viaKeys(); old.focus();
  old.value = "2";
  old.dispatchEvent({ type: "change" });
  await tick(); await tick();
  const a = document.activeElement;
  const after = { sent, fresh: a !== old && a.tagName === "SELECT", value: a.value, inPage: $("content").contains(a) };
  const node = $("content").querySelector('[data-key="k:a"]');
  redrawRow(node, { ...r, value: 1, label: "one" });
  const again = document.activeElement;
  const sub = row("k:s", "Sub", { option: "one", kind: "choice", value: 1, options: [[1, "x", true, null], [2, "y", true, null]] });
  const owner = row("k:o", "Owner", { caption: "Owner", kind: "choice", value: 1, label: "one", options: [[1, "one", true, null], [2, "two", true, null]],
    subs: { options: ["one"], now: "one", rows: [sub], edited: 0 } });
  const main = (v) => ({ set: 0, sets: ["Stills"], tiles: [{ caption: "Owner", text: v }], rows: [{ ...owner, label: v }] });
  view.focus = null;
  $("content").replaceChildren(...drawMain(main("one")));
  const patched = patchMain(main("one"), main("two"));
  console.log(JSON.stringify({ letGo, after, redrawn: again !== a && again.tagName === "SELECT" && again.value === "1", patched,
    rows: $("content").querySelectorAll(".grid > .row").length }));
})();
""")
    assert got["letGo"], "a tapped list lets go of the focus"
    assert got["after"] == {"sent": [["set", {"target": 0, "key": "k:a", "value": 2}]], "fresh": True, "value": "2", "inPage": True}
    assert got["redrawn"]
    assert got["patched"] is True, "Main with a row of sub-choices is patched in place, not drawn anew"


@needs_node
def test_undo_from_the_keyboard_draws_the_list_that_has_it_again(tmp_path):
    """Cmd/Ctrl+Z, Shift+Cmd/Ctrl+Z and Cmd/Ctrl+Y with a list of the settings reached with the keys: the page is drawn
    again for the editor's answer, the keyboard kept on the same list (a fresh one, drawn anew) and the list showing
    the value put back, not the undone one until the focus leaves it. Only until the editor has answered, whatever the
    answer (an undo it refuses too): a poll alone does not draw the list again under the person's hand, and a text
    field keeps Cmd/Ctrl+Z for itself."""
    got = run(tmp_path, """
const press = (key, extra = {}) => { const ev = { key, metaKey: true, ctrlKey: false, altKey: false, shiftKey: false, defaultPrevented: false,
  preventDefault() { this.defaultPrevented = true; }, ...extra }; for (const f of document.listeners.keydown) f(ev); return ev.defaultPrevented; };
// the editor: the list's value, which Undo puts back on "one" and Redo on "two"; `typing()` looked at while it answers
let value = 2, refuse = false;
const during = [];
const r = () => row("k:a", "Alpha", { kind: "choice", value, label: value === 1 ? "one" : "two", options: [[1, "one", true, null], [2, "two", true, null]] });
const n = row("k:n", "Knee", { kind: "range", value: 7500, lo: 7500, hi: 10500, step: 250, unit: "%", label: "75 %", shown_as: { divide: 100, decimals: 0 } });
act = pageAct;
api = async (name) => {
  sent.push(name);
  if (name === "undo" || name === "redo") {
    during.push(typing());
    if (refuse) throw new Refused("Nothing to undo.", 409, {});
    value = name === "undo" ? 1 : 2;
    return { message: "done" };
  }
  return { groups: [{ name: "Drive", color: "#000", rows: [r(), n] }] };
};
// the poll after a request, as `render` ends: the file's new revision, and the page drawn for it
refresh = async () => { state.rev += 1; maybeDraw(); };
$("app").hidden = false; $("app").inert = false; away.since = 0;
state.tabs = ["Shoot"];
view.page = "tab"; view.tab = "Shoot"; view.q = "";
openGroups.set("Shoot", new Set(["Drive"]));
const list = () => $("content").querySelector('[data-key="k:a"] select');
const step = async (key, extra) => {
  const was = document.activeElement, taken = press(key, extra);
  await tick(); await tick();
  const a = document.activeElement;
  return { taken, fresh: a !== was && a === list(), value: a.value, drawn: drawn === contentKey(), typing: typing() };
};
(async () => {
  const out = {};
  await drawContent(contentKey());
  const old = list();
  viaKeys(); old.focus();
  // the file changed elsewhere: the list that has the keyboard is not drawn again under it
  state.rev += 1; maybeDraw(); await tick();
  out.poll = { same: list() === old, typing: typing(), drawn: drawn === contentKey() };
  out.undo = await step("z");
  out.redo = await step("Z", { shiftKey: true });
  out.again = await step("z");
  out.y = await step("y");
  refuse = true;
  out.refused = { ...(await step("z")), count: undoKeys };
  out.during = during;
  out.sent = sent.splice(0);
  // a text field of the settings keeps Cmd/Ctrl+Z, and an undo on its way does not draw the page under it
  const box = $("content").querySelector('[data-key="k:n"] input');
  viaKeys(); box.focus();
  out.field = { taken: press("z"), sent: sent.length };
  undoKeys += 1; out.field.typing = typing(); undoKeys -= 1;
  console.log(JSON.stringify(out));
})();
""")
    assert got["poll"] == {"same": True, "typing": True, "drawn": False}, "a poll alone leaves the focused list as it is"
    for k, v in (("undo", "1"), ("redo", "2"), ("again", "1"), ("y", "2")):
        assert got[k] == {"taken": True, "fresh": True, "value": v, "drawn": True, "typing": True}, k
    assert got["refused"] == {"taken": True, "fresh": False, "value": "2", "drawn": True, "typing": True, "count": 0}
    assert got["during"] == [False] * 5, "the list is drawn again while each answer is on its way"
    assert [w for w in got["sent"] if w != "tab"] == ["undo", "redo", "undo", "redo", "undo"]
    assert got["field"] == {"taken": False, "sent": 0, "typing": True}


@needs_node
def test_a_typed_number_goes_on_the_steps_of_its_range(tmp_path):
    """As the window's number box: a typed number off the steps is put on the nearest one and one past the range on
    its end, before it is sent (the editor refuses any other); the value already held, an emptied box or one holding
    no number sends nothing, and the box shows the value again. The raw value box of an unmapped record likewise
    writes nothing for an emptied box (Number("") is 0) or a fraction."""
    got = run(tmp_path, """
const r = row("k:n", "Knee", { kind: "range", value: 7500, lo: 7500, hi: 10500, step: 250, unit: "%", label: "75 %", shown_as: { divide: 100, decimals: 0 } });
const input = drawRow(r).querySelector("input");
const type = (box, t) => { box.value = t; box.dispatchEvent({ type: "change" }); return box.value; };
const shown = ["92.4", "200", "", "abc", "75", "70"].map((t) => type(input, t));
const typed = sent.splice(0).map(([, b]) => b.value);
state.prefs = { page_sets: ["allow_raw_edits"] };
const page = drawUnmapped({ allow_raw_edits: true, editable: true, rows: [{ id: 0x10, hex: "0x0010", shape: "1×1", value: "7", int: 7, changed: false }] });
const raw = page[3].querySelector("input");
const rawShown = ["", "1.5", "7", "12"].map((t) => type(raw, t));
(async () => {
  await tick();
  console.log(JSON.stringify({ shown, typed, rawShown, raw: sent, snap: [snapToStep(7, 0, 10, 3), snapToStep(11, 0, 10, 3), snapToStep(-5, 0, 10, 3), snapToStep(5, 5, 5, 1)] }));
})();
""")
    # 92.4 is put on 92.5 and 200 on 105; nothing for "", "abc", 75 (held) and 70 (75, the bottom, is held)
    assert got["typed"] == [9250, 10500], got["typed"]
    assert got["shown"] == ["92.5", "105", "75", "75", "75", "75"]
    assert got["rawShown"] == ["7", "7", "7", "12"]
    assert got["raw"] == [["raw_set", {"target": 0, "id": 16, "value": 12}]]
    assert got["snap"] == [6, 9, 0, 5]


@needs_node
def test_a_page_the_file_lost_and_a_refused_page(tmp_path):
    """A page the open file or its definition does not have (Memories, Exposure, My Menu) gives way to Main, and a set
    it does not show to the live settings; a page the editor refuses says why in its place and counts as drawn (it
    is not asked for, and toasted, again at every poll); a page asked for after the session ended brings up the
    login."""
    got = run(tmp_path, """
state.tabs = ["Shoot"];
const kept = (page, extra) => { view.page = page; view.target = 0; Object.assign(state, { memories: null, exposure: null, my_menu: null }, extra); keepViewValid(state); return view.page; };
const pages = { memories: kept("memories", {}), exposure: kept("exposure", {}), mymenu: kept("mymenu", {}), kept: kept("exposure", { exposure: "Exposure" }) };
view.target = 7; keepViewValid(state); const target = view.target;
(async () => {
  view.page = "edits"; view.q = "";
  api = async () => { throw new Refused("This camera's definition has no exposure page.", 409, {}); };
  await drawContent("k1");
  const refused = { text: $("content").textContent, drawn, toast: $("toast").textContent };
  api = async () => { throw new CodeError("Your session ended: enter the access code again."); };
  $("app").hidden = false;
  await drawContent("k2");
  console.log(JSON.stringify({ pages, target, refused, login: [$("login").hidden, $("app").hidden, $("login-msg").textContent] }));
})();
""")
    assert got["pages"] == {"memories": "main", "exposure": "main", "mymenu": "main", "kept": "exposure"}
    assert got["target"] == 0
    assert got["refused"] == {"text": "This camera's definition has no exposure page.", "drawn": "k1", "toast": ""}
    assert got["login"] == [False, True, "Your session ended: enter the access code again."]


@needs_node
def test_the_record_map_and_the_exposure_page_open_a_setting_by_its_key(tmp_path):
    """Compare's record map opens a setting in the baseline column's set, as `openSetting` does: by its key, so in
    Expert mode with the record id beside its name, and in a group that is a page an option opens ("› …"), its row is
    found and brought into view with its details unfolded. The Exposure page's Show in menu finds "ISO" by its key,
    not the first row whose name starts with it, and marks it."""
    got = run(tmp_path, """
state.prefs = { expert: true, show_record_ids: true };
const page = { name: "Profile P1", color: "#000", page: "P1", rows: [row("k:bl", "Black Level", { record_id: "0x0123" })] };
const exp = { name: "ISO", color: "#000", rows: [row("k:min", "ISO AUTO Min. SS", { record_id: "0x0201" }), row("k:iso", "ISO", { record_id: "0x0200" })] };
drawContent = async () => { $("content").replaceChildren(...drawGroups([page, exp], view.tab, false)); };
(async () => {
  view.mode = "compare";
  await cmpOpenSetting({ key: "k:bl", name: "Black Level", tab: "Shoot", group: "Profile P1", open_group: "Profile P1" }, 3);
  const bl = document.querySelector('[data-key="k:bl"]');
  const record = { mode: view.mode, target: view.target, page: view.page, tab: view.tab, seen: !!bl.scrolledTo, detail: xp.detail.has("k:bl") };
  view.target = 0;
  await exShowInMenu({ key: "k:iso", name: "ISO", tab: "Shoot", group: "ISO", live: true });
  const iso = document.querySelector('[data-key="k:iso"]'), min = document.querySelector('[data-key="k:min"]');
  console.log(JSON.stringify({ record, exposure: { focus: iso.classList.contains("focus"), seen: !!iso.scrolledTo, other: min.classList.contains("focus") || !!min.scrolledTo } }));
})();
""")
    assert got["record"] == {"mode": "edit", "target": 3, "page": "tab", "tab": "Shoot", "seen": True, "detail": True}
    assert got["exposure"] == {"focus": True, "seen": True, "other": False}


@needs_node
def test_the_login_clears_what_floats_over_the_page(tmp_path):
    """The login takes down every menu, picker and question over the page and the editor-closed notice (the editor
    answered), drops a poll already on its way, and polls nothing while it is shown; a question that another takes
    the place of answers no."""
    got = run(tmp_path, """
(async () => {
  const picker = el("div"); document.body.append(picker); cmp.pick = { box: picker, key: "k", col: ["a", 0] };
  cmpMenuBox = el("div"); document.body.append(cmpMenuBox);
  for (const id of ["mymenu", "moremenu", "offline"]) $(id).hidden = false;
  away.since = 5; away.fails = 3;
  const first = ask("One", "First?", "Yes");
  const second = ask("Two", "Second?", "Yes");
  const before = polls;
  const answers = [];
  first.then((v) => answers.push(["first", v]));
  showLogin("Signed out.");
  await tick();
  const floating = { picker: !!cmp.pick || document.body.contains(picker), menu: !!cmpMenuBox, mymenu: $("mymenu").hidden, more: $("moremenu").hidden,
    offline: $("offline").hidden, away: [away.since, away.fails], polled: polls > before };
  second.then((v) => answers.push(["second", v]));
  await tick();
  const asked = __fetches.length;
  await poll();
  console.log(JSON.stringify({ floating, answers, polledWhileLogin: __fetches.length - asked, msg: $("login-msg").textContent }));
})();
""")
    assert got["floating"] == {"picker": False, "menu": False, "mymenu": True, "more": True, "offline": True, "away": [0, 0], "polled": True}
    assert got["answers"] == [["first", False], ["second", False]]
    assert got["polledWhileLogin"] == 0 and got["msg"] == "Signed out."


@needs_node
def test_answers_out_of_order_and_a_second_tap(tmp_path):
    """Edit history asked twice (two edits in a row): the older answer, coming last, is dropped. Write tapped twice
    before the first answer starts one check, not two."""
    got = run(tmp_path, """
drawWindows = () => {};
(async () => {
  const answers = [];
  api = (name, body) => { sent.push([name, body]); return new Promise((res) => answers.push(res)); };
  const a = loadHistory(), b = loadHistory();
  answers[1]({ steps: [{ step: 1 }] }); await b;
  answers[0]({ steps: [{ step: 0 }] }); await a;
  const history = xp.history.steps[0].step;
  sent.length = 0;
  openSend(); openSend();
  await tick();
  console.log(JSON.stringify({ history, checks: sent.map(([w]) => w), sending: xp.sending }));
})();
""")
    assert got["history"] == 1
    assert got["checks"] == ["send_check"] and got["sending"] is True


@needs_node
def test_buttons_that_are_not_buttons_and_the_menus_keys(tmp_path):
    """What acts as a button without being one (the record map's setting and shape cells, a firmware badge) is reached
    with Tab and does its work on Enter and on Space. A compare cell's menu opened with the mouse or the keyboard takes
    the focus on its first item, steps with the arrows and gives the focus back on Escape. The status bar's live
    region keeps its text node when the words are the same."""
    got = run(tmp_path, """
const opened = [];
openSetting = async (s) => { opened.push(s.key); };
redraw = () => opened.push("redraw");
const key = (node, k) => node.dispatchEvent({ type: "keydown", key: k });
const page = drawRecords({ title: "Live: records in file order", rows: [{ offset: "000010", id: 16, hex: "0x0010", shape: "2×8", big: true, raw: "00", raw_full: "00",
  value: "x", edited: false, setting: { key: "k:a", title: "Alpha", tab: "Shoot", group: "Drive", note: "" } }] });
const cells = page[2].querySelectorAll('td[role="button"]');
const attrs = cells.map((c) => [c.className, c.getAttribute("tabindex")]);
for (const c of cells) { key(c, "Enter"); key(c, " "); }
const badge = firmwareBadge({ kind: "warn", text: "⚠ firmware not checked", tip: "Why." });
key(badge, " ");
const from = el("td", { tabindex: "0" }); document.body.append(from); from.focus();
cmpShowMenu(10, 10, [["One", null, () => {}], "-", ["Two", null, () => {}]], false);
const menu = cmpMenuBox, first = document.activeElement.textContent;
key(menu, "ArrowDown");
const second = document.activeElement.textContent;
key(menu, "Escape");
$("status").textContent = "Ready";
const node = $("status").firstChild;
setText($("status"), "Ready");
console.log(JSON.stringify({ attrs, opened, toast: $("toast").textContent, role: badge.getAttribute("role"), first, second,
  back: document.activeElement === from, closed: cmpMenuBox === null, kept: $("status").firstChild === node }));
""")
    assert got["attrs"] == [["rm-shape big", "0"], ["rm-setting", "0"]]
    assert got["opened"] == ["redraw", "redraw", "k:a", "k:a"]
    assert got["toast"] == "Why." and got["role"] == "button"
    assert (got["first"], got["second"], got["back"], got["closed"]) == ("One", "Two", True, True)
    assert got["kept"]


@needs_node
def test_stepping_to_the_top_keeps_the_keyboard_off_revert(tmp_path):
    """The keyboard on "+" one step below the top of a range: Enter steps the value to its top, where "+" greys out
    and Revert is there (the row is edited). The focus goes to the setting's own value box, found by what it is, not
    by its place among the row's controls (that place is Revert's now), so Enter again reverts nothing. At the bottom,
    where "+" stays and "−" comes back, the focus stays on "+"; a row of sub-choices does not take it either."""
    got = run(tmp_path, """
act = pageAct;
const base = row("k:n", "Level", { kind: "range", lo: 0, hi: 3, step: 1, original: "0" });
api = async (name, body) => {
  sent.push([name, body]);
  const r = { ...base, value: body.value, label: String(body.value), changed: body.value !== 0 };
  return { row: r, rows: [r], rev: "r" + sent.length };
};
const plusOf = () => $("content").querySelectorAll("button").find((b) => b.getAttribute("aria-label") === "Level: one step up");
const press = async (node) => { node.click(); await tick(); await tick(); };
(async () => {
  $("content").replaceChildren(el("div", { class: "grid" }, drawRow({ ...base, value: 2, label: "2", changed: true })));
  viaKeys(); plusOf().focus();
  await press(plusOf());
  const top = document.activeElement;
  const atTop = { tag: top.tagName, ctl: top.dataset.ctl, words: top.getAttribute("aria-label") || top.textContent };
  // Enter again on whatever has the focus: a button would be pressed, a number box does nothing
  if (top.tagName === "BUTTON") await press(top);
  const afterTop = sent.map(([w, b]) => [w, b.value ?? null]);
  sent.length = 0;
  $("content").replaceChildren(el("div", { class: "grid" }, drawRow({ ...base, value: 0, label: "0", changed: false })));
  viaKeys(); plusOf().focus();
  await press(plusOf());
  const bottom = document.activeElement;
  console.log(JSON.stringify({ atTop, afterTop, bottom: bottom.getAttribute("aria-label") }));
})();
""")
    assert got["atTop"] == {"tag": "INPUT", "ctl": "value", "words": "Level"}
    assert got["afterTop"] == [["set", 3]], "Enter after the step to the top must not revert the setting"
    assert got["bottom"] == "Level: one step up"


@needs_node
def test_the_raw_value_box_is_never_stale(tmp_path):
    """The raw value box of an unmapped record keeps the keyboard after a value is written, so the page is not drawn
    again under it by a poll: it is drawn anew once the editor has taken the value (the focus on the same box), and
    typing the old value back writes it."""
    got = run(tmp_path, """
act = pageAct;
state.prefs = { page_sets: ["allow_raw_edits"] };
let held = 7;
api = async (name, body) => {
  sent.push([name, body]);
  if (name === "raw_set") { held = body.value; return { ok: true }; }
  if (name === "unmapped") return { allow_raw_edits: true, editable: true, rows: [{ id: 16, hex: "0x0010", shape: "1×1", value: String(held), int: held, changed: held !== 7 }] };
  return {};
};
view.page = "unmapped"; view.q = "";
const settle = () => new Promise((r) => setTimeout(r, 20));
(async () => {
  await drawContent(contentKey());
  const box = () => $("content").querySelectorAll("input").find((i) => i.getAttribute("type") === "number");
  viaKeys(); box().focus();
  const type = async (t) => { const b = document.activeElement; b.value = t; b.dispatchEvent({ type: "change" }); await settle(); };
  await type("12");
  const kept = document.activeElement === box();
  await type("7");
  console.log(JSON.stringify({ writes: sent.filter(([w]) => w === "raw_set").map(([, b]) => b.value), kept, held, shows: box().value,
    marked: box().classList.contains("edit") }));
})();
""")
    assert got["writes"] == [12, 7] and got["held"] == 7
    assert got["kept"] and got["shows"] == "7" and got["marked"] is False


@needs_node
def test_the_login_ends_a_write_check_and_the_toasts_undo(tmp_path):
    """A Write check waiting for the camera's read ends once the login takes the page's place: no request after it
    (it would carry no code), and Write can be pressed again. The toast goes with the login; under a modal window it
    stays audible (not inert: a screen reader still hears it) but its Undo presses nothing, nor on the login. The
    Camera link report, still in the state after the code is entered again, comes back as a modal window."""
    got = run(tmp_path, """
act = pageAct;
$("app").hidden = false;
state.job = { title: "Reading the camera" };
api = async (name) => { sent.push([name]); return name === "send_check" ? { reading: true } : {}; };
refresh = async () => {};
(async () => {
  openSend();
  await tick(); await tick();
  const open = !$("send").hidden;
  showLogin("Your session ended: enter the access code again.");
  const at = sent.length;
  await new Promise((r) => setTimeout(r, 1200));
  const write = { open, after: sent.slice(at).map(([w]) => w), sending: xp.sending };
  toast("Recall: 3 value(s) copied.", true);
  showLogin("Signed out.");
  const toastGone = $("toast").hidden;
  $("app").hidden = false; away.since = 0;
  toast("Recall: 3 value(s) copied.", true);
  ask("Write to camera", "Sure?", "Yes");
  const inert = !!$("toast").inert;
  sent.length = 0;
  $("toast").querySelector("button").click();
  await tick();
  const undoUnderWindow = sent.length;
  askOpen(false);
  toast("Recall: 3 value(s) copied.", true);
  $("app").hidden = true;
  $("toast").querySelector("button").click();
  await tick();
  const undoOnLogin = sent.length;
  $("app").hidden = false;
  const rep = { title: "Read failed", ok: false, lines: [["The camera did not answer.", false]] };
  drawReport(rep, false);
  showLogin("Your session ended: enter the access code again.");
  $("app").hidden = false;
  drawReport(rep, false);
  console.log(JSON.stringify({ write, toastGone, inert, undoUnderWindow, undoOnLogin, report: { shown: !$("report").hidden, modal: $("app").inert === true, top: dialogs.length && dialogs[dialogs.length - 1].box.id } }));
})();
""")
    assert got["write"] == {"open": True, "after": [], "sending": False}
    assert got["toastGone"] and got["inert"] is False and got["undoUnderWindow"] == 0 and got["undoOnLogin"] == 0
    assert got["report"] == {"shown": True, "modal": True, "top": "report"}


@needs_node
def test_a_page_load_cut_off_once_is_not_the_editor_gone(tmp_path):
    """One page load that cannot reach the editor (a Wi-Fi blip right after a good poll) counts as a failed poll does:
    the editor-closed notice comes after two in a row, not at once, and no toast is added on top of it."""
    got = run(tmp_path, """
$("offline").hidden = true; $("toast").hidden = true; away.fails = 0; away.since = 0;
api = async () => { throw new Offline("The editor could not be reached. Is it still running, with the web page on?"); };
view.page = "edits";
(async () => {
  await drawContent("k1");
  const once = { notice: !$("offline").hidden, fails: away.fails, toast: !$("toast").hidden };
  await drawContent("k2");
  console.log(JSON.stringify({ once, twice: !$("offline").hidden }));
})();
""")
    assert got["once"] == {"notice": False, "fails": 1, "toast": False}
    assert got["twice"] is True


@needs_node
def test_pop_ups_follow_the_window_and_the_picker_takes_the_keyboard(tmp_path):
    """A pop-up placed near the right edge is moved in again when the window narrows (a phone turned), and is no
    taller than the height the browser leaves. A family table's list marks a value the camera refuses, as a row's
    does. Compare's picker opened from the keyboard takes the focus on its value control, keeps it when drawn again,
    and gives it back to its cell on Escape; Tab out of a compare menu gives the focus back to what opened it."""
    got = run(tmp_path, """
const out = {};
showMyMenuPopup("My Menu: Alpha", [el("button", {}, "Add to My Menu")], 1000, 100, null);
innerWidth = 400; innerHeight = 500;
placePopups();
out.placed = [$("mymenu").style.left, $("mymenu").style.maxHeight];
const cell = familyCell(row("k:f", "Gamma", { kind: "choice", value: 1, cell_title: "PP1 Gamma", options: [[1, "Movie", true, null], [2, "Still", true, null]], refused: [2], refused_why: "Refused." }));
out.family = cell.querySelectorAll("option").map((o) => [o.textContent, o.title || null]);
const r = { key: "k:c", name: "Gamma", cells: [{ editable: true, stored: true, text: "Movie" }], arrows: [] };
const j = { cols: [{ src: "a", section: 0, name: "A Live", editable: true }], rows: [r] };
api = async (name) => ({ row: row("k:c", "Gamma", { kind: "choice", value: 1, options: [[1, "Movie", true, null], [2, "Still", true, null]] }) });
(async () => {
  const td = el("td", { tabindex: "0" }); document.body.append(td);
  viaKeys(); td.focus();
  await cmpPick(j, r, 0, td);
  const a = document.activeElement;
  out.picker = { inPicker: cmp.pick.box.contains(a), ctl: a.dataset.ctl };
  await cmpPickRefresh();
  out.kept = cmp.pick.box.contains(document.activeElement) && document.activeElement.dataset.ctl === "value";
  for (const f of document.listeners.keydown) f({ key: "Escape", defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } });
  out.back = document.activeElement === td && cmp.pick === null;
  cmpShowMenu(10, 10, [["One", null, () => {}]], false);
  cmpMenuBox.dispatchEvent({ type: "keydown", key: "Tab" });
  out.tab = document.activeElement === td && cmpMenuBox === null;
  console.log(JSON.stringify(out));
})();
""")
    assert got["placed"] == ["396px", "492px"]
    assert got["family"] == [["Movie", None], ["Still (refused by the camera)", "Refused."]]
    assert got["picker"] == {"inPicker": True, "ctl": "value"} and got["kept"]
    assert got["back"] and got["tab"]


@needs_node
def test_the_focus_stays_in_the_same_place_of_a_setting_shown_twice(tmp_path):
    """A setting the page shows twice keeps the keyboard in the place it was: Main's row (not its tile at the top) when
    Main is drawn anew with the focus on the row's Revert; a flat list's own row of a sub-choice (not its copy beside the
    owner's option) when the tab is drawn anew. A compare cell keeps it when the compare is drawn anew with the cell's
    new value (its words change, its column does not). A window's button greyed out leaves the focus on the window."""
    got = run(tmp_path, """
const where = (a) => a === document.body || !document.contains(a) ? "lost" : a.closest(".tile") ? "tile" : a.closest(".subs") ? "copy" : a.closest(".row") ? "row" : a.tagName;
(async () => {
  const out = {};
  const m = row("k:o", "Owner", { caption: "Owner", kind: "choice", value: 2, label: "two", changed: true, original: "one", options: [[1, "one", true, null], [2, "two", true, null]] });
  const main = { set: 0, sets: ["Stills"], tiles: [{ caption: "Owner", text: "two", edit: m, changed: true }], rows: [m] };
  view.page = "main"; view.q = ""; view.set = 0;
  api = async () => main;
  await drawContent(contentKey());
  viaKeys(); $("content").querySelectorAll("button").find((b) => b.textContent === "Revert").focus();
  await drawContent(contentKey(), true);
  out.main = [where(document.activeElement), document.activeElement.textContent];
  const sub = row("k:s", "Sub", { option: "one", kind: "choice", value: 1, options: [[1, "x", true, null], [2, "y", true, null]] });
  const owner = row("k:w", "Owner", { kind: "choice", value: 1, label: "one", options: [[1, "one", true, null], [2, "two", true, null]],
    subs: { options: ["one"], now: "one", rows: [sub], edited: 0 } });
  const group = { name: "Drive", color: "#000", rows: [owner, sub] };
  state.tabs = ["Shoot"]; state.prefs = { flat_list: true };
  view.page = "tab"; view.tab = "Shoot";
  openGroups.set("Shoot", new Set(["Drive"]));
  api = async () => ({ groups: [group] });
  await drawContent(contentKey());
  const own = [...$("content").querySelectorAll('[data-key="k:s"]')].find((n) => !n.closest(".subs"));
  viaKeys(); own.querySelector("select").focus();
  await drawContent(contentKey(), true);
  out.flat = where(document.activeElement);
  const cols = [{ src: "a", section: 0, name: "A Live", editable: true }];
  const answer = (text) => ({ cols, rows: [{ key: "k:c", name: "Gamma", where: "", in_sets: false, cells: [{ editable: true, stored: true, text }], arrows: [] }], three: null });
  $("content").replaceChildren(el("table", {}, el("tbody", {}, cmpRow(answer("Movie"), answer("Movie").rows[0], 0))));
  viaKeys(); $("content").querySelector("td.cmp-v").focus();
  const mark = focusMark($("content"));
  $("content").replaceChildren(el("table", {}, el("tbody", {}, cmpRow(answer("Still"), answer("Still").rows[0], 0))));
  focusAgain($("content"), mark);
  out.cell = document.activeElement.classList.contains("cmp-v") && document.activeElement.getAttribute("aria-label").includes("Still");
  const go = (off) => el("button", { disabled: off }, "Connect and read from camera");
  fillWindow("connect", "Connect to the camera", go(false));
  viaKeys(); $("connect").querySelector("button:not(.sel)").focus();
  fillWindow("connect", "Connect to the camera", go(true));
  out.window = document.activeElement === $("connect");
  console.log(JSON.stringify(out));
})();
""")
    assert got["main"] == ["row", "Revert"], "the Main row's Revert, not the tile's list"
    assert got["flat"] == "row", "the sub-choice's own row, not its copy in the owner's details"
    assert got["cell"] and got["window"]


@needs_node
def test_keyboard_or_pointer_is_the_last_input(tmp_path):
    """A list reached with the keys, then a click elsewhere that moves no focus (Safari focuses no clicked button):
    the change lets go of the focus. A list clicked open, then stepped with an arrow key: the change keeps it. A raw
    value written while the box keeps the keyboard draws the page once, and not when digits were typed meanwhile."""
    got = run(tmp_path, """
const r = row("k:a", "Alpha", { kind: "choice", value: 1, label: "one", options: [[1, "one", true, null], [2, "two", true, null]] });
act = pageAct;
api = async (name, body) => { sent.push([name, body]); return { row: { ...r, value: body.value, changed: true }, rows: [{ ...r, value: body.value, changed: true }], rev: "r2" }; };
const arrow = () => { for (const f of document.listeners.keydown) f({ key: "ArrowDown", shiftKey: false, defaultPrevented: false, preventDefault() {} }); };
const change = async (sel) => { sel.value = "2"; sel.dispatchEvent({ type: "change" }); await tick(); await tick(); };
(async () => {
  const out = {};
  $("content").replaceChildren(el("div", { class: "grid" }, drawRow(r)));
  viaKeys(); $("content").querySelector("select").focus();
  viaPointer();
  await change($("content").querySelector("select"));
  out.clickedAway = document.activeElement === document.body;
  $("content").replaceChildren(el("div", { class: "grid" }, drawRow(r)));
  viaPointer(); $("content").querySelector("select").focus();
  arrow();
  await change($("content").querySelector("select"));
  out.arrowKept = document.activeElement.tagName === "SELECT" && $("content").contains(document.activeElement);
  state.prefs = { page_sets: ["allow_raw_edits"] };
  let held = 7, release = null;
  const loads = () => sent.filter(([w]) => w === "unmapped").length;
  api = async (name, body) => {
    sent.push([name, body]);
    if (name === "raw_set") { await new Promise((res) => { release = res; }); held = body.value; return { ok: true }; }
    return { allow_raw_edits: true, editable: true, rows: [{ id: 16, hex: "0x0010", shape: "1×1", value: String(held), int: held, changed: true }] };
  };
  view.page = "unmapped"; view.q = "";
  await drawContent(contentKey());
  const box = () => $("content").querySelectorAll("input").find((i) => i.getAttribute("type") === "number");
  viaKeys(); box().focus();
  const before = loads();
  box().value = "12"; box().dispatchEvent({ type: "change" });
  await tick(); release(); await new Promise((res) => setTimeout(res, 20));
  out.oneDraw = loads() - before;
  const now = loads();
  box().value = "30"; box().dispatchEvent({ type: "change" });
  await tick(); box().value = "305"; release(); await new Promise((res) => setTimeout(res, 20));
  out.typedMeanwhile = { draws: loads() - now, shows: box().value };
  console.log(JSON.stringify(out));
})();
""")
    assert got["clickedAway"] and got["arrowKept"]
    assert got["oneDraw"] == 1
    assert got["typedMeanwhile"] == {"draws": 0, "shows": "305"}


# a comparison of file A's live settings and Memory 1 with file B's live settings, from made-up answers that follow the
# page's columns (`cmp.cols`); each request is kept in `asked`, with the columns or the three-way filter it asked for
MATRIX = """
state.file = { editable: true, name: "A.DAT", model: "M", saved: "" };
state.compare = { b: { name: "B.DAT", model: "M", saved: "" }, base: null, cols: [], tabs: ["Shoot"] };
state.edits = 0;
view.mode = "compare"; view.page = "compare";
cmp.cols = [["a", 0], ["b", 0], ["a", 3]];
const asked = [];
const setName = { 0: "Live", 3: "Memory 1" };
const answer = (differs = true, three = null) => {
  const cols = cmp.cols.map(([src, section]) => ({ src, section, name: `${src.toUpperCase()} · ${setName[section]}`, editable: src === "a" }));
  return { cols, counts: cols.map((c, i) => (differs ? i : 0)), shown: 1, total: 1, three, editable: true, dial: [], whole_sets: [],
    sections: [[0, "Live", "Live settings"], [3, "M1", "Memory 1"]],
    rows: [{ key: "k:a", name: "Alpha", where: "", tab: "Shoot", group: "Drive", color: "#000", in_sets: true, differs, mark: differs ? "differs" : "same",
      cells: cols.map((c, i) => ({ text: differs && i ? "two" : "one", stored: true, editable: c.editable, differs: differs && i > 0 })),
      arrows: cols.slice(1).map(() => [false, false]) }] };
};
api = async (name, body) => { asked.push([name, JSON.parse(JSON.stringify(body.cols)), body.three]); return answer(); };
const press = (node, key) => node.dispatchEvent({ type: "keydown", key });
const heads = () => $("content").querySelectorAll("button.cmp-head");
const stops = () => heads().map((b) => b.getAttribute("tabindex")).join(" ");
const on = () => document.activeElement.dataset.col || document.activeElement.textContent;
const settle = async () => { for (let i = 0; i < 4; i++) await tick(); };
"""


@needs_node
def test_compare_column_headers_are_one_tab_stop_the_arrows_move_along(tmp_path):
    """Compare's column headers are one Tab stop (a roving tabindex): Tab lands on one, the arrows move to the header
    beside it (stopping at either end), Home and End to the first and the last, and the stop goes with the focus, which
    the page's help line says. Each header is named in words (its column, whether it is never changed, how many rows
    differ) and opens its menu as a button does: Enter, Space on its release, a click (a second one closes it, the
    press on the header not closing it first). Enter held down chooses nothing in the menu. An item chosen with the
    keys gives the focus back, so the compare drawn anew for its new columns keeps it on the same column's header, now
    first; so do the next poll and a fold, and a header focused another way takes the stop and keeps the focus though
    its name changed. A column removed hands the focus to the header now in its place, the last one's to the new last;
    the columns cut down to one (no header left) hand it to the removed column's toggle in the column picker."""
    got = run(tmp_path, MATRIX + """
const toggle = (label) => $("content").querySelectorAll(".cmp-pick button").find((b) => b.getAttribute("aria-label") === label);
const choose = async (label) => { cmpMenuBox.querySelectorAll("button").find((x) => x.textContent === label).click(); await settle(); };
const tap = (n) => { for (const f of document.listeners.pointerdown) f({ target: n }); n.click(); };
const head = () => document.activeElement.classList.contains("cmp-head") && $("content").contains(document.activeElement);
const plain = api;
(async () => {
  const out = {};
  await drawContent(contentKey());
  out.first = { stops: stops(), names: heads().map((b) => b.getAttribute("aria-label")), popup: heads()[0].getAttribute("aria-haspopup") };
  out.help = $("content").querySelector("p").textContent.includes("a click on a column header opens its menu (← and → move between the headers)");
  viaKeys(); heads()[0].focus();
  out.moves = ["ArrowRight", "ArrowRight", "ArrowRight", "Home", "ArrowLeft", "End"].map((k) => { press(document.activeElement, k); return [k, on(), stops()]; });
  press(document.activeElement, "Home"); press(document.activeElement, "ArrowRight");
  const b = document.activeElement;
  press(b, "Enter");
  out.menu = { items: cmpMenuBox.querySelectorAll("button").map((x) => x.textContent), inMenu: cmpMenuBox.contains(document.activeElement), expanded: b.getAttribute("aria-expanded") };
  const n = asked.length;
  document.activeElement.dispatchEvent({ type: "keydown", key: "Enter", repeat: true });
  await settle();
  out.held = { open: !!cmpMenuBox, asked: asked.length - n };
  await choose("Make baseline");
  out.baseline = { cols: asked[asked.length - 1][1], on: on(), stops: stops(), anew: document.activeElement !== b, expanded: document.activeElement.getAttribute("aria-expanded") };
  const was = document.activeElement;
  state.rev = 2;
  await drawContent(contentKey());
  out.poll = { on: on(), anew: document.activeElement !== was };
  redrawCompare();
  out.fold = on();
  const h0 = document.activeElement;
  press(h0, " ");
  const onPress = !!cmpMenuBox;
  h0.dispatchEvent({ type: "keyup", key: " " });
  const open = !!cmpMenuBox;
  for (const f of document.listeners.keydown) f({ key: "Escape", defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } });
  out.space = { onPress, open, closed: cmpMenuBox === null, on: on(), expanded: document.activeElement.getAttribute("aria-expanded") };
  heads()[2].focus();
  const taken = stops();
  api = async (name, body) => { const j = await plain(name, body); j.counts = j.counts.map((c) => c + 5); return j; };
  state.rev = 3;
  await drawContent(contentKey());
  out.other = { taken, on: on(), head: head(), name: document.activeElement.getAttribute("aria-label") };
  api = plain;
  press(document.activeElement, "Enter");
  await choose("Remove column");
  out.last = { cols: asked[asked.length - 1][1], on: on(), head: head(), stops: stops() };
  press(document.activeElement, "Home");
  press(document.activeElement, "Enter");
  await choose("Remove column");
  const t = document.activeElement;
  out.one = { cols: asked[asked.length - 1][1], heads: heads().length, on: t.getAttribute("aria-label"), pressed: t.getAttribute("aria-pressed"), shown: $("content").contains(t) };
  press(t, "Enter");
  await settle();
  out.back = { cols: asked[asked.length - 1][1], on: document.activeElement.getAttribute("aria-label"), pressed: document.activeElement.getAttribute("aria-pressed") };
  toggle("A M1").focus(); toggle("A M1").click();
  await settle();
  heads()[0].focus();
  press(document.activeElement, "Enter");
  await choose("Remove column");
  out.place = { cols: asked[asked.length - 1][1], on: on(), head: head(), stops: stops() };
  viaPointer();
  const h = heads()[1];
  tap(h);
  const opened = !!cmpMenuBox && cmpMenuFrom === h;
  cmpMenuAt = 0;
  tap(h);
  out.click = { opened, closed: cmpMenuBox === null, stops: stops() };
  console.log(JSON.stringify(out));
})();
""")
    assert got["first"] == {"stops": "0 -1 -1", "popup": "menu",
                            "names": ["A · Live: baseline", "B · Live, never changed: 1 differ", "A · Memory 1: 2 differ"]}
    assert got["help"]
    assert got["moves"] == [["ArrowRight", "b:0", "-1 0 -1"], ["ArrowRight", "a:3", "-1 -1 0"], ["ArrowRight", "a:3", "-1 -1 0"],
                            ["Home", "a:0", "0 -1 -1"], ["ArrowLeft", "a:0", "0 -1 -1"], ["End", "a:3", "-1 -1 0"]]
    assert got["menu"] == {"items": ["Make baseline", "Remove column", "Copy all shown rows to A · Live", "Copy all shown rows to A · Memory 1"],
                           "inMenu": True, "expanded": "true"}
    assert got["held"] == {"open": True, "asked": 0}, "Enter held down on the header must not choose the menu's first item"
    # Make baseline: B's live settings first, the keyboard on its header, drawn anew
    assert got["baseline"] == {"cols": [["b", 0], ["a", 0], ["a", 3]], "on": "b:0", "stops": "0 -1 -1", "anew": True, "expanded": "false"}
    assert got["poll"] == {"on": "b:0", "anew": True} and got["fold"] == "b:0"
    assert got["space"] == {"onPress": False, "open": True, "closed": True, "on": "b:0", "expanded": "false"}
    assert got["other"] == {"taken": "-1 -1 0", "on": "a:3", "head": True, "name": "A · Memory 1: 7 differ"}
    assert got["last"] == {"cols": [["b", 0], ["a", 0]], "on": "a:0", "head": True, "stops": "-1 0"}
    assert got["one"] == {"cols": [["a", 0]], "heads": 0, "on": "B Live", "pressed": "false", "shown": True}
    assert got["back"] == {"cols": [["a", 0], ["b", 0]], "on": "B Live", "pressed": "true"}
    assert got["place"] == {"cols": [["b", 0], ["a", 3]], "on": "b:0", "head": True, "stops": "0 -1"}
    assert got["click"] == {"opened": True, "closed": True, "stops": "-1 0"}


@needs_node
def test_greyed_out_toolbar_buttons_stay_reachable_and_say_why(tmp_path):
    """A greyed-out button of the toolbar, the Compare bar and the compare page is not disabled (Tab would skip it): it
    says it is unavailable (`aria-disabled`) and, pressed, says why in the toast instead of acting; Undo folded into
    More is greyed out there too, takes the focus as any item does, and says why when chosen. The column picker's
    toggles are told apart by their file's letter, Previous and Next name their keys, and Next and Merge keep the
    keyboard when the compare is drawn anew (Merge's words hold a count that changed). The three-way list draws the
    compare at once, keeping the focus, though a list of the page has it; a poll then leaves it alone."""
    got = run(tmp_path, MATRIX + """
(async () => {
  const out = {};
  const said = (b) => { $("toast").textContent = ""; b.click(); return $("toast").textContent; };
  state = { ...state, tabs: ["Shoot"], link: { up: null, text: "USB", state: "idle" }, job: null, can_undo: false, can_redo: true, report: null, recent: [], history: 0, camera: null, status: "" };
  api = async () => answer();
  pageRender();
  out.undo = { disabled: $("b-undo").disabled, aria: $("b-undo").getAttribute("aria-disabled"), said: said($("b-undo")), redo: $("b-redo").getAttribute("aria-disabled") };
  const undo = $("b-undo");
  undo.classList.add("folded"); bar1.append(undo);
  openMore(true);
  const item = $("moremenu").querySelector("button");
  out.more = { off: item.classList.contains("off"), aria: item.getAttribute("aria-disabled"), disabled: item.disabled, focused: document.activeElement === item, said: said(item) };
  undo.classList.remove("folded");
  state.edits = 2;
  drawCompareBar(state, state.file);
  const swap = $("b-swap");
  out.swap = { disabled: swap.disabled, aria: swap.getAttribute("aria-disabled"), off: swap.classList.contains("off"), said: said(swap) };
  state.edits = 0;
  drawCompareBar(state, state.file);
  said(swap);
  await tick();
  out.swapOn = swap.getAttribute("aria-disabled");
  cmp.cols = [["a", 0]];
  drawCompareBar(state, state.file);
  out.csv = said($("b-csv-cmp"));
  setFontScale(1.4);
  out.font = { said: said($("b-font-inc")), pct: $("font-scale-pct").textContent };
  setFontScale(1.0);
  cmp.cols = [["a", 0], ["b", 0]];
  api = async () => answer(false);
  await drawContent(contentKey());
  const button = (label) => $("content").querySelectorAll("button").find((b) => b.getAttribute("aria-label") === label);
  out.next = { disabled: button("Next difference").disabled, aria: button("Next difference").getAttribute("aria-disabled"),
    keys: [button("Previous difference").getAttribute("aria-keyshortcuts"), button("Next difference").getAttribute("aria-keyshortcuts")], said: said(button("Next difference")) };
  viaKeys(); button("Next difference").focus();
  state.rev = 3;
  await drawContent(contentKey());
  out.nextKept = $("content").contains(document.activeElement) && document.activeElement.getAttribute("aria-label");
  out.picker = $("content").querySelectorAll(".cmp-pick button").map((b) => b.getAttribute("aria-label"));
  const three = { cols: [["base", 0], ["a", 0], ["b", 0]], a: 1, b: 3, both: 0, conflict: 0, against: "", tags: {}, filters: [["all", "All rows"], ["conflict", "Conflicts"]] };
  api = async (name, body) => { asked.push([name, null, body.three]); return answer(false, three); };
  cmp.three = "all";
  state.rev = 4;
  await drawContent(contentKey());
  const mergeOf = () => $("content").querySelectorAll("button").find((b) => b.textContent.startsWith("Merge B into A"));
  viaKeys(); mergeOf().focus(); mergeOf().click();
  three.b = 0;
  state.rev = 5;
  await drawContent(contentKey());
  const m = document.activeElement;
  out.merge = { kept: $("content").contains(m) && m.textContent, aria: m.getAttribute("aria-disabled"), said: said(m) };
  const list = $("content").querySelector("select");
  viaKeys(); list.focus();
  const before = asked.length;
  list.value = "conflict"; list.dispatchEvent({ type: "change" });
  await settle();
  const now = document.activeElement;
  out.three = { asked: asked.slice(before).map((a) => a[2]), kept: now.tagName === "SELECT" && now !== list && $("content").contains(now) };
  const n = asked.length;
  state.rev = 6;
  maybeDraw();
  await settle();
  out.pollLeaves = asked.length === n && document.activeElement === now;
  out.sent = sent.map(([w]) => w);
  console.log(JSON.stringify(out));
})();
""")
    assert got["undo"] == {"disabled": False, "aria": "true", "said": "There is no edit to undo.", "redo": "false"}
    # folded into More, it is greyed out there too, takes the focus as any item does, and says why when chosen
    assert got["more"] == {"off": True, "aria": "true", "disabled": False, "focused": True, "said": "There is no edit to undo."}
    assert got["swap"] == {"disabled": False, "aria": "true", "off": True,
                           "said": "Swap A/B opens both files again, so A's edits would be lost: download file A or revert its edits first."}
    assert got["swapOn"] == "false" and got["sent"] == ["swap_ab", "merge"], "only what was pressed while on was sent"
    assert got["csv"] == "Pick at least two columns first: the export is the comparison as shown."
    assert got["font"] == {"said": "The text is at its largest size (140 %).", "pct": "140%"}
    assert got["next"] == {"disabled": False, "aria": "true", "keys": ["Shift+F3 Alt+ArrowUp", "F3 Alt+ArrowDown"],
                           "said": "No row shown differs from the baseline: there is no difference to step to."}
    assert got["picker"] == ["A Live", "A M1", "B Live", "B M1"]
    assert got["nextKept"] == "Next difference"
    # merged with the keys: drawn anew with nothing left to merge, the keyboard stays on Merge, now greyed out
    assert got["merge"] == {"kept": "Merge B into A (0)", "aria": "true",
                            "said": "B made no change where A kept the base value: there is nothing to merge."}
    assert got["three"] == {"asked": ["conflict"], "kept": True}
    assert got["pollLeaves"], "a poll must not draw the compare under the three-way list that has the focus"


def test_only_the_status_bar_and_the_toast_speak_and_each_open_is_named():
    """The page's live regions are the status bar's (its edits and its message), the toast and the editor-closed
    notice: the toolbar's spinner says nothing to a screen reader (the status bar says in words what the camera is
    doing), the change map is for the pointer only, and the script makes no live region of its own. The Compare bar's
    three Open… buttons are told apart by their file."""
    page, script = PAGE.read_text(encoding="utf-8"), APP.read_text(encoding="utf-8")
    speaking = re.findall(r'<[^>]*\bid="([^"]+)"[^>]*(?:role="(?:status|alert)"|aria-live=)', page)
    assert sorted(speaking) == ["edits", "offline", "status", "toast"]
    busy = re.search(r'<span id="busy"[^>]*>', page).group(0)
    assert 'aria-hidden="true"' in busy and "role=" not in busy
    assert 'aria-hidden="true"' in re.search(r'<div id="cmp-map"[^>]*>', page).group(0)
    assert not re.search(r'aria-live|role: "(?:status|alert)"', script)
    opens = [re.search(rf'<button id="b-open-{w}"[^>]*aria-label="([^"]+)"', page).group(1) for w in ("a", "b", "base")]
    assert opens == ["Open file A…", "Open file B…", "Open a base file…"]


# the editor's six Settings tabs as the state gives them (`settings_tabs`), About the last (`SETTINGS_ABOUT`)
SETTINGS_TABS = """[["Appearance", "Theme."], ["Camera link", "USB."], ["Editing & Compare", "Compare."], ["Backups & start-up", "Copies."],
  ["Camera support & web page", "Definitions."], ["ℹ About", "Which editor this is."]]"""


@needs_node
def test_the_window_opened_last_stacks_first(tmp_path):
    """The page's windows stack from the top by when they were opened or asked for, the newest first, under the
    questions (ask, send, report), which keep their place first: #windows does not scroll and each window is as tall
    as the screen at most, so one that landed below another could be out of sight. Backups from the toolbar, then
    Settings: Settings first. Changes from Settings > About: Changes first. Then the status bar's version: Settings
    first again, and on top for Escape, which closes it and leaves Changes, with the focus left where it was. Backups
    from Settings > Backups & start-up: Backups first. The page itself opens with its sections in that order."""
    page = PAGE.read_text(encoding="utf-8")
    sections = re.findall(r'<section id="([^"]+)"', re.search(r'<div id="windows">(.*?)\n</div>', page, re.S).group(1))
    assert sections[:3] == ["ask", "send", "report"], sections
    got = run(tmp_path, """
(async () => {
  api = async (name) => (name === "backups" ? { list: [] } : { blocks: [] });
  state = { ...state, version: "0.2.0", version_short: "0.2.0", not_sony: "Not Sony's.", settings_tabs: """ + SETTINGS_TABS + """,
    about: { links: [], details: "d" }, dirs: { originals: "o", camera: "c" }, prefs: { prefs_path: "prefs.json", theme: "dark", zoom: 1, density: 1 } };
  // #windows as the page has it (the harness makes each element on its first use, outside it)
  for (const id of ["backdrop", ...""" + json.dumps(sections) + """]) $("windows").append($(id));
  $("mymenu").hidden = true;
  const order = () => $("windows").children.map((n) => n.id).filter((id) => id !== "backdrop");
  const esc = () => { const e = { key: "Escape", shiftKey: false, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
    for (const f of document.listeners.keydown) f(e); };
  const button = (box, words) => $(box).querySelectorAll("button").find((b) => b.textContent === words);
  drawVersion(state);
  const seen = { start: order() };
  // A: Backups from the toolbar, then Settings from the toolbar
  $("b-backups").click(); await tick();
  $("b-settings").click(); await tick();
  seen.a = order();
  // Changes from Settings > About
  $("foot-version").click();
  button("settings", "Changes").click(); await tick();
  seen.changes = order();
  // B: then the version, the focus in Changes
  const kept = button("changelog", "✖\ufe0e") || $("changelog").querySelector("button");
  kept.focus();
  $("foot-version").click();
  seen.b = { order: order(), tab: xp.settingsTab, focus: document.activeElement === kept };
  esc();
  seen.esc = { settings: xp.windows.settings, changes: xp.windows.changelog, backups: xp.windows.backups };
  esc();
  seen.esc2 = { changes: xp.windows.changelog };
  // Backups from Settings > Backups & start-up, Backups open already: to the front
  openSettings(3);
  button("settings", "📂 View backups…").click(); await tick();
  seen.fromSettings = order();
  console.log(JSON.stringify(seen));
})();
""")
    fixed = ["ask", "send", "report"]
    assert got["start"] == sections
    assert got["a"][:5] == fixed + ["settings", "backups"], got["a"]
    assert got["changes"][:6] == fixed + ["changelog", "settings", "backups"], got["changes"]
    assert got["b"] == {"order": got["b"]["order"], "tab": 5, "focus": True} and got["b"]["order"][:6] == fixed + ["settings", "changelog", "backups"], got["b"]
    assert got["esc"] == {"settings": False, "changes": True, "backups": True}, "Escape closes the window on top, Settings"
    assert got["esc2"] == {"changes": False}
    assert got["fromSettings"][:5] == fixed + ["backups", "settings"], got["fromSettings"]
    assert sorted(got["fromSettings"]) == sorted(sections), "every window kept, none added"


@needs_node
def test_the_status_bar_version_opens_settings_on_about_and_its_changes(tmp_path):
    """As in the window: the status bar's right end names the editor and its short version, the whole version on
    hover, and a click opens Settings on its last tab, About, from wherever Settings was (closed, or open on another
    tab). About gives the version, the build (when there is one), the cameras it works with and the not-affiliated
    line; its Changes asks the editor for the changelog and shows it, release by release; the licences, a page on the
    editor's computer, are greyed out with where they are. The welcome page names no version of its own: the status
    bar's is the only one on that screen."""
    got = run(tmp_path, """
(async () => {
  const asked = [];
  api = async (name) => { asked.push(name); return { blocks: [[2, "Unreleased"], [3, "The editor"], [1, "A point."]] }; };
  state = { ...state, version: "0.2.0 (build 1a2b3c4)", version_short: "0.2.0", build: "1a2b3c4", works_with: ["ILCE-1M2"], not_sony: "Not Sony's.",
    settings_tabs: """ + SETTINGS_TABS + """, prefs: { prefs_path: "prefs.json", theme: "dark", zoom: 1, density: 1 } };
  drawVersion(state);
  const b = $("foot-version");
  const label = { text: b.textContent, title: b.title, aria: b.getAttribute("aria-label") };
  const welcomeLinks = welcome().querySelectorAll("button, a").map((n) => n.textContent).filter((t) => t.includes("0.2.0"));
  const welcomeText = welcome().textContent;
  b.click();
  const settings = $("settings");
  const texts = settings.querySelectorAll("p, div").map((n) => n.textContent);
  const buttons = settings.querySelectorAll("button").map((n) => [n.textContent, !!n.disabled]);
  const shown = { open: xp.windows.settings, tab: xp.settingsTab, about: SETTINGS_ABOUT, hidden: settings.hidden, title: settings.querySelector(".title > span").textContent,
    on: settings.querySelectorAll(".set-tabs button.on").map((n) => n.textContent), windows: Object.keys(xp.windows) };
  settings.querySelectorAll("button").find((n) => n.textContent === "Changes").click();
  await tick(); await tick();
  const changes = { open: xp.windows.changelog, settings: xp.windows.settings, asked, title: $("changelog").querySelector(".title > span").textContent,
    heads: $("changelog").querySelectorAll("h1").map((n) => n.textContent), text: $("changelog").textContent,
    clickable: $("changelog").querySelectorAll("button, a").map((n) => n.textContent).filter((t) => t.includes("0.2.0")) };
  delete state.build;
  xp.keys.settings = null;
  drawSettings();
  const noBuild = $("settings").textContent;
  // from another tab: the version turns Settings to About
  settings.querySelectorAll(".set-tabs button").find((n) => n.textContent === "Appearance").click();
  const away = xp.settingsTab;
  b.click();
  console.log(JSON.stringify({ label, welcomeLinks, welcomeText, texts, buttons, shown, changes, noBuild, away, back: xp.settingsTab }));
})();
""")
    assert got["label"] == {"text": "Camset Editor 0.2.0", "title": "Camset Editor 0.2.0 (build 1a2b3c4)\nClick for Settings > About", "aria": "Camset Editor 0.2.0"}
    assert "0.2.0" not in got["welcomeText"] and got["welcomeLinks"] == [], "no version on the welcome page"
    assert got["shown"] == {"open": True, "tab": 5, "about": 5, "hidden": False, "title": "Settings", "on": ["ℹ About"],
                            "windows": ["backups", "history", "settings", "connect", "changelog"]}, "no About window of its own"
    for t in ["Camset Editor", "Version 0.2.0", "Build 1a2b3c4", "Works with: ILCE-1M2", "Not Sony's.", "Which editor this is."]:
        assert t in got["texts"], (t, got["texts"])
    assert ["Changes", False] in got["buttons"] and ["Third-party licences", True] in got["buttons"]
    assert got["changes"]["open"] is True and got["changes"]["settings"] is True and got["changes"]["asked"] == ["changelog"]
    assert got["changes"]["title"] == "Changes" and got["changes"]["clickable"] == []
    assert got["changes"]["heads"] == ["Unreleased"] and "A point." in got["changes"]["text"] and "Camset Editor 0.2.0 (build 1a2b3c4)" in got["changes"]["text"]
    assert "Build" not in got["noBuild"] and "Version 0.2.0" in got["noBuild"]
    assert (got["away"], got["back"]) == (0, 5)


@needs_node
def test_the_version_turns_settings_to_about_with_a_settings_field_focused(tmp_path):
    """Settings open on another tab with the focus in one of its text fields, which `drawWindows` leaves alone so
    that a poll does not draw it away from under the cursor: the status bar's version still turns Settings to About,
    drawn there and then, as a click on a tab draws it."""
    got = run(tmp_path, """
(async () => {
  api = async () => ({ blocks: [] });
  state = { ...state, version: "0.2.0", version_short: "0.2.0", not_sony: "Not Sony's.", settings_tabs: """ + SETTINGS_TABS + """,
    about: { links: [], details: "d" }, prefs: { prefs_path: "prefs.json", theme: "dark", zoom: 1, density: 1 } };
  drawVersion(state);
  openSettings(0);
  const field = el("input", { type: "text" });
  field.type = "text";
  $("settings").querySelector(".wbody").append(field);
  field.focus();
  xp.keys.settings = null;
  drawWindows();
  const left = $("settings").contains(field);
  const before = $("settings").textContent.includes("Version 0.2.0");
  $("foot-version").click();
  console.log(JSON.stringify({ left, before, tab: xp.settingsTab, about: $("settings").textContent.includes("Version 0.2.0"),
    on: $("settings").querySelectorAll(".set-tabs button.on").map((n) => n.textContent) }));
})();
""")
    assert got["left"] is True, "a poll leaves Settings alone under the cursor"
    assert {k: got[k] for k in ("before", "tab", "about", "on")} == {"before": False, "tab": 5, "about": True, "on": ["ℹ About"]}


@needs_node
def test_changes_says_when_the_editor_could_not_be_asked_and_asks_again(tmp_path):
    """The page's Changes window, its request failed: it says so in plain words and how to try again, and keeps
    nothing, so closing and opening it again asks the editor again and shows the changelog."""
    got = run(tmp_path, """
(async () => {
  const asked = [];
  let fail = true;
  api = async (name) => { asked.push(name); if (fail) throw new Error("The editor did not answer."); return { blocks: [[2, "Unreleased"], [1, "A point."]] }; };
  state = { ...state, version: "0.2.0" };
  openWindow("changelog");
  await tick(); await tick();
  const failedText = $("changelog").textContent;
  const kept = xp.changelog;
  fail = false;
  closeWindow("changelog");
  openWindow("changelog");
  await tick(); await tick();
  console.log(JSON.stringify({ asked, failedText, kept, again: $("changelog").textContent, toast: $("toast").textContent }));
})();
""")
    assert "could not be asked" in got["failedText"] and "open it again to try again" in got["failedText"]
    assert "Asking the editor" not in got["failedText"] and got["kept"] is None
    assert got["toast"] == "The editor did not answer."
    assert got["asked"] == ["changelog", "changelog"]
    assert "A point." in got["again"] and "could not be asked" not in got["again"]


@needs_node
def test_settings_foot_names_where_settings_are_kept_and_nothing_of_abouts(tmp_path):
    """As in the window: Settings end with where the settings are kept, on every tab; the version, the not-affiliated
    line, Changes and a way into About are the About tab's alone, so the foot has no button and no version."""
    got = run(tmp_path, """
(async () => {
  api = async () => ({ blocks: [] });
  state = { ...state, version: "0.2.0 (build 1a2b3c4)", version_short: "0.2.0", not_sony: "Not Sony's.", settings_tabs: """ + SETTINGS_TABS + """,
    about: { links: [], details: "d" }, prefs: { prefs_path: "prefs.json", theme: "dark", zoom: 1, density: 1 } };
  const feet = [];
  for (const tab of [0, 2, 3, SETTINGS_ABOUT]) {
    xp.settingsTab = tab;
    openWindow("settings");
    const foot = $("settings").querySelector(".set-foot");
    feet.push({ tab, buttons: foot.querySelectorAll("button, a").length, text: foot.textContent, title: foot.querySelector("span").title });
  }
  console.log(JSON.stringify({ feet }));
})();
""")
    for f in got["feet"]:
        assert f == {"tab": f["tab"], "buttons": 0, "text": "⚙\ufe0e Preferences", "title": "Preferences file: prefs.json"}, f


@needs_node
def test_about_has_the_windows_lines_links_and_copy_details(tmp_path):
    """The page's Settings > About draws what the editor sends (`state.about`, the window's words): the system, the
    camera link program and the licence lines; the project's pages as links that open in a new tab and tell those
    pages nothing of the page; and Copy details, which puts the editor's details on the clipboard and says so."""
    got = run(tmp_path, """
(async () => {
  const copied = [];
  navigator.clipboard.writeText = async (t) => { copied.push(t); };
  state = { ...state, version: "0.2.0", version_short: "0.2.0", works_with: ["ILCE-1M2 (firmware 4.00)"], not_sony: "Not Sony's.",
    about: { system: "System: macOS 15.2 (aarch64)", helper: "Camera link program: found", licence: "MIT licence. Copyright (c) X.",
      links: [{ text: "Project page", url: "https://example.com/p", title: "P" }, { text: "Report a problem", url: "https://example.com/p/issues", title: "R" }],
      details: "Camset Editor 0.2.0\\nSystem: macOS 15.2 (aarch64)" }, settings_tabs: """ + SETTINGS_TABS + """, prefs: { prefs_path: "prefs.json" } };
  openSettings(SETTINGS_ABOUT);
  const about = $("settings");
  const links = about.querySelectorAll("a").map((n) => [n.textContent, n.getAttribute("href"), n.getAttribute("target"), n.getAttribute("rel")]);
  about.querySelectorAll("button").find((b) => b.textContent === "Copy details").click();
  await tick(); await tick();
  console.log(JSON.stringify({ texts: about.querySelectorAll("p").map((n) => n.textContent), links, copied, toast: $("toast").textContent }));
})();
""")
    for line in ["System: macOS 15.2 (aarch64)", "Works with: ILCE-1M2 (firmware 4.00)", "Camera link program: found", "MIT licence. Copyright (c) X."]:
        assert line in got["texts"], got["texts"]
    assert got["links"] == [["Project page", "https://example.com/p", "_blank", "noopener noreferrer"],
                            ["Report a problem", "https://example.com/p/issues", "_blank", "noopener noreferrer"]]
    assert got["copied"] == ["Camset Editor 0.2.0\nSystem: macOS 15.2 (aarch64)"]
    assert got["toast"] == "About's details copied, to paste into a message about a problem"


@needs_node
def test_copy_details_falls_back_to_the_copy_command(tmp_path):
    """On the page's plain http address a browser has no Clipboard API: Copy details then copies with the older copy
    command from a text box it takes away again, whether the command copies or fails; a failure says to select the
    lines instead."""
    got = run(tmp_path, """
(async () => {
  Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
  const make = document.createElement.bind(document);
  document.createElement = (tag) => { const n = make(tag); if (tag === "textarea") n.setSelectionRange = () => {}; return n; };
  const ran = [];
  const before = document.body.children.length;
  document.execCommand = (c) => { ran.push(c); return true; };
  const copied = await copyText("details");
  const kept = document.body.children.length;
  document.execCommand = () => { throw new Error("refused"); };
  state = { ...state, version: "0.2.0", version_short: "0.2.0", not_sony: "Not Sony's.", about: { links: [], details: "details" },
    settings_tabs: """ + SETTINGS_TABS + """, prefs: { prefs_path: "prefs.json" } };
  openSettings(SETTINGS_ABOUT);
  $("settings").querySelectorAll("button").find((b) => b.textContent === "Copy details").click();
  await tick(); await tick();
  console.log(JSON.stringify({ copied, ran, left: [kept - before, document.body.children.length - before], toast: $("toast").textContent }));
})();
""")
    assert got["copied"] is True and got["ran"] == ["copy"]
    assert got["left"] == [0, 0], "the text box is taken away both times"
    assert got["toast"] == "This browser did not let the page copy: select the lines above and copy them"
