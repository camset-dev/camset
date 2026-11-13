"""The camera's own help (In-Camera Guide) for every menu row, read off the screen (2026-11-01).

    .venv/bin/python -u kit/help_run.py --scan kit2_page_scan_movie --context "Movie mode"

Walks the page scan's cycle with Down, as the scan did, one row at a time. On each row: C4, the trash
button, which the owner allowed for this alone and only where the footer draws the help button. On
the popup the cursor starts on Add to My Menu, which writes the file: Down, and Enter only once the
lit entry reads In-Camera Guide. The guide's title and text are read, Down pages a long text, and OK
(Enter, only on a guide screen) closes it back onto the row. Nothing is chosen, so the settings
downloaded before and after must match. Rows on the never-open list, the Delete page, My Menu and the
Main tiles are passed over; with --by-hand-rows the settings changed by hand only are read too (their
guide only shows text), never Access Authen.

Results: <run>/help.jsonl in the camera's runs/<model>_fw<fw>/, one line per row with its guide frames. A row already there for this
context is not read again, so a stopped walk resumes where it left off. The help text is Sony's
wording (the owner's choice); it comes out of anything published (docs/RELEASING.md).
"""
import argparse
import difflib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import ocr, safety, screen  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.live import LiveCamera  # noqa: E402
from camkit.vlm import check_readers  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.screen import same_position  # noqa: E402
from camkit.session import wait_for  # noqa: E402
from drive import help_refused, highlighted  # noqa: E402
from page_model import key_text  # noqa: E402
from prove_run import Failed  # noqa: E402   (one class: a row prove_run --help-text cannot read is skipped)
from runner import (EXIT_UNRESTORED, add_scan_argument, close_for_restore, end_session, load_scan,  # noqa: E402
                    restore_checked, wait_shooting)

TITLE, BODY = (40, 0, 640, 46), (0, 46, 640, 420)      # the guide: orange name, text, OK in the footer
SKIP_PAGES = re.compile(r"^(My Menu|Playback > Delete)")   # repeats of other tabs; the Delete menu, by hand
NEVER_HELP = re.compile(r"access authen", re.I)           # the owner: that screen is never opened remotely


def on_label(lit: str, label: str) -> bool:
    """The lit bar (icon, label, value) shows the label, allowing an OCR slip ("Initill Focus Mag.",
    2026-11-01): the scan's position check after every Down already says which row it is."""
    want, got = key_text(label).lower()[:12], key_text(lit).lower()
    if want in got:
        return True
    return max((difflib.SequenceMatcher(None, want, got[i:i + len(want)]).ratio()
                for i in range(max(1, len(got) - len(want) + 1))), default=0) >= 0.75


def read_guide(frame) -> tuple[str, str]:
    words = ocr.read([frame.path])[frame.path]
    return ocr.text_in(words, TITLE).strip(), ocr.text_in(words, BODY).strip()


def guide(cam, label: str) -> dict:
    """C4 on the lit row, through the popup to the guide, read it, OK. The cursor ends on the row."""
    glyph = screen.help_glyph(cam.frame.image)
    cam.press("c4", allow={"c4"})
    popup = cam.read().kind == "helppop"
    if popup:
        lit = highlighted(cam.frame.image, cam.frame.path)
        if re.search(r"my menu", lit, re.I):
            cam.press("down")
            lit = highlighted(cam.frame.image, cam.frame.path)
        if not re.search(r"in-?camera guide", lit, re.I):
            cam.cancel_to_menu()
            raise Failed(f"{label}: the help popup's lit entry reads {lit!r}, not In-Camera Guide")
        cam.press("enter")
    if cam.read().kind != "guide":
        kind, frame = cam.read().kind, cam.frame.path.name
        cam.cancel_to_menu()
        raise Failed(f"{label}: after C4 the screen is {kind!r} ({frame}), not the guide")
    frames, title, body = [cam.frame.path.name], *read_guide(cam.frame)
    texts = [body]
    for _ in range(6):                          # a long text pages with Down (none seen yet)
        cam.press("down")
        if cam.read().kind != "guide":
            cam.cancel_to_menu()
            raise Failed(f"{label}: Down on the guide left it ({cam.read().kind})")
        _, more = read_guide(cam.frame)
        if more == texts[-1]:
            break
        frames.append(cam.frame.path.name)
        texts.append(more)
    if cam.read().kind != "guide":
        raise Failed(f"{label}: not on the guide before OK")
    cam.press("enter")                          # OK: only closes the guide
    return {"title": title, "text": " ".join(texts), "frames": frames, "popup": popup,
            "my_menu": glyph == "help_key", "disabled": "currently disabled" in " ".join(texts).lower()}


def main():
    ap = argparse.ArgumentParser()
    add_scan_argument(ap)
    ap.add_argument("--context", required=True, help="the state the walk runs in (Movie mode, Stills mode)")
    ap.add_argument("--run", default="kit2_help")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many rows (a trial)")
    ap.add_argument("--by-hand-rows", action="store_true",
                    help="also read the help of settings that are changed by hand only (network, sound, USB...): "
                         "the guide only shows text; Access Authen. stays passed over")
    a = ap.parse_args()
    cycle, model = load_scan(a.scan)
    run = Run(a.run)
    out_path = run.dir / "help.jsonl"
    done = set()
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("context") == a.context and r.get("text") is not None:
                    done.add((r["breadcrumb"], r["label"]))
    check_readers()     # no reader listed: stop before the link opens, nothing pressed
    hdmi = eyes_from_config(run)
    ending, had = None, len(done)
    try:
        with Link(run) as link, open(out_path, "a", encoding="utf-8", newline="\n") as out:
            hdmi.attach(link)
            if screen.read(hdmi.grab(save=False)).kind in ("menu", "tiles"):
                link.press("menu", cleanup=True)
                time.sleep(1.0)
            wait_for(hdmi, ("shooting",), "the settings download", link=link)
            before = link.download("before")
            time.sleep(5)
            cam = LiveCamera(link, hdmi, run)
            try:
                walk(cam, cycle, model, done, out, a)
            except Exception as e:                  # a dropped link or anything else too: the guide is closed first
                print(f"stopped: {type(e).__name__}: {e}", flush=True)
            close_for_restore(cam, link)
            print(f"{len(done) - had} rows read", flush=True)
            # a help walk changes nothing; if it did, the start goes back, even when the shooting screen does not come
            ending = end_session(link, hdmi, before, "the settings download after the walk", reach=wait_shooting)
        restored = restore_checked(run, ending, before)
    finally:
        hdmi.close()
    if not restored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)


def walk(cam, cycle, model, done, out, a) -> None:
    """MENU, then Down through the scan's whole cycle reading each row's guide (guide) where its footer draws the help
    button and it was not read in this context before (`done`, which each row read joins); every screen is checked
    against the scan."""
    n, read = len(cycle), 0
    cam.press("menu")
    j = next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)
    if j is None:
        raise Failed(f"the menu opened on a screen the scan does not know ({cam.read().kind})")
    for _ in range(n):
        pos = cycle[j]
        page = model.get(pos.get("page"))
        if pos["kind"] == "menu" and page and pos["row"] is not None and pos["row"] < len(page["rows"]):
            label, crumb = page["rows"][pos["row"]]["label"], page["breadcrumb"]
            never = safety.never_open(label)
            if a.by_hand_rows and never and never.startswith("by hand only") and not NEVER_HELP.search(label):
                never = None                    # the guide shows text; the row is not opened
            skip = ("passed over" if SKIP_PAGES.match(crumb) else
                    never or help_refused(cam.read().kind, cam.frame.image))
            if (crumb, label) not in done and not skip:
                lit = highlighted(cam.frame.image, cam.frame.path)   # the bar: icon, label, value
                if not on_label(lit, label):
                    raise Failed(f"the lit row reads {lit!r}, the scan says {label!r}")
                r = guide(cam, label)
                if not same_position(cam.read(), pos["screen"]):
                    raise Failed(f"{label}: after OK the screen is not the row the walk was on")
                out.write(json.dumps({"context": a.context, "breadcrumb": crumb, "label": label, **r}) + "\n")
                out.flush()
                done.add((crumb, label))
                read += 1
                print(f"{crumb[:34]:34s} {label[:30]:30s} {r['text'][:90]!r}", flush=True)
                if a.limit and read >= a.limit:
                    break
            elif skip:
                print(f"{crumb[:34]:34s} {label[:30]:30s} (passed over: {skip})", flush=True)
        cam.press("down")
        j = (j + 1) % n
        if not same_position(cam.read(), cycle[j]["screen"]):
            raise Failed(f"after Down the screen is not the scan's position {j}")


if __name__ == "__main__":
    main()
