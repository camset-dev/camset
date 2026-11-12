"""Prove Drive Mode's Cont. / Single Bracket settings: the step and image fields of its carousel
(2026-10-31). Stills mode; the drive mode set from the menu.

    .venv/bin/python -u kit/provers/bracket_run.py --option "Cont. Bracket" --look      # read the fields only
    .venv/bin/python -u kit/provers/bracket_run.py --option "Cont. Bracket"             # every step and count
    .venv/bin/python -u kit/provers/bracket_run.py --option "Single Bracket" --sample 12

The carousel shows the option's fields under it: [1.0EV] [5 Images] [>]. Right moves the focus from
the carousel to the step field, then the images field, then the > box, which opens Bracket Settings
and once wrote five records (2026-10-28): so Right is never pressed with the focus on the images
field, and a > lit by mistake is left with Left. Up/Down change the focused field.
One visit: the option, the step, the images, both fields read back as wanted, OK, a settings
download and a diff. The option is chosen once with its fields unchanged before the base download,
so only the bracket record moves between proofs. The start file goes back on at the end.
Proofs go to runs/<model>_fw<fw>/kit2_pass2/proofs.jsonl, path ["Drive Mode", option], labelled "1.0 EV 5 Img."
("0.3 EV 2 Img. +" for the two-image brackets) as the schema names them.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, jsonl, match, ocr, safety, screen  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.runs import Run  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import LOCK_S, Failed, carousel_text, to_shooting  # noqa: E402
from runner import (add_scan_argument, changes_of, close_screen, load_scan, menu_from_shooting,  # noqa: E402
                    proofs_file, prover_session, scan_position, write_json)

BOXES = {"step": (137, 352, 346, 406), "images": (354, 352, 563, 406), "next": (574, 352, 625, 406)}
OPTIONS = ["Single Shooting", "Continuous Shooting", "Self-timer(Single)", "Self-timer(Cont.)",
           "Cont. Bracket", "Single Bracket", "Focus Bracket", "White Balance Bracket", "DRO Bracket"]


def fields(cam) -> dict:
    lines = ocr.read([cam.frame.path])[cam.frame.path]
    return {k: ocr.text_in(lines, (x0 + 2, y0 + 2, x1 - 2, y1 - 2)).strip() for k, (x0, y0, x1, y1) in BOXES.items()}


def step_of(t: str) -> float | None:
    t = re.sub(r"(?<=[.,])Z", "7", re.sub(r"(?<=[.,])S", "5", t or ""))   # "O.ZEV", "1.SEV"
    t = re.sub(r"(?<=[.,])[oO]|[oO](?=[.,]\d)", "0", t)                # "1.OEV", "O.7EV"
    m = re.search(r"(\d)\s*[.,]\s*(\d)\s*E", t)
    return float(f"{m.group(1)}.{m.group(2)}") if m else None


def images_of(t: str) -> tuple | None:
    """(count, sign): "5 Images" -> (5, ""); a two-image bracket's direction as "+" or "-"."""
    m = re.search(r"(\d+)\s*[Il|]?m?a?g", t or "")
    if not m:
        return None
    sign = "+" if "+" in t else "-" if re.search(r"[-−–]", t) else ""
    return int(m.group(1)), sign


def label(step: float, images: tuple) -> str:
    n, sign = images
    return f"{step:.1f} EV {n} Img." + (f" {sign}" if sign else "")


def focus(cam) -> str | None:
    """The field with the cursor: the box drawn orange (none while the carousel has it)."""
    o = screen._orange(cam.frame.image)
    score = {k: float(o[y0:y1, x0:x1].mean()) for k, (x0, y0, x1, y1) in BOXES.items()}
    best = max(score, key=score.get)
    return best if score[best] > 0.15 else None


def title(cam) -> str:
    return carousel_text(cam).split(":")[0].strip()


def open_carousel(cam, cycle, model, option: str):
    menu_from_shooting(cam)              # MENU, once more if it went unanswered after a download
    j = scan_position(cam, cycle)
    if j is None or go_to(cam, cycle, model, j, "Drive Mode") is None:
        raise Failed("could not reach Drive Mode by the scan")
    cam.press("enter")
    head = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (110, 0, 640, 60)).lower()
    if cam.read().kind != "dialog" or "drive mode" not in head or not title(cam):
        raise Failed(f"Enter on Drive Mode opened {cam.read().kind} ({cam.frame.path.name})")
    want = match.key(option)
    for _ in range(len(OPTIONS) + 2):
        t = title(cam)
        if match.key(t) == want:
            return
        here = next((i for i, o in enumerate(OPTIONS) if match.key(o) == match.key(t)), None)
        cam.press("down" if here is None or here < OPTIONS.index(option) else "up")
    raise Failed(f"the carousel never showed {option!r} ({cam.frame.path.name})")


def right_to(cam, field: str):
    if field == "images" and focus(cam) != "step":
        raise Failed(f"Right to the images field from {focus(cam)!r}, not the step field")
    cam.press("right")
    got = focus(cam)
    if got == "next":
        cam.press("left")                    # never Enter or Right on the > box
        raise Failed(f"Right lit the > box ({cam.frame.path.name}); back with Left")
    if got != field:
        raise Failed(f"Right put the cursor on {got!r}, not the {field} field ({cam.frame.path.name})")


def rank(field: str, v):
    """A field's value as a number that Down lowers (the look, 2026-10-31): the step itself, and the
    images 9, 7, 5, 3, 2 (-), 2 (+) in that order."""
    if v is None:
        return None
    if field == "step":
        return v
    n, sign = v
    return n * 10 + {"": 5, "-": 1, "+": 0}[sign]


def read_field(cam, field: str, read):
    """The focused field's value; a reading that does not parse is looked at once more ("0.7EV" read
    "O.ZEV" on the frame right after the press, 2026-10-31)."""
    v = read(fields(cam)[field])
    if v is None:
        time.sleep(0.5)
        cam.refresh("reread")
        v = read(fields(cam)[field])
    return v


def set_field(cam, field: str, want, read) -> None:
    """Up/Down until the focused field reads `want`: Down when the wanted value is lower, and the
    other way at an end the list does not come round from."""
    last = None
    for _ in range(30):
        now = read_field(cam, field, read)
        if now == want:
            return
        if now is None:
            break
        key = "down" if rank(field, want) < rank(field, now) else "up"
        if last == "turned":
            key = "up" if key == "down" else "down"
        cam.press(key)
        after = read_field(cam, field, read)
        if after == now:
            if last == "turned":
                break                        # both ways tried: not in this list
            last = "turned"
    raise Failed(f"the {field} field never read {want!r} (last {fields(cam)[field]!r}, {cam.frame.path.name})")


def to_end(cam, field: str, read, key: str = "up", most: int = 20):
    """Up until the field stops changing or comes round: a list's first value either way."""
    seen = [read(fields(cam)[field])]
    for _ in range(most):
        cam.press(key)
        now = read(fields(cam)[field])
        if now == seen[-1] or now in seen:
            return
        seen.append(now)


def walk(cam, field: str, read, most: int = 20) -> list:
    """The field's values in Down order, from where it stands to the end or round to the first."""
    vals = [read(fields(cam)[field])]
    for _ in range(most):
        cam.press("down")
        now = read(fields(cam)[field])
        if now is None or now == vals[-1] or now in vals:
            break
        vals.append(now)
    return vals


def look(cam, cycle, model, option: str) -> dict:
    """{step: [images...]}: each step's image counts, read by stepping both fields (no OK). Each
    field is taken to one end first, so a list that does not come round is read whole."""
    open_carousel(cam, cycle, model, option)
    right_to(cam, "step")
    to_end(cam, "step", step_of)
    out, seen = {}, set()
    for _ in range(30):
        st = step_of(fields(cam)["step"])
        if st is None or st in seen:
            break
        seen.add(st)
        right_to(cam, "images")
        to_end(cam, "images", images_of)
        counts = [c for c in walk(cam, "images", images_of) if c is not None]
        out[st] = counts
        print(f"   {st:.1f} EV: {[label(st, c).split(' EV ')[1] for c in counts]}", flush=True)
        cam.press("left")
        if focus(cam) != "step":
            raise Failed(f"Left from the images field went to {focus(cam)!r} ({cam.frame.path.name})")
        cam.press("down")
    cam.press("menu")                        # Cancel: nothing chosen
    return out


def commit(cam, option: str):
    """OK, from a field: once to leave the field if the dialog stays, then OK on the carousel."""
    for _ in range(2):
        t = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
        if safety.confirmation(t):
            raise Failed(f"the screen reads like a confirmation ({safety.confirmation(t)})")
        cam.press("enter")
        if match.key(title(cam)) != match.key(option):
            return
        if focus(cam) is not None:
            raise Failed(f"OK left the cursor on the {focus(cam)} box ({cam.frame.path.name})")
    raise Failed(f"OK left the Drive Mode carousel open ({cam.frame.path.name})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--option", required=True, choices=("Cont. Bracket", "Single Bracket"))
    ap.add_argument("--look", action="store_true", help="read every step's image counts, choose nothing")
    ap.add_argument("--sample", type=int, default=0, help="prove this many settings spread over the list")
    ap.add_argument("--rest", action="store_true", help="leave out the settings already proved (a run cut short)")
    add_scan_argument(ap)
    ap.add_argument("--context", default=None)
    a = ap.parse_args()
    cycle, model = load_scan(a.scan)
    run = Run("kit2_pass2")
    hdmi = eyes_from_config(run)
    with proofs_file(run, a.context) as out, \
            prover_session(run, hdmi, start_tag="bracket-before", settle=LOCK_S, say_start=False, end_why="the restore",
                           end_tag="end", note="the start file left records apart") as s:
        cam, link = s.cam, s.link
        lists = look(cam, cycle, model, a.option)
        write_json(run.dir / f"bracket_{a.option.split()[0].lower().strip('.')}_lists.json",
                   {str(k): v for k, v in lists.items()})
        close_screen(cam, link)
        if a.look:
            return
        todo = [(st, c) for st, cs in sorted(lists.items()) for c in cs]
        place = {x: k for k, x in enumerate(todo)}     # a proof's index: its place in the whole list
        if a.rest:
            done = {r["label"] for r in jsonl.read(run.dir / "proofs.jsonl")
                    if r.get("path") == ["Drive Mode", a.option] and r.get("applied")}
            todo = [x for x in todo if label(*x) not in done]
        if a.sample and len(todo) > a.sample:
            n = len(todo)
            todo = [todo[i] for i in sorted({round(i * (n - 1) / (a.sample - 1)) for i in range(a.sample)})]
        # the option once, its fields as they are: the base
        open_carousel(cam, cycle, model, a.option)
        held = (step_of(fields(cam)["step"]), images_of(fields(cam)["images"]))
        commit(cam, a.option)
        to_shooting(link, hdmi, "the base download")
        time.sleep(1)
        base = link.download(f"bracket-{a.option.split()[0].lower()}-base")
        time.sleep(LOCK_S)
        bc = camset.read(base)
        print(f"{a.option}: holds {label(*held) if None not in held else held}; {len(todo)} to prove", flush=True)
        for st, c in todo:
            i = place[(st, c)]
            if run.stop_requested():
                print("STOP file: stopping before the next setting", flush=True)
                break
            open_carousel(cam, cycle, model, a.option)
            right_to(cam, "step")
            set_field(cam, "step", st, step_of)
            right_to(cam, "images")
            set_field(cam, "images", c, images_of)
            f = fields(cam)
            if step_of(f["step"]) != st or images_of(f["images"]) != c:
                raise Failed(f"the fields read {f} before OK, not {label(st, c)!r}")
            chosen = cam.frame.path.name
            commit(cam, a.option)
            to_shooting(link, hdmi, "the download after OK")
            time.sleep(1)
            dat = link.download(f"bracket-{a.option.split()[0].lower()}-{i}")
            time.sleep(LOCK_S)
            ch = camset.diff(bc, camset.read(dat))
            rec = {"path": ["Drive Mode", a.option], "kind": "list", "index": i, "label": label(st, c),
                   "fields": f"{f['step']} | {f['images']}", "via": "the option's step and images fields",
                   "chosen_frame": chosen, "dat": dat.name, "base": base.name, "applied": True,
                   "final": (st, c) == held,
                   "changes": changes_of(ch)}
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(f"   {label(st, c):18s} " + (", ".join(f"{x.key} {x.before!r}->{x.after!r}" for x in ch[:3])
                                             or "no change"), flush=True)


if __name__ == "__main__":
    main()
