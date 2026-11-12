"""Prove My Menu's item codes: Add Item on every item the camera offers, one settings download per add (2026-11-07).

    .venv/bin/python -u kit/provers/mymenu_run.py --allow "Add Item" [--in Movie] [--scan RUN] [--limit N] [--lap-only]
    .venv/bin/python -u kit/provers/mymenu_run.py --relabel                (the run's proofs named again; no camera)

Add Item is a never-open action row (camkit.safety): a camera run (--lap-only too, which opens the picker) opens it
only when given --allow "Add Item", the owner's word, refuses to start without it or with any other --allow, and every
proof line carries it ("allowance", runner.allowed_or_exit).

My Menu's six pages are 42 slot records (camera.my_menu.records), each holding a menu-item code; the a1 II names 260
codes, 42 of them read back from a file on 2026-10-31, the rest derived. This prover proves the rest on the camera:
My Menu Setting > Add Item opens a picker that is the camera's menu again ("Add Item: Select an item", 59 pages here;
no Playback items), Enter on an item asks for a location (My Menu1-6), Enter on a page moves into its slots, Enter adds
("Added."), and the picker comes back on the item just added. A download works inside the picker, and closes it (MENU and Enter reopen it on the same item). Each add is diffed
with the download before it: the page's record gains the code in the slot after its items (the slot cursor opens
below them; the prover checks that slot alone changed, from empty), which names that code with the item's name. The name
is settled against the camera's own row names (item_name: the menu tree's rows and the Help Guide's menu list) from the
two readings of the lit row, the OCR text and the vision reader's words, for the OCR carries icon noise and the group's
name on a page's first row, and the reader now and then answers with the group's name; twins (the Still and Movie
"Fn Menu Settings") are numbered by their place in the picker (twin_names). `--relabel` names a run's proofs again by
that rule from the readings they kept, touching no camera. Six pages take 42 items; then the session ends restoring
the start file (the camera restarts on an upload), a new session opens, and the walk goes on where it was.

First a lap of the picker (Down until the first item comes round) lists the items in order, so a stopped run resumes
by (page, label). Only Add Item is ever opened: never Sort, Delete Item, Delete Page or Delete All. Proofs go to
runs/<model>_fw<fw>/kit2_pass2/proofs.jsonl as kind "list", path ["My Menu Setting", "Add Item"]; kit/pass2_report.py
credits each slot's new code with its label, and kit/schema_update.py names a code proved in one slot in all 42.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, jsonl, ocr, safety  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.live import LiveCamera, lit_text  # noqa: E402
from camkit.match import LOOKALIKES, clean as clean_option, norm  # noqa: E402
from camkit.runs import Run  # noqa: E402
from crawl_run import find_position, go_to  # noqa: E402
from prove_run import LOCK_S, Failed, to_shooting, vlm_option  # noqa: E402
from runner import (EXIT_UNRESTORED, LATEST_SCAN, add_allow_argument, add_in_argument, allowed_or_exit,  # noqa: E402
                    close_for_restore, end_session, in_mode, load_scan, proofs_file, read_json, restore_checked,
                    scan_arg, write_json, write_text)

ROW = "Add Item"
PATH = ["My Menu Setting", "Add Item"]
PAGES, SLOTS = 6, 7
EMPTY = 2                       # an empty slot (camera.my_menu.empty)
LAP_MAX = 700
# the item's name is settled against the camera's own row names (item_name): the menu tree's rows and the Help
# Guide's menu list, data/<model>_fw<fw>/


def squash(t) -> str:
    """A name's letters and digits alone, lower-case, Cyrillic look-alikes mended: what two readings of one row share."""
    return re.sub(r"[^a-z0-9]+", "", str(t or "").translate(LOOKALIKES).lower())


def words(t) -> list:
    return re.findall(r"[a-z0-9&+]+", str(t or "").translate(LOOKALIKES).lower())


def row_names(camera: str) -> dict:
    """The camera's menu rows by squash(): the menu tree's top rows (every mode's) and the Help Guide's menu list,
    the tree from private/evidence/<model>_fw<fw>/ when it is here, the guide from data/<model>_fw<fw>/; the tree's
    spelling first (as the screen shows it), the guide's where the tree has none."""
    from camkit import datafiles, definitions
    out = {}
    tree = definitions.menu_tree_file(camera)
    if tree.exists():
        doc = datafiles.load_menu_tree(tree)            # whole (My Menu's rows among them)
        for tabs in [doc.get("tabs") or []] + [m.get("tabs") or [] for m in doc.get("modes") or []]:
            for tb in tabs:
                for pg in tb.get("pages") or []:
                    for r in pg.get("rows") or []:
                        out.setdefault(squash(r["label"]), r["label"])
    guide = definitions.data_dir(camera) / f"help_guide_menu_{camera}.jsonl"
    for r in jsonl.read(guide):
        if r.get("item"):
            out.setdefault(squash(r["item"]), r["item"])
    return out


def item_name(lit: str, vlm: str, rows: dict) -> tuple:
    """(name, source) of a picker item from the two readings of its lit row: the OCR text (`lit`), which carries icon
    noise and, on a page's first row, the group's name before the item's ("Image Quality/Rec Log Shooting Setting"),
    and the vision reader's words (`vlm`), which now and then are the group's instead of the item's ("AF/MF" for
    Preset Focus/Zoom, 2026-11-07). The camera's own row names (`rows`, row_names) settle it:
      "map"      the row name the OCR text ends with, the longest; when the reader's words are one of those too,
                 theirs ("Camera Set. Memory" over the movie menu's "MR Camera Set. Memory"); failing an ending, the
                 row the reader's words make with words the OCR text has ("Shoot Mode" + "S&Q": "S&Q Shoot Mode")
      "vision"   the reader's words when they are a row's name and the OCR text ends with no row's
      "reading"  the reader's words, else the cleaned OCR, when neither names a row (kept for the viewer to judge)"""
    o, v = squash(lit), squash(vlm)
    ends = [k for k in rows if k and o.endswith(k)]
    if ends:
        return rows[v if v in ends else max(ends, key=len)], "map"
    have = set(words(lit)) | set(words(vlm))
    vw = set(words(vlm))
    grown = [k for k, lab in rows.items() if vw and vw < set(words(lab)) <= have]
    if grown:
        return rows[max(grown, key=len)], "map"
    if v in rows:
        return rows[v], "vision"
    return (vlm or clean_option(lit)), "reading"


def twin_names(items: list) -> list:
    """A name several items share (the Still and Movie "Fn Menu Settings", told apart on the screen by an icon alone)
    is numbered by the items' order in the picker: the first keeps it, the next are "name (2)", "name (3)"..., as the
    report names a picker's twins. Returns the items with "label" settled."""
    seen = {}
    for it in items:
        n = seen.get(it["label"], 0) + 1
        seen[it["label"]] = n
        if n > 1:
            it["label"] = f"{it['label']} ({n})"
    return items


def text(cam) -> str:
    f = cam.frame
    return ocr.text_in(ocr.read([f.path])[f.path], (0, 0, 640, 480))


def counter(t: str) -> tuple | None:
    """The n/N at the top right of a picker screen ("Add Item: Select an item 1/59")."""
    m = re.search(r"(\d+)\s*/\s*(\d+)", t[:80])
    return (int(m.group(1)), int(m.group(2))) if m else None


def state(cam) -> dict:
    """What the picker shows: "items" (an item lit), "location" (a My Menu page lit), "slot" (the cursor in a page's
    slots: the title still says location, nothing lit reads), "added" (the notice), else the screen kind."""
    t = text(cam)
    lit = lit_text(cam.frame.image, cam.frame.path)
    page = counter(t)
    if re.search(r"select an item", t, re.I):
        kind = "items"
    elif re.search(r"select a location", t, re.I):
        kind = "location" if re.search(r"my menu", lit, re.I) else "slot"
    elif re.match(r"\W*added", t.strip(), re.I):
        kind = "added"
    else:
        kind = cam.read().kind
    return {"kind": kind, "page": page[0] if page else None, "pages": page[1] if page else None, "lit": lit, "text": t}


def settle_items(cam, why: str, limit: float = 8.0) -> dict:
    """Wait for the picker's item list (the "Added." notice passes by itself; a download's notice and lock too)."""
    end = time.monotonic() + limit
    while True:
        st = state(cam)
        if st["kind"] == "items":
            return st
        if time.monotonic() > end:
            raise Failed(f"{why}: the picker did not come back ({st['kind']}, {cam.frame.path.name}): {st['text'][:80]!r}")
        time.sleep(0.4)
        cam.refresh(why)


def item_key(st: dict) -> tuple:
    return (st["page"], norm(st["lit"]))


def to_add_item(cam, cycle, model):
    """From the menu just opened to the Add Item row, lit, then Enter into the picker."""
    j = find_position(cam, cycle, model)
    if j is None or go_to(cam, cycle, model, j, ROW) is None:
        raise Failed(f"could not reach {ROW!r} by the scan")
    lit = lit_text(cam.frame.image, cam.frame.path)
    if not re.search(r"add item", lit, re.I):
        raise Failed(f"the lit row is {lit!r}, not {ROW}")
    cam.press("enter")
    return settle_items(cam, "into the picker")


def lap(cam, rows: dict, say) -> list:
    """Down through the whole picker until the first item comes round: [{page, lit, label, label_from, vlm}] in
    order, each named by item_name against the camera's row names and twins numbered (twin_names)."""
    items, first = [], None
    for _ in range(LAP_MAX):
        st = settle_items(cam, "lap")
        seen = vlm_option(cam)
        if not st["lit"]:
            st["lit"] = seen                       # OCR read nothing in the cursor: the reader's words key the item
        key = item_key(st)
        if first is None:
            first = key
        elif key == first and items:
            return twin_names(items)
        name, src = item_name(st["lit"], seen, rows)       # the OCR text is kept beside it as "shown"
        items.append({"page": st["page"], "lit": st["lit"], "label": name, "label_from": src, "vlm": seen,
                      "frame": cam.frame.path.name})
        say(f"  lap {len(items):3d}: page {st['page']}/{st['pages']}  {st['lit']!r}  vision {seen!r}  -> {name!r} ({src})")
        cam.press("down")
    raise Failed(f"the picker did not come round in {LAP_MAX} presses")


def relabel(proofs: Path, rows: dict, say) -> int:
    """Name every Add Item proof in `proofs` again by today's rule (item_name, twin_names) from the readings it kept
    ("shown", "vlm"), in picker order; the file is rewritten in place with the old one kept beside it as
    proofs.jsonl.<stamp>.bak. Returns how many labels changed."""
    lines = jsonl.read(proofs)
    mine = [r for r in lines if r.get("path") == PATH and r.get("my_menu")]
    mine.sort(key=lambda r: (r.get("picker_page") or 0, r.get("index") or 0))
    items = []
    for r in mine:
        name, src = item_name(r.get("shown") or "", r.get("vlm") or "", rows)
        items.append({"label": name, "label_from": src, "proof": r})
    twin_names(items)
    changed = 0
    for it in items:
        r = it["proof"]
        if r.get("label") != it["label"] or r.get("label_from") != it["label_from"]:
            if r.get("label") != it["label"]:
                say(f"  {r['my_menu']['code']:5d} {r.get('label')!r} -> {it['label']!r} ({it['label_from']}; shown {r.get('shown')!r}, vision {r.get('vlm')!r})")
                changed += 1
            r["label"], r["label_from"] = it["label"], it["label_from"]
    if changed or any("label_from" not in r for r in mine):
        keep = proofs.with_name(f"{proofs.name}.{time.strftime('%Y%m%d-%H%M%S')}.bak")
        keep.write_bytes(proofs.read_bytes())
        write_text(proofs, "".join(json.dumps(r) + "\n" for r in lines))    # whole: a stop mid-write leaves the old
        say(f"{changed} labels changed; the file before is {keep.name}")
    return changed


def to_item(cam, key: tuple, say) -> dict:
    """Down until the lit item is `key` (page, normalised label), at most one lap."""
    for _ in range(LAP_MAX):
        st = settle_items(cam, "to the item")
        if not st["lit"]:
            st["lit"] = vlm_option(cam)
        if item_key(st) == key:
            return st
        cam.press("down")
    raise Failed(f"item {key} not found in a lap of the picker")


def move_pages(cam, page: int):
    """On the location screen, Up/Down until My Menu `page` is lit (its n/6 counter says so)."""
    for _ in range(PAGES * 2):
        st = state(cam)
        if st["kind"] != "location":
            raise Failed(f"not on the location screen ({st['kind']}, {cam.frame.path.name})")
        if st["page"] == page:
            return
        cam.press("down" if (st["page"] or 1) < page else "up")
    raise Failed(f"My Menu{page} not reached on the location screen")


def add_one(cam, link, item: dict, page: int, slot: int, prev: Path, records: list, say) -> dict:
    """Add the lit item to My Menu `page` below its `slot` items, download, and diff with `prev`: the page's record
    must gain the code in slot `slot` and nothing else move."""
    chosen = cam.frame.path.name
    cam.press("enter")
    st = state(cam)
    if st["kind"] == "items":
        return {"skipped": "Enter did not open the location screen (an item that cannot be added now)",
                "frame": cam.frame.path.name}
    if st["kind"] != "location":
        if st["kind"] in ("notice", "dialog"):
            say(f"  a {st['kind']} after Enter: {st['text'][:80]!r}; MENU cancels it")
            cam.press("menu")
        raise Failed(f"Enter on {item['label']!r} opened {st['kind']} ({cam.frame.path.name}): {st['text'][:80]!r}")
    move_pages(cam, page)
    cam.press("enter")
    st = state(cam)
    if st["kind"] != "slot":
        raise Failed(f"Enter on My Menu{page} left {st['kind']} ({cam.frame.path.name})")
    cam.press("enter")                   # the slot cursor opens below the page's items: the item is appended
    end = time.monotonic() + 8.0
    while state(cam)["kind"] not in ("added", "items"):
        if time.monotonic() > end:
            st = state(cam)
            raise Failed(f"after the slot's Enter the screen is {st['kind']} ({cam.frame.path.name}): {st['text'][:80]!r}")
        time.sleep(0.4)
        cam.refresh("adding")
    settle_items(cam, "after the add")
    dat = link.download(f"mymenu-{page}-{slot}")
    done = time.monotonic()
    changes = camset.diff(camset.read(prev), camset.read(dat))
    rec_key = f"global:0x{records[page - 1]:04x}"
    moved = [c for c in changes if c.key == rec_key]
    others = [c for c in changes if c.key != rec_key]
    if len(moved) != 1 or others:
        raise Failed(f"the add changed {[c.key for c in changes]}, not {rec_key} alone")
    before, after = moved[0].before, moved[0].after
    diff_slots = [i for i, (x, y) in enumerate(zip(before, after, strict=True)) if x != y]
    if diff_slots != [slot] or before[slot] != EMPTY:
        raise Failed(f"the page's slots moved {diff_slots} (expected slot {slot + 1} alone, from empty): {before} -> {after}")
    code = after[slot]
    back_to_picker(cam, done)
    return {"code": code, "dat": dat, "chosen": chosen, "changes": [{"key": moved[0].key, "before": before, "after": after}]}


def back_to_picker(cam, done: float) -> dict:
    """A download closes the menu ("Saving to the connected device...", then the shooting screen): after the lock,
    MENU reopens the menu on the Add Item row and Enter reopens the picker on the item just added."""
    while time.monotonic() - done < LOCK_S:
        time.sleep(0.3)
    end = time.monotonic() + 25
    while True:
        cam.refresh("after-download")
        st = state(cam)
        if st["kind"] == "items":
            return st
        if cam.read().kind == "shooting":
            break
        if time.monotonic() > end:
            raise Failed(f"after the download the camera stayed on {st['kind']} ({cam.frame.path.name})")
        time.sleep(0.4)
    cam.press("menu")
    lit = lit_text(cam.frame.image, cam.frame.path)
    if not re.search(r"add item", lit, re.I):
        raise Failed(f"the menu reopened on {lit!r}, not Add Item ({cam.frame.path.name})")
    cam.press("enter")
    return settle_items(cam, "back into the picker")


def allowed(allow) -> str:
    """The proof lines' allowance for a camera run, which opens Add Item: exits before anything connects unless --allow
    names that row, the owner's word, and nothing else (runner.allowed_or_exit then says it and gives its words)."""
    if not safety.named(ROW, allow):
        sys.exit(f"mymenu_run: {ROW} is never-open (an action); a run opens it only with the owner's word, "
                 f"--allow {ROW!r}")
    others = [x for x in allow if not safety.named(ROW, [x])]
    if others:
        sys.exit(f"mymenu_run: --allow names {others}: this run opens no never-open row but {ROW}")
    return allowed_or_exit(allow)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", default=LATEST_SCAN, type=scan_arg,
                    help="the page scan of the menu the camera shows now (a run in the camera's runs, or a path; "
                         "default: the camera's latest page scan made in the mode --in names, runner.latest_scan)")
    add_in_argument(ap)
    ap.add_argument("--limit", type=int, default=0, help="add this many items, then stop (a trial)")
    ap.add_argument("--lap-only", action="store_true", help="list the picker's items and stop, adding nothing")
    ap.add_argument("--run", default="kit2_pass2")
    ap.add_argument("--relabel", action="store_true",
                    help="name the run's Add Item proofs again by today's rule from their readings, touching no camera")
    add_allow_argument(ap)
    a = ap.parse_args()
    allowance = "" if a.relabel else allowed(a.allow)       # --relabel touches no camera
    from camkit import datafiles, definitions
    doc = definitions.with_evidence(read_json(definitions.active()), definitions.active())
    datafiles.stop_if_left(definitions.key(doc), "mymenu_run.py")      # its menu tree, if still in data/
    rows = row_names(definitions.key(doc))
    say = lambda m: print(m, flush=True)
    if a.relabel:
        run = Run(a.run)
        say(f"{len(rows)} row names; naming {run.dir / 'proofs.jsonl'} again")
        relabel(run.dir / "proofs.jsonl", rows, say)
        cached = run.dir / "mymenu_items.json"
        if cached.exists():
            items = read_json(cached)
            for it in items:
                it["label"], it["label_from"] = item_name(it["lit"], it.get("vlm") or "", rows)
            write_json(cached, twin_names(items), indent=1)
        return
    cycle, model = load_scan(in_mode(a.scan, a.in_mode))
    records = doc["camera"]["my_menu"]["records"]
    if len(records) != PAGES:
        sys.exit(f"the definition names {len(records)} My Menu page records, not {PAGES}")
    run = Run(a.run)
    out = proofs_file(run, None, {"allowance": allowance})
    proved = set()
    for r in jsonl.read(run.dir / "proofs.jsonl"):
        if r.get("path") == PATH and r.get("applied"):
            proved.add((r.get("picker_page"), norm(r.get("shown") or r["label"])))
    hdmi = eyes_from_config(run)
    items, k, added_total, unrestored = None, 0, 0, False
    try:
        while True:
            start = ending = None
            with Link(run) as link:
                hdmi.attach(link)
                to_shooting(link, hdmi, "the start download")
                start = link.download("before")
                time.sleep(LOCK_S)
                cam = LiveCamera(link, hdmi, run, may_open=set(a.allow))       # the owner's word for Add Item
                lap_only = False
                try:
                    cam.press("menu")
                    to_add_item(cam, cycle, model)
                    if items is None:
                        cached = run.dir / "mymenu_items.json"
                        if cached.exists() and not a.lap_only:
                            items = read_json(cached)
                            say(f"{len(items)} items from {cached.name}; {len(proved)} proved before")
                        else:
                            items = lap(cam, rows, say)
                            write_json(cached, items, indent=1)
                            say(f"{len(items)} items in the picker; {len(proved)} proved before")
                        if a.lap_only:
                            lap_only = True
                    if not lap_only:                    # --lap-only: the items listed, nothing added
                        prev, fill, per_page = start, 0, [0] * PAGES
                        while k < len(items) and fill < PAGES * SLOTS and (not a.limit or added_total < a.limit):
                            it = items[k]
                            key = (it["page"], norm(it["lit"]))
                            if key in proved:
                                k += 1
                                continue
                            to_item(cam, key, say)
                            page = fill % PAGES + 1               # round the pages: each takes up to 7 a fill
                            slot = per_page[page - 1]
                            got = add_one(cam, link, it, page, slot, prev, records, say)
                            if "skipped" in got:
                                say(f"  {it['label']!r}: {got['skipped']}")
                                out.write(json.dumps({"path": PATH, "kind": "list", "index": k, "label": it["label"],
                                                      "picker_page": it["page"], "applied": False, "why": got["skipped"],
                                                      "chosen_frame": got["frame"]}) + "\n")
                                k += 1
                                cam.press("down")
                                continue
                            rec = {"path": PATH, "kind": "list", "index": k, "label": it["label"],
                                   "label_from": it.get("label_from"), "shown": it["lit"],
                                   "vlm": it["vlm"] or vlm_option(cam), "picker_page": it["page"], "chosen_frame": got["chosen"],
                                   "dat": got["dat"].name, "base": prev.name, "applied": True, "changes": got["changes"],
                                   "my_menu": {"page": page, "slot": slot, "code": got["code"]}}
                            out.write(json.dumps(rec) + "\n")
                            out.flush()
                            say(f"{k + 1:3d}/{len(items)} {it['label']!r:36s} -> My Menu{page} (item {slot + 1}): code {got['code']}")
                            proved.add(key)
                            prev, fill, added_total = got["dat"], fill + 1, added_total + 1
                            per_page[page - 1] += 1
                            k += 1
                            cam.press("down")
                except Exception as e:              # a Failed choice, a press refused, a STOP: end here, restoring
                    say(f"stopped: {type(e).__name__}: {e}")
                    k = len(items) if items is not None else k   # no second guess at the camera's state
                close_for_restore(cam, link)        # cleanup presses: they go out after a STOP too
                ending = end_session(link, hdmi, start, "the end of the fill")
            if not restore_checked(run, ending, start):      # says so: THE START FILE DID NOT TAKE
                unrestored = True
                break
            if lap_only or items is None or k >= len(items) or (a.limit and added_total >= a.limit):
                break
            say(f"My Menu emptied by the start file; {len(items) - k} items to go")
            time.sleep(10)
        say(f"finished: {added_total} items added and proved this run; {len(proved)} proved in all")
    finally:
        hdmi.close()
        out.close()
    if unrestored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)


if __name__ == "__main__":
    main()
