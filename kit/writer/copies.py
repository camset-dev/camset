"""The values the camera keeps in more than one record: a live setting and the per-mode copies it keeps beside it
("copies" on the live setting, "copy_of" on each copy; docs/DATA_CONTRACTS.md, "A value kept in more than one record").
The camera's hand table names the families (COPIES in its hand tables file, writer/hand_tables.py: the Picture
Profile parameters in use and the profile in use, each with its Stills and Movie copy, and the other settings Different Set for Still/Mv keeps
per mode); the rule an editor leans on, that in a file the camera wrote the live value equals at least one of its
copies, is checked here on the camera's own downloads at every write, and a download that contradicts a family stops the
write. Keys only, never a value (docs/decisions/0016)."""
import json
import re
import sys
from pathlib import Path

KEY = re.compile(r"global:0x([0-9a-f]{4})(?:\[(\d+)\])?")
# how many of the camera's downloads (runs/<model>_fw<fw>/downloads.jsonl) a write reads, spread evenly over the list:
# the full check over every download was made once by hand (DATA_CONTRACTS), and a write reads a sample of it again
SAMPLE = 200


def downloads(run_root: Path, most: int = SAMPLE) -> list:
    """Up to `most` of the camera's downloads, spread evenly over its download log (every file the camera wrote that the
    kit kept, camkit.link), those still on disk."""
    log = run_root / "downloads.jsonl"
    if not log.exists():
        return []
    names = [json.loads(x)["path"] for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]
    step = max(1, len(names) // most)
    return [p for p in (run_root / n for n in names[::step][:most]) if p.exists()]


def value_of(cs, key: str, section: int = 0):
    """A setting's value in a read file's section, the live settings by default (an array's element by its index);
    None when the section lacks it."""
    m = KEY.fullmatch(key)
    rec = cs.get(section, int(m[1], 16)) if m and section < len(cs.sections) else None
    if rec is None:
        return None
    v = rec.value()
    if m[2] is None:
        return v
    return v[int(m[2])] if isinstance(v, list) and int(m[2]) < len(v) else None


def section_mode(cs, section: int, camera: dict) -> str | None:
    """The shooting mode a read file's section is in: the live settings' by camera.live_mode (the record that says the
    mode the file was saved in), a memory set's by camera.memory_sets.modes; None where neither says."""
    if section == 0:
        live = camera.get("live_mode") or {}
        v = value_of(cs, live["key"]) if live.get("key") else None
        return (live.get("modes") or {}).get(str(v))
    return next((m for m, sets in ((camera.get("memory_sets") or {}).get("modes") or {}).items() if section in sets),
                None)


def row_mode(row: str) -> str:
    """The shooting mode a proof row was made in, by its context ("ISO [Movie mode]": Movie; "[S&Q mode]": S&Q; a
    Time-lapse context: Time-lapse); a row whose context names none is the Stills menu's."""
    ctx = re.search(r"\[([^\]]*)\]\s*$", row)
    words = ctx[1] if ctx else ""
    if re.search(r"\bMovie mode\b|\bmovie\b", words):
        return "Movie"
    if re.search(r"\bS&Q mode\b", words):
        return "S&Q"
    return "Time-lapse" if re.search(r"Time-lapse", words) else "Stills"


def contradictions(files: list, table: dict, camera: dict | None = None, modes: list | None = None,
                   unknown: frozenset = frozenset()) -> tuple:
    """({live key: [the files where its value equals none of its copies']}, how many files read, how many could not be
    read, how many sections were checked against the mode rule, how many live sections camera.live_mode did not name
    the mode of, the first section where a setting is not the copy for its section's mode or None). A file lacking a
    record counts as one that contradicts; a file the reader cannot frame is skipped and counted, for it says nothing of
    the rule. With `camera` and `modes` (modes[i]: the modes whose value each family's i-th copy is) every section of
    each file is checked too: the setting equals the copy for the section's mode, (live key, file, section, mode) the
    first that does not. A live section whose mode live_mode does not name (no live_mode, or a value it lists no mode
    for) gets only the weaker check, and is counted, so a live_mode wrong for a camera shows. A family in `unknown`,
    whose copies' modes are not known yet, gets the weaker check in every section instead: the setting equals one of
    its copies there."""
    from camkit import camset
    bad, read, unread, checked, unnamed, mismatch = {}, 0, 0, 0, 0, None
    for f in files:
        try:
            cs = camset.read(f)
        except (ValueError, OSError):
            unread += 1
            continue
        read += 1
        for live, copies in table.items():
            v = value_of(cs, live)
            if v is None or not any(value_of(cs, c) == v for c in copies):
                bad.setdefault(live, []).append(f)
        if camera is None or not modes:
            continue
        for section in range(len(cs.sections)):
            mode = section_mode(cs, section, camera)
            unnamed += mode is None and section == 0
            for live, copies in table.items():
                v, held = value_of(cs, live, section), [value_of(cs, c, section) for c in copies]
                if v is None or None in held:
                    continue
                if live in unknown:
                    checked += 1
                    if v not in held and mismatch is None:
                        mismatch = (live, f, section, "any")
                    continue
                own = [x for x, ms in zip(held, modes, strict=False) if mode in ms]
                if mode is None or len(own) != 1:
                    continue
                checked += 1
                if v != own[0] and mismatch is None:
                    mismatch = (live, f, section, mode)
    return bad, read, unread, checked, unnamed, mismatch


def with_copies(doc: dict, table: dict, run_root: Path, most: int = SAMPLE, modes: list | None = None,
                unknown: frozenset = frozenset()) -> int | None:
    """Each family of the hand table written: "copies" (its copies' keys) on the live setting, "copy_of" (the live
    setting's key) on each copy, every other setting losing an old one. A family one of whose settings the definition
    lacks is printed and gets neither. A download that contradicts a family (its live value equals none of its copies')
    stops the write (exit 1, the family and the file named, nothing written): dropping the family's copy_of quietly
    would make its copies editable on their own, which the camera never leaves them. A download that cannot be read is
    skipped and counted. With no downloads in the camera's runs the definition is left as it is (nothing a run does not
    show is written). With `modes` (the hand table's modes for each copy, by its place) each copy of every family also
    gets "copy_for", the modes whose value it is, and every section of every download read is checked against them (the
    live settings' mode by camera.live_mode, a memory set's by camera.memory_sets.modes): a section where the setting is
    not the copy for its mode stops the write (exit 1, the family, the file and the section named). A family in
    `unknown` (its copies' modes not known yet) gets no copy_for, and the weaker rule is checked in every section; its
    copies take the setting's proof (its rows and values), for until their modes are known they are proved with it. A
    copy with copy_for lists only its own modes' rows in proved.menu: copies and copy_of say they belong together, the
    same way whatever the proofs wrote, where the records a proof wrote would tell how the camera's Different Set for
    Still/Mv box stood (decision 16). Returns how many live settings carry copies, or None with no downloads."""
    files = downloads(run_root, most)
    if not files:
        print(f"copies: no downloads in {run_root} to check the rule on, so the definition's are left as they are")
        return None
    by_key = {s["key"]: s for s in doc["settings"]}
    keep = {live: copies for live, copies in table.items() if live in by_key and all(c in by_key for c in copies)}
    for live in sorted(set(table) - set(keep)):
        print(f"  copies   {live}: the definition lacks it or one of its copies; not written")
    camera = doc.get("camera") or {}
    bad, n, unread, checked, unnamed, mismatch = contradictions(files, keep, camera, modes, frozenset(unknown))
    if bad:
        live, where = sorted(bad.items())[0]
        sys.exit(f"copies: {live}'s value equals none of its copies {keep[live]} in {where[0].relative_to(run_root)}"
                 f"{f' and {len(where) - 1} more downloads' if len(where) > 1 else ''}"
                 f"{f' ({len(bad) - 1} more families contradicted)' if len(bad) > 1 else ''}: the camera's hand table "
                 "(COPIES) is wrong for this camera, or the file is no camera's; nothing written")
    if mismatch:
        live, where, section, mode = mismatch
        what = "equals none of its copies" if mode == "any" else f"is not the copy for its section's mode ({mode})"
        sys.exit(f"copies: {live} {what} in {where.relative_to(run_root)}, section {section}: the camera's hand table "
                 "(COPIES and its modes) or camera.live_mode is wrong for this camera, or the file is no camera's; "
                 "nothing written")
    copy_of = {c: live for live, copies in keep.items() for c in copies}
    copy_for = {c: list(modes[i]) for live, copies in keep.items() if live not in unknown
                for i, c in enumerate(copies) if modes and i < len(modes)}
    for s in doc["settings"]:
        for field, want in (("copies", keep.get(s["key"])), ("copy_of", copy_of.get(s["key"])),
                            ("copy_for", copy_for.get(s["key"]))):
            if want is None:
                s.pop(field, None)
            else:
                s[field] = list(want) if field in ("copies", "copy_for") else want
        mine = copy_for.get(s["key"])
        menu = (s.get("proved") or {}).get("menu")
        if mine and menu and any(row_mode(r) in mine for r in menu):
            # a row of another mode that wrote this copy says how the family's Different Set box stood then: the copy's
            # proof is its own mode's rows (the values they prove are the same)
            s["proved"]["menu"] = [r for r in menu if row_mode(r) in mine]
    for live, copies in keep.items():
        if live in unknown and by_key[live].get("proved"):
            # until its copies' modes are known they are proved with their setting: its rows and values, so a copy's own
            # proof rows (which a choice wrote it, per the camera's box) say nothing
            for c in copies:
                by_key[c]["proved"] = json.loads(json.dumps(by_key[live]["proved"]))
    if modes:
        print(f"copies: copy_for on {len(copy_for)} copies, the hand table's modes; the mode rule held in {checked} "
              f"family sections of {n} downloads read"
              + (f"; {unnamed} live sections whose mode camera.live_mode does not name had only the weaker check"
                 if unnamed else ""))
    print(f"copies: {len(keep)} live settings with the copies the camera keeps of them ({len(copy_of)} copies), the "
          f"rule held in each of {n} downloads read" + (f", {unread} that could not be read skipped" if unread else ""))
    return len(keep)
