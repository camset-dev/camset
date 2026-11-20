"""The third role's readers (camkit.vlm.voters: the third reader, or several asked in turn) for the options pass 1's OCR
and second reader read differently; kit/pass1_map.py then takes the majority, one vote per model family.

    .venv/bin/python -u kit/tiebreak.py kit2_crawl_movie          # a run in the camera's runs/<model>_fw<fw>/
    .venv/bin/python -u kit/tiebreak.py kit2_pass1 --revote --was Qwen3.8-27B-4bit     # the lines already there

Reads <run>/options.jsonl (kit/pass1_labels.py) and appends to <run>/tiebreak.jsonl, one line per
option of a list, checklist or side list the two readers disagreed on; options already there are
skipped, so it resumes. Carousels, grids and number fields are left to pass1_map's own rules.

A line holds "frame", "path", "index", "ocr" (OCR's reading), "vllm" (the second reader's, from options.jsonl) and
"omlx" (the first third reader's), whatever readers play the roles (the names of the servers that first did); "voters",
each further third reader asked, in turn ({"reader": its name, "model", "selected": its reading}); "models", the model
that read "vllm" (the second reader's, as configured) and "omlx" ({"vllm": ..., "omlx": ...}); and "winner", what the
majority names (pass1_map.majority) or null. The third readers are asked in the order private/config.json gives them,
each only while no reading stands: OCR, the second reader and the third readers asked so far, one vote per model family
(camkit.reading.model_id), so a third reader of the second's family adds no vote.

A third reader that fails is no vote, kept out of the line's "models" and "voters"; after FAIL_RUN failures in a row it
is asked nothing more in the run, said once.

--revote asks today's third readers about the lines already there, where no reading stands by family, and writes
tiebreak.jsonl afresh with what each line held kept: a third reader whose family has read the line already is not asked
again, and a line none of them answered is kept as it was, for a later --revote to ask again. A line written before lines named their models (no "models") takes them from --was MODEL, the model the third
reader ran when it was written (its "omlx" kept as that model's), and the second reader's model as configured today;
--revote refuses to go on without --was while such a line is there. The old file is kept beside it as
tiebreak.jsonl.before_revote (once; a later --revote leaves it as it is).

A run folder a --network run marked (camkit.vlm.LOCAL_MARKER) is read with local third readers only
(camkit.vlm.local_only_runs: a third reader that is not local is left out, said, and the tool stops when none is left),
and an option of an identity or connection row a network decision opened ("network" on its line, other than a Wi-Fi or
Bluetooth setting's) is never asked about (docs/decisions/0008).
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import jsonl, paths, runs, safety, vlm  # noqa: E402
from camkit.reading import model_id  # noqa: E402
from camkit.vlm import PROMPTS, NoReader, make_reader, readers  # noqa: E402
from pass1_map import majority, voices  # noqa: E402

BEFORE = "tiebreak.jsonl.before_revote"        # the file --revote wrote afresh, as it was
FAIL_RUN = 3                                   # failures in a row after which a third reader is asked nothing more
_FAILS: dict = {}                              # reader name -> its failures in a row in this run


def asked_of(reader, cfg: dict, image: bytes) -> tuple:
    """(the reading of the option under the cursor, the model that answered: the configured one, or the one the server
    says answered where that is another family, camkit.vlm.answered_model; whether it answered). A failure (an error,
    an answer that is no JSON object) is no reading, and after FAIL_RUN in a row the reader is asked nothing more in
    this run (down), said once."""
    name = str(cfg.get("name"))
    reader.served = None                          # a cached answer names no server's model: the configured one's
    try:
        a = reader.ask(image, PROMPTS["option"])
    except Exception as e:
        a = {"_error": vlm.scrub(str(e))[:80]}
    ok = vlm.usable(a)
    _FAILS[name] = 0 if ok else _FAILS.get(name, 0) + 1
    if _FAILS[name] == FAIL_RUN:
        print(f"reader {name!r} failed {FAIL_RUN} times in a row ({a.get('_error') if isinstance(a, dict) else a}): "
              "it is asked nothing more in this run", flush=True)
    said = str(a.get("selected") or "") if ok else ""
    return said, vlm.answered_model(str(cfg.get("model") or ""), getattr(reader, "served", None)), ok


def down(cfg: dict) -> bool:
    """A third reader that failed FAIL_RUN times in a row in this run: asked nothing more."""
    return _FAILS.get(str(cfg.get("name")), 0) >= FAIL_RUN


def families(line: dict) -> set:
    """The model families that have read a line already: the second reader's and each third reader's that answered."""
    models = line.get("models") or {}
    return {model_id(models.get("vllm")), model_id(models.get("omlx"))} | {
        model_id(v.get("model")) for v in line.get("voters") or [] if isinstance(v, dict)}


def vote(line: dict, asking: list, image) -> tuple:
    """Today's third readers asked in turn about a line (asking: [(config, reader)]): on a line with no "omlx" (a new
    one) the first is asked whatever its family and goes under "omlx"; every other only while no reading stands by
    family and only where its family has not read the line (families), under "voters". A reader that does not answer
    is kept out of "models" and "voters", so that a later --revote asks it again; one that is down is not asked. The
    line's "winner" taken afresh. image: a function giving the frame's bytes, called only when a reader is asked.
    (how many were due, a reader down counted with them; how many answered)."""
    picture, asked, answered = None, 0, 0
    for cfg, reader in asking:
        if "omlx" in line and (majority(voices(line))[0] is not None or model_id(cfg.get("model")) in families(line)):
            continue
        if down(cfg):                             # due, and down: as a reader that did not answer
            line.setdefault("omlx", "")
            asked += 1
            continue
        if picture is None:
            picture = image()
        said, model, ok = asked_of(reader, cfg, picture)
        asked, answered = asked + 1, answered + ok
        if "omlx" not in line:
            line["omlx"] = said
            if ok:
                line["models"]["omlx"] = model
        elif ok:
            line.setdefault("voters", []).append({"reader": str(cfg["name"]), "model": model, "selected": said})
    line["winner"] = majority(voices(line))[0]
    return asked, answered


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
    for i, x in enumerate(todo, 1):
        line = {"frame": x["frame"], "path": x["path"], "index": x["index"], "ocr": x["ocr"],
                "vllm": str((x["vlm"] or {}).get("selected") or ""), "models": {"vllm": str(second.get("model") or "")}}
        vote(line, asking, lambda x=x: (run / "shots" / x["frame"]).read_bytes())
        jsonl.append(run / "tiebreak.jsonl", line)
        say(i, line)


def say(i, line: dict) -> None:
    more = "".join(f" {v['reader']}={v['selected'][:24]!r}" for v in line.get("voters") or [])
    print(i, line["frame"], repr(line["ocr"][:24]), repr(line["vllm"][:24]), repr(line.get("omlx", "")[:24]) + more,
          "->", repr(line["winner"]), flush=True)


def revote(run: Path, recs: list, asking: list, second: dict, was: str | None) -> None:
    """--revote: today's third readers asked about the lines already in tiebreak.jsonl (vote), each line's readings
    kept, the file written afresh, the old one kept beside it (BEFORE). A line of an identity or connection row a
    network decision opened is never asked about: its winner is taken by family from what it holds."""
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
    changed, asked_lines, unanswered, out = 0, 0, 0, []
    for i, t in enumerate(lines, 1):
        line, named = dict(t), isinstance(t.get("models"), dict)
        if not named:
            line["models"] = {"vllm": str(second.get("model") or ""), "omlx": was}
        asked = answered = 0
        if network.get(line["frame"], safety.LIFT_NETWORK) == safety.LIFT_NETWORK:
            asked, answered = vote(line, asking, lambda line=line: (run / "shots" / line["frame"]).read_bytes())
        else:                                     # never asked about: its winner by family, from what it holds
            line["winner"] = majority(voices(line))[0]
        if asked and not answered:                # no third reader answered: the line as it was, to ask again later
            line, unanswered = t, unanswered + 1
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
    print(f"{len(lines)} lines: {asked_lines} answered by a third reader of today, {unanswered} that none answered "
          f"kept as they were (a later --revote asks them again), {changed} with another winner than before; "
          f"{paths.shown(f)} written afresh (the old one kept as {BEFORE}); kit/pass1_map.py makes the map again",
          flush=True)


if __name__ == "__main__":
    main()
