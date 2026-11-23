"""The third role's readers (camkit.vlm.voters: the third reader, or several asked in turn) for the options pass 1's OCR
and second reader read differently; kit/pass1_map.py then takes the majority, one vote per model family.

    .venv/bin/python -u kit/tiebreak.py kit2_crawl_movie          # a run in the camera's runs/<model>_fw<fw>/
    .venv/bin/python -u kit/tiebreak.py kit2_pass1 --revote --was Qwen3.8-27B-4bit     # the lines already there

Reads <run>/options.jsonl (kit/pass1_labels.py) and appends to <run>/tiebreak.jsonl, one line per
option of a list, checklist or side list the two readers disagreed on; options already there are
skipped, so it resumes. Carousels, grids and number fields are left to pass1_map's own rules.

A line holds "frame", "path", "index", "ocr" (OCR's reading), "vllm" (the second reader's, from options.jsonl) and
"omlx" (the first third reader's that answered), whatever readers play the roles (the names of the servers that first
did); "voters", each further third reader that answered, in turn ({"reader": its name, "model", "selected": its
reading}); "models", the model
that read "vllm" (the second reader's, as configured) and "omlx" ({"vllm": ..., "omlx": ...}); and "winner", what the
majority names (pass1_map.majority) or null; "third_only": true where third readers alone carry the majority, a reading
neither OCR nor the second reader gave (pass1_map.third_only), which never stands on those later votes alone: the line
keeps every reading and no "winner", and the summary lists it for a look by eye.
The third readers are asked in the order private/config.json gives them, each only while no reading stands: OCR, the
second reader and the third readers asked so far, one vote per model family (camkit.reading.model_id), none for a
family that read two things. A third reader of a family that has read the line already (the second reader's included)
is not asked: it could make no reading stand.

A third reader that fails, or reads nothing, is no answer, kept out of the line's "models" and "voters"; after FAIL_RUN
failures in a row it is asked nothing more in the run, said once. An option none of them answered, none of another
family was there to ask, or whose frame is not under shots/, is not written: a rerun asks it again.

--revote asks today's third readers about the lines already there, where no reading stands by family, and writes
tiebreak.jsonl afresh with what each line held kept: a third reader whose family has read the line already is not asked
again, and a line none of them answered, none of another family was there to ask, or whose frame is missing, is kept
as it was, for a later --revote to ask again. A line written before lines named their models (no "models") takes them from --was MODEL, the model the third
reader ran when it was written (its "omlx" kept as that model's), and the second reader's model as configured today;
--revote refuses to go on without --was while such a line is there. The old file is kept beside it as
tiebreak.jsonl.before_revote (once; a later --revote leaves it as it is).

A run folder a --network run marked (camkit.vlm.LOCAL_MARKER) is read with local third readers only
(camkit.vlm.local_only_runs: a third reader that is not local is left out, said, and the tool stops when none is left),
and an option of an identity or connection row a network decision opened ("network" on its line, other than a Wi-Fi or
Bluetooth setting's) is never asked about (docs/decisions/0008).
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import jsonl, paths, runs, safety, vlm  # noqa: E402
from camkit.reading import model_id  # noqa: E402
from camkit.vlm import PROMPTS, NoReader, make_reader, readers  # noqa: E402
from pass1_map import majority, settled, third_only, voices  # noqa: E402

BEFORE = "tiebreak.jsonl.before_revote"        # the file --revote wrote afresh, as it was
FAIL_RUN = 3                                   # failures in a row after which a third reader is asked nothing more
_FAILS: dict = {}                              # reader name -> its failures in a row in this run


def asked_of(reader, cfg: dict, image: bytes) -> tuple:
    """(the reading of the option under the cursor, the model that answered: the configured one, or the one the server
    says answered where that is another family, camkit.vlm.answered_model; whether it answered). A failure (an error,
    an answer that is no JSON object) is no answer, and after FAIL_RUN in a row the reader is asked nothing more in this
    run (down), said once; an empty reading is no answer either, though no failure of the reader's."""
    name = str(cfg.get("name"))
    reader.served = None                          # a cached answer names no server's model: the configured one's
    try:
        a = reader.ask(image, PROMPTS["option"])
    except Exception as e:
        a = {"_error": vlm.scrub(str(e))[:80]}
    usable = vlm.usable(a)
    _FAILS[name] = 0 if usable else _FAILS.get(name, 0) + 1
    if _FAILS[name] == FAIL_RUN:
        print(f"reader {name!r} failed {FAIL_RUN} times in a row ({a.get('_error') if isinstance(a, dict) else a}): "
              "it is asked nothing more in this run", flush=True)
    said = str(a.get("selected") or "").strip() if usable else ""
    return said, vlm.answered_model(str(cfg.get("model") or cfg.get("name") or ""), getattr(reader, "served", None)), bool(said)


def down(cfg: dict) -> bool:
    """A third reader that failed FAIL_RUN times in a row in this run: asked nothing more."""
    return _FAILS.get(str(cfg.get("name")), 0) >= FAIL_RUN


def families(line: dict) -> set:
    """The model families that have read the line: the second reader's, where it read something, and each third
    reader's that did (camkit.reading.family_voted's rule)."""
    models = line.get("models") or {}
    read = [models.get(k) for k in ("vllm", "omlx") if str(line.get(k) or "").strip()]
    read += [v.get("model") for v in line.get("voters") or [] if isinstance(v, dict) and str(v.get("selected") or "").strip()]
    return {model_id(m) for m in read}


def _shares_url(asking: list) -> bool:
    """Whether any two configured third readers share an endpoint URL (requiring model-major execution)."""
    urls = [vlm._reader_url(cfg) for cfg, _ in asking if vlm._reader_url(cfg)]
    return len(urls) > len(set(urls))


def vote(line: dict, asking: list, image, finalize: bool = True) -> tuple:
    """Today's third readers asked in turn about a line (asking: [(config, reader)]), each only while no reading stands
    by family and only where its family has read nothing on the line (families: the second reader's included), for by
    camkit.reading.standing's rule such a reader could make no reading stand. The first that answers goes under "omlx"
    on a line that has none (a new one), the others under "voters". A reader that does not answer is kept out of
    "models" and "voters", so that a rerun asks it again; one that is down is not asked. The line's "winner" taken
    afresh (settle). image: a function giving the frame's bytes, called only when a reader is asked (a frame not there
    raises FileNotFoundError, for the caller to keep the line as it was or leave it out). (how many were due, a reader
    down counted with them; how many answered)."""
    picture, due, answered = None, 0, 0
    for cfg, reader in asking:
        if settled(line) is not None or model_id(cfg.get("model") or cfg.get("name")) in families(line):
            continue
        due += 1
        if down(cfg):                             # due, and down: as a reader that did not answer
            continue
        if picture is None:
            picture = image()
        said, model, ok = asked_of(reader, cfg, picture)
        if not ok:
            continue
        answered += 1
        if "omlx" not in line:
            line["omlx"] = said
            line["models"]["omlx"] = model
        else:
            line.setdefault("voters", []).append({"reader": str(cfg["name"]), "model": model, "selected": said})
        if not finalize:
            settle(line)
    if finalize:
        line.setdefault("omlx", "")
        settle(line)
    return due, answered


def _ask_all(states: list, asking: list, read_image, on_missing=None) -> None:
    """Ask `asking` about each line state: model-major when readers share a URL (one swap per model), else
    frame-major."""
    model_major = len(asking) > 1 and _shares_url(asking)
    batches = [[pair] for pair in asking] if model_major else [asking]
    for batch in batches:
        for st in states:
            if st.get("skip") or st["missing"]:
                continue
            try:
                d, a = vote(st["line"], batch, lambda st=st: read_image(st), finalize=not model_major)
            except FileNotFoundError:
                st["missing"] = True
                if on_missing is not None:
                    on_missing(st)
                continue
            st["due"] += d
            st["answered"] += a
    if model_major:
        for st in states:
            if not st.get("skip") and not st["missing"]:
                st["line"].setdefault("omlx", "")
                settle(st["line"])


def settle(line: dict) -> dict:
    """The line's "winner" (pass1_map.majority) and its "third_only" mark taken afresh from what it holds; a line third
    readers alone carry keeps every reading, marked, and no winner (pass1_map.settled)."""
    text, _ = majority(voices(line))
    line["winner"] = None if third_only(text, line) else text
    if third_only(text, line):
        line["third_only"] = True
    else:
        line.pop("third_only", None)
    return line


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if {"-h", "--help"} & set(argv):     # before anything is read, connected or asked
        print(__doc__.strip())
        sys.exit(0)
    ap = argparse.ArgumentParser(prog="kit/tiebreak.py", add_help=False)
    ap.add_argument("run")
    ap.add_argument("--revote", action="store_true")
    ap.add_argument("--was", default=None)
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        sys.exit("usage: kit/tiebreak.py RUN [--revote [--was MODEL]] (a run in the camera's runs/<model>_fw<fw>/, or a "
                 "path)")
    if a.was and not a.revote:
        sys.exit("--was goes with --revote: it names the model the third reader ran when the lines already there were "
                 "written")
    readers(stop=True)                        # none listed: its sentence, and nothing read
    run = paths.run_path(a.run)
    runs.private_if_marked(run)               # a --network or --owner run's folder: tiebreak.jsonl 0600 in it too
    vlm.local_only_runs(run)                  # a --network run's frames: local readers only (make_reader)
    recs = jsonl.read(run / "options.jsonl")
    try:
        cfgs = vlm.voters()
        second = vlm.role("second")
    except (NoReader, ValueError) as e:       # one reader listed: the third role has none; a role naming none
        sys.exit(str(e))
    asking = []
    for cfg in cfgs:
        try:
            asking.append((cfg, make_reader(cfg, timeout=240)))
        except NoReader as e:                 # not local, and the run's frames go to local readers only
            if len(cfgs) == 1:
                sys.exit(str(e))
            print(f"{e}: left out", flush=True)
    if not asking:
        sys.exit("no third reader may read this run's frames: each is left out above")
    print("third readers, asked in turn: " + ", ".join(f"{c['name']!r} ({model_id(c.get('model'))})" for c, _ in asking)
          + f"; the second reader {second['name']!r} ({model_id(second.get('model'))})", flush=True)
    if a.revote:
        revote(run, recs, asking, second, a.was)
        return
    done = {t["frame"] for t in jsonl.read(run / "tiebreak.jsonl")}
    todo = [x for x in recs if not x["agreed"] and x["kind"] in ("list", "checklist", "sidelist")
            and x["frame"] not in done and x.get("network", safety.LIFT_NETWORK) == safety.LIFT_NETWORK]
    print(len(todo), "to tie-break", flush=True)
    second_model = str(second.get("model") or second.get("name") or "")
    states = [{
        "x": x,
        "line": {"frame": x["frame"], "path": x["path"], "index": x["index"], "ocr": x["ocr"],
                 "vllm": str((x["vlm"] or {}).get("selected") or ""), "models": {"vllm": second_model}},
        "due": 0, "answered": 0, "missing": False,
    } for x in todo]
    _ask_all(states, asking, lambda st: (run / "shots" / st["x"]["frame"]).read_bytes())
    unanswered, same, missing, alone = 0, 0, [], []
    for i, st in enumerate(states, 1):
        line = st["line"]
        if st["missing"]:                         # the frame is gone: nobody can answer, a rerun asks again
            missing.append(st["x"]["frame"])
            continue
        if not st["answered"] and (st["due"] or line["winner"] is None):
            # no third reader answered, or none of another family was there to ask: not written, so a rerun asks again
            unanswered += bool(st["due"])
            same += not st["due"]
            continue
        jsonl.append(run / "tiebreak.jsonl", line)
        alone += [line] if line.get("third_only") else []
        say(i, line)
    print(f"{len(todo)} to tie-break: {len(todo) - unanswered - same - len(missing)} written; left for a rerun, "
          f"{unanswered} that no third reader answered, {same} with no third reader of another family than the readers "
          f"who read it (camkit.vlm.one_family) and {len(missing)} whose frame is not under shots/", flush=True)
    said_missing(run, missing)
    said_alone(run, alone)


def said_missing(run: Path, missing: list) -> None:
    for frame in missing:
        print(f"  frame not under shots/: {run.name} {frame}", flush=True)


def said_alone(run: Path, alone: list) -> None:
    """The lines third readers alone carry ("third_only"), by run, frame and index, for a look by eye."""
    if alone:
        print(f"{len(alone)} lines third readers alone named, a reading neither OCR nor the second reader gave (marked "
              "\"third_only\", no winner, on the map's review list): look at each frame by eye", flush=True)
    for line in alone:
        print(f"  third readers alone: {run.name} {line['frame']} index {json.dumps(line.get('index'))}", flush=True)


def say(i, line: dict) -> None:
    more = "".join(f" {v['reader']}={v['selected'][:24]!r}" for v in line.get("voters") or [])
    print(i, line["frame"], repr(line["ocr"][:24]), repr(line["vllm"][:24]), repr(line.get("omlx", "")[:24]) + more,
          "->", repr(line["winner"]), flush=True)


def revote(run: Path, recs: list, asking: list, second: dict, was: str | None) -> None:
    """--revote: today's third readers asked about the lines already in tiebreak.jsonl (vote), each line's readings
    kept, the file written afresh, the old one kept beside it (BEFORE). A line of an identity or connection row a
    network decision opened is never asked about: its winner is taken by family from what it holds. A line whose frame
    is not under shots/ is kept as it was, said."""
    f = run / "tiebreak.jsonl"
    if not f.exists():
        sys.exit(f"{run.name}: no tiebreak.jsonl, so nothing to vote on again (kit/tiebreak.py {run.name} writes one)")
    lines = jsonl.read(f)
    unmarked = [t for t in lines if not isinstance(t.get("models"), dict)]
    if unmarked and not was:
        sys.exit(f"{len(unmarked)} lines of {f.name} name no models (written before lines did): give --was MODEL, the "
                 "model the third reader ran when they were written, so that their \"omlx\" counts as that model's; "
                 "nothing asked, nothing written")
    network = {x["frame"]: x.get("network", safety.LIFT_NETWORK) for x in recs}
    second_model = str(second.get("model") or second.get("name") or "")
    states = []
    for t in lines:
        line, named = dict(t), isinstance(t.get("models"), dict)
        if not named:
            line["models"] = {"vllm": second_model, "omlx": was}
        asked = network.get(line["frame"], safety.LIFT_NETWORK) == safety.LIFT_NETWORK
        if not asked:                             # never asked about: its winner by family, from what it holds
            settle(line)
        states.append({"orig": t, "line": line, "named": named, "asked": asked, "skip": not asked,
                       "due": 0, "answered": 0, "missing": False})

    def _on_missing(st):
        st["due"], st["answered"] = 1, 0

    _ask_all(states, asking, lambda st: (run / "shots" / st["line"]["frame"]).read_bytes(), on_missing=_on_missing)
    changed, asked_lines, unanswered, same, missing, out = 0, 0, 0, 0, [], []
    for i, st in enumerate(states, 1):
        t, line, named, asked = st["orig"], st["line"], st["named"], st["asked"]
        if st["missing"]:                         # the frame is gone: as a line nobody answered, said below
            missing.append(t["frame"])
        due, answered = st["due"], st["answered"]
        if asked and not answered and (due or not named):
            # no third reader of today answered, or none of another family was there to ask a line that named no models:
            # the line as it was, its old winner with it, for a later --revote to ask
            line = t
            unanswered += bool(due)
            same += not due
        asked_lines += bool(answered)
        changed += line.get("winner") != t.get("winner")
        out.append(line)
        say(i, line)
    if not (run / BEFORE).exists():
        shutil.copy2(f, run / BEFORE)
    part = f.with_name(f.name + ".part")
    part.write_text("", encoding="utf-8")
    for line in out:
        jsonl.append(part, line)
    part.replace(f)
    print(f"{len(lines)} lines: {asked_lines} answered by a third reader of today; kept as they were for a later "
          f"--revote, {unanswered} that none answered ({len(missing)} of them with no frame under shots/) and {same} with "
          f"no third reader of another family to ask; "
          f"{changed} with another winner than before; {paths.shown(f)} written afresh (the old one kept as {BEFORE}); "
          "kit/pass1_map.py makes the map again", flush=True)
    said_missing(run, missing)
    said_alone(run, [line for line in out if line.get("third_only")])


if __name__ == "__main__":
    main()
