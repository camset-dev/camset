"""Rebuild the generated files that are committed, from their one source (the pre-commit hook runs this).

    .venv/bin/python kit/tools/build_docs.py                  # write them; every definition is left as it is
    .venv/bin/python kit/tools/build_docs.py --write-schema   # and first rewrite the active camera's definition
    .venv/bin/python kit/tools/build_docs.py --definitions    # and first every definition's parts from data/
    .venv/bin/python kit/tools/build_docs.py --check          # list the stale ones

The definitions are editor/definitions/<model>_fw<fw>.json, one per model and firmware (docs/decisions/0019).
--write-schema runs kit/schema_update.py --write, which rewrites the definition of the camera the kit works on
(camkit.paths: --camera, CAMSET_CAMERA or private/config.json) from its tables, data/ and that camera's proof runs in
runs/<model>_fw<fw>/: only on the machine that holds them, by whoever maps that camera, and schema_update.py refuses
runs whose downloads are another camera's. --definitions runs kit/schema_update.py --from-data --write, which brings
every definition's parts from data/ (the camera section, the project's own help, the format, the Expert marks, the
notes' evidence apart) up to date without runs, after a camera file or help file there was edited. The pre-commit
hook passes neither (kit/tests/test_build_docs.py checks), so a commit never rewrites a definition.

The proof viewer is rebuilt for the camera the kit works on, when that camera has proof runs
(runs/<model>_fw<fw>/kit2_pass2/report.json); with none it is not built, and says so, as kit/tools/proof_viewer.py
refuses a page without the camera's own runs. --no-viewer (the pre-commit hook) never looks at runs/.

Each fact is edited in one place only (docs/decisions/0014); docs/WHERE_FACTS_LIVE.md, "Where each fact lives", maps them.
Committed because other tools read them as files:
  editor/definitions/<model>_fw<fw>.json kit/schema_update.py, with --write-schema or --definitions only
  docs/formats/sony_camset_ids_<model>_fw<fw>.ksy
                                         kit/tools/camset_ksy.py: each definition's record names, one file per
                                         definition; the hand-written format imports the reference definition's
                                         (camkit.definitions.REFERENCE)
  kit/camkit/formats/                    kaitai-struct-compiler: the Python reader of docs/formats/sony_camset.ksy and
                                         the record names it imports, which a test reads the sample with beside the
                                         block (decision 20's tie), and SOURCES.json, the SHA-256 of what each .ksy
                                         gave it (reader_part), so that --check sees a .ksy changed since with no
                                         compiler
  kit/common/never_touch.h               never_touch_h: the buttons and camera properties camlink and the camera
                                         helper never send, from kit/camkit/safety.py
  docs/decisions/index.md, its table     decisions_index: each record's number, title, date and status, from the record
  mkdocs.yml, the nav's model pages      mkdocs_nav: one entry per docs/models/<model>_fw<fw>.md
and, local only, runs/<model>_fw<fw>/_viewer/index.html (kit/tools/proof_viewer.py). STATUS, MEMORY_MAP, the model appendix's
measured block and the data-contract tables are not committed: the docs site renders them from these sources
(mkdocs.yml, kit/tools/docs_macros.py), using status_md and memory_map_md below, one section per definition. No
generated file carries a date.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# camkit before any other package, as in every kit program: a Python without the kit's packages is told so (camkit/start.py)
from camkit import ROOT, camset, definitions, paths  # noqa: E402
import yaml  # noqa: E402
import camset_ksy  # noqa: E402

DOCS = ROOT / "docs"
PY = sys.executable
VIEWER_NO_RUNS = 3          # kit/tools/proof_viewer.py's exit status for a page refused for want of the camera's runs (its NO_RUNS)
HEAD = "Rendered from {src} when the docs are built (`kit/tools/docs_macros.py`); edit those, not this page."


def esc(t) -> str:
    return str(t).replace("|", "\\|").replace("\n", " ")


def first_sentence(t: str, n: int = 170) -> str:
    """Up to the first full stop that ends a sentence: not one after a menu's short abbreviation (Rec., Comp.)."""
    t = (t or "").strip()
    s = t
    for m in re.finditer(r"[.!?](?=\s+[A-Z(\"']|$)", t):
        word = re.search(r"(\w+)$", t[:m.start()])
        if word and len(word.group(1)) <= 4 and word.group(1)[0].isupper():
            continue
        s = t[:m.end()]
        break
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def state(s) -> str:
    """proved; no_proof, a setting no proof can reach, with its reason (unproved_reason: not on this camera, a working
    value the camera keeps, a network block, ...); or open, what is left to prove."""
    if s.get("proved"):
        return "proved"
    return "no_proof" if s.get("unproved_reason") else "open"


class Records:
    """The schema's settings by record: the live section's, and the memory sets' (a set falls back on the live
    records a registration copies, as the editor's schema.find does)."""

    def __init__(self, doc):
        self.live, self.set = collections.defaultdict(list), collections.defaultdict(list)
        for s in doc["settings"]:
            if s.get("area") == "global":
                self.live[s["id"]].append(s)
            if s.get("area") == "set" or s.get("in_sets"):
                self.set[s["id"]].append(s)

    def of(self, sec: int, rid: int) -> list:
        return (self.live if sec == 0 else self.set).get(rid, [])

    @staticmethod
    def cls(settings) -> str:
        """A record's state: proved, partly, named (not proved), cant (no proof can reach it), none (not named)."""
        if not settings:
            return "none"
        real = [s for s in settings if state(s) in ("proved", "open")]
        if not real:
            return "cant"
        p = sum(state(s) == "proved" for s in real)
        return "proved" if p == len(real) else "partly" if p else "named"

    def byte_counts(self, sec: int, rid: int, r) -> collections.Counter:
        settings = self.of(sec, rid)
        total_bytes = r.size * r.count
        if not settings:
            return collections.Counter({"none": total_bytes})
        if any("@" in s["key"] for s in settings):
            byte_cls = ["none"] * total_bytes
            for s in settings:
                if "@" in s["key"]:
                    off = int(s["key"].split("@")[1])
                    sz = s.get("field_size") or (s.get("size") if s.get("size") and s.get("size") < r.size else 2)
                    c = Records.cls([s])
                    for b in range(off, min(total_bytes, off + sz)):
                        byte_cls[b] = c
            return collections.Counter(byte_cls)
        elif any(s.get("index") is not None for s in settings):
            counts = collections.Counter()
            for i in range(r.count):
                el_settings = [s for s in settings if s.get("index") == i]
                counts[Records.cls(el_settings)] += r.size
            return counts
        else:
            return collections.Counter({Records.cls(settings): total_bytes})


CLS_NAME = {"proved": "proved", "partly": "partly proved", "named": "named, not proved",
            "cant": "no proof possible", "none": "not in the schema"}


def status_md(doc, sample=None) -> str:
    sample = sample or definitions.sample(doc)
    settings = doc["settings"]
    tabs = list(doc.get("tabs") or []) + sorted({s.get("tab") or "Other" for s in settings} - set(doc.get("tabs") or []))
    by_tab = collections.defaultdict(collections.Counter)
    for s in settings:
        by_tab[s.get("tab") or "Other"][state(s)] += 1
    total = collections.Counter(state(s) for s in settings)
    lay = (doc.get("layouts") or [{}])[0]
    L = [f"# Status: {lay.get('model', doc.get('model'))}, firmware {lay.get('firmware', '?')}", "",
         HEAD.format(src=f"`editor/definitions/{definitions.key(doc)}.json` and the layout's reference file"), "",
         "What the schema knows and how much of it the camera has proved. A setting is proved when the camera showed "
         "the option and wrote the value (docs/REMAPPING_PLAYBOOK.md); \"no proof possible\" is a setting no proof "
         "can reach on this body (not on its menus, a working value the camera keeps, a network block...), with its "
         "reason; \"not proved\" is what is left to find.", "",
         "## Settings", "", "| Tab | Settings | Proved | No proof possible | Not proved |", "|---|---|---|---|---|"]
    for t in tabs:
        c = by_tab.get(t)
        if c:
            L.append(f"| {esc(t)} | {sum(c.values())} | {c['proved']} | {c['no_proof']} | {c['open']} |")
    L.append(f"| **All** | **{len(settings)}** | **{total['proved']}** | **{total['no_proof']}** | **{total['open']}** |")

    if sample and sample.exists():
        cs, recs = camset.read(sample), Records(doc)
        L += ["", "## The file's bytes", "",
              f"Value bytes of the live settings and of one memory set in `{paths.shown(sample)}` (the record headers, counts "
              "and checksums are structure), by the state of the settings that cover them:", "",
              "| Section | Records | " + " | ".join(CLS_NAME[c].capitalize() for c in CLS_NAME) + " |", "|---|---|" + "---|" * len(CLS_NAME)]
        for sec, label in ((0, "Live settings"), (1, "A memory set")):
            n = collections.Counter()
            for rid, r in cs.sections[sec].items():
                n.update(recs.byte_counts(sec, rid, r))
            tot = sum(n.values())
            L.append(f"| {label} | {len(cs.sections[sec])} | " + " | ".join(f"{100 * n[c] / tot:.1f}%" for c in CLS_NAME) + " |")

    L += ["", "## Not proved", "", "| Record | Setting | Where | Known |", "|---|---|---|---|"]
    for s in sorted((s for s in settings if state(s) == "open"), key=lambda s: s["key"]):
        L.append(f"| `{s['key']}` | {esc(s['name'])} | {esc(s.get('tab') or '')} > {esc(s.get('group') or '')} | {esc(first_sentence(s.get('note')))} |")

    why = collections.Counter((s["unproved_reason"]["kind"], s["unproved_reason"]["why"]) for s in settings
                              if not s.get("proved") and s.get("unproved_reason"))
    if why:
        # the kind as the definition's schema names it (schemas/definition.schema.json, unproved_reason)
        L += ["", "## No proof possible", "", "| Settings | Kind | Why |", "|---|---|---|"]
        for (kind, text), n in sorted(why.items(), key=lambda kv: (-kv[1], kv[0])):
            L.append(f"| {n} | `{kind}` | {esc(text)} |")

    # no "values without a name" list: it was read off the old lists of the values camera files held (observed), the
    # owner's own settings among them (decision 16), which no definition carries now
    L += ["", "See `docs/MEMORY_MAP.md` for every record of the file, and the proof viewer (`kit/tools/proof_viewer.py`) for the "
          "camera's frames behind each proof."]
    return "\n".join(L) + "\n"


def header_rows(cs) -> list:
    """The header's parts as its container block places them, in file order, with the bytes no part names: (offset,
    length, name, what it is)."""
    b = cs.block
    minor = "the minor, shown with two digits" if b.decode == "major_minor" else "the minor's two digits"
    parts = [(b.magic_at.n, len(b.magic), "magic", "the bytes every such file starts with"),
             (b.model[0].n, b.model[1].n - b.model[0].n, "model", "NUL-padded text"),
             (b.saved[0].n, b.saved[1].n - b.saved[0].n, "saved", "the save time, NUL-padded text"),
             (b.firmware[0].n, b.firmware[1].n - b.firmware[0].n, "firmware",
              f"{b.decode}: the major version, then {minor} ({cs.firmware})"),
             (b.header_checksum.at.n, b.header_checksum.width, "header checksum",
              f"{b.header_checksum.kind} of {b.header_checksum.over[0]} up to {b.header_checksum.over[1]}")]
    if b.video_system is not None:
        parts.append((b.video_system[0].n, 1, "video system",
                      "the video system the camera was set to: " + ", ".join(f"{v} {n}" for v, n in b.video_system[1])
                      + f" ({cs.video_system})"))
    out, at = [], 0
    for off, n, name, what in sorted(parts):
        if off > at:
            out.append((at, off - at, "(not described)", "no part of the block names these bytes"))
        out.append((off, n, name, what))
        at = off + n
    if at < b.sections_start.n:
        out.append((at, b.sections_start.n - at, "(not described)", "no part of the block names these bytes"))
    return out


def memory_map_md(doc, sample=None) -> str:
    """The byte layout of a settings file with what every record holds (kit/memory_map_doc.py's, ported from the
    archived kit and keyed to the proof states). The header's parts come from the file's container block, the
    contract (docs/decisions/0020)."""
    sample = sample or definitions.sample(doc)
    cs, recs = camset.read(sample), Records(doc)
    d = cs.data
    # no value shapes of the records no setting covers: they were read off one body's downloads ("constant" is what
    # its files held), so they are kept with the mapper's evidence (camkit.datafiles.record_shapes_file), which a page
    # for everyone never reads (docs/decisions/0016)

    def meaning(settings):
        ns = [s["name"] for s in settings]
        if not ns:
            return ""
        if len(ns) == 1:
            return esc(ns[0])
        if all(s.get("index") is not None for s in settings):
            return esc(f"{ns[0]} ({len(ns)} elements)" if len(set(ns)) == 1 else f"{ns[0]} … {ns[-1]} ({len(ns)} elements)")
        return esc("; ".join(ns[:3])) + (f" … ({len(ns)} settings)" if len(ns) > 3 else "")

    def status(sec, rid, settings):
        return CLS_NAME[Records.cls(settings)]

    def table(sec, base=0):
        rows = ["| Offset | ID | Shape | Bytes | Holds | State |", "|---|---|---|---|---|---|"]
        for rid, r in cs.sections[sec].items():
            st = recs.of(sec, rid)
            rows.append(f"| 0x{r.offset - base:05x} | 0x{rid:04x} | {r.size}×{r.count} | {r.size * r.count} | {meaning(st)} | {status(sec, rid, st)} |")
        return rows

    def summary(sec):
        rs = cs.sections[sec]
        named = [rid for rid in rs if recs.of(sec, rid)]
        b = sum(8 + r.size * r.count for r in rs.values())
        nb = sum(8 + sum(v for k, v in recs.byte_counts(sec, rid, rs[rid]).items() if k != "none") for rid in named)
        return len(rs), len(named), b, nb

    blk = cs.block
    lay = (doc.get("layouts") or [{}])[0]
    L = [f"# Memory map of a {cs.model} settings file", "",
         HEAD.format(src=f"`{paths.shown(sample)}` (layout), `editor/definitions/{definitions.key(doc)}.json` (meanings, and "
                         "its container block)"), "",
         f"Firmware {lay.get('firmware', '?')}. File size {len(d)} bytes; all integers little-endian. Values are not listed: "
         "open a file in the editor or the proof viewer.", "",
         "## Summary", "", "| Section | Records | Named | Bytes | Named bytes |", "|---|---|---|---|---|"]
    for sec, label in ((0, "Live settings (section 0)"), (1, f"Each memory set (sections 1-{len(cs.sections) - 1})")):
        n, m, b, nb = summary(sec)
        L.append(f"| {label} | {n} | {m} ({m / n:.0%}) | {b} | {nb} ({nb / b:.0%}) |")
    L += ["", "`docs/STATUS.md` has how much of it is proved.", "",
          f"## Header (0x00-0x{blk.sections_start.n - 1:02x})", "",
          "| Offset | Length | Field | Content |", "|---|---|---|---|"]
    for off, n, name, what in header_rows(cs):
        here = d[off:off + n]
        show = f"`{here.split(bytes(1))[0].decode('ascii', 'replace')}`" if name in ("magic", "model") else f"`{here.hex(' ')}`"
        if name == "saved":
            show = "`YYYYMMDD_HHMMSS`"
        L.append(f"| 0x{off:02x} | {n} | {name} | {show}. {esc(what)} |")
    t = blk.trailer_checksum
    L += ["", "## Sections", "",
          f"Each section is a `u32` record count and then its records: `u16 id`, `u16 0x{blk.marker:04X}`, "
          f"`u16 element size`, `u16 element count`, then `size × count` value bytes (the "
          f"`id_marker_size_count` framing, little-endian). The trailer checksum, {t.kind} of {t.over[0]} up to {t.over[1]}, "
          f"is at {t.at}.", "",
          "| Section | Offset | Records | Holds |", "|---|---|---|---|"]
    names = ((doc.get("camera") or {}).get("memory_sets") or {}).get("names") or {}
    pos = blk.sections_start.n
    for i, sec in enumerate(cs.sections):
        L.append(f"| {i} | 0x{pos:05x} | {len(sec)} | {'live settings' if i == 0 else esc(names.get(str(i), f'memory set {i}'))} |")
        pos += 4 + sum(8 + r.size * r.count for r in sec.values())
    L += [f"| trailer | 0x{blk.trailer_site(len(d)):05x} | | checksum |", "",
          "The twelve memory sets share one record layout, so the memory-set table gives offsets from the start of a set "
          "and holds for every set.", "", "## Live settings (section 0)", "", "Offsets are absolute.", ""]
    L += table(0)
    first = cs.sections[1]
    base = min(r.offset for r in first.values())
    L += ["", "## Memory set (sections 1-12)", "", "Offsets are from the set's first record.", ""]
    L += table(1, base=base)
    present = set(cs.sections[0])
    absent = sorted(i for i in recs.live if i not in present)
    if absent:
        L += ["", "## Settings whose record is absent from the reference file", "",
              "The camera writes some records only once a feature has been used; a file that holds them is a few "
              "records longer.", "", "| ID | Holds | State |", "|---|---|---|"]
        L += [f"| 0x{i:04x} | {meaning(recs.live[i])} | {status(0, i, recs.live[i])} |" for i in absent]
    return "\n".join(L) + "\n"


def never_touch_h(doc=None) -> str:
    """kit/common/never_touch.h: the buttons and properties camlink and the camera helper never send, from
    kit/camkit/safety.py, which the kit's Python guards read; both C++ programs compile it in."""
    from camkit import safety

    def names(xs) -> str:
        return ", ".join(json.dumps(x) for x in sorted(xs))

    rules = "\n".join(f"    {{{json.dumps(why)}, {json.dumps('|'.join(pats))}}},"
                      for why, pats in safety.NEVER_PROPERTIES.items())
    return f"""// kit/common/never_touch.h: what camlink and the editor's camera helper never send, compiled into both. Written by
// kit/tools/build_docs.py from kit/camkit/safety.py (MENU_INPUTS, GUARDED_INPUTS, NEVER_INPUTS, MIN_HOLD_MS, MAX_HOLD_MS,
// NEVER_PROPERTIES), which the kit's own guards read: edit safety.py, never this file (docs/decisions/0014). The kit's
// tests check that it is current and compile it (kit/common/guards_test.cpp).
#pragma once

#include <cctype>
#include <cstddef>
#include <regex>
#include <string>

namespace never_touch {{

// buttons pressed whenever asked: the menus' arrows, Enter and Menu, the multi-selector and the dials
inline const char* const kMenuButtons[] = {{{names(safety.MENU_INPUTS)}}};
// buttons pressed only where the caller says it allows them, on a screen it checked first (C4 is the trash button)
inline const char* const kGuardedButtons[] = {{{names(safety.GUARDED_INPUTS)}}};
// buttons never pressed: they record, light up, drive the lens or run what they are assigned
inline const char* const kNeverButtons[] = {{{names(safety.NEVER_INPUTS)}}};
// how long a press holds its button, in ms: a Down accepted and an Up refused would leave it held
constexpr int kMinHoldMs = {safety.MIN_HOLD_MS}, kMaxHoldMs = {safety.MAX_HOLD_MS};

// properties never set, each with why: a regular expression (ECMAScript) searched in the SDK's property name
// (CrDeviceProperty.h, without "CrDeviceProperty_"). Case matters: the SDK's names are CamelCase and each pattern
// starts with its capital, so it matches where a word of the name starts (with case ignored, 23 of the a1 II's names
// were refused by accident inside other words: FocusBracket's "usB", the *Preset names' "reset")
struct Rule {{
    const char* why;
    const char* pattern;
}};
inline const Rule kProperties[] = {{
{rules}
}};

template <std::size_t N>
inline bool listed(const char* const (&names)[N], const std::string& name) {{
    for (const char* n : names)
        if (name == n) return true;
    return false;
}}
inline bool menuButton(const std::string& name) {{ return listed(kMenuButtons, name); }}
inline bool guardedButton(const std::string& name) {{ return listed(kGuardedButtons, name); }}
inline bool neverButton(const std::string& name) {{ return listed(kNeverButtons, name); }}

// Why a property is never set, "" when it may be. The name as the SDK's table spells it, with or without
// "CrDeviceProperty_"; one that is no name (a code such as 0x1234, or empty) is never set either.
inline std::string property(const std::string& name) {{
    const std::string bare = name.rfind("CrDeviceProperty_", 0) == 0 ? name.substr(17) : name;
    bool word = !bare.empty() && std::isalpha(static_cast<unsigned char>(bare[0]));
    for (char c : bare) word = word && (std::isalnum(static_cast<unsigned char>(c)) || c == '_');
    if (!word) return "no property name: a code or an empty name is never set";
    for (const Rule& r : kProperties) {{
        std::smatch m;
        if (std::regex_search(bare, m, std::regex(r.pattern, std::regex::ECMAScript)))
            return std::string(r.why) + ": " + m.str(0);
    }}
    return "";
}}

}}  // namespace never_touch
"""


def between(text: str, start: str, end: str, body: str, where: str) -> str:
    """text with the lines between the marker lines `start` and `end` replaced by body (the markers stay)."""
    a, b = text.find(start), text.find(end)
    if a < 0 or b < a:
        raise SystemExit(f"{where} has lost its markers {start!r} and {end!r}: put them back around the generated part")
    a = text.index("\n", a) + 1
    b = text.rindex("\n", 0, b) + 1
    return text[:a] + body + text[b:]


DECISIONS_START = "<!-- the table: written by kit/tools/build_docs.py from the records in this folder; edit those -->"
DECISIONS_END = "<!-- end of the table -->"


STATUS_CHARS = 60          # the decisions table's Status column: at most this many characters, of whole clauses


def status_cell(said: str) -> str:
    """A record's Status line (on one line, its links' text without their targets) as the decisions table shows it:
    its asides in brackets left out (the record holds them), its "carried out" clause too (the Date column shows it),
    then as many of its clauses (split at ';') as fit in STATUS_CHARS, with "; …" when some are left out; never cut
    inside a word or a date. A first clause too long alone is cut after its last whole word that fits, with "…"."""
    while re.search(r"\([^()]*\)", said):
        said = re.sub(r"\s*\([^()]*\)", "", said)
    clauses = [c.strip() for c in said.split(";") if c.strip() and not c.strip().startswith("carried out")]
    for n in range(len(clauses), 0, -1):
        cell = "; ".join(clauses[:n]) + ("; …" if n < len(clauses) else "")
        if len(cell) <= STATUS_CHARS:
            return cell
    cell = ""
    for word in clauses[0].split() if clauses else ():
        if len(f"{cell} {word}".strip()) + 1 > STATUS_CHARS:
            break
        cell = f"{cell} {word}".strip()
    return cell + "…" if clauses else ""


def decision_rows() -> list:
    """(number, title, file name, date, status) of every record in docs/decisions/, from its own heading, Date line
    and Status line; a record whose Status says it was carried out later says so beside its date. The status is the
    Status line as status_cell shortens it."""
    out = []
    for p in sorted((DOCS / "decisions").glob("[0-9][0-9][0-9][0-9]-*.md"), key=lambda p: p.name):
        text = p.read_text(encoding="utf-8")
        head = re.search(r"^# (\d+)\. (.+)$", text, re.M)
        date = re.search(r"^- \*\*Date:\*\* (.+)$", text, re.M)
        if not head or not date:
            raise SystemExit(f"{p.relative_to(ROOT).as_posix()} needs a '# N. Title' heading and a '- **Date:**' line")
        status = re.search(r"^- \*\*Status:\*\*(.*?)(?:\n\s*\n|\n- )", text, re.M | re.S)
        said = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", " ".join((status.group(1) if status else "").split()))
        done = re.search(r"carried out\s+(\d{4}-\d{2}-\d{2})", said)
        when = date.group(1).strip() + (f"; carried out {done.group(1)}" if done else "")
        out.append((int(head.group(1)), head.group(2).strip(), p.name, when, status_cell(said)))
    return out


def decisions_index(doc=None) -> str:
    """docs/decisions/index.md with its table written from the records: number, title, date and status (each edited
    once, in its record: docs/decisions/0014)."""
    p = DOCS / "decisions" / "index.md"
    rows = "".join(f"| {n} | [{esc(title)}]({name}) | {esc(when)} | {esc(said)} |\n"
                   for n, title, name, when, said in decision_rows())
    return between(p.read_text(encoding="utf-8"), DECISIONS_START, DECISIONS_END,
                   "\n| # | Decision | Date | Status |\n|---|---|---|---|\n" + rows + "\n", "docs/decisions/index.md")


NAV_START = "# the model pages: written by kit/tools/build_docs.py from docs/models/*.md; add a page there, not here"
NAV_END = "# end of the model pages"


def model_pages() -> list:
    """(model, firmware, page path) of every model page, docs/models/<model>_fw<fw>.md, in name order: the name's own
    characters, as macOS and Linux sort paths (Windows sorts them case-folded, which puts ILCE-7RM4_ before
    ILCE-7RM4A_, and the nav would differ from the committed one there)."""
    out = []
    for p in sorted((DOCS / "models").glob("*_fw*.md"), key=lambda p: p.name):
        m = re.fullmatch(r"(.+)_fw(\d+\.\d+)", p.stem)
        if m:
            out.append((m.group(1), m.group(2), p.relative_to(DOCS).as_posix()))
    return out


def mkdocs_nav(doc=None) -> str:
    """mkdocs.yml with the Reference section's model pages written from docs/models/ (a camera's page is added by
    adding the page: the playbook's "What you deliver")."""
    p = ROOT / "mkdocs.yml"
    text = p.read_text(encoding="utf-8")
    start = text.find(NAV_START)
    indent = text[text.rfind("\n", 0, start) + 1:start] if start >= 0 else ""
    lines = "".join(f'{indent}- "{model}, firmware {fw}": {page}\n' for model, fw, page in model_pages())
    return between(text, NAV_START, NAV_END, lines, "mkdocs.yml")


def record_name_files() -> dict:
    """{docs/formats/sony_camset_ids_<model>_fw<fw>.ksy: what writes it} of every definition in editor/definitions/
    (a second camera's definition gets its own file); each is written from its own definition, whatever `doc`."""
    return {camset_ksy.ids_path(p.stem): (lambda doc, p=p: camset_ksy.render(definitions.load_public(p)))
            for p in sorted(definitions.DIR.glob("*.json"))}


# what stays committed because other tools read it as a file: Kaitai's compiler, ImHex and the Web IDE read the
# record names (one file per definition), and both C++ programs compile the safety lists in; STATUS, MEMORY_MAP and
# the appendix's measured block are rendered by the docs site instead (kit/tools/docs_macros.py), so no copy of them is
# committed
GENERATED = {
    **record_name_files(),
    ROOT / "kit" / "common" / "never_touch.h": never_touch_h,
    # and two lists in files written by hand, between their markers: the decisions' table, the nav's model pages
    DOCS / "decisions" / "index.md": decisions_index,
    ROOT / "mkdocs.yml": mkdocs_nav,
}


def reference() -> dict:
    """The definition the generated files are made from (camkit.definitions.REFERENCE)."""
    return definitions.load_public(camset_ksy.SCHEMA)


READER = ROOT / "kit" / "camkit" / "formats"         # the Python reader kaitai-struct-compiler writes
SOURCES = READER / "SOURCES.json"                    # {.ksy file name: the SHA-256 of its reader_part} it was compiled from
CONTAINER = DOCS / "formats" / "sony_camset.ksy"     # the hand-written format the reader is compiled from
REBUILD = ("rebuild the reader (kaitai-struct-compiler 0.11: brew install kaitai-struct-compiler on macOS, or the "
           "package for your system at kaitai.io; then kit/tools/build_docs.py --no-viewer)")


def ksy_yaml(p: Path):
    """A .ksy read as YAML; yaml.YAMLError naming the file when it does not read as YAML."""
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"{p.relative_to(ROOT).as_posix()} does not read as YAML ({str(e).splitlines()[0]})") from e


def reader_sources() -> list:
    """The .ksy files the reader is compiled from: the container and the record names it imports (meta.imports, each
    <name>.ksy beside it)."""
    spec = ksy_yaml(CONTAINER) or {}
    return [CONTAINER] + [CONTAINER.parent / f"{name}.ksy" for name in (spec.get("meta") or {}).get("imports") or []]


def reader_part(spec):
    """What of a .ksy's YAML the reader is compiled from, as data: comments, layout and line ends are gone with the
    YAML read, and each enum value's doc is left out here, as kaitai-struct-compiler leaves it out of the Python
    reader (the record names' docs hold each record's proof counts, and a proof alone must not stale the reader).
    Keys become text with their type, so a mapping of numbers and "_" (a switch's cases) sorts."""
    if isinstance(spec, list):
        return [reader_part(x) for x in spec]
    if not isinstance(spec, dict):
        return spec
    out = {}
    for k, v in spec.items():
        if k == "enums" and isinstance(v, dict):          # an enums section, the top level's or a type's
            v = {name: {value: {f: x for f, x in e.items() if f != "doc"} if isinstance(e, dict) else e
                        for value, e in (values or {}).items()}
                 for name, values in v.items()}
        out[f"{type(k).__name__}:{k}"] = reader_part(v)
    return out


def sha256(p: Path) -> str:
    """The SHA-256 of what the reader is compiled from in a .ksy (reader_part), so a .ksy whose reader would come out
    the same (a comment, a proof count, \\r\\n line ends) does not stale it."""
    part = reader_part(ksy_yaml(p))
    return hashlib.sha256(json.dumps(part, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def source_hashes() -> dict:
    """{file name: SHA-256} of the reader's .ksy files as they are now (SOURCES.json's shape)."""
    return {p.name: sha256(p) for p in reader_sources() if p.exists()}


def reader_stale() -> list:
    """Why the committed reader is not what its .ksy files give now, in words, by SOURCES.json: no compiler needed."""
    try:
        was = json.loads(SOURCES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [f"{SOURCES.relative_to(ROOT).as_posix()} is missing or unreadable: {REBUILD}"]
    try:
        now = source_hashes()
    except yaml.YAMLError as e:
        return [f"{e}: correct it, then {REBUILD}"]
    out = [f"{(CONTAINER.parent / name).relative_to(ROOT).as_posix()} changed: {REBUILD}"
           for name in sorted(now) if was.get(name) != now[name]]
    out += [f"{(CONTAINER.parent / name).relative_to(ROOT).as_posix()} is no longer one the reader is compiled from: "
            f"{REBUILD}" for name in sorted(set(was) - set(now))]
    return out


def parsers():
    """The reader generated from the format by kaitai-struct-compiler, the kit's (Python), which a test reads the
    sample with beside the container block, and SOURCES.json beside it (the SHA-256 of what each .ksy gave it,
    reader_part). Without the compiler the committed ones stay, and when a .ksy changed since in what the reader is compiled
    from it says so here, as --check (CI) will."""
    ksc = shutil.which("kaitai-struct-compiler")
    if not ksc:
        why = reader_stale()
        print("kaitai-struct-compiler not found: the generated reader left as it is" +
              "".join(f"\nthe reader is stale: {w}" for w in why))
        return
    spec, out = CONTAINER, READER
    r = subprocess.run([ksc, "--target", "python", "--python-package", "camkit.formats", "--outdir", str(out), str(spec)],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"kaitai-struct-compiler could not compile {spec.relative_to(ROOT).as_posix()}:\n"
                         f"{(r.stderr or r.stdout).strip()}")
    SOURCES.write_text(json.dumps(source_hashes(), indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out.relative_to(ROOT).as_posix()} (the Python reader, and {SOURCES.name})")


def stale() -> list:
    """The committed generated files that differ from what their sources give now, the record names no definition
    gives any more, then why the reader is stale (reader_stale), in words."""
    doc = reference()
    gone = [f"{p.relative_to(ROOT).as_posix()}: no definition gives it now: delete it"
            for p in sorted(camset_ksy.FORMATS.glob(f"{camset_ksy.IDS_PREFIX}*.ksy")) if p not in GENERATED]
    return [p.relative_to(ROOT).as_posix() for p, make in GENERATED.items()
            if not p.exists() or p.read_text(encoding="utf-8") != make(doc)] + gone + reader_stale()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="only list the generated files that are out of date")
    ap.add_argument("--write-schema", action="store_true",
                    help="first rewrite the definition of the camera the kit works on from its runs "
                         "(kit/schema_update.py --write; never the pre-commit hook)")
    ap.add_argument("--definitions", action="store_true",
                    help="first bring every definition's parts from data/ up to date, without runs "
                         "(kit/schema_update.py --from-data --write; never the pre-commit hook)")
    ap.add_argument("--no-schema", action="store_true", help=argparse.SUPPRESS)    # the default since --write-schema
    ap.add_argument("--no-viewer", action="store_true", help="leave the local proof viewer as it is (the pre-commit hook)")
    a = ap.parse_args(argv)
    if a.check:
        out = stale()
        print("\n".join(f"stale: {p}" for p in out) or "all generated files are current")
        sys.exit(1 if out else 0)
    # the runs are looked at only for the schema and the viewer: the hook (--no-viewer) never does
    root = paths.run_root(required=False) if (a.write_schema or not a.no_viewer) else None
    have_runs = root is not None and (root / "kit2_pass2" / "report.json").exists()
    if a.definitions:
        subprocess.run([PY, str(ROOT / "kit" / "schema_update.py"), "--from-data", "--write"], check=True)
    if a.write_schema and have_runs:
        mine = f"editor/definitions/{root.name}.json"
        subprocess.run([PY, str(ROOT / "kit" / "schema_update.py"), "--write"], check=True, stdout=subprocess.DEVNULL,
                       env={**os.environ, paths.ENV: root.name})
        print(f"wrote {mine}, {root.name}'s definition")
    elif a.write_schema:
        where = f"{paths.shown(root)}/kit2_pass2" if root is not None else "runs/ (no camera named)"
        print(f"no proof runs in {where}: every definition left as it is")
    elif not a.definitions:
        print("every definition left as it is (--write-schema rewrites the active camera's from its runs, "
              "--definitions every one's parts from data/)")
    doc = reference()
    for p, make in GENERATED.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(make(doc), encoding="utf-8", newline="\n")
        print(f"wrote {p.relative_to(ROOT).as_posix()}")
    parsers()
    if have_runs and not a.no_viewer:
        r = subprocess.run([PY, str(ROOT / "kit" / "tools" / "proof_viewer.py")], capture_output=True, text=True,
                           env={**os.environ, paths.ENV: root.name})
        if r.returncode == VIEWER_NO_RUNS:          # its camera's runs are not this definition's (no definition yet)
            print(f"proof viewer not built: {(r.stderr or '').strip()}")
        else:
            if r.returncode:
                sys.stderr.write(r.stderr or "")
            r.check_returncode()
            print(f"wrote {paths.shown(Path(r.stdout.strip().splitlines()[-1]))}")
    elif not a.no_viewer:          # as proof_viewer.py: no page where the kit has not run on the camera
        print(f"proof viewer not built: no proof runs in {paths.shown(root) + '/kit2_pass2' if root is not None else 'runs/ (no camera named)'}; "
              "it is for whoever ran the kit on their camera")


if __name__ == "__main__":
    main()
