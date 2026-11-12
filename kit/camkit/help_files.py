"""Help text files: each setting's help, kept apart from the definitions (editor/definitions/<model>_fw<fw>.json) by
who wrote it (docs/decisions/0018).

    data/<model>_fw<firmware>/help_<model>_fw<firmware>.json   the project's own words; published, and merged into the
                                                               definition by kit/schema_update.py
    private/help/help_<model>_fw<firmware>.json                the camera's In-Camera Guide text (Sony's); never published

Both have one shape (schemas/help-file.schema.json): {"model", "firmware", "source", "settings": {key: {"help",
"option_help"}}}. The editor and the proof viewer show the private file's text in place of the definition's when
they find it.

A help file is used only for the camera it says it is for: its own "model" and "firmware" must be the definition's
(read() checks; the editor's Schema::apply_help too). Its name does not count: setting keys can be the same on two
Sony bodies, so a file copied or renamed for another camera, or for another firmware of the same model, would put
that camera's text on the wrong settings. Such a file, or one that names neither, is refused: its text is not used,
and a line says why. help_<model>_fw<firmware>.json is only where each is looked for.
"""
import json
from pathlib import Path

from . import ROOT, paths

OWN = ROOT / "data"
PRIVATE = ROOT / "private" / "help"
OWN_SOURCE = ("Camset's own words, written from the definition (each setting's name, options and notes) and general "
              "photographic knowledge, never from the camera's guide; published with the definitions")
SONY_SOURCE = "The camera's In-Camera Guide, read off its screen by kit/help_run.py and prove_run --help-text (Sony's text: private use only)"


def name(doc) -> str:
    return f"help_{doc['model']}_fw{doc['layouts'][0]['firmware']}.json"


def own_path(doc) -> Path:
    """The project's own help file: in the camera's folder under data/ (data/<model>_fw<firmware>/)."""
    return OWN / name(doc).removeprefix("help_").removesuffix(".json") / name(doc)


def refused(path: Path, doc) -> str | None:
    """Why the help file at path is not for doc's camera, in plain words; None when its own model and firmware are
    doc's (or there is no file)."""
    if not path.exists():
        return None
    try:
        h = json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError:
        return "it does not read as a help file"
    if not isinstance(h, dict) or not isinstance(h.get("settings"), dict):
        return "it does not read as a help file"
    model, firmware = doc["model"], doc["layouts"][0]["firmware"]
    if not h.get("model") or not h.get("firmware"):
        return "it does not say which camera it is for (its model and firmware)"
    if (h["model"], h["firmware"]) != (model, firmware):
        return f"it is for the {h['model']} firmware {h['firmware']}, not the {model} firmware {firmware}"
    return None


_told = set()          # the refusals already said, so a file read twice in one command is said once


def read(path: Path, doc) -> dict:
    """{key: {"help": str, "option_help": [[value, str], ...]}}; empty when there is no file, and when the file is not
    for doc's camera (refused(): its own model and firmware decide, not its name), which is printed once, with why."""
    why = refused(path, doc)
    if why:
        if (path, why) not in _told:
            _told.add((path, why))
            print(f"help: {paths.shown(path)} is not used: {why}")
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))["settings"] if path.exists() else {}


def write(path: Path, doc, table: dict, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rel = Path("../" * (len(path.relative_to(ROOT).parts) - 1)) / "schemas" / "help-file.schema.json"
    out = {"$schema": rel.as_posix(), "model": doc["model"], "firmware": doc["layouts"][0]["firmware"],
           "source": source, "settings": dict(sorted(table.items()))}
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def taken(doc) -> dict:
    """The help the schema's settings carry, by key, taken out of them."""
    out = {}
    for s in doc["settings"]:
        t = {f: s.pop(f) for f in ("help", "option_help") if s.get(f)}
        s.pop("help", None), s.pop("option_help", None)
        if t:
            out[s["key"]] = t
    return out


def put(doc, table: dict) -> int:
    """Give the schema's settings the table's help; returns how many got some."""
    n = 0
    for s in doc["settings"]:
        t = table.get(s["key"]) or {}
        for f in ("help", "option_help"):
            if t.get(f):
                s[f] = t[f]
        n += bool(t)
    return n
