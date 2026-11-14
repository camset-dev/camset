"""A third reader (omlx) for the options pass 1's OCR and vLLM read differently; kit/pass1_map.py then
takes the majority of three.

    .venv/bin/python -u kit/tiebreak.py kit2_crawl_movie          # a run in the camera's runs/<model>_fw<fw>/

Reads <run>/options.jsonl (kit/pass1_labels.py) and appends to <run>/tiebreak.jsonl, one line per
option of a list, checklist or side list the two readers disagreed on; options already there are
skipped, so it resumes. Carousels, grids and number fields are left to pass1_map's own rules.

A run folder a --network run marked (camkit.vlm.LOCAL_MARKER) is read with a local third reader only
(camkit.vlm.local_only_runs: the tool stops when the third is not local), and an option of an identity or connection
row a network decision opened ("network" on its line, other than a Wi-Fi or Bluetooth setting's) is never asked about
(docs/decisions/0008).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import jsonl, paths, runs, safety, vlm  # noqa: E402
from camkit.vlm import PROMPTS, NoReader, make_reader, readers, role  # noqa: E402
from page_model import same_text  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: kit/tiebreak.py RUN (a run in the camera's runs/<model>_fw<fw>/, or a path)")
    readers(stop=True)                        # none listed: its sentence, and nothing read
    run = paths.run_path(sys.argv[1])
    runs.private_if_marked(run)               # a --network or --owner run's folder: tiebreak.jsonl 0600 in it too
    vlm.local_only_runs(run)                  # a --network run's frames: local readers only (make_reader)
    recs = jsonl.read(run / "options.jsonl")
    try:
        r = make_reader(role("third"), timeout=240)
    except NoReader as e:                     # one reader listed: the third role has none; or it is not local
        sys.exit(str(e))
    done = {t["frame"] for t in jsonl.read(run / "tiebreak.jsonl")}
    todo = [x for x in recs if not x["agreed"] and x["kind"] in ("list", "checklist", "sidelist")
            and x["frame"] not in done and x.get("network", safety.LIFT_NETWORK) == safety.LIFT_NETWORK]
    print(len(todo), "to tie-break", flush=True)
    for i, x in enumerate(todo, 1):
        try:
            a = r.ask((run / "shots" / x["frame"]).read_bytes(), PROMPTS["option"])
        except Exception as e:
            a = {"_error": str(e)[:80]}
        o, v, m = x["ocr"], str((x["vlm"] or {}).get("selected") or ""), str(a.get("selected") or "")
        winner = o if m and same_text(m, o) else v if m and same_text(m, v) else None
        jsonl.append(run / "tiebreak.jsonl", {"frame": x["frame"], "path": x["path"], "index": x["index"],
                                              "ocr": o, "vllm": v, "omlx": m, "winner": winner})
        print(i, x["frame"], repr(o[:24]), repr(v[:24]), repr(m[:24]), "->", repr(winner), flush=True)


if __name__ == "__main__":
    main()
