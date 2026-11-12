"""--write's gate: the questions pass 2's report holds that the writer does not settle (a conflict it leaves standing,
a new record it does not add, a record not one to one, a name dispute, a carried-over value outside a hand rule), each
to be accepted by name in the mapper's accepted file before the definition is written: private/evidence/<model>_fw<fw>/
accepted_<model>_fw<fw>.json (camkit.datafiles.accepted_file), private whole, for each entry is a ruling on one
mapping's report (docs/decisions/0016); the pull request carries the gate's count instead."""
import collections
import sys
from pathlib import Path

from camkit import datafiles, paths
from runner import read_json

from .proofs import mixed

# what a report holds that the writer does not settle, which a person must accept by name before --write writes
# (accepted_file): the kinds, as the accepted file names them
QUESTION_KINDS = ("conflict", "new", "not one to one", "name dispute", "carried over")


def accepted_file(camera: str) -> Path:
    """private/evidence/<model>_fw<fw>/accepted_<model>_fw<fw>.json: what a person looked at in the report and
    accepted (camkit.datafiles.accepted_file)."""
    return datafiles.accepted_file(camera)


def read_accepted(camera: str) -> list:
    """The accepted file's entries, none without one."""
    p = accepted_file(camera)
    return read_json(p).get("accepted") or [] if p.exists() else []


def questions(report: list, unresolved: list = (), added: frozenset = frozenset()) -> list:
    """What the report holds that the writer leaves open, one dict each ({kind, key, row, value, label, camera} as
    they apply): the conflicts the writer did not settle (`unresolved`: a label it kept against the camera's reading,
    by a hand rule or because the reading was not sure), the new records it did not add (`added`: the definition's keys
    after the pass; a record proved but missing from them counts, whatever its verdict), the
    records not one to one, the name disputes and the carried-over values outside a hand rule. A section the report
    lacks is empty (pass2_report grows them)."""
    out, seen = [], set()

    def put(q):
        sig = (q["kind"], q["key"], q.get("value"), q.get("label"))
        if sig not in seen:
            seen.add(sig)
            out.append(q)
    for q in unresolved:
        put(dict(q, kind="conflict"))
    for e in report:
        row = e.get("row", "")
        for k, r in (e.get("records") or {}).items():
            if mixed(r):
                put({"kind": "not one to one", "key": k, "row": row})
            elif k not in added and (r.get("verdict") == "new" or added):     # proved, and the definition lacks it
                put({"kind": "new", "key": k, "row": row})
            for d in r.get("name_disputes") or []:
                put({"kind": "name dispute", "key": k, "row": row, "value": d.get("value"), "label": d.get("label"),
                     "camera": d.get("shown") or d.get("vlm")})
        for c in e.get("carried_over") or []:
            if not c.get("hand_rule"):
                put({"kind": "carried over", "key": c["key"], "row": row, "label": c.get("label"),
                     "value": c.get("value")})
    return out


def accepts(entry: dict, q: dict) -> bool:
    """An accepted entry covers a question of its kind and key, and of its value and label where it names them (an
    entry without a value covers every value of the record)."""
    return entry.get("kind") == q["kind"] and entry.get("key") == q["key"] and \
        all(f not in entry or entry[f] == q.get(f) for f in ("value", "label"))


def gate(open_ones: list, camera: str, force: bool, write: bool = True) -> bool:
    """--write's gate: True when every open question is accepted in the camera's accepted file; otherwise each one is
    printed, and the writer stops (exit 1) unless forced, with a loud warning. An entry that answers no question is
    listed to be taken out. A carried-over value is listed without
    its value: the value a record kept may be the camera's own setting (decision 16), so an entry names key and label."""
    accepted = read_accepted(camera)
    left = [q for q in open_ones if not any(accepts(a, q) for a in accepted)]
    # every entry answers a question of the report; one that no longer does is taken out, so it hides no later
    # question on the same record (docs/DATA_CONTRACTS.md): said, not refused
    stale = [a for a in accepted if not any(accepts(a, q) for q in open_ones)]
    if stale:
        print(f"gate: {len(stale)} entries of {paths.shown(accepted_file(camera))} answer no question of this report; "
              "take them out:")
        for a in stale:
            print(f"  {a.get('kind', ''):15s} {a.get('key', ''):22s} "
                  + " ".join(f"{f} {a[f]!r}" for f in ("value", "label") if f in a))
    if not left:
        print(f"gate: {len(open_ones)} open questions in the report, every one accepted in "
              f"{paths.shown(accepted_file(camera))}")
        return True
    counts = collections.Counter(q["kind"] for q in left)
    print(f"\ngate: {len(left)} open questions the report holds and {paths.shown(accepted_file(camera))} does not "
          f"accept ({', '.join(f'{n} {k}' for k, n in sorted(counts.items()))}):")
    for q in left:
        what = " ".join(f"{f} {q[f]!r}" for f in ("value", "label", "camera") if q.get(f) is not None
                        and not (q["kind"] == "carried over" and f == "value"))
        print(f"  {q['kind']:15s} {q['key']:22s} {q.get('row', '')[:56]:56s} {what}")
    print("Look at each in the report (report.md, the proof viewer); settle it with a proof, or add an entry "
          "{kind, key, value, label, why, date} to the accepted file (docs/DATA_CONTRACTS.md).")
    if not write:
        print("(--write refuses until each is settled or accepted)")
        return False
    if not force:
        sys.exit("schema_update: refused to write, open questions above (--force writes anyway)")
    print("\n" + "!" * 78 + f"\n!! --force: writing with {len(left)} open questions NOT accepted; the definition holds "
          "them as the writer\n!! left them. Never for a submission.\n" + "!" * 78)
    return False
