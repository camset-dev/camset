"""The values the camera keeps in more than one record: a live setting and the per-mode copies it keeps beside it
("copies" on the live setting, "copy_of" on each copy; docs/DATA_CONTRACTS.md, "A value kept in more than one record").
The camera's hand table names the families (COPIES in its hand tables file, writer/hand_tables.py: the Picture
Profile parameters in use and the profile in use, each with its Stills and Movie copy, and the other settings Different Set for Still/Mv keeps
per mode); the rule an editor leans on, that in a file the camera wrote the live value equals at least one of its
copies, is checked here on the camera's own downloads at every write, and a download that contradicts a family stops the
write. The switches of the camera's own that keep a family's copies apart (KEEPS_APART: the a1 II's Different Set for
Still/Mv boxes whose effect on the copies was proved) go on each switch as "keeps_apart" (with_keeps_apart), checked
against the copies written here. Keys only, never a value (docs/decisions/0016)."""
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


# the fields of a keeps_apart entry, in the order the definition writes them
APART_FIELDS = ("setting", "apart", "untick_sets")


def apart_problem(switch: dict, e: dict, by_key: dict, taken: dict) -> str | None:
    """Why the hand table's entry `e` for `switch` (KEEPS_APART) cannot take effect in the definition (`by_key`, its
    settings by key; `taken`, each family already named by a switch and which), in words, or None: the switch must be a
    scalar setting with values, `apart` some of them but not all; the family's setting another setting, which lists its
    copies (copies, as with_copies wrote them), each a setting of the definition saying whose mode it is (copy_for), and
    named by no other switch; `untick_sets` one of the setting's values and each copy's."""
    codes = [v for v, _ in switch.get("values") or []]
    if not switch.get("scalar") or len(codes) < 2:
        return "the switch is not a setting with named values"
    if any(v not in codes for v in e["apart"]):
        return f"apart names a value the switch does not list ({sorted(set(e['apart']) - set(codes))})"
    if set(codes) <= set(e["apart"]):
        return "apart names every value of the switch, so the copies would never share one"
    fam = by_key.get(e["setting"])
    if fam is None:
        return f"the definition lacks {e['setting']}"
    if fam["key"] == switch["key"]:
        return "the switch names itself"
    copies = [by_key.get(c) for c in fam.get("copies") or ()]
    if not copies or None in copies:
        return f"{e['setting']} lists no copies the definition holds (COPIES, written where the downloads bear it out)"
    if not all(c.get("copy_for") for c in copies):
        return f"{e['setting']}'s copies do not say whose mode they are (copy_for: COPY_MODES_UNKNOWN, or no COPY_MODES)"
    if e["setting"] in taken:
        return f"{e['setting']} is kept apart by {taken[e['setting']]} already"
    if "untick_sets" in e:
        for s in (fam, *copies):
            if not takes(s, e["untick_sets"]):
                return f"untick_sets is not one of {s['key']}'s values"
    return None


def takes(s: dict, v: int) -> bool:
    """Whether setting `s` holds `v` among its values: one it names, or a number of its range on its step."""
    if v in [x for x, _ in s.get("values") or []]:
        return True
    lo, hi = s.get("range") or (None, None)
    return lo is not None and lo <= v <= hi and (v - lo) % max(1, s.get("step") or 1) == 0


def apart_proof(e: dict, part) -> dict:
    """What proved a KEEPS_APART entry `e`: its "evidence" (the family kept apart and shared by the switch) and its
    "untick" (the value leaving the apart values gave the family), from the entry itself (the ILCE-1M2's pass, the hand
    evidence put back into the tables) and from `part`, its part of the hand evidence read apart (the plain pass)."""
    part = part if isinstance(part, dict) else {}
    return {f: e.get(f) or part.get(f) for f in ("evidence", "untick") if e.get(f) or part.get(f)}


def shared_contradictions(files: list, entries: list, by_key: dict) -> tuple:
    """({(switch key, family key): (the first file, its section)} where a download holds the switch at a value outside
    the entry's apart values while the family's setting and its copies hold more than one value, how many files read,
    how many could not be read, how many sections were checked). `entries`: [(switch key, entry)]. Every section both
    the switch and the family live in (the live settings, and the memory sets for settings kept in them) whose records
    the file holds."""
    from camkit import camset
    bad, read, unread, checked = {}, 0, 0, 0
    for f in files:
        try:
            cs = camset.read(f)
        except (ValueError, OSError):
            unread += 1
            continue
        read += 1
        for key, e in entries:
            sw, fam = by_key[key], by_key[e["setting"]]
            family = [fam["key"], *(fam.get("copies") or ())]
            for section in range(len(cs.sections)):
                if not all(section == 0 and s.get("area") == "global" or section > 0 and s.get("in_sets")
                           for s in (sw, *(by_key[k] for k in family))):
                    continue
                v = value_of(cs, key, section)
                held = [value_of(cs, k, section) for k in family]
                if v is None or None in held or v in e["apart"]:
                    continue
                checked += 1
                if len(set(held)) > 1:
                    bad.setdefault((key, e["setting"]), (f, section))
    return bad, read, unread, checked


def with_keeps_apart(doc: dict, table: dict, run_root: Path | None = None, evidence: dict | None = None,
                     most: int = SAMPLE) -> int:
    """The hand table's switches that keep a family's copies apart (KEEPS_APART: the a1 II's Different Set for Still/Mv
    boxes whose effect on the copies was proved) written as "keeps_apart" on each switch's setting, its entries in the
    table's order, each with the fields APART_FIELDS names; every other setting losing an old one. An entry is written
    only where the hand evidence shows it (apart_proof: "evidence"), its untick_sets only where it shows that too
    ("untick"): the evidence reaches no field of the definition, but without it the fact is not written, said. An
    entry that cannot take effect (apart_problem: a switch or a family the definition lacks, a family whose copies or
    their modes it does not hold, a value the switch or the family does not list, a family a switch named before) is
    printed, "not applied", and left out. With the camera's downloads (up to `most` of them, spread over its download
    log, as with_copies reads them), every section where a download holds the switch outside an entry's apart values
    must hold the family's setting and its copies at one value, the switch read in that same section and only in the
    sections it lives in (a live switch in the live settings alone, whatever the memory sets hold): a download that
    contradicts an entry stops the write (exit 1, the switch, the family, the file and the section named, nothing
    written), as with_copies and check_video_systems stop it, for the hand table is then wrong or incomplete for a
    state the camera wrote; a download that cannot be read is skipped and counted; with no downloads that is said and
    the entries are written as the tables give them. A switch none of whose entries takes effect gets no field. Read after with_copies, whose copies and copy_for it leans on.
    `evidence`: the plain pass's KEEPS_APART part of the hand evidence, read apart ({switch key: {place: fields}});
    the ILCE-1M2's pass has it put back into the entries. Keys and value codes only, never a value a file held
    (docs/decisions/0016). Returns how many switches carry one."""
    by_key = {s["key"]: s for s in doc["settings"]}
    kept, taken = [], {}
    for key, entries in table.items():
        switch = by_key.get(key)
        if switch is None:
            print(f"  keeps apart {key}: the definition lacks it; not applied")
            continue
        for i, e in enumerate(entries):
            why = apart_problem(switch, e, by_key, taken)
            proof = apart_proof(e, ((evidence or {}).get(key) or {}).get(str(i)))
            if why is None and not proof.get("evidence"):
                why = "nothing in the hand evidence shows it (its \"evidence\" in KEEPS_APART)"
            if why:
                print(f"  keeps apart {key} -> {e['setting']}: {why}; not applied")
                continue
            taken[e["setting"]] = key
            out = {f: e[f] for f in APART_FIELDS if f in e}
            if "untick_sets" in out and not proof.get("untick"):
                print(f"  keeps apart {key} -> {e['setting']}: nothing in the hand evidence shows what leaving the apart "
                      "values gave the family (its \"untick\" in KEEPS_APART); written without untick_sets")
                out.pop("untick_sets")
            kept.append((key, out))
    files = downloads(run_root, most) if run_root is not None else []
    if kept and not files:
        print(f"keeps apart: no downloads {f'in {run_root}' if run_root is not None else 'given'} to check the shared "
              "values on; written as the hand tables give them")
    elif kept:
        bad, n, unread, checked = shared_contradictions(files, kept, by_key)
        if bad:
            (key, fam), (f, section) = sorted(bad.items(), key=lambda kv: kv[0])[0]
            sys.exit(f"keeps apart: {f.relative_to(run_root)}, section {section}, holds {key} outside its apart values "
                     f"with {fam} and its copies at more than one value"
                     + (f" ({len(bad) - 1} more entries contradicted)" if len(bad) > 1 else "")
                     + ": the camera's hand table (KEEPS_APART) is wrong or incomplete for a state the camera wrote "
                     "(another mode, a memory recalled, another menu), or the file is no camera's; nothing written. "
                     "Take the entry out of KEEPS_APART, or prove the state that file shows, then write again.")
        print(f"keeps apart: the family held one value in each of {checked} sections with the switch outside its apart "
              f"values, of {n} downloads read" + (f", {unread} that could not be read skipped" if unread else ""))
    want = {}
    for key, e in kept:
        want.setdefault(key, []).append(e)
    for s in doc["settings"]:
        if s["key"] in want:
            s["keeps_apart"] = want[s["key"]]
        else:
            s.pop("keeps_apart", None)
    if want:
        print(f"keeps apart: {len(want)} switches with the families they keep apart "
              f"({sum(len(v) for v in want.values())} families)")
    return len(want)
