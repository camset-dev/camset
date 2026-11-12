"""Read-only walk of carousel options' second axes ("Spot: Standard" / "Spot: Large").

    .venv/bin/python -u kit/axis_walk.py [--rows "Metering Mode" ...]

For each carousel option pass 1 saw with side arrows (‹ › at the selected option): open the
carousel, go to the option, press Right until the title comes back round or stops changing (at most
12), reading the title after each press; Left as many times back; MENU cancels the carousel, so
nothing is committed. Settings are downloaded before and after and must not differ.
Results: runs/<model>_fw<fw>/kit2_axes/axes.json {row: {option: [axis values in Right order, from the one held]}}.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import screen  # noqa: E402
from camkit.frames import eyes_from_config, load  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.live import LiveCamera  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.screen import same_position  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import PASS1, carousel_text, frame_file, main_name, option_key, to_shooting  # noqa: E402
from runner import (EXIT_UNRESTORED, add_scan_argument, close_for_restore, end_session, load_scan,  # noqa: E402
                    read_json, restore_checked, write_json)

AXIS_GLYPHS = ("side_left", "side_right")
SKIP = {"Creative Look"}         # its arrows belong to the look's parameter strip, not a second axis


def axis_options() -> dict:
    """row -> [option labels with side arrows in pass 1's frames], with the row's option labels."""
    out = {}
    for r in read_json(PASS1 / "map_all.json")["rows"]:
        if r["kind"] != "dialog" or " > ".join(r["path"]) in SKIP:
            continue
        by = {}
        for o in r["options"]:
            by.setdefault(o["index"], o)
        labels, with_axis = [by[i]["label"] for i in sorted(by)], []
        for i in sorted(by):
            p = frame_file(r["path"], by[i]["frame"])          # the row's own crawl first (pass1_map's "run")
            if p and all(screen.read(load(p)).glyphs.get(g) for g in AXIS_GLYPHS):
                with_axis.append(by[i]["label"])
        if with_axis:
            out[" > ".join(r["path"])] = {"labels": labels, "axis": with_axis}
    return out


def title(cam) -> str:
    time.sleep(0.4)                               # the title redraws after the strip
    cam.refresh("reread")
    return carousel_text(cam)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", action="append", default=None)
    add_scan_argument(ap)
    a = ap.parse_args()
    todo = {k: v for k, v in axis_options().items() if not a.rows or k in a.rows}
    print({k: v["axis"] for k, v in todo.items()}, flush=True)
    cycle, model = load_scan(a.scan)
    run = Run("kit2_axes")
    out_path = run.dir / "axes.json"
    found = read_json(out_path) if out_path.exists() else {}
    hdmi = eyes_from_config(run)
    try:
        with Link(run) as link:
            hdmi.attach(link)
            to_shooting(link, hdmi, "the settings download")
            before = link.download("before")
            time.sleep(5)
            cam = LiveCamera(link, hdmi, run)
            try:
                cam.press("menu")
                j = next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)
                if j is None:
                    raise RuntimeError(f"the menu opened on a screen the scan does not know ({cam.read().kind})")
                for row, info in todo.items():
                    j = go_to(cam, cycle, model, j, row)
                    if j is None:
                        raise RuntimeError(f"on the way to {row!r} a screen was not the one the scan recorded")
                    for opt in info["axis"]:
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
                                                                               "back": back}
                        write_json(out_path, found, indent=1, ensure_ascii=False)   # whole: earlier axes stay
                        cam.press("menu")                                  # cancel: nothing committed
                        if cam.read().kind != "menu":
                            raise RuntimeError(f"MENU did not cancel the {row} carousel ({cam.read().kind})")
            except Exception as e:
                print(f"error: {type(e).__name__}: {e}; cancelling", flush=True)
                close_for_restore(cam, link)        # cleanup presses; when they fail too, the restore all the same
            # a read-only walk; if anything changed, the start goes back
            ending = end_session(link, hdmi, before, "the settings download after the walk")
        restored = restore_checked(run, ending, before)
    finally:
        hdmi.close()
    if not restored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)


if __name__ == "__main__":
    main()
