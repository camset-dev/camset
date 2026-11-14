"""A second reader for the camera's help text (2026-11-01): the guide frames, read again by a vision model.

    .venv/bin/python -u kit/help_reads.py

kit/help_run.py and prove_run --help-text read each guide with OCR alone, which slips now and then
("focus area trame", an icon inside the text read as "MB"). Every guide frame they saved is asked of the
first vision reader (private/config.json "readers"). Where its words and the OCR's agree, the text stands;
where they differ, the second vision reader decides by agreeing with one of them; with no two in
agreement the first vision reader's text is used and the frame is listed for review.

Results: runs/<model>_fw<fw>/kit2_help/help_reads.jsonl (the camera's runs, camkit.paths), one line per guide (its
first frame), which schema_update uses for the text. Answers are cached (runs/<model>_fw<fw>/_cache/vlm), so a rerun
after more walking asks only the new frames. A help run folder a --network run marked (camkit.vlm.LOCAL_MARKER) is
read by local readers only (camkit.vlm.local_only_runs).
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import jsonl, paths, vlm  # noqa: E402
from camkit.vlm import make_reader, readers  # noqa: E402

RUN = paths.module_root() / "kit2_help"
PROMPT = ('This is a Sony camera help screen: an orange title at the top, white help text below, and an OK '
          'button. Reply with JSON only: {"title": the orange title exactly, "text": the white help text exactly '
          'as written, lines joined with single spaces, quotation marks kept}')
# the Shoot Mode carousel (kit2_help/carousel_help.jsonl, 2026-11-02): each mode's description on its own screen
CAROUSEL_PROMPT = ('This is a Sony camera Shoot Mode screen: "Shoot Mode" at the top, an orange mode name, a white '
                   'description below it, and a strip of mode letters. Reply with JSON only: {"title": the orange '
                   'mode name exactly, "text": the white description exactly as written, lines joined with single '
                   'spaces; an icon inside the text written as the words it shows, "S&Q" for the S&Q icon}')


def words(t: str) -> str:
    """What two readings must share: the letters and digits, in order."""
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def tidy(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def ask(reader, frames: list, prompt=PROMPT) -> str:
    """One reader's text for a guide (a long guide pages over several frames)."""
    parts = []
    for fr in frames:
        a = reader.ask((RUN / "shots" / fr).read_bytes(), prompt)
        parts.append(tidy(a.get("text") if isinstance(a.get("text"), str) else ""))
    return " ".join(p for p in parts if p)


def decide(ocr: str, first: str, second) -> tuple[str, str]:
    """(text, how): the OCR when the first vision reader agrees with it, else the reading two readers share,
    else the first vision reader's ("review")."""
    if words(ocr) == words(first):
        return first or ocr, "agreed"                 # same words: the model's spacing and quotes
    if re.sub(r"[^a-z]", "", ocr.lower()) == re.sub(r"[^a-z]", "", (first or "").lower()):
        # the same words with other digits: OCR reads them one by one, the models drop one (120p's
        # "119.88fps" read 119.8 by both vision readers, 2026-11-02)
        return ocr, "OCR (digits)"
    s = second()
    if s is not None and words(s) == words(first):
        return first, "two vision readers"
    if s is not None and words(s) == words(ocr):
        return ocr, "OCR and the second reader"
    return first or ocr, "review"


def built_readers() -> list:
    """The readers listed (none listed: its sentence, and nothing asked), each built; while camkit.vlm.LOCAL_ONLY is
    set (the help run's folder a --network run marked: local_only_runs), the ones that are not local are left out
    (make_reader builds none), and with none left the tool stops before it asks anything."""
    listed = readers(stop=True)
    if vlm.LOCAL_ONLY:
        listed = [r for r in listed if vlm.local_reader(r)]
        if not listed:
            sys.exit("the help run's frames are a --network run's (docs/decisions/0008), and no local reader is listed: "
                     "nothing asked")
    return [make_reader(r) for r in listed]


def main():
    vlm.local_only_runs(RUN)                 # a --network run's frames: local readers only (make_reader)
    asked = built_readers()
    done = {}
    out_path = RUN / "help_reads.jsonl"
    for r in jsonl.read(out_path):
        done[r["frame"]] = r
    todo = []
    for name in ("help.jsonl", "option_help.jsonl", "field_help.jsonl", "carousel_help.jsonl", "drive_help.jsonl"):
        for r in jsonl.read(RUN / name):
            if r.get("text") and r.get("frames") and r["frames"][0] not in done:
                todo.append({**r, "prompt": CAROUSEL_PROMPT if name == "carousel_help.jsonl" else PROMPT})
    print(f"{len(todo)} guides to read ({len(done)} read before)", flush=True)

    def one(r):
        first = ask(asked[0], r["frames"], r["prompt"])

        def second():
            try:
                return ask(asked[1], r["frames"], r["prompt"]) if len(asked) > 1 else None
            except Exception as e:                    # the local server may be off
                print(f"   second reader: {type(e).__name__}: {str(e)[:60]}", flush=True)
                return None
        text, how = decide(r["text"], first, second)
        return {"frame": r["frames"][0], "frames": r["frames"], "ocr": r["text"], "vlm": first,
                "text": text, "how": how}

    counts = {}
    with open(out_path, "a", encoding="utf-8", newline="\n") as out, ThreadPoolExecutor(8) as ex:
        for res in ex.map(one, todo):
            out.write(json.dumps(res) + "\n")
            out.flush()
            counts[res["how"]] = counts.get(res["how"], 0) + 1
            if res["how"] != "agreed":
                print(f"{res['how']:26s} {res['frame']}\n   OCR {res['ocr'][:110]!r}\n   VLM {res['vlm'][:110]!r}",
                      flush=True)
    print(counts, flush=True)


if __name__ == "__main__":
    main()
