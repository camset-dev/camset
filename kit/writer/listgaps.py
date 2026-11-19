"""A public list one value short (docs/decisions/0016, 0025): a setting whose public proof lists every value of its list
but one tells that one value apart, and where it is the value the mapper's camera held when the proofs began (a start
file's), the definition would publish the owner's setting. Both writer passes check every write for such a list,
after the names and the marks are set (questions), and the gate counts each as an open question
(writer/gate.py): one whose missing value no start file holds, or where no start file is here to tell, a person may
accept by its key in the camera's accepted file; one whose missing value a start file holds is never accepted, and
--write refuses while it stands (OneShort). What the camera's own list never offers is no gap: a value a not_offered
mark names (held or not) and a setting an unproved_reason covers say publicly, and the same for every owner, why the
list stops short. Keys and counts only in what is printed, never the value."""
import collections
from pathlib import Path

from camkit import camset, definitions, provenance

from .copies import value_of

# the gate's kind of open question for a list one value short (the accepted file's word, schemas/accepted.schema.json)
KIND = "one value short"
# what each kind of gap is, by whether a start file holds the missing value
WHY = {"a": "a start file of this camera holds the value it lacks",
       "b": "no start file of this camera holds the value it lacks",
       "c": "no start file of this camera is here to tell whether it held the value it lacks"}
WAYS_OUT = ("prove the value from another start (choose it in a session that starts on another value); a held "
            "not-offered mark (the hand tables' NOT_OFFERED with held) where the camera holds the value from the "
            "factory and no list of the menus chooses it back; or keep the setting out by a reason (UNPROVED)")


class OneShort(SystemExit):
    """--write refused, in plain words: a public list would stop one value short of a value a start file of this
    camera held (decision 16). Exit status 1."""


def one_short(doc: dict) -> list:
    """[(setting, the value its public list lacks)] for each setting whose public proof (camkit.definitions.lean_proof,
    after the names and the marks) lists every value of its list but one: the values a not_offered mark names (held or
    not) aside, nothing for a setting an unproved_reason covers, a proof that lists no values or a scale proved on a
    line (every value)."""
    out = []
    for s in doc.get("settings") or []:
        p = s.get("proved")
        if not isinstance(p, dict) or s.get("unproved_reason") or (p.get("sampled") or {}).get("linear") is True:
            continue
        lean = definitions.lean_proof(p)
        if "values" not in lean:
            continue
        marked = {m.get("value") for m in s.get("not_offered") or [] if isinstance(m, dict)}
        listed = {v for v, _ in s.get("values") or [] if not isinstance(v, (list, dict))}
        missing = listed - set(lean["values"]) - marked
        if len(missing) == 1:
            out.append((s, next(iter(missing))))
    return out


def start_files(run_root: Path) -> list:
    """The camera's session start files (*_before.DAT) its downloads manifest lists (camkit.provenance) that are
    still there, each once, in the manifest's order; none without the runs."""
    out = []
    for e in provenance.entries(run_root) if run_root is not None else []:
        p = Path(run_root) / e.get("path", "")
        if p.name.endswith("_before.DAT") and p.exists() and p not in out:
            out.append(p)
    return out


def held(files: list, settings: list) -> dict:
    """{setting key: {value: how many of `files` hold it}} for `settings`, in every section a setting lives in (the
    live settings for a global one, every memory set for one the sets keep): what the camera held at each start."""
    out = collections.defaultdict(collections.Counter)
    for f in files:
        try:
            cs = camset.read(f)
        except (OSError, ValueError):
            continue
        for s in settings:
            sections = [0] if s.get("area") == "global" else []
            if s.get("area") == "set" or s.get("in_sets"):
                sections += list(range(1, len(cs.sections)))
            seen = {value_of(cs, s["key"], si) for si in sections}
            for v in seen:
                if isinstance(v, int) and not isinstance(v, bool):
                    out[s["key"]][v] += 1
    return out


def questions(doc: dict, run_root: Path | None) -> list:
    """The gate's open questions for the lists one value short (one_short), one each: {"kind": KIND, "key", "row" (the
    setting's name), "start": "a" (a start file of this camera holds the missing value), "b" (none does) or "c" (no
    start file here, start_files), "files" (how many hold it)}; never the value."""
    short = one_short(doc)
    if not short:
        return []
    files = start_files(run_root)
    counts = held(files, [s for s, _ in short]) if files else {}
    out = []
    for s, v in short:
        n = counts.get(s["key"], {}).get(v, 0)
        out.append({"kind": KIND, "key": s["key"], "row": s.get("name", ""),
                    "start": "c" if not files else "a" if n else "b", "files": n})
    return out


def line(q: dict) -> str:
    """A gap's words for the gate's list: its kind (WHY) and, for kind (a), how many start files."""
    n = q.get("files") or 0
    return WHY[q["start"]] + (f" ({n} start file{'s' if n != 1 else ''})" if q["start"] == "a" else "")


def refusal(held_ones: list) -> str:
    """--write's refusal for the gaps whose missing value a start file holds, naming each setting and the ways out."""
    keys = "\n".join(f"  {q['key']:22s} {q.get('row', '')[:56]}  ({line(q)})" for q in held_ones)
    return (f"schema_update: refused to write: {len(held_ones)} public list{'s' if len(held_ones) != 1 else ''} would "
            "stop one value short of a value a start file of this camera held, which tells that value "
            f"(docs/decisions/0016, 0025):\n{keys}\nClear each one: {WAYS_OUT}. --force does not write past this, nor "
            "does a ruling in the accepted file.")
