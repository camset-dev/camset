"""A setting's note: what it says (for everyone) kept apart from its evidence (the runs and days that prove it, shown in
Expert mode only), a note compared with its evidence apart so a rerun does not write it again, a line added once, and
a part of evidence alone added once (add_evidence: the owner's allowance a proof carries)."""
import re

# what proves a note: a run's folder (runs/kit2_quality) or the day it was seen (2026-11-03)
EVIDENCE = re.compile(r"\bruns/[\w.-]+|\b20\d\d-\d\d-\d\d\b")
# a parenthesis with nothing inside it, and the space before it
PAREN = re.compile(r"( ?)\(([^()]*)\)")
# a last clause of a sentence, after "; ", that names a run or a day: "Movie menu only; menu-verified 2026-10-23."
TAIL = re.compile(r";\s+((?:[^;().]|\.(?!\s))*?(?:\bruns/[\w.-]+|\b20\d\d-\d\d-\d\d\b)(?:[^;().]|\.(?!\s))*?)(?=\.(?:\s|$)|$)")


def split_evidence(note: str) -> tuple:
    """A note in two: what it says, for everyone, and what proves it (the runs and the days, how and when it was
    seen), for Expert mode. Each part of a parenthesis (parts are split by "; ") that names a run or a day is
    evidence, and the parenthesis goes when nothing else is left in it; so is a sentence's last clause after "; "
    that names one. A day in the running text ("since Camera Settings Reset was run on 2026-10-30") is what the note
    says, and stays. ("", "") for no note; (note, "") when nothing in it is evidence."""
    found = []

    def paren(m):
        parts = m.group(2).split("; ")
        kept = [p for p in parts if not EVIDENCE.search(p)]
        if len(kept) == len(parts):
            return m.group(0)
        found.extend(p for p in parts if EVIDENCE.search(p))
        return f"{m.group(1)}({'; '.join(kept)})" if kept else ""

    def tail(m):
        found.append(m.group(1))
        return ""

    plain = TAIL.sub(tail, PAREN.sub(paren, note))
    if not found:
        return note, ""
    return re.sub(r"  +", " ", plain).strip(), "; ".join(found)


def with_evidence_apart(item: dict) -> dict:
    """A setting or layout with its note's evidence (split_evidence) in "note_evidence", right after "note"; as it
    was when its note holds none (a note split before keeps its evidence)."""
    plain, evidence = split_evidence(item.get("note", ""))
    if not evidence:
        return item
    out = {}
    for k, v in item.items():
        if k == "note_evidence":
            continue
        out[k] = plain if k == "note" else v
        if k == "note":
            out["note_evidence"] = evidence
    return out


def with_tidy_note(item: dict) -> dict:
    """A setting or layout whose note (and its evidence) has no space in front or after and none doubled: 110 notes of
    the ILCE-1M2's began with a space from before the project's history was cut (a line added to an empty note), and
    the editor showed it. As it was when its note is tidy already."""
    tidy = {k: re.sub(r" {2,}", " ", item[k]).strip() for k in ("note", "note_evidence") if isinstance(item.get(k), str)}
    return {**item, **tidy} if any(item[k] != v for k, v in tidy.items()) else item


# an owner's allowance a proof carries, one part of a note's evidence (add_evidence; runner.allowed_or_exit's words)
ALLOWANCE = re.compile(r"the owner allowed .+? remotely, 20\d\d-\d\d-\d\d")


def without_allowances(evidence: str) -> str:
    """A note's evidence without the owner's allowances add_evidence put there (ALLOWANCE, one part each)."""
    return "; ".join(p for p in (evidence or "").split("; ") if not ALLOWANCE.fullmatch(p))


def note_is(item: dict, wanted: str) -> bool:
    """Whether a setting's note already says `wanted`: word for word, or as with_evidence_apart left it (what it says
    in "note", its evidence in "note_evidence"), the owner's allowances add_evidence added after it aside. A note a
    table writes whole compares this way, or every rerun would write it again (its evidence was taken out after the
    last one, or an allowance was added to it)."""
    note, evidence, split = item.get("note", ""), item.get("note_evidence", ""), split_evidence(wanted)
    return note == wanted or (note, evidence) == split or (note, without_allowances(evidence)) == split


def put_note(item: dict, wanted: str) -> None:
    """A note written whole: the evidence of the one it replaces goes with it (from_data splits the new one's out)."""
    item["note"] = wanted
    item.pop("note_evidence", None)


def fix_differs(item: dict, fix: dict) -> bool:
    """Whether a table's fix ({field: value}) changes the setting, a note compared by note_is."""
    return any(not note_is(item, v) if f == "note" else item.get(f) != v for f, v in fix.items())


def apply_fix(item: dict, fix: dict) -> None:
    item.update({f: v for f, v in fix.items() if f != "note"})
    if "note" in fix and not note_is(item, fix["note"]):
        put_note(item, fix["note"])


def add_line(item: dict, line: str) -> bool:
    """The line after the setting's note, once: not again when the note says it already, whole or with its evidence
    apart (a rerun found the line missing because its evidence had been taken out, and added it again, 2026-11-06),
    and with one space between, none in front. A note split before takes the line split too, its evidence after the
    note's own. Whether it was added."""
    note, (plain, evidence) = (item.get("note") or "").strip(), split_evidence(line)
    if line in note or (plain and plain in note):
        return False
    if item.get("note_evidence"):
        item["note"] = f"{note} {plain}".strip()
        if evidence:
            item["note_evidence"] = f"{item['note_evidence']}; {evidence}"
    else:
        item["note"] = f"{note} {line}".strip()
    return True


def add_evidence(item: dict, words: str) -> bool:
    """`words`, a part of evidence (it names a run or a day: "the owner allowed Monitor Brightness remotely,
    2026-11-09"), in the setting's note_evidence once, after the evidence it holds, right after "note" as
    with_evidence_apart places it. A note a table has just written whole is taken apart first, as from_data would take
    it (with_evidence_apart), so the words are not lost to that and added again on the next run. What the note says
    stays as it was; the words never go into it (a row's name may hold parentheses). Not again when the evidence holds
    the words already (but put back right after "note" when it sits elsewhere). Whether they were added."""
    if not EVIDENCE.search(words):
        raise ValueError(f"not evidence (no run, no day): {words!r}")
    plain, found = split_evidence(item.get("note") or "")
    have = found or item.get("note_evidence") or ""
    added = words not in have
    keys = list(item)
    placed = "note" in keys and keys[keys.index("note") + 1:keys.index("note") + 2] == ["note_evidence"]
    if not added and not found and placed:
        return False
    # a note written whole with the words in it already is taken apart all the same, and evidence left elsewhere is
    # put back right after "note"
    evidence = (f"{have}; {words}" if have else words) if added else have
    fields = [(k, v) for k, v in item.items() if k != "note_evidence"]
    item.clear()
    for k, v in fields:
        item[k] = plain if k == "note" else v
        if k == "note":
            item["note_evidence"] = evidence
    item.setdefault("note_evidence", evidence)
    return added
