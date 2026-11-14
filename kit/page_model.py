"""Build the page model from a page scan: structure from pixels, labels and values by vote.

    .venv/bin/python kit/page_model.py [--vlm] [kit2_page_scan]        # a run in the camera's runs/<model>_fw<fw>/
    .venv/bin/python kit/page_model.py --mode Stills kit2_page_scan    # only record the mode an older scan was made in

With --vlm, runs the VLM page-reading pass (asking the "second" reader, 8 at a time, or the reader --reader NAME
names when that one is away) before building the model; a scan folder a --network run marked (camkit.vlm.LOCAL_MARKER)
is read by a local reader only (camkit.vlm.local_only_runs), and the tool stops before asking anything otherwise.
For each scanned page it lines up the pixel reader's rows (how many, which are greyed: authoritative
for structure), OCR (and a second OCR engine as "ocr2" when one is installed), and each VLM's reading (only answers already in the VLM cache are
used: this never calls a server). Labels the user confirmed (<run>/user_labels.json, keyed by page
counter and row) count as a reading too, and so do labels read by eye off the frame where the readers
disagreed (<run>/checked_labels.json, same keys, each naming its frame). A label or value is "confirmed" when two of those sources agree
after icon noise is stripped; otherwise every source's reading is kept for review.

Writes <run>/model.json and prints a summary with the disagreements. A runner takes a scan by default only while its
model.json is built from its lap (runner.scan_unready: the lap's scan id, recorded in <run>/scan_mode.json as
"model_of", for a scan made since 2026-11-11; else the model newer than the lap): after a lap is written again, run
this again.

--mode MODE records the shooting mode the scan was made in (<run>/scan_mode.json, that one field, runner.record_mode)
and does nothing else: for a scan made before kit/page_scan.py recorded it itself (2026-11-11), which no runner takes
by default until it does (runner.latest_scan). Say only a mode the scan's own run log or frames show; a scan that
records a mode keeps it.
"""
import argparse
import collections
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import config, ocr, paths, safety  # noqa: E402
from camkit.runs import private_if_marked  # noqa: E402
from camkit.screen import MENU_ROW_PITCH, MENU_ROW_TOP  # noqa: E402
from camkit.vlm import PROMPTS, NoReader, cache_key, cached, local_only_runs, make_reader, readers, role  # noqa: E402
from runner import (SCAN_MODES, OcrUnavailable, read_frames, read_json, record_mode, record_model,  # noqa: E402
                    scan_mode, scan_unready, write_json)


def alive(cfg) -> bool:
    body = {"model": cfg["model"], "max_tokens": 3, "messages": [{"role": "user", "content": "OK"}],
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(cfg["url"] + "/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=50).read()
        return True
    except Exception as e:
        print(time.strftime("%H:%M:%S"), "not yet:", str(e)[:80], flush=True)
        return False


def vlm_read_pages(root: Path, reader_name: str | None = None):
    """Ask a reader for every page's first frame (answers go to the VLM cache): the "second" reader, or the
    configured reader --reader names when that one is away (a server on another machine switched off)."""
    listed = readers(stop=True)                 # none listed: its sentence, and nothing asked
    cfg = role("second") if not reader_name else next((r for r in listed if r["name"] == reader_name), None)
    if cfg is None:
        sys.exit(f"--reader {reader_name!r}: no reader of that name in private/config.json")
    # a run folder a --network run marked: local readers only, refused before even the first "alive" request
    local_only_runs(root)
    try:
        reader = make_reader(cfg)
    except NoReader as e:
        sys.exit(f"{e}: name a local reader with --reader; nothing asked")
    for _ in range(40):
        if cfg.get("kind") == "anthropic" or alive(cfg):     # Claude: the SDK retries for itself
            break
        time.sleep(60)
    else:
        sys.exit(f"gave up waiting for {cfg['name']}")
    firsts = collections.OrderedDict()
    for r in read_json(root / "scan_rekeyed.json"):
        if r["kind"] == "menu":
            firsts.setdefault(r["page"], r)

    def one(rec):
        try:
            reader.ask((root / "shots" / rec["frame"]).read_bytes(), PROMPTS["menu"])
            return "ok"
        except Exception as e:
            return f"error {e}"
    t = time.monotonic()
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, firsts.values()))
    print(f"read {sum(r == 'ok' for r in res)}/{len(res)} pages in {time.monotonic() - t:.0f} s", flush=True)


def cached_vlm(image: bytes, kind: str) -> dict:
    """{reader name: answer} for the answers already cached; no requests."""
    out = {}
    for r in config().get("readers") or []:
        answer = cached(cache_key(image, PROMPTS[kind], r["model"]))     # camkit.vlm's own cache, as a reader keeps it
        if answer is not None:
            out[r["name"]] = answer
    return out


def key_text(s) -> str:
    """Compare labels/values without icon noise, case, spacing or punctuation variants."""
    t = safety.clean_label(str(s or ""))
    t = t.replace("›", ">").replace("’", "'").translate(str.maketrans("l1|0", "iiio"))   # OCR look-alikes
    return re.sub(r"[\s.]+", "", t)


def same_text(a, b) -> bool:
    """Equal, or equal but for a 1-2 character prefix: OCR reads a row's icon as letters glued to the
    label ("SAF Frame Move Amt" for "AF Frame Move Amt")."""
    ka, kb = key_text(a), key_text(b)
    if not ka or not kb:
        return False
    short, long_ = sorted((ka, kb), key=len)
    return ka == kb or (len(long_) - len(short) <= 2 and long_.endswith(short) and len(short) >= 4)


def vote(readings: dict) -> tuple:
    """(value, agreed_by): the cleanest reading another source matches (VLM before OCR, shorter
    before longer, then the shorter raw text: one OCR engine keeps an icon read as "•" that the
    other drops, 2026-10-30), else (None, [])."""
    names = sorted(readings, key=lambda n: (n in ("ocr", "ocr2"), len(key_text(readings[n])),
                                            len(str(readings[n] or ""))))
    for a in names:
        same = [b for b in names if b != a and same_text(readings[a], readings[b])]
        if same:
            return readings[a], sorted([a] + same)
    return None, []


def main():
    ap = argparse.ArgumentParser(description="Build the page model from a page scan")
    ap.add_argument("run", nargs="?", default=None, type=paths.run_arg,
                    help="run folder (a run in the camera's runs/<model>_fw<fw>/, or a path; default: kit2_page_scan, "
                         "but --mode takes only a scan named)")
    ap.add_argument("--vlm", action="store_true", help="run VLM page-reading pass before building model")
    ap.add_argument("--reader", default=None, metavar="NAME",
                    help="with --vlm: the configured reader to ask, by its name, instead of the \"second\" one")
    ap.add_argument("--mode", default=None, type=scan_mode,
                    help=f"only record the shooting mode the scan was made in ({', '.join(SCAN_MODES)}) and stop")
    a = ap.parse_args()
    if a.mode and a.run is None:
        sys.exit("page_model: --mode records the mode of the scan named: page_model.py --mode MODE <run>")
    run = Path(a.run or paths.run_arg("kit2_page_scan"))
    private_if_marked(run)              # a --network or --owner run's folder: model.json 0600 in it too
    if a.mode:
        if a.vlm or a.reader:
            sys.exit("page_model: --mode only records the scan's mode; run --vlm on its own")
        if not (run / "scan_rekeyed.json").is_file():
            sys.exit(f"page_model: {run} holds no whole lap (scan_rekeyed.json): no page scan to record a mode for")
        try:
            record_mode(run, a.mode)
        except ValueError as e:
            sys.exit(f"page_model: {e}")
        why = scan_unready(run)
        print(f"{run.name}: recorded as a {a.mode} mode page scan ({run / 'scan_mode.json'})"
              + (f"; no runner takes it by default yet: {why}" if why else ""))
        return
    if a.vlm:
        vlm_read_pages(run, a.reader)
    shots = run / "shots"
    recs = read_json(run / "scan_rekeyed.json")
    pages = collections.OrderedDict()
    for r in recs:
        if r["kind"] == "menu":
            pages.setdefault(r["page"], []).append(r)
    firsts = [rs[0] for rs in pages.values()]
    # a frame the OCR helper cannot read (a torn PNG) is named and left unread, never taken for a page without text:
    # its OCR readings stay out of the vote, which the other readers decide (runner.read_frames)
    try:
        ocr_lines, unread = read_frames([shots / r["frame"] for r in firsts])
    except OcrUnavailable as e:                     # the engine, not a frame: model.json left as it is
        sys.exit(f"{e}; no page model made, {run / 'model.json'} left as it is")
    # a second, independent OCR engine when one is installed (Apple Vision and RapidOCR miss different
    # rows: kit/tools/ocr_compare.py); its readings vote as "ocr2". One that cannot run gives no vote
    eng2, ocr2_lines, unread2 = ocr.second(), {}, {}
    if eng2:
        try:
            ocr2_lines, unread2 = read_frames([shots / r["frame"] for r in firsts], eng2)
        except OcrUnavailable as e:
            print(f"the second OCR engine gives no vote: {e}", flush=True)
            eng2 = None
    for p, why in {**unread, **unread2}.items():
        print(f"not read by OCR, left out of the vote: {p.name}: {why}", flush=True)
    user = read_json(run / "user_labels.json") if (run / "user_labels.json").exists() else {}
    # labels read by eye off the scan's own frame where the readers disagreed (not the user's word;
    # each entry names its frame): a reading like any other
    eye = read_json(run / "checked_labels.json") if (run / "checked_labels.json").exists() else {}
    model, confirmed, total, disagreements = [], 0, 0, []
    for key, rs in pages.items():
        first = rs[0]
        path = shots / first["frame"]
        lines = ocr_lines.get(path)               # None: the frame was not read (unread), not a page without text
        lines2 = ocr2_lines.get(path) if eng2 else None
        vlm = cached_vlm(path.read_bytes(), "menu")
        n = max(r["rows"] or 0 for r in rs)
        states = {}
        for r in rs:
            for i, st in enumerate(r["slots"] or []):
                if st != "cursor":
                    states.setdefault(i, st)
        crumb = {"ocr": ocr.text_in(lines, (0, 0, 520, 40))} if lines is not None else {}
        counter = {"ocr": ocr.text_in(lines, (520, 0, 640, 40))} if lines is not None else {}
        for name, a in vlm.items():
            crumb[name], counter[name] = a.get("breadcrumb"), a.get("page")
        # the page's n/N, by OCR; on a page OCR did not read, the vision readers' (agreed, else the first given), so
        # the owner's labels for it (user_labels.json, checked_labels.json) still reach the vote
        page_no = (counter["ocr"] if "ocr" in counter else vote(counter)[0]
                   or next((str(v) for v in counter.values() if v), "") or "").replace(" ", "")
        rows = []
        for i in range(n):
            y0 = MENU_ROW_TOP + MENU_ROW_PITCH * i
            labels, values = {}, {}
            if lines is not None:
                labels["ocr"] = ocr.text_in(lines, (140, y0, 470, y0 + 52)).strip()
                values["ocr"] = ocr.text_in(lines, (470, y0, 640, y0 + 52)).strip()
            if lines2 is not None:
                labels["ocr2"] = ocr.text_in(lines2, (140, y0, 470, y0 + 52)).strip()
                values["ocr2"] = ocr.text_in(lines2, (470, y0, 640, y0 + 52)).strip()
            vgrey = {}
            for name, a in vlm.items():
                vr = (a.get("rows") or [])
                if i < len(vr) and isinstance(vr[i], dict):
                    labels[name], values[name] = vr[i].get("label"), vr[i].get("value")
                    vgrey[name] = vr[i].get("greyed")
            if str(i) in user.get(page_no, {}):
                labels["user"] = user[page_no][str(i)]["label"]
            if str(i) in eye.get(page_no, {}):
                labels["eye"] = eye[page_no][str(i)]["label"]
            label, by = vote(labels)
            value, vby = vote(values)
            total += 1
            confirmed += bool(by)
            row = {"slot": i, "label": label, "label_by": by, "value": value, "value_by": vby,
                   "greyed": states.get(i) == "greyed" if i in states else None,
                   "vlm_greyed": vgrey, "readings": {"label": labels, "value": values},
                   # never-open by the label, else by any reading (an unread OCR leaves the others to say it)
                   "never_open": safety.never_open(label or "") or next(
                       (w for w in (safety.never_open(x) for x in labels.values() if x) if w), None)}
            if not by:
                disagreements.append((first["frame"], i, labels))
            rows.append(row)
        vlm_rows = {name: len(a.get("rows") or []) for name, a in vlm.items()}
        model.append({"page": vote(counter)[0] or counter.get("ocr"), "breadcrumb": vote(crumb)[0] or crumb.get("ocr"),
                      "key": key, "frame": first["frame"], "down_from_start": first["n"], "rows": rows,
                      "vlm_row_counts": vlm_rows, "readers": sorted(vlm),
                      **({"ocr_unread": unread[path]} if path in unread else {}),
                      **({"ocr2_unread": unread2[path]} if path in unread2 else {})})
    write_json(run / "model.json", model, indent=1)
    record_model(run, recs)                 # which lap the model is of (runner.scan_unready), where the scan says it
    readers = collections.Counter(n for p in model for n in p["readers"])
    mismatched = [(p["page"], len(p["rows"]), p["vlm_row_counts"]) for p in model
                  if any(c != len(p["rows"]) for c in p["vlm_row_counts"].values())]
    print(f"{len(model)} pages, {total} rows; labels confirmed by two sources: {confirmed}/{total}")
    print(f"VLM readings available: {dict(readers)}")
    print(f"pages where a VLM counts a different number of rows: {len(mismatched)} {mismatched[:6]}")
    for frame, i, labels in disagreements[:25]:
        print(f"  ? {frame} row {i}: " + " | ".join(f"{k}={str(v)[:28]!r}" for k, v in labels.items()))


if __name__ == "__main__":
    main()
