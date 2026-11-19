"""Read-only walk of carousel options' second axes ("Spot: Standard" / "Spot: Large").

    .venv/bin/python -u kit/axis_walk.py [--rows "Metering Mode" ...]
    CAMSET_EYES=osd .venv/bin/python -u kit/axis_walk.py --scan SCAN --map kit2_fin_crawl_brk/map.json \\
        --rows "Bracket Settings > Bracket Type"

For each carousel option pass 1 saw with side arrows (‹ › at the selected option): open the
carousel, go to the option, press Right until the title comes back round or stops changing (at most
12), reading the title after each press; Left as many times back; MENU cancels the carousel, so
nothing is committed. Settings are downloaded before and after and must not differ.
Results: runs/<model>_fw<fw>/kit2_axes/axes.json {row: {option: [axis values in Right order, from the one held]}}.
kit/prove_run.py on pass 1's map adds an axis job for every value the file lists; without it no second axis is proved,
so walk the axes before proving.

--map: the carousels of a run's own map instead of pass 1's (kit/pass1_map.py --own's map.json in a crawl's folder,
read with that crawl's own frames; a row a switched state alone opens: Bracket Type with the drive mode dial on BRK). A
row inside a submenu is reached by its path and keyed by it whole ("Bracket Settings > Bracket Type"). Each entry it
writes names that map ("map": proving.base.map_key), and kit/prove_run.py --map with the same map proves those entries
alone (proving.jobs.axis_jobs), a run on pass 1's map never them. The rows axes.json holds already stay as they are:
a row whose entries another map's walk wrote, or pass 1's, is left out and said, before anything connects.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import paths, screen  # noqa: E402
from camkit.frames import eyes_from_config, load  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.screen import same_position  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import PASS1, carousel_text, enter_any, frame_file, main_name, option_key  # noqa: E402
from proving.base import map_key  # noqa: E402
from proving.screens import title_settled  # noqa: E402
from runner import (add_scan_argument, load_scan, menu_from_shooting, prover_session, read_json,  # noqa: E402
                    write_json)

AXIS_GLYPHS = ("side_left", "side_right")
SKIP = {"Creative Look"}         # its arrows belong to the look's parameter strip, not a second axis
MAP = None                       # --map: a run's own map.json (main sets it), else pass 1's map_all.json


def map_frame(r: dict, fr: str):
    """A --map row's saved frame: in the crawl its row names ("run", a merged map's), else in the map's own crawl's
    shots/ (pass1_map.py --own writes map.json beside them); None where it is not there. Frame numbers repeat across
    runs, so pass 1's folders are never looked in for them."""
    root = Path(MAP).resolve().parent
    p = (root.parent / r["run"] / "shots" / fr) if r.get("run") else (root / "shots" / fr)
    return p if p.exists() else None


def axis_options() -> dict:
    """row -> [option labels with side arrows in pass 1's frames (--map: that map's own crawl's)], with the row's option
    labels."""
    out = {}
    for r in read_json(Path(MAP) if MAP else PASS1 / "map_all.json")["rows"]:
        if r["kind"] != "dialog" or " > ".join(r["path"]) in SKIP:
            continue
        by = {}
        for o in r["options"]:
            by.setdefault(o["index"], o)
        labels, with_axis = [by[i]["label"] for i in sorted(by)], []
        for i in sorted(by):
            # the row's own crawl first (pass1_map's "run")
            p = map_frame(r, by[i]["frame"]) if MAP else frame_file(r["path"], by[i]["frame"])
            if p and all(screen.read(load(p)).glyphs.get(g) for g in AXIS_GLYPHS):
                with_axis.append(by[i]["label"])
        if with_axis:
            out[" > ".join(r["path"])] = {"labels": labels, "axis": with_axis}
    return out


def held_elsewhere(todo: dict, found: dict, mine) -> list:
    """The rows of `todo` whose entries in axes.json (`found`) another walk wrote: another map's, or pass 1's where this
    walk is a --map's (`mine`, its map_key; None for pass 1's). Their entries stay as they are."""
    return [row for row in todo if any(not isinstance(o, dict) or o.get("map") != mine
                                       for o in (found.get(row) or {}).values())]


def back_to_page(cam, path) -> None:
    """From the row of `path` after MENU closed its carousel back to its menu page: Left out of each submenu (a row
    inside one), as a prover goes back up after a row."""
    for _ in range(len(path) + 2):
        if cam.read().kind != "submenu":
            break
        cam.press("left")


def title(cam) -> str:
    """The carousel's title once its strip has stopped changing (proving.screens.title_settled: it redraws after the
    side strip; over HDMI watched, over OSD 0.4 s and a fresh grab as before), as prove_run.axis_title reads it."""
    title_settled(cam)
    return carousel_text(cam)


def main():
    global MAP
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", action="append", default=None)
    ap.add_argument("--map", default=None, type=paths.run_arg,
                    help="a run's own map.json (kit/pass1_map.py --own) instead of pass 1's: kit2_crawl/map.json is in "
                         "the camera's runs/<model>_fw<fw>/")
    add_scan_argument(ap)
    a = ap.parse_args()
    MAP = a.map
    todo = {k: v for k, v in axis_options().items() if not a.rows or k in a.rows}
    cycle, model = load_scan(a.scan)
    run = Run("kit2_axes")
    out_path = run.dir / "axes.json"
    found = read_json(out_path) if out_path.exists() else {}
    mine = map_key(a.map, run.root) if a.map else None
    for row in held_elsewhere(todo, found, mine):
        print(f"{row}: axes.json holds its axes from another walk ({'pass 1' if mine else 'a --map'}'s): left as it is, "
              "not walked", flush=True)
        del todo[row]
    if a.map and not todo:
        sys.exit(f"no carousel of {a.map} with a second axis to walk: nothing was sent to the camera")
    print({k: v["axis"] for k, v in todo.items()}, flush=True)
    hdmi = eyes_from_config(run)
    # a read-only walk in the session every runner runs (runner.prover_session): if anything changed, the start goes
    # back, and a camera not known to be as the start file exits EXIT_UNRESTORED
    with prover_session(run, hdmi, start_why="the settings download", say_start=False,
                        end_why="the settings download after the walk", watch_restart=False) as s:
        cam = s.cam
        try:
            menu_from_shooting(cam)
            j = next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)
            if j is None:
                raise RuntimeError(f"the menu opened on a screen the scan does not know ({cam.read().kind})")
            for row, info in todo.items():
                path = row.split(" > ")
                j = go_to(cam, cycle, model, j, path[0])
                if j is None:
                    raise RuntimeError(f"on the way to {row!r} a screen was not the one the scan recorded")
                for opt in info["axis"]:
                    if len(path) > 1:
                        enter_any(cam, path, 0)                    # into its submenus, down to the row
                    cam.press("right")
                    if cam.read().kind != "dialog":
                        raise RuntimeError(f"Right on {row!r} opened {cam.read().kind}")
                    for _ in range(len(info["labels"]) + 1):         # Down to the option by its name
                        if option_key(main_name(title(cam), "dialog")) == option_key(main_name(opt, "dialog")):
                            break
                        cam.press("down")
                    else:
                        raise RuntimeError(f"{row}: never reached {opt!r}")
                    seen, rights = [title(cam)], 0
                    for _ in range(12):
                        if not cam.read().glyphs.get("side_right"):
                            break                                      # the end of a non-wrapping axis
                        cam.press("right")
                        rights += 1
                        t = title(cam)
                        if t == seen[0] or t == seen[-1]:
                            break
                        seen.append(t)
                    for _ in range(rights):
                        cam.press("left")
                    back = title(cam)
                    print(f"{row} / {opt}: {seen}  (back on {back!r})", flush=True)
                    found.setdefault(row, {})[main_name(opt, "dialog")] = {"values": seen, "rights": rights,
                                                                           "back": back, **({"map": mine} if mine else {})}
                    write_json(out_path, found, indent=1, ensure_ascii=False)   # whole: earlier axes stay
                    cam.press("menu")                                  # cancel: nothing committed
                    if cam.read().kind != ("menu" if len(path) == 1 else "submenu"):
                        raise RuntimeError(f"MENU did not cancel the {row} carousel ({cam.read().kind})")
                    back_to_page(cam, path)
                    if len(path) > 1 and not same_position(cam.read(), cycle[j]["screen"]):
                        raise RuntimeError(f"back from {row!r}, its menu page does not look as the scan recorded it")
        except Exception as e:
            print(f"error: {type(e).__name__}: {e}; cancelling", flush=True)
            s.close()           # cleanup presses; when they fail too, the restore all the same


if __name__ == "__main__":
    main()
