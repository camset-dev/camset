"""Prove Reg. Custom Shoot Set's values: each option of an item's list, for one Recall Custom hold
(2026-10-30).

    .venv/bin/python -u kit/provers/customshoot_values.py --allow "Reg. Custom Shoot Set" --hold 1 --items "Shoot Mode,Metering Mode"

Reg. Custom Shoot Set is a never-open action row: as in kit/provers/customshoot_run.py, a run opens it only when given
--allow "Reg. Custom Shoot Set", the owner's word, and every proof line carries it ("allowance").

Enter on an item's label opens its list (a popup, opened on the hold's value). First a look: Down
from the hold's value until the list comes round or stops, then Up past it for the options above.
Then one visit per option, the hold's own value last: the list, the option, Enter, Register, a
settings download and a diff with the base. An item whose Enter opens something other than a list
is left with a message (kit/provers/customshoot_run.py's notes have the screen). With --counted (Focus Area's list,
whose Tracking rows show only an icon) the options are counted and named in the camera's own Focus Area order, the
values of a live setting (--order-from, default the ILCE-1M2's 0x0f46) in the definition of the camera the kit works
on; a camera with no definition, or none with that setting on its Focus Area row, stops the run before the camera is
touched, saying what to prove first.

Every Register also rewrites a hidden per-hold record (0x0c09), so the run registers the hold once
unchanged first, and each item's proofs are diffed with a download made just before them; the start file (downloaded before that) goes back on at the end,
and hold 3 is opened and cancelled as in kit/provers/customshoot_run.py. Proofs go to
runs/<model>_fw<fw>/kit2_pass2/proofs.jsonl as kind "list", path ["Reg. Custom Shoot Set", "Recall Custom hold N", item].

    .venv/bin/python -u kit/provers/customshoot_values.py --allow "Reg. Custom Shoot Set" --hold 1 --follow "Exposure step=0.5EV,0.3EV" --record global:0x0c39

--follow ROW=OPTION,OPTION (2026-11-20), in place of --items: a record the hold writes at Register from a live setting no
item of its screen shows (the lead: 0x0c39, the Exposure step). For each option in turn, in one session: the live list
row ROW put on the option through its menu row (mode_switch.set_row), a download, the hold registered as it stands (no
item changed), a download. Two registrations are needed in one session, so that the record is seen to change both ways:
the restore at a run's end puts the start file back, so a second run would find the element as the first found it.
One proof line per registration (kind "registration mirror", as kit/provers/memreg_run.py's and framepos_run.py's, so
pass 2's report keeps it out of its rows and hands it to kit/schema_update.py as a value a registration wrote):
"record" the --record key, "element" the hold's (hold 1's is 0), "index" the option's code in the camera's definition
(the one setting at ROW), "label" the option; applied only when the live record holds that code in the
download after it was set and the element changed to it at Register from the download before (one that held the code
already may hold what the camera had). Nothing else of the item proofs runs: no unchanged Register first. A run that
stopped part way exits EXIT_INCOMPLETE (a refusal EXIT_REFUSED) once its start file is back and checked, so a chain stops.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, definitions, ocr, paths, safety, screen  # noqa: E402
# option matching: one set of rules for every prover (camkit/match.py has the slips it guards against)
from camkit.match import clean as clean_option, index_of, norm, same  # noqa: E402,F401
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link, StopRequested  # noqa: E402
from camkit.live import LiveCamera  # noqa: E402
from camkit.vlm import check_readers  # noqa: E402
from camkit.runs import Run  # noqa: E402
from customshoot_run import ITEMS, LAST_OPENED, ROW, allowed, cancel_hold, lines, open_hold, row_box, to_item, to_register  # noqa: E402
from prove_run import Failed, to_shooting, vlm_option  # noqa: E402
from proving.base import wait_lock  # noqa: E402
from proving.screens import later  # noqa: E402
from runner import (EXIT_INCOMPLETE, EXIT_REFUSED, EXIT_UNRESTORED, add_allow_argument, add_scan_argument,  # noqa: E402
                    changes_of, close_for_restore, close_screen, load_scan, proofs_file, prover_session, restoring)

POP_Y0, POP_DY = 118, 50                 # the popup's first option centre and pitch
# the live setting whose values, by code, are the camera's Focus Area options in the order a hold's list offers them
# (--counted): read from the definition of the camera the kit works on when a run needs it (focus_area_order), never
# another body's. The ILCE-1M2 keeps them in 0x0f46; on another body, prove Focus Area and name its record --order-from
ORDER_KEY = "global:0x0f46"
FOCUS_AREA_ROW = "Focus Area"
MIRROR_KIND = "registration mirror"     # --follow's proof lines: kit/pass2_report.py's MIRROR_KIND
RECORD_KEY = re.compile(r"(global|set(\d+)):0x([0-9a-f]{4})")


def follow_plan(follow: str, record: str | None, hold: int, where=None) -> dict:
    """--follow ROW=OPTION,OPTION and --record KEY checked before the camera is touched: {"row" (its path), "live" (the
    key of the one setting at that row in the definition of the camera the kit works on, or `where`), "options"
    [(label, code)], "record", "element" (the hold's: hold 1's is 0)}. Exits, saying why, on a value missing, a record
    that is no record key, a row the definition holds no one setting with values at, or an option not among them."""
    row, _, opts = follow.partition("=")
    path = [x.strip() for x in row.split(" > ") if x.strip()]
    labels = [x.strip() for x in opts.split(",") if x.strip()]
    if not path or not labels:
        sys.exit(f"--follow {follow!r}: give the live row and its options, ROW=OPTION,OPTION ('Exposure step=0.5EV,"
                 "0.3EV'); nothing was sent to the camera")
    if not record or not RECORD_KEY.fullmatch(record):
        sys.exit(f"--follow needs --record, the record the hold is claimed to write the row's value into, as a key "
                 f"('global:0x0c39'), not {record!r}; nothing was sent to the camera")
    p = definitions.active() if where is None else Path(where)
    doc = definitions.load_public(p) if p.exists() else {"settings": []}
    at = [s for s in doc["settings"] if s.get("row") == path and s.get("values")]
    if len(at) != 1:
        held = "no setting" if not at else f"{len(at)} settings ({', '.join(s['key'] for s in at)})"
        sys.exit(f"--follow {' > '.join(path)!r}: the definition {paths.shown(p)} holds {held} with values at that row, "
                 "where it needs one: its values name the codes the record must take. Nothing was sent to the camera")
    values = [(v, str(lab)) for v, lab in at[0]["values"]]
    out = []
    for lab in labels:
        j = index_of([n for _, n in values], lab)
        if j is None:
            sys.exit(f"--follow: {lab!r} is not among {' > '.join(path)}'s values in the definition "
                     f"({', '.join(n for _, n in values)}); nothing was sent to the camera")
        out.append((values[j][1], values[j][0]))
    return {"row": path, "live": at[0]["key"], "options": out, "record": record, "element": hold - 1}


def element_of(cs, key: str, i: int):
    """Element i of the record `key` ("global:0x0c39", "set1:0x019a") in a settings file; None where it has none."""
    m = RECORD_KEY.fullmatch(key)
    rec = cs.get(int(m[2]) if m[2] else 0, int(m[3], 16)) if m else None
    vals = rec.values() if rec is not None else []
    return vals[i] if i < len(vals) else None


def follow_line(h: int, plan: dict, label: str, code: int, before: Path, set_dat: Path, dat: Path, chosen: str,
                said: str) -> dict:
    """The proof line of one --follow registration: `before` the download before the live row was set, `set_dat` the
    one after it, `dat` the one after Register. Applied only when the live record holds the option's code after it was
    set, and the record's element for the hold changed to that code at Register; else "not_applied" says why."""
    a, b, c = camset.read(before), camset.read(set_dat), camset.read(dat)
    el, key = plan["element"], plan["record"]
    was, now = element_of(b, key, el), element_of(c, key, el)
    why = None
    if element_of(b, plan["live"], 0) != code:
        why = f"{' > '.join(plan['row'])} does not hold the option chosen in the download after it was set"
    elif now is None:
        why = f"the file has no element {el} of {key}"
    elif was == now:
        why = "the element did not change at Register: what it holds may be the camera's own"
    elif now != code:
        why = "the element changed at Register, but not to the code of the option chosen"
    # "record" as the definition keys a whole record (a memory set's "set:"), as framepos_run.py's lines name theirs: a
    # hold record's slots share one encoding (0x0e80, the holds' Cont. Bracket setting), and "element" says the hold's
    return {"path": [ROW, f"Recall Custom hold {h}"], "menu": ROW, "kind": MIRROR_KIND,
            "record": re.sub(r"^set\d+:", "set:", key), "key": key, "element": el, "index": code, "label": label, "hold": h,
            "follows": {"row": plan["row"], "key": plan["live"]},
            "via": f"{' > '.join(plan['row'])} = {label} chosen through its menu row, then Recall Custom hold {h} "
                   "registered as it stood (Register on its screen, no item changed)",
            "set_base": before.name, "set_dat": set_dat.name, "set_changes": changes_of(camset.diff(a, b)),
            "base": set_dat.name, "dat": dat.name, "after": dat.name, "chosen_frame": chosen, "said": said,
            "changes": changes_of(camset.diff(b, c)), "applied": why is None, **({"not_applied": why} if why else {})}


def follow(cam, link, hdmi, cycle, model, h: int, plan: dict, start: Path, out) -> list:
    """--follow's registrations, in one session: per option the live row set through its menu row and a download, the
    hold registered as it stands and a download, a proof line (follow_line). Returns the lines written."""
    from mode_switch import open_menu, set_row
    say = lambda m: print(m, flush=True)     # noqa: E731
    before, lines_written = start, []
    for label, code in plan["options"]:
        tag = re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-")
        open_menu(cam)
        set_row(cam, cycle, model, plan["row"], label, say)
        close_screen(cam, link)
        to_shooting(link, hdmi, "the download after the live row")
        set_dat = link.download(f"hold{h}-{tag}-set")       # camlink waits for the camera to allow it
        wait_lock(time.monotonic(), hdmi, clock=time)       # the menu's lock after it (camkit.session.wait_lock)
        open_hold(cam, cycle, model, h)
        chosen, dat, said = register(cam, link, hdmi, f"hold{h}-at-{tag}")
        line = follow_line(h, plan, label, code, before, set_dat, dat, chosen, said)
        out.write(json.dumps(line) + "\n")
        out.flush()
        lines_written.append(line)
        el = plan["element"]
        print(f"   {' > '.join(plan['row'])} = {label} (code {code}): {plan['record']}[{el}] "
              f"{element_of(camset.read(set_dat), plan['record'], el)!r} -> "
              f"{element_of(camset.read(dat), plan['record'], el)!r} at Register; "
              f"{'applied' if line['applied'] else 'not applied: ' + line['not_applied']}", flush=True)
        before = dat
    return lines_written


def focus_area_order(key: str = ORDER_KEY, where=None) -> list:
    """The camera's Focus Area options in code order: the values of the setting `key` in the definition of the camera
    the kit works on (`where`: a definition's key or path instead). Exits, saying why and what to do, when the camera
    has no definition, or its definition no such setting on the Focus Area row with values."""
    named = where is not None and str(where).endswith(".json")
    # the active camera's stops, saying how, when nothing names the camera
    p = definitions.active() if where is None else Path(where) if named else definitions.path(where)
    camera = p.stem                               # a definition is named by its camera's key
    if not p.exists():
        sys.exit(f"--counted names a hold's Focus Area rows in the camera's own Focus Area order, which is read from "
                 f"its definition, and the {camera} has none yet ({paths.shown(p)}). Prove Focus Area on this camera "
                 "first (prove_run on the Focus Area row), write the definition (kit/schema_update.py --write), then "
                 "run again; or prove the item without --counted")
    s = next((s for s in definitions.load_public(p)["settings"] if s.get("key") == key), None)
    if s is None or not s.get("values") or (s.get("row") or [None])[-1] != FOCUS_AREA_ROW:
        why = ("has no setting " + key) if s is None else \
            (f"names no values for {key}" if not s.get("values") else f"has {key} on another row than Focus Area")
        sys.exit(f"--counted names a hold's Focus Area rows in the camera's own Focus Area order, and the {camera}'s "
                 f"definition ({paths.shown(p)}) {why}. Prove Focus Area on this camera first (prove_run on the "
                 "Focus Area row), write the definition (kit/schema_update.py --write), and pass --order-from with the "
                 "key of the live setting whose values are the menu's Focus Area options in code order (the "
                 f"ILCE-1M2's is {ORDER_KEY}); or prove the item without --counted")
    return [v for _, v in sorted(s["values"])]


def option_now(cam) -> str | None:
    """The option on the cursor's row of an open list, as OCR reads it; the vision reader's reading where OCR leaves
    the row empty or reads a look-alike beside a decimal point (the owner's rule: ask the reader before failing a
    row). None when no list is open, or neither reads the row."""
    s = cam.read()
    if s.kind != "list" or s.row is None:
        return None
    y = POP_Y0 + POP_DY * s.row
    raw = ocr.text_in(lines(cam), (80, y - 24, 560, y + 24)).strip()
    t = clean_option(raw) or None
    if t is None:
        # OCR left the lit row empty: a short white label on the orange bar ("8"" in hold 3's Shutter Speed, the rows
        # above and below read, 2026-11-08). The vision reader reads it, when it names something
        return clean_option(vlm_option(cam)) or None
    if SHAKY.search(t) or GLUED_ZERO.match(raw):
        # a look-alike letter beside a decimal point: "F2.8" read "F2.o" keyed like "F20" (hold 1's
        # Aperture, 2026-10-31); or a zero glued to the digits, which is the radio ring ("02" for 2) or a decimal
        # point lost ("08"" for 0.8"; cleaned, it would pass for 8"). The vision model reads it instead, when it
        # gives digits there
        v = clean_option(vlm_option(cam))
        if v and not SHAKY.search(v) and re.search(r"\d", v):
            return v
    return t


SHAKY = re.compile(r"\d[.,][oOlI|]|[oOlI|][.,]\d")
GLUED_ZERO = re.compile(r"[oO0]\d")
UNREAD = "(a row no reader could read"          # a look's stand-in for such a row, with a number of its own: "(... 30)"


def unread(o) -> bool:
    return str(o).startswith(UNREAD)


def next_option(cam, before, n: int) -> str | None:
    """The option the cursor reached after a press in a look: option_now, which asks the vision reader when OCR reads
    the row empty, then once more on a later frame. None only when the popup did not move (moved: the end of a list
    that does not come round). A row nothing could read while the popup moved is still a row, so the list is counted
    whole and goes on: UNREAD with a number no other row of the look has (`n`), which no reading matches (a None
    reading once ended hold 3's Shutter Speed list at 10", 29 options with 8" to 1/200 missing, when OCR left 8"
    empty and no reader was asked, 2026-11-08). A screen that is no list any more fails the look: what was read is not
    a whole list."""
    o = option_now(cam)
    if o is not None:
        return o
    time.sleep(0.5)
    cam.refresh("reread")
    if cam.read().kind != "list":
        raise Failed(f"the list closed during the look ({cam.read().kind}, {cam.frame.path.name})")
    o = option_now(cam)
    if o is not None:
        return o
    return None if not moved(cam, before) else f"{UNREAD} {n})"


def settled(cam, before, o, last, n: int):
    """A reading after a press, read once more on a later frame when it is the option read before (`last`) though the
    popup moved: a frame caught before the press showed reads the row before, and a look that took it for the end of
    the list counted a list of 7 that comes round as 3 (review 4, 2026-11-09). The end is where the popup stops
    moving. A row nothing reads on the later frame is UNREAD with its number `n`, as in next_option."""
    if o is not None and same(o, last) and moved(cam, before):
        time.sleep(0.5)
        cam.refresh("reread")
        return option_now(cam) or f"{UNREAD} {n})"
    return o


def open_item(cam, cycle, model, h: int, k: int):
    open_hold(cam, cycle, model, h)
    to_item(cam, k)
    cam.press("enter")
    if cam.read().kind != "list":
        raise Failed(f"Enter on {ITEMS[k]!r} opened {cam.read().kind} ({cam.frame.path.name}), not a list")
    # a list whose cursor row no reader can read is still a list: the look keeps the row as UNREAD, and a visit
    # fails in to_option, which cannot tell where the cursor is


def look(cam, link, cycle, model, h: int, k: int) -> tuple:
    """(options top to bottom, index of the hold's value, whether Down was seen to come round). A row no reader can
    read is kept in its place (next_option); the bottom of a list that does not come round is where the popup stops
    moving, or where the same option reads again."""
    open_item(cam, cycle, model, h, k)
    opts = [option_now(cam) or f"{UNREAD} 0)"]          # the hold's own row, unread too, keeps its place
    stuck = wrapped = False
    for _ in range(80):
        before = popup_image(cam)
        cam.press("down")
        o = settled(cam, before, next_option(cam, before, len(opts)), opts[-1], len(opts))
        if o is None or same(o, opts[-1]):
            stuck = True                       # the bottom: this list does not come round
            break
        seen = index_of(opts, o)
        if seen is not None:
            # a frame taken mid-scroll can read as an option seen before, so look again, and coming
            # round must bring the option after it next (2026-10-31)
            time.sleep(0.5)
            cam.refresh("reread")
            o = option_now(cam)
            seen = index_of(opts, o) if o is not None else None
            if seen is None:
                opts.append(o if o is not None else f"{UNREAD} {len(opts)})")    # the popup moved: a row
                continue
            if seen + 1 < len(opts):
                cam.press("down")
                nxt = option_now(cam)
                if unread(opts[seen + 1]):
                    # the row after it was read by no reader the first time: nothing to check it by, and a reading
                    # now names it, unless it names another option
                    if nxt is not None and index_of(opts, nxt) is None:
                        opts[seen + 1] = nxt
                elif nxt is None or not same(nxt, opts[seen + 1]):
                    raise Failed(f"{o!r} read as option {seen} ({opts[seen]!r}), but {nxt!r} came after it, "
                                 f"not {opts[seen + 1]!r}")
            # round again: the labels read since the wrap before this one were re-reads of the
            # first ones ("±0.0" read "‡0.0" the first time)
            del opts[len(opts) - seen:]
            wrapped = True
            break
        opts.append(o)
    start = 0
    if stuck:
        for _ in range(len(opts) - 1):
            cam.press("up")
        for _ in range(60):
            before = popup_image(cam)
            cam.press("up")
            o = settled(cam, before, next_option(cam, before, len(opts)), opts[0], len(opts))
            if o is None or same(o, opts[0]) or same(o, opts[start]):
                # the top: the popup stopped, or the top option read so far reads again (Up does not move there, as
                # Down does not at the bottom; the hold's own when nothing stands above it)
                break
            opts.insert(0, o)
            start += 1
    close_screen(cam, link)
    return opts, start, wrapped


def popup_image(cam):
    """The popup's rows (white, at grey > 150): Down at the end of a list that does not come round
    leaves them as they were."""
    return screen._grey(cam.frame.image)[75:400, 65:575] > 150


def moved(cam, before) -> bool:
    if int((popup_image(cam) != before).sum()) > 40:
        return True
    time.sleep(0.5)                         # a late frame: look once more before calling it the end
    cam.refresh("recheck")
    return int((popup_image(cam) != before).sum()) > 40


def look_by_count(cam, link, cycle, model, h: int, k: int) -> tuple:
    """Focus Area's "Tracking:" rows show only an icon (Spot XL to XS differ by a subscript letter,
    and a row renders a little differently at each height of the capture), so its options are
    counted. The list comes round (Tracking: Custom 3, then Regist Focus Area at the top), which shows
    as the cursor jumping back to the popup's top row: Down to that jump, then one lap more
    (2026-10-31). (labels top to bottom, the hold's index)."""
    open_item(cam, cycle, model, h, k)
    row, downs = cam.read().row, 0
    while True:
        cam.press("down")
        downs += 1
        row, top = came_round(cam, row)
        if top:
            break
        if downs == 60:
            raise Failed("Down never came round to the top of the list")
    opts = [option_now(cam)]
    while True:
        cam.press("down")
        row, top = came_round(cam, row)
        if top:
            break
        opts.append(option_now(cam))
        if len(opts) == 60:
            raise Failed("Down never came round to the top of the list a second time")
    close_screen(cam, link)
    return opts, (len(opts) - downs) % len(opts)


def came_round(cam, prev) -> tuple:
    """(the cursor's popup row after a Down, whether it jumped up to the top row: the list came
    round). A frame caught mid-move is looked at again; one with no cursor keeps the row before."""
    r = cam.read().row
    if r is not None and prev is not None and r < prev:
        time.sleep(0.5)
        cam.refresh("recheck")
        r = cam.read().row
    if r is None:
        return prev, False
    return r, r == 0 and prev not in (None, 0)


def order_names(opts: list, order: list) -> list | None:
    """Labels for a counted Focus Area list: the rows a hold offers above the camera's own options
    ("Regist Focus Area") by their reading, then `order` (focus_area_order)."""
    extra = []
    for o in opts:
        if o is None or ":" in o or index_of(order, o) is not None:
            break
        extra.append(o)
    return name_by_order(opts, extra + order)


def name_by_order(opts: list, names: list) -> list | None:
    """Labels from the camera's own order (`names`, by code) for rows OCR cannot tell apart: only
    when the counts agree and every row OCR can read whole ("Wide", "Custom 3": no colon) stands
    where `names` has it."""
    if len(opts) != len(names):
        return None
    if any(":" not in str(o) and norm(o) != norm(n) for o, n in zip(opts, names, strict=True)):
        return None
    return list(names)


def check_row(cam, label: str):
    """The cursor row against the label counted to: whole when readable, else its "Spot:" or
    "Tracking:" prefix."""
    now = option_now(cam) or ""
    ok = norm(now) == norm(label) if ":" not in label else now.lower().startswith(label.split(":")[0].lower())
    if not ok:
        raise Failed(f"counted to {label!r}, the cursor row reads {now!r} ({cam.frame.path.name})")


def to_option(cam, opts: list, j: int, wraps: bool):
    for _ in range(4):
        at = index_of(opts, option_now(cam))
        if at is None:
            raise Failed(f"cannot tell which option the cursor is on ({option_now(cam)!r}, {cam.frame.path.name})")
        if at == j:
            return
        d = j - at
        if wraps and abs(d) > len(opts) // 2:
            d -= len(opts) if d > 0 else -len(opts)
        for _ in range(abs(d)):
            cam.press("down" if d > 0 else "up")
    raise Failed(f"option {opts[j]!r} never took the cursor ({cam.frame.path.name})")


def register(cam, link, hdmi, name: str):
    to_register(cam)
    full = ocr.text_in(lines(cam), (0, 0, 640, 480))
    if safety.confirmation(full):
        raise Failed(f"the screen reads like a confirmation ({safety.confirmation(full)}): no Register")
    chosen = cam.frame.path.name
    cam.press("enter")
    said = ocr.text_in(lines(cam), (0, 0, 640, 480))
    if cam.read().kind == "notice" and "registered" not in said.lower():
        raise Failed(f"after Register: {said[:90]!r} ({cam.frame.path.name})")
    to_shooting(link, hdmi, "the download after Register")
    dat = link.download(name)                           # camlink waits up to 5 s for the camera to allow it
    wait_lock(time.monotonic(), hdmi, clock=time)       # the menu's lock after it (camkit.session.wait_lock)
    return chosen, dat, said.strip()


def shown_value(cam) -> str:
    """The value on the cursor's row of the hold's screen: after a choice, the item's new value."""
    r = cam.read().row
    return ocr.text_in(lines(cam), row_box(r, 380, 625)).strip() if r is not None else ""


def shows(item: str, label: str, shown: str) -> bool:
    """The hold's screen shows the option chosen: Drive Mode's row shows "Cont. Shooting" for every
    speed (2026-10-31)."""
    if item == "Drive Mode" and label.startswith("Cont. Shooting"):
        label = "Cont. Shooting"
    return same(label, shown) or re.sub(r"\s+", "", clean_option(label).lower()) == re.sub(r"\s+", "", clean_option(shown).lower())


def spread(n: int, sample: int) -> list:
    """Option indexes to prove: all of them, or `sample` spread from the first to the last."""
    if not sample or n <= sample:
        return list(range(n))
    return sorted({round(i * (n - 1) / (sample - 1)) for i in range(sample)})


def prove_item(cam, link, hdmi, cycle, model, h, k, opts, s0, wraps, base, base_path, out, which, counted=False,
               put_back=True):
    """The options `which` of item k's list in turn, the hold's own value last (reached by counting
    presses from the option the list opens on when `counted`). `put_back=False` leaves the last option
    chosen (--prepare: the start file puts the hold back at the end)."""
    name = ITEMS[k]
    cur = s0
    for j in [j for j in which if j != s0] + ([s0] if put_back else []):
        open_item(cam, cycle, model, h, k)
        if counted:
            for _ in range(abs(j - cur)):
                cam.press("down" if j > cur else "up")
            check_row(cam, opts[j])
        else:
            to_option(cam, opts, j, wraps)
        # the second reading, of the option itself (it used to be taken on Register, where it named
        # whatever row the screen showed: 1 of 235 named the option, 2026-10-31)
        seen_vlm = later(vlm_option, cam)
        cam.press("enter")
        if cam.read().kind != "checklist":
            raise Failed(f"{name}: Enter on {opts[j]!r} left a {cam.read().kind} screen "
                         f"({cam.frame.path.name})")
        cur = j
        # the hold's screen shows the value just chosen on the item's row: a different one means the
        # cursor was not where the count or the reading said, so nothing is registered. Focus Area's
        # rows are icons, and OCR leaves short values ("F9") empty: those are only kept
        shown = shown_value(cam)
        if shown and not counted and not shows(name, opts[j], shown):
            raise Failed(f"{name}: chose {opts[j]!r} but the hold's screen shows {shown!r} "
                         f"({cam.frame.path.name}): not registered")
        chosen, dat, said = register(cam, link, hdmi, f"hold{h}-{name}-{j}")
        ch = camset.diff(base, camset.read(dat))
        rec = {"path": [ROW, f"Recall Custom hold {h}", name], "kind": "list", "index": j,
               "label": opts[j], "final": j == s0, "chosen_frame": chosen, "vlm": seen_vlm.result(),
               "shown_on_hold": shown,
               **({"via": "counted presses, labels in the camera's Focus Area order after the hold's own top rows"} if counted else {}),
               "dat": dat.name, "base": base_path.name, "said": said, "applied": True,
               "changes": changes_of(ch)}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        brief = ", ".join(f"{c.key} {c.before!r}->{c.after!r}" for c in ch[:4]) or "no change"
        print(f"   {opts[j][:28]:28s} {brief}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=int, required=True, choices=(1, 2, 3))
    ap.add_argument("--items", default=None, help="item names, comma-separated (as on the hold's screen)")
    ap.add_argument("--follow", default=None, metavar="ROW=OPTION,OPTION",
                    help="instead of --items: register the hold as it stands with the live list row ROW on each OPTION "
                         "in turn, set through its menu row first, to see --record's element for the hold follow it")
    ap.add_argument("--record", default=None, metavar="KEY",
                    help="with --follow: the record the hold is claimed to write ROW's value into ('global:0x0c39')")
    add_scan_argument(ap)
    ap.add_argument("--context", default=None, help="the state these proofs are made in")
    ap.add_argument("--sample", type=int, default=0,
                    help="in a longer list, prove this many options spread over it (and the hold's own)")
    ap.add_argument("--labels", default="",
                    help="prove only these options (comma-separated, as the list shows them), and the hold's own")
    ap.add_argument("--prepare", default="",
                    help="first choose this option of another item and leave it ('Shoot Mode=Manual Exposure': "
                         "the shutter speed and aperture items are refused while the hold is in P, as after a "
                         "settings reset, 2026-11-07); the start file puts the hold back at the end")
    ap.add_argument("--counted", action="store_true",
                    help="count the options and name them in the camera's Focus Area order (its Tracking "
                         "rows show only an icon), as the camera's definition has it")
    ap.add_argument("--order-from", default=None, metavar="KEY",
                    help="with --counted: the live setting of the camera's definition whose values, by code, are the "
                         f"Focus Area options in the menu's order (default {ORDER_KEY}, the ILCE-1M2's)")
    add_allow_argument(ap)
    a = ap.parse_args()
    if a.order_from and not a.counted:
        sys.exit("--order-from names the record --counted reads the Focus Area order from, and without --counted "
                 "nothing reads it: add --counted (Focus Area's list), or leave --order-from out")
    if (a.items is None) == (a.follow is None):
        sys.exit("give --items (the hold's items to prove) or --follow (a live row the hold's Register is seen to copy), "
                 "one of them; nothing was sent to the camera")
    if a.follow is not None and (a.prepare or a.counted or a.labels or a.sample):
        sys.exit("--follow registers the hold as it stands: --prepare, --counted, --labels and --sample go with --items; "
                 "nothing was sent to the camera")
    if a.record and a.follow is None:
        sys.exit("--record names the record --follow checks, and without --follow nothing checks it; nothing was sent "
                 "to the camera")
    order = focus_area_order(a.order_from or ORDER_KEY) if a.counted else None      # before the camera is touched
    plan = follow_plan(a.follow, a.record, a.hold) if a.follow is not None else None    # so is this
    allowance = allowed(a.allow, "customshoot_values")
    h = a.hold
    want = [x.strip() for x in (a.items or "").split(",") if x.strip()]
    prepare = None
    if a.prepare:
        item, _, option = a.prepare.partition("=")
        if item.strip() not in ITEMS or not option.strip():
            sys.exit(f"--prepare wants 'ITEM=OPTION' with an item of a hold; the items are {ITEMS}")
        prepare = (item.strip(), option.strip())
    bad = [x for x in want if x not in ITEMS]
    if bad:
        sys.exit(f"not items of a hold: {bad}; the items are {ITEMS}")
    cycle, model = load_scan(a.scan)
    run = Run("kit2_pass2")
    check_readers()     # no reader listed: stop before the link opens, nothing pressed
    hdmi = eyes_from_config(run)
    stopped = []                    # what stopped --follow's registrations part way, if anything
    try:
        with proofs_file(run, a.context, {"allowance": allowance}) as out, \
                prover_session(run, hdmi, may_open=set(a.allow), say_start=False,    # may_open: the owner's word
                               close_eyes=False, exit_unrestored=False,         # carried to the end (below)
                               end_why="the settings download after the hold",
                               note="the start file left records apart (see above)") as s:
            cam, link, start = s.cam, s.link, s.start
            if plan is not None:
                print(f"start file: {start.name}; hold {h} registered as it stands with "
                      f"{' > '.join(plan['row'])} on {', '.join(lab for lab, _ in plan['options'])} in turn, "
                      f"{plan['record']}[{plan['element']}] watched", flush=True)
                # no item proofs after it (want is empty): the session ends restoring the start file
                try:
                    follow(cam, link, hdmi, cycle, model, h, plan, start, out)
                except Exception as e:
                    stopped.append(e)          # prover_session says it, closes and restores; the exit status says it
                    raise
            else:
                open_hold(cam, cycle, model, h)
                _, base_path, _ = register(cam, link, hdmi, f"hold{h}-unchanged")
                base = camset.read(base_path)
                print(f"start file: {start.name}; base after one unchanged Register: {base_path.name} "
                      f"({len(camset.diff(camset.read(start), base))} records apart)", flush=True)
            if prepare is not None:
                # the preparing choice is a proof like any other, left in place for the items after it
                k = ITEMS.index(prepare[0])
                opts, s0, wraps = look(cam, link, cycle, model, h, k)
                j = index_of(opts, prepare[1])
                if j is None:
                    raise Failed(f"--prepare: {prepare[1]!r} is not in {prepare[0]}'s list {opts}")
                to_shooting(link, hdmi, "the preparing item's base")
                base_path = link.download(f"hold{h}-{prepare[0]}-base")     # camlink waits for the camera to allow it
                done = time.monotonic()
                base = camset.read(base_path)
                wait_lock(done, hdmi, clock=time)       # the menu's lock after it (camkit.session.wait_lock)
                prove_item(cam, link, hdmi, cycle, model, h, k, opts, s0, wraps, base, base_path, out, [j],
                           put_back=False)
                print(f"prepared: {prepare[0]} = {opts[j]!r} (left in place)", flush=True)
            for name in want:
                k = ITEMS.index(name)
                try:
                    if a.counted:
                        read, s0 = look_by_count(cam, link, cycle, model, h, k)
                        opts, wraps = order_names(read, order), False
                        if opts is None:
                            raise Failed(f"{len(read)} options that do not stand in the camera's Focus Area "
                                         f"order: {read}")
                        print(f"{name}: {len(opts)} options counted, the hold's is {opts[s0]!r} (row {s0})",
                              flush=True)
                    else:
                        opts, s0, wraps = look(cam, link, cycle, model, h, k)
                except Failed as e:
                    print(f"{name}: {e}", flush=True)
                    close_screen(cam, link)
                    continue
                print(f"{name}: {len(opts)} options, the hold's is {opts[s0]!r}: {opts}", flush=True)
                try:
                    # the item's own base: an item stopped part-way leaves its value, which the
                    # next item's diffs would otherwise carry (2026-10-30)
                    to_shooting(link, hdmi, "the item's base")
                    base_path = link.download(f"hold{h}-{name}-base")       # camlink waits for the camera to allow it
                    done = time.monotonic()
                    base = camset.read(base_path)
                    wait_lock(done, hdmi, clock=time)   # the menu's lock after it (camkit.session.wait_lock)
                    blank = [j for j, o in enumerate(opts) if unread(o)]
                    if blank:
                        print(f"{name}: {len(blank)} rows no reader could read, left unproved (places {blank}); "
                              f"they are counted, so every other option stands in its place", flush=True)
                    which = [j for j in spread(len(opts), a.sample) if j not in blank]
                    if a.labels:
                        asked = [x.strip() for x in a.labels.split(",") if x.strip()]
                        which = [index_of(opts, x) for x in asked]
                        missing = [x for x, j in zip(asked, which, strict=True) if j is None]
                        if missing and not blank:
                            raise Failed(f"not all of {a.labels!r} are in the list {opts}")
                        if missing:
                            # the list has rows no reader could read: those asked for may be among them
                            print(f"{name}: not found in the list, left for another run: {missing}", flush=True)
                        which = [j for j in which if j is not None]
                    prove_item(cam, link, hdmi, cycle, model, h, k, opts, s0, wraps, base, base_path, out,
                               which, a.counted)
                except Failed as e:
                    print(f"{name} stopped: {e}", flush=True)
                    close_screen(cam, link)
        ended = time.monotonic()        # the session's last download (its end's, or its restore check's) came before
        # the hold's working copy put back, which the start file does not cover: a STOP at cancel_hold's first press
        # (not a cleanup press) or an error leaves it where it is, which exits EXIT_UNRESTORED (runner.restoring)
        with restoring("putting the hold's working copy back"), Link(run) as link:
            hdmi.attach(link)
            to_shooting(link, hdmi, "before putting the working copy back")
            # the menu's lock after that download, from when the session ended (camkit.session.wait_lock; the link's
            # open alone mostly outlasts it): it stood for 4 s before the link and 5 s after
            wait_lock(ended, hdmi, clock=time)
            cam = LiveCamera(link, hdmi, run, may_open=set(a.allow))     # the owner's word, as above
            try:
                cancel_hold(cam, link, cycle, model, LAST_OPENED)
            except Exception:
                close_for_restore(cam, link, start)        # cleanup presses before the link closes over an open dialog
                raise
            to_shooting(link, hdmi, "the last download")      # camlink waits for the camera to allow the download
            last = camset.diff(camset.read(start), camset.read(link.download("end")))
            print(f"at the end: {len(last)} records differ from the start file "
                  f"{[c.key for c in last][:8]}", flush=True)
    finally:
        hdmi.close()
    if not s.restored or last:
        # the first session's start file did not take, or the camera still differs after the working copy went
        # back: not as its start file, which the exit status says (runner.EXIT_UNRESTORED)
        sys.exit(EXIT_UNRESTORED)
    if stopped and not isinstance(stopped[0], StopRequested):
        # --follow stopped part way, its start file back and checked: a refusal or anything else, as boxes_run exits
        sys.exit(EXIT_REFUSED if isinstance(stopped[0], safety.Refused) else EXIT_INCOMPLETE)


if __name__ == "__main__":
    main()
