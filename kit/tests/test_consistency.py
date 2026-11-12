"""The shipped definition against itself and against the proofs it was written from: the inference layers of
kit/schema_update.py (the Recall Custom holds' shared encoding, the holds' bracket places, the picker families' shared
code tables, the movie copies, the scaled numbers) checked over what it wrote, not over the code that wrote it.

Run: .venv/bin/python -m pytest kit/tests/test_consistency.py -q
The definition is editor/definitions/ILCE-1M2_fw4.00.json; the proofs are the a1 II's pass 2 (runs/, never versioned),
and the tests that need them skip without them. Nothing here names a value of the owner's files (decision 16): the
tests assert on labels, keys and counts.
"""
import collections
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset, datafiles, definitions, paths  # noqa: E402

DOC = definitions.load(paths.A1II)
SETTINGS = DOC["settings"]
BY_KEY = {s["key"]: s for s in SETTINGS}
PASS2 = paths.a1ii_root() / "kit2_pass2"


def need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} not present")
    return path


def labels(s: dict) -> dict:
    return {v: lab for v, lab in s.get("values") or []}


def proved(s: dict) -> list:
    return list((s.get("proved") or {}).get("values") or [])


def proofs() -> list:
    return [json.loads(line) for line in Path(need(PASS2 / "proofs.jsonl")).read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------- a. the Recall Custom holds

def test_recall_custom_holds_share_their_labels():
    """Recall Custom hold 1-3 are one record's slots with one encoding (schema_update: "a value a hold's list proved
    names the same value in the other holds"): wherever any hold proved a value, every hold names it alike."""
    holds = collections.defaultdict(dict)
    for s in SETTINGS:
        m = re.fullmatch(r"Recall Custom hold ([123])", s["group"])
        if m:
            holds[(s["id"], s["name"])][int(m.group(1))] = s
    assert len(holds) >= 20 and all(set(h) == {1, 2, 3} for h in holds.values()), "each item in all three holds"
    bad = []
    for (rid, name), h in holds.items():
        for v in set().union(*(proved(s) for s in h.values())):
            named = {n: labels(s).get(v) for n, s in h.items()}
            if len(set(named.values())) != 1 or None in named.values():
                bad.append(f"{name} (0x{rid:04x}) value {v}: {named}")
    assert not bad, "\n".join(bad)


# ---------------------------------------------------------------- b. the holds' bracket places

def bracket_rule():
    """schema_update's rule, read from it: each hold record copies its live list (HOLD_BRACKET_COPIES), numbered by
    the live code's place in the live list from 0."""
    import schema_update as S
    out = {}
    for hold, live in S.HOLD_BRACKET_COPIES.items():
        codes = sorted(labels(BY_KEY[live]))
        out[hold] = (live, codes)
    return out


def test_the_holds_bracket_copies_follow_the_live_lists_by_place():
    rule = bracket_rule()
    assert rule, "schema_update names the holds' bracket copies"
    bad = []
    for hold, (live, codes) in rule.items():
        h, lv = BY_KEY[hold], labels(BY_KEY[live])
        assert len(labels(h)) == len(codes), f"{hold}: one place per live code"
        for place, lab in labels(h).items():
            if lab != lv[codes[place]]:
                bad.append(f"{hold} place {place} {lab!r} against {live} {codes[place]} {lv[codes[place]]!r}")
        for place in proved(h):          # a proved place names a live code the live list proved
            if codes[place] not in proved(BY_KEY[live]):
                bad.append(f"{hold} proved place {place}: live code {codes[place]} not proved in {live}")
    assert not bad, "\n".join(bad)


def test_every_proved_bracket_registration_matches_the_place_rule():
    """Every proof whose registration wrote a hold's bracket copy: the slot written holds the place, in the live list,
    of the live bracket setting the same download holds."""
    rule = bracket_rule()
    seen, bad = 0, []
    for p in proofs():
        for c in p.get("changes") or []:
            if c["key"] not in rule or not p.get("dat") or not (PASS2 / "dat" / p["dat"]).exists():
                continue
            live, codes = rule[c["key"]]
            rec = camset.read(PASS2 / "dat" / p["dat"]).get(0, int(live.split(":0x")[1], 16))
            for slot, (b, a) in enumerate(zip(c["before"], c["after"], strict=True)):
                if a == b:
                    continue
                seen += 1
                if rec.value() not in codes or codes.index(rec.value()) != a:
                    bad.append(f"{p['dat']}: {c['key']} slot {slot} against {live}")
    if not seen:
        pytest.skip("no proof registered a bracket")
    assert not bad, "\n".join(bad)


# ---------------------------------------------------------------- c. the picker families

def family(s: dict) -> str | None:
    """The picker a setting is a slot of: slots of one family are chosen from one screen's list of functions."""
    n = s["name"]
    m = re.match(r"(Fn Menu \((?:Still|Movie|Playback)\)|Custom Key \((?:Still|Movie|Playback)\)|My Dial) ?\d*:", n)
    if m:
        return m.group(1)
    m = re.fullmatch(r"(?:Front dial|Rear Dial [LR]|Control Wheel) \((?:M mode|other modes)(, movie)?\)", n)
    if m:
        return "Dial/Wheel (movie)" if m.group(1) else "Dial/Wheel (still)"
    return None


FAMILIES = collections.defaultdict(list)
for _s in SETTINGS:
    if family(_s):
        FAMILIES[family(_s)].append(_s)
FULL = 10                # a slot that proved this many values was proved in full (the others sample three)


def test_the_picker_families_are_found():
    assert set(FAMILIES) == {"Fn Menu (Still)", "Fn Menu (Movie)", "Fn Menu (Playback)", "Custom Key (Still)",
                             "Custom Key (Movie)", "Custom Key (Playback)", "My Dial", "Dial/Wheel (still)",
                             "Dial/Wheel (movie)"}
    for name, slots in FAMILIES.items():
        assert any(len(proved(s)) >= FULL for s in slots), f"{name}: one slot proved in full"


@pytest.mark.parametrize("fam", sorted(FAMILIES))
def test_a_sampled_picker_slot_is_a_subset_of_the_slot_proved_in_full(fam):
    """A slot proved at three points names each value as the slots proved in full on the same screen name it: every
    proved (value, label) of a sampled slot is in the code table of each full slot that has the value, with the same
    label, and in at least one."""
    slots = FAMILIES[fam]
    full = [s for s in slots if len(proved(s)) >= FULL]
    bad = []
    for s in slots:
        if s in full:
            continue
        for v in proved(s):
            lab = labels(s).get(v)
            have = {f["name"]: labels(f)[v] for f in full if v in labels(f)}
            if not have:
                bad.append(f"{s['name']}: {v} {lab!r} in no full slot's table")
            elif any(other != lab for other in have.values()):
                bad.append(f"{s['name']}: {v} {lab!r}, full slots {have}")
    assert not bad, f"{len(bad)} sampled values named otherwise than the full slots name them:\n" + "\n".join(bad)


@pytest.mark.parametrize("fam", sorted(FAMILIES))
def test_one_picker_family_names_each_code_alike_in_every_slot(fam):
    """The slots of one family share one screen's list of functions, so a code carries one label in all of them,
    proved or filled in (a full slot's reading not carried to its siblings shows here)."""
    named = collections.defaultdict(lambda: collections.defaultdict(list))
    for s in FAMILIES[fam]:
        for v, lab in s.get("values") or []:
            named[v][lab].append(s["name"].split(": ")[-1])
    bad = [f"{v}: " + "; ".join(f"{lab!r} in {len(where)} slot(s)" for lab, where in by.items())
           for v, by in sorted(named.items()) if len(by) > 1]
    assert not bad, f"{len(bad)} codes named two ways in {fam}:\n" + "\n".join(bad)


# ---------------------------------------------------------------- d. repeated labels

# A label named twice in one setting's values, by the picker family it is repeated in. A true twin is one function
# the camera lists twice with a different icon; the others are listed so a new repeat fails, each with why it stands.
TWINS = {
    "AEL hold": "spot and normal metering: two codes, the spot icon apart (stills names the second Spot AEL hold)",
    "AEL toggle": "spot and normal metering, as AEL hold",
    "Fixed Speed STBY": "Custom Key zoom and Remote zoom: two codes, a remote icon apart (stills names them apart)",
    "Fixed Speed REC": "Custom Key zoom and Remote zoom, as Fixed Speed STBY",
    "SteadyShot": "the stills and the movie SteadyShot: 209 proved on the stills Fn menu, 210 on the movie screens",
    "Sbj Recog Frm Disp.": "the stills and the movie item: 1144 on the stills screens, 1145 on the movie screens",
    "Record Setting": "Movie and Time-lapse/S&Q Record Setting: an S&Q icon apart (the Fn Menu names them apart)",
    "FTP Trans. (This Img.)": "two FTP transfer items an icon apart, both proved on the playback Fn menu and keys",
}
# one label, one code proved on the Fn Menu screens and another on the Custom Key screens, both kept in both
# families' tables: the same words for what may be two functions (one opens the setting, one is the key's own)
SCREEN_SPLIT = {
    "Pre-Capture": "2081 proved on the stills Fn menu, 2110 on the stills custom keys",
    "Subject Recog in AF": "314 proved on the Fn menus, 1049 on the custom keys",
    "Regist. Face Priority": "970 proved on the Fn menus, 1008 on the custom keys (both hand table)",
    "Protect": "2551 proved on the playback Fn menu, 336 on the playback custom keys",
}
REPEATS = {
    "Custom Key (Movie)": {"AEL hold", "AEL toggle", "Record Setting", "Fixed Speed STBY"},
    "Custom Key (Still)": {"Pre-Capture", "Fixed Speed REC", "Fixed Speed STBY", "Subject Recog in AF"},
    "Fn Menu (Still)": {"Pre-Capture", "Protect", "Regist. Face Priority", "SteadyShot", "Subject Recog in AF"},
    "Fn Menu (Movie)": {"Pre-Capture", "Protect", "Regist. Face Priority", "Sbj Recog Frm Disp.", "SteadyShot",
                        "Subject Recog in AF"},
    "Fn Menu (Playback)": {"FTP Trans. (This Img.)", "Pre-Capture", "Protect", "SteadyShot", "Subject Recog in AF"},
}


def test_no_label_is_repeated_inside_a_setting_but_the_listed_ones():
    got = collections.defaultdict(set)
    for s in SETTINGS:
        count = collections.Counter(lab for _, lab in s.get("values") or [])
        for lab, n in count.items():
            if n > 1:
                got[family(s) or s["key"]].add(lab)
    assert dict(got) == REPEATS
    assert set().union(*REPEATS.values()) == set(TWINS) | set(SCREEN_SPLIT), "each repeat has its reason"


# ---------------------------------------------------------------- e. the movie copies

def same_scale(a: dict, b: dict) -> list:
    return [f for f in ("values", "range", "step", "unit", "shown_as") if a.get(f) != b.get(f)]


def test_the_white_balance_fine_tune_movie_copies_match_their_stills_twins():
    """Each preset's fine-tune "(…, movie)" copy against its "(…, stills)" copy and the setting in use ("(…)"): the
    three offer the same labels, range and step."""
    by_name = {s["name"]: s for s in SETTINGS}
    movie = [s for s in SETTINGS if s["name"].startswith("WB fine-tune") and s["name"].endswith(", movie)")]
    assert len(movie) >= 20
    bad = []
    for s in movie:
        for twin_name in (s["name"].replace(", movie)", ", stills)"), s["name"].replace(", movie)", ")")):
            twin = by_name.get(twin_name)
            if twin is None:
                bad.append(f"{s['name']}: no {twin_name}")
            elif same_scale(s, twin):
                bad.append(f"{s['name']} against {twin_name}: {same_scale(s, twin)} differ")
    assert not bad, "\n".join(bad)


def test_the_picture_profile_movie_copies_match_their_stills_copies():
    """A profile's "(movie)" copy against its "(stills)" copy in the same profile (its unnamed copy when it has none):
    one profile's two copies of a parameter offer the same labels, range and step."""
    by_name = {(s["name"], s["group"], s.get("index")): s for s in SETTINGS}
    movie = [s for s in SETTINGS if s["name"].endswith(" (movie)") and re.search(r"\bPP\d+$", s["group"])]
    assert len(movie) >= 100
    bad = []
    for s in movie:
        base = s["name"][: -len(" (movie)")]
        twin = next((by_name[k] for k in ((base + " (stills)", s["group"], s.get("index")),
                                          (base, s["group"], s.get("index"))) if k in by_name), None)
        if twin is None:
            bad.append(f"{s['name']} ({s['group']}): no stills copy")
        elif same_scale(s, twin):
            bad.append(f"{s['name']} ({s['group']}) against {twin['name']}: {same_scale(s, twin)} differ")
    assert not bad, f"{len(bad)}:\n" + "\n".join(bad[:40])


# ---------------------------------------------------------------- f. scaled numbers

def test_a_scaled_number_reads_as_the_camera_showed_it():
    """shown_as: every proof of such a setting with the camera's shown text shows the stored value divided by divide,
    with decimals places, then the unit (Knee Point stores 7500 for 75%)."""
    scaled = {k: s for k, s in BY_KEY.items() if s.get("shown_as")}
    assert scaled
    seen, bad = 0, []
    for p in proofs():
        if not p.get("shown"):
            continue
        for c in p.get("changes") or []:
            pairs = (list(enumerate(zip(c["before"], c["after"], strict=True))) if isinstance(c["after"], list)
                     else [(None, (c["before"], c["after"]))])
            for i, (b, a) in pairs:
                s = scaled.get(c["key"] if i is None else f"{c['key']}[{i}]")
                if s is None or a == b:
                    continue
                seen += 1
                sa = s["shown_as"]
                want = f"{a / sa['divide']:.{sa['decimals']}f}{s.get('unit') or ''}"
                if re.sub(r"\s", "", p["shown"]) != want:
                    bad.append(f"{s['key']} {' > '.join(p['path'])}: shown {p['shown']!r} ({p['dat']})")
    assert seen, "proofs of the scaled settings"
    assert not bad, "\n".join(bad)


# ---------------------------------------------------------------- g. what backs each name

@pytest.mark.skipif(not definitions.evidence_path(definitions.path(paths.A1II)).exists(),
                    reason="the name sources are evidence, in the mapper's private/evidence/ (camkit.definitions)")
def test_every_proved_value_says_what_backs_its_name():
    from writer.proofs import NAME_SOURCES
    words = set(NAME_SOURCES)
    missing, unknown = [], []
    for s in SETTINGS:
        names = (s.get("proved") or {}).get("names") or {}
        missing += [f"{s['key']} {v}" for v in proved(s) if str(v) not in names]
        unknown += [f"{s['key']} {w!r}" for w in names.values() if w not in words]
    assert not missing, f"{len(missing)} proved values with no source: {missing[:20]}"
    assert not unknown, unknown[:20]


# ---------------------------------------------------------------- h. the accepted file

@pytest.mark.skipif(not datafiles.accepted_file(paths.A1II).exists(),
                    reason="the accepted file is the mapper's own, private whole (private/evidence/, not here)")
def test_the_accepted_file_validates_and_names_known_records():
    import jsonschema
    p = datafiles.accepted_file(paths.A1II)
    doc = json.loads(Path(p).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(json.loads((ROOT / "schemas" / "accepted.schema.json").read_text(encoding="utf-8"))).validate(doc)
    report = PASS2 / "report.json"
    known = set(BY_KEY)
    if report.exists():
        known |= {k for e in json.loads(Path(report).read_text(encoding="utf-8")) for k in e["records"]}
    else:                # without the report, a slot of a record the definition holds whole counts as known
        known |= {re.sub(r"\[\d+\]$", "", k) for k in BY_KEY}
    # kind "new" is a record the report found and the mapping accepted rather than added: it is known by its own statement, report or no report
    known |= {e["key"] for e in doc["accepted"] if e.get("kind") == "new"}
    unknown = [e["key"] for e in doc["accepted"] if e["key"] not in known and re.sub(r"\[\d+\]$", "", e["key"]) not in known]
    assert not unknown, unknown
