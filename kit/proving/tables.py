"""Tables, Fn Menu tiles and Custom Key/Dial Set.: the jobs kit/table_walk.py's walk gives (one per cell, tile or
key), the way to a cell, a picker function that opens a screen of its own, and the prover that chooses every option
of a cell's list or picker and puts the saved one back."""
import json
import re
import time
from pathlib import Path

import numpy as np

from camkit import camset, match, ocr, safety, screen
from camkit.vlm import PROMPTS
from runner import read_json, changes_of, write_json

from . import base
from .base import RUN_ROOT, Failed, RestoreAfter
from .nav import after_download, move_to, to_row
from .options import function_name, option_index, same_functions
from .putback import put_back_leftovers, say_put_back
from .screens import (BAR_X, _matches, ask_second, bar_text, first_time_notice, info_notice_ok, option_key, place,
                      refuse_or_fail, same_place, vlm_option)

# Picker functions that open a setup screen of their own when chosen (a Recall Custom hold's registration, which
# copies that hold into the registration working copy; Rating's Rating Set; Recog. Target Select's targets) are
# proved like any other since 2026-11-07: the key takes the function, MENU leaves the screen (its footer's Cancel),
# and the proof goes on (leave_own_screen). Until then they were passed over, never chosen (the old kit's Custom
# Key runs, 2026-10-22). A function whose screen MENU does not leave that way is learned here and passed over from
# then on, as before.
OWN_FILE = RUN_ROOT / "kit2_pass2" / "own_screen.json"
# a saved Recall Custom hold is not chosen back to put the key as it was: its registration copies that hold into a
# working slot the camera keeps through an upload (0x18cb[3], 2026-10-29); the session's upload puts the key back
HOLD = re.compile(r"recall\s*custom", re.I)


def own_screen(label: str, screen: str | None = None) -> bool:
    """A function learned on this screen to open a screen of its own that MENU does not leave with the key on its
    cell (own_screen.json; Rating opens Rating Set on a playback key, not on a playback Fn tile, 2026-10-30)."""
    if screen is None or not OWN_FILE.exists():
        return False
    return any(x["screen"] == screen and x["name"] == function_name(label) for x in read_json(OWN_FILE))


def learn_own_screen(label: str, screen: str):
    learned = json.loads(OWN_FILE.read_text(encoding="utf-8")) if OWN_FILE.exists() else []
    entry = {"screen": screen, "name": function_name(label), "label": label}
    if not any(x["screen"] == screen and x["name"] == entry["name"] for x in learned):
        write_json(OWN_FILE, learned + [entry], indent=1, ensure_ascii=False)


def screen_of(job) -> str | None:
    """The screen a table job is on: its menu row, and which of two rows of that name."""
    return f"{job['path'][0]}#{job.get('nth', 0)}" if job.get("path") else None


def table_jobs(scope_names=None) -> list:
    """One job per table cell kit/table_walk.py saw open a list or the function picker and come round:
    {"path": [row], "kind": "table", "option": "<row label> / <column label>", "cell": [x, y] (the
    cursor's centre on it), "columns": [the x of each column the walk saw, left to right], "opens": "list" |
    "picker", "labels": [options in Down order]}."""
    if not base.TABLES.exists():
        return []
    out = []
    for row, t in read_json(base.TABLES).items():
        if t.get("screen") == "keyset":
            out += key_jobs(row, t, scope_names)
            continue
        # a table's row named as all its cells read it, the values glued onto a cell's reading left out (they are the
        # camera's own settings: match.table_row_label); the Fn Menu's rows come named by their section; unread or
        # repeated headers: the cell's place names it (match.walked_cell_names, which the report names old lines by)
        names = match.walked_cell_names(t)
        columns = sorted({c["pos"][0] for c in t["cells"]})
        for i, c in enumerate(t["cells"]):
            if c.get("opens") not in ("list", "picker") or not c.get("wrapped"):
                continue
            name = names[i]
            labels = [o["label"] for o in c["options"]]
            if scope_names and not in_scope(scope_names, row, t, name):
                continue
            if len({option_key(l) for l in labels}) != len(labels):
                print(f"skipping {row} / {name}: two options read the same ({labels})", flush=True)
                continue
            out.append({"path": t["path"], "kind": "table", "screen": t.get("screen", "table"), "option": name,
                        "nth": t.get("nth", 0), "commit": t.get("commit", "ok"), "cell": c["pos"], "columns": columns,
                        "opens": c["opens"],
                        "labels": labels, "frames": [o.get("frame") for o in c["options"]],
                        "pages": [o.get("page") for o in c["options"]], "saved": saved_index(c["options"])})
    return out


def saved_index(options: list) -> int | None:
    """The option the walk found saved (kit/table_walk.py marks it), when it marked exactly one."""
    saved = [i for i, o in enumerate(options) if o.get("saved")]
    return saved[0] if len(saved) == 1 else None


def in_scope(scope_names: set, row: str, t: dict, name: str) -> bool:
    """--rows names a table cell by its job key, "<path> / <cell>" ("Fn Menu Settings / Playback Lower / 6"), or by
    the tables file's own row key, which adds the screen for a second screen of the same row ("Fn Menu Settings
    (playback) / ..."). Either names it; the job key is what --list prints and the end check wants."""
    return row in scope_names or f"{row} / {name}" in scope_names or f"{' > '.join(t['path'])} / {name}" in scope_names


def table_planned(job, k: int) -> bool:
    """Option k is proved for its own sake: not a function with a screen of its own, and in the
    sample when there is one. The saved option is chosen last in any case, to put it back; when it
    is not planned its proof is marked so ("planned": false) and the report leaves its label out,
    since only the user's own assignment would put it among the proved values."""
    return not own_screen(job["labels"][k], screen_of(job)) and ("plan" not in job or k in job["plan"])


def table_order(job, c: int) -> list:
    """The options a table proof chooses, in turn from the one after the saved option c, ending on c
    to put it back. Options proved in an earlier session of this run (job["done"]) are left out: each
    proof is diffed against the start file, so they need not be chosen again, and a 218-function
    tile cut off near its end does not start over."""
    n, done = len(job["labels"]), set(job.get("done", ()))
    # a saved function with a screen of its own, or a saved Recall Custom hold (HOLD), is not chosen to put it back:
    # the session's upload puts the key's assignment back instead
    tail = [] if own_screen(job["labels"][c], screen_of(job)) or HOLD.search(job["labels"][c] or "") else [c]
    return [k for k in [(c + i) % n for i in range(1, n)] if table_planned(job, k) and k not in done] + tail


def sample_pickers(jobs: list) -> list:
    """--picker-sample: slots whose picker lists exactly the functions another slot's does (Fn Menu's
    24 tiles, keys of one kind) share one code table. The first slot of each such group is proved in
    full; the others prove three functions (first, middle, last of the list) and their saved one,
    which shows they store the same codes. About 17 hours of Fn Menu proofs become about 2."""
    firsts = []
    for j in jobs:
        if j.get("opens") != "picker":
            continue
        where = (" > ".join(j["path"]), j.get("screen"), j.get("nth", 0))
        if any(w == where and same_functions(f["labels"], j["labels"]) for w, f in firsts):
            n = len(j["labels"])
            j["plan"] = sorted({0, n // 2, n - 1} - {k for k, l in enumerate(j["labels"]) if own_screen(l, screen_of(j))})
        else:
            firsts.append((where, j))
    return jobs


def key_jobs(row: str, t: dict, scope_names=None) -> list:
    """Custom Key/Dial Set.: one job per key or Dial/Wheel cell whose picker the walk came round.
    cell = [page, "key", row] or [page, x, y] (the grid cell's centre); "nth": the second row with the
    same label (movies)."""
    out = []
    for page in t["pages"]:
        for it in page["items"]:
            if it.get("opens") != "picker" or not it.get("wrapped"):
                continue
            if "row" in it:
                cell, name = [page["tab"], "key", it["row"]], it["key"] or f"page {page['tab'] + 1} key {it['row'] + 1}"
            else:
                cell = [page["tab"], *it["pos"]]
                name = " / ".join(x for x in (it["key"], it.get("col_label", "")) if x) or \
                    f"page {page['tab'] + 1} cell {it['pos']}"
            name = f"{name} @{'.'.join(str(x) for x in cell)}"        # key names repeat across pages' OCR
            if t.get("nth"):
                name = f"{row[len(t['path'][0]):].strip(' ()')}: {name}"   # "movie: AEL Button @0.key.0"
            labels = [o["label"] for o in it["options"]]
            if scope_names and not in_scope(scope_names, row, t, name):
                continue
            if len({option_key(l) for l in labels}) != len(labels) and \
                    not all(re.fullmatch(r"\d+/\d+", o.get("page") or "") for o in it["options"]):
                # functions told apart only by an icon ("AEL hold" for the spot one too, "Add Rating"
                # for each star count) are found by page and row; without the pages they cannot be
                print(f"skipping {row} / {name}: two functions read the same", flush=True)
                continue
            out.append({"path": t["path"], "kind": "table", "screen": "keyset", "nth": t.get("nth", 0),
                        "option": name, "cell": cell, "opens": "picker", "labels": labels,
                        "frames": [o.get("frame") for o in it["options"]],
                        "pages": [o.get("page") for o in it["options"]], "saved": saved_index(it["options"])})
    return out


def to_key(cam, cell):
    """Custom Key/Dial Set.: from its page tabs (they wrap) to page cell[0], Enter, then Down to the
    key (cell = [page, "key", row]) or arrows to the Dial/Wheel cell centred at cell[1:]."""
    for _ in range(7):
        s = cam.read()
        if s.kind != "keyset" or s.focus != "tabs":
            raise Failed(f"not on the Custom Key tabs ({s.kind}, {s.focus}, {cam.frame.path.name})")
        if s.group == cell[0]:
            break
        cam.press("down")
    else:
        raise Failed(f"Custom Key page {cell[0]} not reached")
    cam.press("enter")
    if cell[1] == "key":
        for _ in range(cell[2]):
            cam.press("down")
        s = cam.read()
        if not (s.kind == "keyset" and s.focus == "keys" and s.row == cell[2] and s.group == cell[0]):
            raise Failed(f"the cursor is not on key {cell[2]} of page {cell[0]} ({s.kind}, {s.focus}, {s.row})")
    else:
        separate_modes(cam)
        to_cell(cam, cell[1:], kind="keyset")


SEPARATE_BOX = (slice(110, 134), slice(72, 98))     # the "Separate M mode and other modes." tick box, Dial/Wheel page


def separate_ticked(frame) -> bool:
    """Whether the Dial/Wheel page's "Separate M mode and other modes." box is ticked: a red tick fills it (119 of
    624 pixels red when ticked, none when not, 2026-11-07)."""
    roi = np.asarray(frame.image)[SEPARATE_BOX].astype(int)
    red = (roi[..., 0] > 150) & (roi[..., 1] < 110) & (roi[..., 2] < 110)
    return int(red.sum()) > 30


def separate_modes(cam):
    """The Dial/Wheel page's dials were walked with "Separate M mode and other modes." ticked (two columns, M mode
    and Other); the owner's settings reset unticked it, which leaves one column where the cells were recorded
    (2026-11-07). The cursor opens the page on the first dial row: Up reaches the box, Enter ticks it, Down comes
    back. The start file unticks it again when the run restores it."""
    if separate_ticked(cam.frame):
        return
    cam.press("up")
    cam.press("enter")
    if cam.read().kind != "keyset" or not separate_ticked(cam.frame):
        raise Failed(f"could not tick 'Separate M mode and other modes' ({cam.read().kind}, {cam.frame.path.name})")
    cam.press("down")
    TICKED.append(True)                  # prove_table_row takes a fresh base before the first proof


TICKED: list = []


def near(marker, cell, tol: int = 6) -> bool:
    return marker is not None and abs(marker[0] - cell[0]) <= tol and abs(marker[1] - cell[1]) <= tol


def table_column(s, cell, columns=None) -> str:
    """Where the column of the table cell at `cell` ([x, y], the cursor's centre on it when the table was walked) is
    from the lit cell the reader sees (s.boxes[0]: its x0, x1; s.marker: its centre): "here", "left" or "right",
    or "gone" when the table now shows fewer columns than the walk saw and this one is not among them.
    The lit box spanning the walked x is the cell's column, whatever its width: Image Quality Settings draws one
    column 336 px wide, SLOT 1 only, when the camera records to one slot, and two of 168 px with two (2026-11-08: the
    walk's SLOT 1 at x 376 lies inside the one column centred at 464). A centre within 6 px of the walked x is too
    (the walk's own layout: both readings agree). A lit box that spans more than one walked column (`columns`, the
    job's) stands for the first of them only, so a later slot's cell is "gone", never taken for the first's."""
    cx, mx = cell[0], s.marker[0]
    if abs(mx - cx) <= 6:
        return "here"
    x0, x1 = s.boxes[0] if s.boxes else (mx, mx)
    if not x0 <= cx <= x1:
        return "right" if cx > mx else "left"
    spanned = [c for c in columns or [] if x0 <= c <= x1]
    if len(spanned) > 1 and abs(min(spanned) - cx) > 6:
        return "gone"
    return "here"


def on_table_cell(s, cell, columns=None) -> bool:
    """The reader's lit table cell is the one at `cell`: its row (centre within 6 px of the walked y) and its column
    (table_column)."""
    return (s.kind == "table" and s.marker is not None and abs(s.marker[1] - cell[1]) <= 6
            and table_column(s, cell, columns) == "here")


def to_cell(cam, cell, limit: int = 12, kind: str = "table", columns=None):
    """Arrows to the table cell centred at `cell`, rows first. The camera skips cells that are off
    ("-": JPEG Quality with the slot on RAW), so every press is looked at; one that moves nothing fails. A table's
    cell is found by the table the reader sees now (table_column: the lit cell's box against the walked x and
    `columns`), not by the walked x alone; a keyset's by its centre."""
    for _ in range(limit):
        s = cam.read()
        if s.kind != kind or (kind == "keyset" and s.focus != "cell"):
            raise Failed(f"on the way to the cell at {cell} the screen is {s.kind} ({cam.frame.path.name})")
        side = table_column(s, cell, columns) if kind == "table" and s.focus == "cell" else None
        if side == "gone":
            raise Failed(f"the table shows fewer columns than the walk saw ({len(columns)}), and the cell at {cell} "
                         f"is in one it no longer shows (the camera records to one slot?): it cannot be proved "
                         f"on this screen ({cam.frame.path.name})")
        if s.focus == "cell" and (on_table_cell(s, cell, columns) if kind == "table" else near(s.marker, cell)):
            return
        dx, dy = cell[0] - s.marker[0], cell[1] - s.marker[1]
        sideways = side if side in ("left", "right") else ("right" if dx > 0 else "left")
        key = ("down" if dy > 0 else "up") if abs(dy) > 6 else sideways
        before = s.marker
        cam.press(key)
        if cam.read().kind == kind and cam.read().marker == before:
            raise Failed(f"{key} towards the cell at {cell} did not move the cursor ({cam.frame.path.name})")
    raise Failed(f"the cell at {cell} not reached in {limit} presses")


TILE_STALL_S = 7.0


def to_tile(cam, tile, limit: int = 12):
    """Arrows to the Fn Menu tile (row, column), rows first. Each press is checked from the frame, and the next
    press steers from wherever the cursor really is, so a press seen late is corrected rather than failed: the OSD
    image can hold a stale picture for up to 7 s after a press the camera took (a Right on the Still row, 2026-11-07).
    A press that shows no move after that long, twice in a row, fails the walk."""
    stalls = 0
    for _ in range(limit):
        s = cam.read()
        if s.kind != "fnmenu":
            raise Failed(f"on the way to tile {tile} the screen is {s.kind} ({cam.frame.path.name})")
        if [s.row, s.field] == list(tile):
            return
        key = ("down" if tile[0] > s.row else "up") if tile[0] != s.row else ("right" if tile[1] > s.field else "left")
        before = (s.row, s.field)
        cam.press(key)
        end = time.monotonic() + TILE_STALL_S
        while cam.read().kind == "fnmenu" and (cam.read().row, cam.read().field) == before and time.monotonic() < end:
            time.sleep(0.5)
            cam.refresh(f"{key}-again")
        if cam.read().kind == "fnmenu" and (cam.read().row, cam.read().field) == before:
            stalls += 1
            if stalls >= 2:
                raise Failed(f"{key} towards tile {tile} did not move the cursor ({cam.frame.path.name})")
        else:
            stalls = 0
    raise Failed(f"tile {tile} not reached in {limit} presses")


OWN_KINDS = ("list", "checklist", "fields", "sidelist", "dialog", "slider", "table")   # a screen of a function's own


def leave_own_screen(cam, job, name: str, label: str) -> dict:
    """A picker function whose choice opened a setup screen of its own (2026-11-07): a Recall Custom hold's
    registration checklist (the hold's items, Import Current Setting and Register, "MENU Cancel" in its footer),
    Rating's Rating Set, Recog. Target Select's targets, a My Dial function's My Dial Settings table. The key took
    the function; MENU leaves the screen, nothing on it is pressed (Register would write the hold). A radio list
    open on its saved option (Cnt Sht Spd Bst Settings, the speed the function uses, over the picker still behind
    it) is left with Enter on that option instead: the choice it already holds, so nothing changes but the key.
    Returns what opened, for the proof: the report credits the function with the key's record alone, since the
    screen writes records of its own (the hold copied into the registration working copy). When the way out does
    not bring the key's screen back on its cell, the function is learned as one with a screen of its own and passed
    over from then on, as before."""
    s = cam.read()
    opened = {"kind": s.kind, "frame": cam.frame.path.name,
              "title": ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 56))}
    if s.kind == "list" and s.current is not None and s.row == s.current:
        opened["left_by"] = "enter on its saved option"
    else:
        opened["left_by"] = "menu"
    print(f"   {label!r} opened a {s.kind} of its own ({opened['title'][:40]!r}): {opened['left_by']} leaves it",
          flush=True)
    cam.press("enter" if opened["left_by"].startswith("enter") else "menu")
    if on_cell(cam, job):
        return opened
    learn_own_screen(label, screen_of(job))
    raise Failed(f"{name}: choosing {label!r} opened a {opened['kind']} of its own ({opened['frame']}) that "
                 f"{opened['left_by']} did not leave with the key on its cell ({cam.read().kind}, "
                 f"{cam.frame.path.name}); it is passed over from now on")


def on_cell(cam, job) -> bool:
    s, cell = cam.read(), job["cell"]
    if job.get("screen") == "fnmenu":
        return s.kind == "fnmenu" and [s.row, s.field] == list(cell)
    if job.get("screen") == "keyset":
        if cell[1] == "key":
            return s.kind == "keyset" and s.focus == "keys" and s.row == cell[2] and s.group == cell[0]
        return s.kind == "keyset" and s.focus == "cell" and near(s.marker, cell[1:])
    return on_table_cell(s, job["cell"], job.get("columns"))


def list_options(cam) -> list:
    """The options a list that does not scroll shows, top to bottom, as OCR reads each row (as bar_text reads the lit
    one: the saved option's radio read as a letter stays in front, which option matching takes off); [] for a list
    that scrolls, or a screen that is no list."""
    s = cam.read()
    if s.kind != "list" or s.scroll is not None or not s.count:
        return []
    lines = ocr.read([cam.frame.path])[cam.frame.path]
    x0, x1 = BAR_X["list"]
    out = []
    for i in range(s.count):
        top = screen.LIST_ROW_TOP + i * screen.LIST_ROW_PITCH
        t = ocr.text_in(lines, (x0, top + 2, x1, top + 46)).strip(" •")
        out.append(re.sub(r"\s+[oO0]$", "", t))
    return out


def reader_rows(cam) -> list:
    """The labels of the list's rows, top to bottom, as the "second" vision reader reads them (the menu question,
    through ask_second and so camkit.vlm.ask_role); [] when it cannot be asked or answers in another shape."""
    try:
        v = ask_second(cam.frame.path.read_bytes(), PROMPTS["menu"], timeout=60)
    except Exception:
        return []
    rows = v.get("rows") if isinstance(v, dict) else None
    return [str(r.get("label") or "") for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def to_option(cam, labels, cur: int, k: int, kind: str, job, name: str) -> list:
    """The cursor moved to option k (labels[k]) and checked on it before Enter (option_index); returns the options a
    list that does not scroll showed, for the proof (list_options).
    A list showing as many options as the walk saw is stepped by position, as before (move_to): its icons' OCR varies
    ("Lossless Comp (M) KAW", "50м L: 50M"), which is why option_index goes by the walk's row there.
    A list showing another number of options is walked by its labels: the camera offers options the walk never saw
    (File Format's RAW, RAW & JPEG and JPEG when it records to one slot, where the two-slot walk knew RAW and JPEG, so a
    step by the walk's order landed on RAW & JPEG, 2026-11-08). The wanted label's row among the options read (option
    matching: "O JPEG" is JPEG), else among the rows the vision reader reads, asked once before the row fails (the
    owner, 2026-11-06); then Down or Up the rows between. A label neither finds fails in plain words, naming what each
    read. A list that scrolls, a picker or a carousel is stepped by the walk's order (move_to)."""
    seen = list_options(cam) if kind == "list" else []
    if seen and len(seen) != len(labels):
        rows = [i for i, t in enumerate(seen) if _matches(t, labels) == [k]]
        read = []
        if len(rows) != 1:
            read = reader_rows(cam)
            rows = [i for i, t in enumerate(read) if _matches(t, labels) == [k]] if len(read) == len(seen) else []
        if len(rows) != 1:
            raise Failed(f"{name}: {labels[k]!r} is not one of the options the list shows (OCR read "
                         f"{' · '.join(seen)}; the vision reader {' · '.join(read) or 'nothing'}), so it is not chosen")
        at = cam.read().row
        if at is None:
            raise Failed(f"{name}: no cursor on the list ({cam.frame.path.name})")
        key = "down" if rows[0] > at else "up"
        for _ in range(abs(rows[0] - at)):
            cam.press(key)
            if cam.read().kind != kind:
                raise Failed(f"{key} in the {kind} left it ({cam.read().kind})")
    else:
        move_to(cam, cur, k, len(labels), kind)
    if option_index(cam, labels, kind, job) != k:
        raise Failed(f"{name}: the cursor is not on {labels[k]!r} ({bar_text(cam)!r})"
                     + (f"; the list shows {' · '.join(seen)}" if seen else ""))
    return seen


def table_button(cam) -> str:
    s = cam.read()
    if s.kind != "table" or s.focus != "button":
        return ""
    (x0, x1), (y0, y1) = s.boxes[0], s.bar
    return ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (x0, y0, x1, y1))


def to_ok(cam):
    """From a cell down to the buttons, then along them to the one that reads OK (Image Quality
    Settings has Rec. Media Settings beside it: Enter there opens that submenu)."""
    for _ in range(6):
        if cam.read().kind == "table" and cam.read().focus == "button":
            break
        cam.press("down")
    for key in ("right", "right", "left", "left", "left", None):
        if option_key(table_button(cam)) == "ok":
            return
        if key is None or cam.read().kind != "table":
            break
        cam.press(key)
    raise Failed(f"could not reach the table's OK button ({cam.read().kind}, {cam.frame.path.name})")


def cell_value(cam) -> str:
    s = cam.read()
    if s.kind == "fnmenu":                      # the tile's function, named at the top right
        return ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (330, 55, 640, 105))
    if s.kind != "table" or not s.boxes:
        return ""
    (x0, x1), (y0, y1) = s.boxes[0], s.bar
    return ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (x0, y0, x1, y1))


def prove_table_row(cam, link, run, job, base_path: Path, out, top=None) -> Path:
    """One table cell, Fn Menu tile or Custom Key: every option of its list or picker, each chosen,
    then the table's OK (Fn Menu tiles and keys take their function at once; MENU leaves), download,
    diff. Starts at the option after the saved one and wraps round, so the last proof puts the saved
    one back; that diff must be empty. Any screen the proof did not expect fails the cell (the
    session's restore puts the start file back): a notice after a choice, a picker function whose
    screen of its own MENU does not leave (leave_own_screen), anything but the row after OK."""
    path, labels, kind, where = job["path"], job["labels"], job["opens"], job.get("screen", "table")
    name, n = f"{path[0]} / {job['option']}", len(job["labels"])
    base = camset.read(base_path)
    row_place = place(cam)
    last, order, c, prev = base_path, None, None, None
    history = []                                   # each download's records differing from the start
    while True:
        if order is not None:
            to_row(cam, path, top, row_place)
            if not same_place(place(cam), row_place):
                raise Failed(f"{name}: back at the row, the page or cursor row is not the one proved before")
        cam.press("right")
        if cam.read().kind != where and not (first_time_notice(cam) and cam.read().kind == where):
            if order is None:
                refuse_or_fail(cam, name, f"not a {where}")
            raise Failed(f"{name}: Right opened {cam.read().kind}, not the {where}")
        if where in ("fnmenu", "keyset"):
            {"fnmenu": to_tile, "keyset": to_key}[where](cam, job["cell"])
        else:
            to_cell(cam, job["cell"], columns=job.get("columns"))
        if TICKED:
            # the Dial/Wheel page's box was just ticked (separate_modes): MENU back to the row and a fresh base, so
            # each proof shows the dial alone and the put-back diffs empty; the start file unticks the box at the end
            TICKED.clear()
            cam.press("menu")
            if not same_place(place(cam), row_place):
                raise Failed(f"{name}: after ticking the Dial/Wheel page's box the screen is {cam.read().kind}, not the row")
            base_path = link.download(f"{path[-1]}-rebase")
            base, last = camset.read(base_path), base_path
            print(f"   a fresh base after ticking 'Separate M mode and other modes': {base_path.name}", flush=True)
            after_download(cam, time.monotonic())
            continue
        cam.press("enter")
        if cam.read().kind != kind:
            if order is None:                       # the cell can be off in the start state
                refuse_or_fail(cam, name, f"not its {kind}")
            raise Failed(f"{name}: Enter on the cell opened {cam.read().kind}, not its {kind}")
        cur = option_index(cam, labels, kind, job)
        if cur is None:
            raise Failed(f"{name}: could not tell which option the {kind} opened on ({bar_text(cam)!r})")
        if order is None:
            c = cur
            order = table_order(job, c)
            skipped = [labels[k] for k in range(n) if k != c and own_screen(labels[k], screen_of(job))]
            earlier = sum(1 for k in set(job.get("done", ())) - {c} if table_planned(job, k))
            print(f"{name}: saved value {labels[c]!r}; proving {len(order)} options"
                  + (f" ({earlier} proved in an earlier session)" if earlier else "")
                  + (f", passing over {skipped}" if skipped else ""), flush=True)
            if HOLD.search(labels[c] or "") and c not in set(job.get("done", ())):
                # a saved Recall Custom hold is never chosen back (table_order): its proof is the key's record as the
                # start file holds it, a display proof as a one-option list's, so the cell is done with the others
                out.write(json.dumps({"path": path, "kind": "table", "proof": "display", "screen": where,
                                      "option": job["option"], "cell": job["cell"], "opens": kind, "index": c,
                                      "label": labels[c], "shown": bar_text(cam), "chosen_frame": cam.frame.path.name,
                                      "vlm": vlm_option(cam), "base": base_path.name, "changes": [], "applied": True,
                                      "planned": True}) + "\n")
                out.flush()
                print(f"   {labels[c]!r:24s} held: the key's record as the start file has it", flush=True)
            if not order:
                raise RestoreAfter(f"{name}: nothing left to prove")
        elif cur != prev:
            raise Failed(f"{name}: the {kind} opened on option {cur}, the last OK chose {prev} ({labels[prev]!r})")
        k = order.pop(0)
        seen = to_option(cam, labels, cur, k, kind, job, name)     # by the labels on screen, then checked
        chosen, shown, seen_vlm = cam.frame.path.name, bar_text(cam), vlm_option(cam)
        cam.press("enter")
        chose_info, own = None, None
        if not on_cell(cam, job) and cam.read().kind not in OWN_KINDS:
            chose_info = info_notice_ok(cam, name)                 # an information notice after the choice: its OK
        if not on_cell(cam, job) and cam.read().kind in OWN_KINDS:
            own = leave_own_screen(cam, job, name, labels[k])      # a setup screen of its own, left as it is
        if not on_cell(cam, job):
            raise Failed(f"{name}: after choosing {labels[k]!r} the screen is {cam.read().kind} "
                         f"({cam.frame.path.name}), not the {where} on its cell")
        in_cell, cell_frame = cell_value(cam), cam.frame.path.name     # the cell showing the new value
        if where in ("fnmenu", "keyset") or job.get("commit") == "menu":   # taken at once; MENU leaves
            cam.press("menu")
        else:
            to_ok(cam)
            cam.press("enter")
        info = None
        if cam.read().kind == "notice":
            # an information notice after OK (2026-10-29: after a My Dial choice, a note that a custom key brings
            # that dial set up) takes its own OK; anything that reads like a confirmation fails the cell
            text_n = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
            if not text_n or safety.confirmation(text_n) or not re.search(r"can be|will be|is set|recalled", text_n, re.I):
                raise Failed(f"{name}: after the table's OK a notice came up ({cam.frame.path.name}): {text_n[:80]!r}")
            info = {"text": text_n, "frame": cam.frame.path.name}
            print(f"   information after OK: {text_n[:70]!r}", flush=True)
            cam.press("enter")
        if not same_place(place(cam), row_place):
            raise Failed(f"{name}: after the table's OK the screen is {cam.read().kind} ({cam.frame.path.name}), "
                         f"not the row")
        dat = link.download(f"{path[-1]}-{k}")
        done = time.monotonic()
        changes = camset.diff(base, camset.read(dat))
        history.append({ch.key: ch.after for ch in changes})
        rec = {"path": path, "kind": "table", "screen": where, "option": job["option"], "cell": job["cell"], "opens": kind,
               "index": k, "label": labels[k], "shown": shown, "in_cell": in_cell, "chosen_frame": chosen,
               "cell_frame": cell_frame, "vlm": seen_vlm, "row_frame": cam.frame.path.name, "dat": dat.name,
               "base": base_path.name, "changes": changes_of(changes),
               "applied": True, "planned": table_planned(job, k), **({"info_notice": info} if info else {}),
               **({"chose_notice": chose_info} if chose_info else {}), **({"own_screen": own} if own else {}),
               **({"options_seen": seen} if seen else {})}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        brief = ", ".join(f"{ch.key} {ch.before!r}->{ch.after!r}" for ch in changes[:6]) or "no change"
        print(f"   {labels[k]!r:24s} {brief}{' ...' if len(changes) > 6 else ''}", flush=True)
        last, prev = dat, k
        after_download(cam, done)
        if k == c:
            if changes:
                put_back = put_back_leftovers(changes, history)
                if put_back is None:
                    raise Failed(f"{name}: back on the saved value, {len(changes)} records still differ from the start")
                say_put_back(name, put_back)
            break
        if not order:
            raise RestoreAfter(f"{name}: its saved function {labels[c]!r} has a screen of its own; "
                               f"the session's upload puts it back")
    to_row(cam, path, top, row_place)
    return last
