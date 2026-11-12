"""Help text that is not on a row's or an option's guide, from kit/drive.py runs (2026-11-02).

    .venv/bin/python kit/tools/help_extras.py --fields kit2_help_fields --carousel kit2_dialmenu2 --guides kit2_help_sr kit2_lens50

--fields RUN: a number field's own In-Camera Guide ("help" on each field: ISO Range Limit's Minimum and
Maximum). A guide's field is counted by the Rights and Lefts pressed in the fields before it; its
title must be on the fields screen. -> kit2_help/field_help.jsonl
--carousel RUN: the Shoot Mode carousel's description of each mode, shown on its own screen (it has no
guide): every family's iAuto, P, A, S and M, each taken once. -> kit2_help/carousel_help.jsonl
--guides RUN...: the guides drive.py's "help" opened on rows no walk reads (the Screen Reader submenu, on the
never-open list): a row's before Right opened its list, an option's after, named by the guide's title;
each read once. -> kit2_help/drive_help.jsonl

The mode a drive ran in is its start file's shooting family (0x13bf: Stills 0, Movie 1, S&Q 2,
Time-lapse 3). The frames are copied into kit2_help/shots, where kit/help_reads.py reads them
again; schema_update.py places the text. Sony's wording, the owner's choice; it comes out of anything
published (docs/RELEASING.md). Every run named here, and kit2_help, is in the camera's runs/<model>_fw<fw>/
(camkit.paths).
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, jsonl, ocr, paths  # noqa: E402
from camkit.frames import load  # noqa: E402
from help_run import read_guide  # noqa: E402

RUN_ROOT = paths.module_root()          # the camera's runs, runs/<model>_fw<fw>/
HELP = RUN_ROOT / "kit2_help"
CONTEXTS = {0: "Stills mode", 1: "Movie mode", 2: "S&Q mode", 3: "S&Q mode"}
MODES = ["Intelligent Auto", "Program Auto", "Aperture Priority", "Shutter Priority", "Manual Exposure"]
TITLE, BODY = (120, 58, 640, 108), (120, 112, 640, 316)       # the carousel: orange mode name, white text


def context(run_dir: Path, drive: dict) -> str:
    return CONTEXTS[camset.read(run_dir / "dat" / drive["before"]).get(0, 0x13bf).value()]


def field_guides(screens: list) -> list[tuple[int, dict]]:
    """(field, screen) for each guide screen opened in number fields: Right opens the fields from the
    row, then each Right moves one field on and each Left one back."""
    field, out = -1, []
    for s in screens:
        key = s["after"].split(":")[0].split("@")[0]
        if key in ("right", "left") and s["kind"] == "fields":
            field += 1 if key == "right" else -1
        elif s["kind"] == "guide" and field >= 0:
            out.append((field, s))
    return out


def family(text: str) -> str:
    """The family a mode's description is written for. Read off the description alone: on the whole
    screen an icon splits "S&Q Motion" and "Time-lapse"."""
    t = re.sub(r"\s+", " ", text).lower()
    if re.search(r"s&q\W*motion", t):
        return "S&Q"
    if re.search(r"time-\W*lapse", t):
        return "Time-lapse"
    return "Stills" if "still image" in t else "Movie"


def fields(run: str) -> list[dict]:
    src, out = RUN_ROOT / run, []
    for d in jsonl.read(src / "drive.jsonl"):
        ctx = context(src, d)
        shown = " ".join(s["text"] for s in d["screens"] if s["kind"] == "fields")
        for k, s in field_guides(d["screens"]):
            title, body = read_guide(load(src / "shots" / s["frame"]))
            if not title or title not in shown:
                print(f"skipping {s['frame']}: its title {title!r} is not on the fields screen", flush=True)
                continue
            name = f"fields_{ctx.split()[0].lower()}_{s['frame']}"
            shutil.copy(src / "shots" / s["frame"], HELP / "shots" / name)
            out.append({"context": ctx, "path": d["path"], "field": k, "label": title, "title": title,
                        "text": re.sub(r"\s+", " ", body), "frames": [name], "source": paths.shown(src / "shots" / s["frame"])})
    return out


def carousel(run: str) -> list[dict]:
    src, seen, out = RUN_ROOT / run, set(), []
    for d in jsonl.read(src / "drive.jsonl"):
        if d["path"] != ["Shoot Mode"]:
            continue
        for s in d["screens"]:
            mode = next((m for m in MODES if m.lower() in s["text"].lower()), None)
            if s["kind"] != "dialog" or mode is None:               # the MR modes are never visited
                continue
            f = src / "shots" / s["frame"]
            words = ocr.read([f])[f]
            body = re.sub(r"\s+", " ", ocr.text_in(words, BODY)).strip()
            fam = family(body)
            if (fam, mode) in seen:
                continue
            seen.add((fam, mode))
            name = "shootmode_" + s["frame"]
            shutil.copy(f, HELP / "shots" / name)
            out.append({"family": fam, "label": mode, "title": ocr.text_in(words, TITLE).strip(), "text": body,
                        "frames": [name], "source": paths.shown(src / "shots" / s["frame"])})
    return out


def guide_screens(screens: list) -> list[tuple[bool, dict]]:
    """(an option's?, screen) for each guide opened: by C4, or by Enter on the popup's In-Camera Guide (a
    Down on a guide shows it again). It is an option's once Right has opened the row's list."""
    opened, prev, out = False, None, []
    for s in screens:
        key, came_from, prev = s["after"].split(":")[0].split("@")[0], prev, s["kind"]
        if key == "right" and s["kind"] in ("list", "dialog"):
            opened = True
        if s["kind"] == "guide" and (key == "help" or (key == "enter" and came_from == "helppop")):
            out.append((opened, s))
    return out


def guides(runs: list) -> list[dict]:
    seen, out = set(), []
    for run, d in ((r, d) for r in runs for d in jsonl.read(RUN_ROOT / r / "drive.jsonl")):
        src = RUN_ROOT / run
        ctx, n = context(src, d), 0
        for opened, s in guide_screens(d["screens"]):
            title, body = read_guide(load(src / "shots" / s["frame"]))
            label = title if opened else None
            if not title or (ctx, tuple(d["path"]), label) in seen:
                continue
            seen.add((ctx, tuple(d["path"]), label))
            name = f"guide_{run}_{s['frame']}"
            shutil.copy(src / "shots" / s["frame"], HELP / "shots" / name)
            out.append({"context": ctx, "path": d["path"], "index": n if opened else -1, "label": label, "title": title,
                        "text": re.sub(r"\s+", " ", body), "frames": [name], "source": paths.shown(src / "shots" / s["frame"])})
            n += opened
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fields", help="a drive.py run with \"help\" on number fields")
    ap.add_argument("--carousel", help="a drive.py run through the Shoot Mode carousel (Set with Menu)")
    ap.add_argument("--guides", nargs="+", help="drive.py runs with \"help\" on rows and their options")
    a = ap.parse_args()
    (HELP / "shots").mkdir(parents=True, exist_ok=True)          # the guide frames' copies, read again by help_reads
    for run, make, name in ((a.fields, fields, "field_help.jsonl"), (a.carousel, carousel, "carousel_help.jsonl"),
                            (a.guides, guides, "drive_help.jsonl")):
        if not run:
            continue
        rows = make(run)
        with open(HELP / name, "w", encoding="utf-8", newline="\n") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
        print(f"{name}: {len(rows)} texts from {run}", flush=True)
        for r in rows:
            print(f"   {r.get('context') or r['family']:12s} {' > '.join(r.get('path') or [])[:34]:34s} "
                  f"{str(r['label'])[:14]:14s} {r['text'][:70]}", flush=True)


if __name__ == "__main__":
    main()
