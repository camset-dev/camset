"""The value names a definition publishes, read again by every vision reader on the proof frames behind them: a label
audit, with no camera.

    .venv/bin/python kit/tools/label_audit.py [ROOT] [--sources S,...] [--kinds K,...] [--all] [--reader NAME ...]
        [--cache DIR] [--census-cache DIR ...] [--parallel N] [--timeout S] [--minutes M] [--max-questions N]
        [--fail-run N] [--dry-run] [--json] [--definition FILE]

ROOT is a camera's run root (runs/<model>_fw<fw>/; by default the camera the kit works on). What a record holds is
proved by the camera's own file; what rests on a reading is each value's name, and the definition's proved.names says
what backs it (kit/writer/proofs.py NAME_SOURCES). The audit takes:
  scope    every value name whose source is one of --sources (default "one reader" and "vision model"), and every
           name whose proof frame is of a kind of --kinds (default: checklist, star rating, table picker; the kinds of
           camkit.reading.QUESTIONS, as kit/tools/reader_census.py names them), or with --all every name
  frame    the proof line that backs the name, as the pass-2 report credits it (kit2_pass2/report.json: a row, a
           record and the label credited with the value; kit/pass2_report.py's report_proofs and rows_of: the latest
           line of each option, its own run's frame): of several, one whose report source is the definition's, then
           one whose label is the published name, then the newest frame. Its kind of screen and options come as
           kit/tools/reader_census.py --questions takes them (question_items), each option's recorded label put as the
           definition names its value (corrected); a checklist's box is expected in the state its published name says
  asking   each reader (the second and every third one, a paid one only when named, or each --reader) is asked the
           kind's new question (camkit.reading.QUESTIONS), never an old one and never with the options handed over,
           through reader_census.ask_all: answers kept in --cache (by default the census's own folder in the system's
           temporary folder, never in the runs), the camera's own cache (<root>/_cache/vlm) and each --census-cache
           looked in and never written, so an answer kept there is not asked again; --parallel, --timeout, --minutes
           (each reader's), --max-questions, --fail-run and --dry-run as the census has them
  judging  the question is whether the name is spelled as drawn, not only whether a reader picks its option: a vote
           is right only where the reading spells the published name (pass2_report.same_label), or, where that name
           is a part of the line the camera draws, the part of the reading in its place (after or before the colon:
           "DRO Bracket: Hi" for Hi), or the name alone of the options held in it as a whole word; a reading that
           picks the option by the census's rule (judge: a loose likeness, an icon left out, the closest option) but
           spells it otherwise is a vote of its own ("spelled otherwise"); a star count, a number and a box's state
           are judged exactly, as the census does. One vote per model family (camkit.reading.model_id: the first
           reader of a family that answered); per name, with two families or more: all agree, some agree, none agree
           and all on another reading (one other option, or one other text alike, the name's own option spelled
           otherwise among them), each picks the option but they spell it apart, or none agree and they differ; with
           one family, "one family" (as published or not), never "all agree"
Left out, and counted: a name no report line credits, a line of an identity or connection row a network decision
opened (decision 8), a frame of a run that opened a row an owner decision names (camkit.vlm.NO_READER_MARKER, decision
9: never read), a frame not on disk, a black frame, a frame the census would take no question from, a radio button's
name, a checklist name that says no tick state. A frame of a run a --network run marked (camkit.vlm.LOCAL_MARKER) goes
to local readers only (camkit.vlm.local_reader), and a hosted reader (reader_census.is_hosted) is sent no frame
reader_census.hosted_refused refuses.

Output. The console gets counts only, per source and per kind (no reading, label, value or file name: decision 16, as
the census prints); --json prints them as one JSON object and nothing else on standard output. The names not every
family confirmed go, one JSON line each, to <root>/_label_audit/labels.jsonl (LEDGER), owner-only (0600 in a 0700
folder on POSIX), rewritten whole by each run that asks (a dry run writes nothing): the setting's key, the value's code,
the published name, its source, the kind, the report row, the frame's path from <root>, each reader's model, family,
reading and verdict, and the verdict, ordered with "none agree, all on another reading" first. It is kept beside the
frames it names, in the camera's run root, because it holds what the runs hold (the camera's labels, the readers'
readings, the frames' names): runs/ is git-ignored and kit/tools/check_public.py refuses any file under it, so it never
reaches a commit, an issue or the docs (decision 16).

It changes nothing: not the definition, not a map, not a proof line, nothing in the runs but its own file. A name found
wrong, read by eye on its frame, is pinned in the camera's hand table (VALUE_FIXES, [key, code, name], in
data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json) and the definition rebuilt (kit/rebuild.py --write): its source is
then "hand table". A crawl's checked_labels.json corrects pass 1's map (kit/pass1_map.py), which a proof line already
made does not read again: it reaches a name only through the row's next proof.
"""
import argparse
import collections
import contextlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pass2_report as p2  # noqa: E402
import reader_census as rc  # noqa: E402
from camkit import definitions, paths, reading, runs, vlm  # noqa: E402
from writer.proofs import NAME_SOURCES, mixed, reader_source  # noqa: E402

SOURCES = ("one reader", "vision model")                       # --sources' default
KINDS = ("checklist", "star rating", "table picker")           # --kinds' default
LEDGER = Path("_label_audit") / "labels.jsonl"                 # the private file, under the camera's run root
# the census's kinds a proof line of each kind gives (reader_census.question_items), for a line's name
ITEM_KINDS = {"list": ("list", "scale", "star rating"), "sidelist": ("side list",), "table": ("table picker",),
              "dialog": ("carousel",), "axis": ("axis",), "lookbase": ("look base",), "checklist": ("checklist",),
              "fields": ("number field",), "wbgrid": ("wb grid",), "look": ("look",)}
LABEL_KINDS = {"list", "scale", "side list", "table picker", "carousel", "axis", "look base"}
VERDICTS = ("none agree, all on another reading", "picks the option, spelled otherwise", "none agree, apart",
            "some agree", "one family, not as published", "one family, spelled as published", "all agree", "not read")
LISTED = VERDICTS[:5]                                   # the verdicts the private file lists, in this order
NOT_TICKED = re.compile(r"(?:not|no|off)\b|un")       # how a checklist value's name for an unticked box begins (folded)
DEFAULTS = {"minutes": 60.0, "timeout": 60.0}


class Name:
    """One value name of the definition: key, value (its code as proved.names keys it), name (the published label),
    source (proved.names'), and once its proof is found, row (the report's), line (the proof line), after (a
    checklist line's: whether the value is the one the box's visit wrote), frame, kind (the census's), item (the
    reader_census.Item judged against the published name), question; why: the reason it is left out, or None;
    local_only: its frame goes to local readers only; hosted_why: why a hosted reader is sent none, or None; part: how
    the published name stands in the label the run recorded where it is not the whole of it (part_of), or None."""

    def __init__(self, key, value, name, source):
        self.key, self.value, self.name, self.source = key, str(value), name, source
        self.row = self.line = self.after = self.frame = self.kind = self.item = self.question = None
        self.why, self.local_only, self.hosted_why, self.part = None, False, None, None


# ------------------------------------------------------------------------------------------------ the names

def published(doc: dict) -> list:
    """[Name] for every value proved.names gives a source, with the label the definition publishes for it (None where
    its values list none)."""
    out = []
    for s in doc.get("settings") or []:
        labels = {str(v): lab for v, lab in s.get("values") or [] if not isinstance(v, (list, dict))}
        for v, src in ((s.get("proved") or {}).get("names") or {}).items():
            out.append(Name(s["key"], v, labels.get(str(v)), src))
    return out


def credits(report: list) -> dict:
    """{(key, value): [(row, label, the report's word for its readers)]}: each label a report row credits with a value
    of a record, as the writer names from them (never a record not one to one, nor one sampled from the option the
    camera held)."""
    out = collections.defaultdict(list)
    for e in report:
        for k, r in (e.get("records") or {}).items():
            if mixed(r) or r.get("sampled_from_start"):
                continue
            for lab, v in (r.get("proved") or {}).items():
                if not isinstance(v, (list, dict)):
                    out[(k, str(v))].append((e["row"], str(lab), (r.get("names") or {}).get(lab)))
    return out


def option_lines(main: Path, camera: str) -> tuple:
    """(proofs, {row: {label: [(line, after)]}}) of the runs the report reads, as kit/pass2_report.py takes them: every
    proof qualified with its run (report_proofs), the latest line of each option that counts (rows_of), each under the
    label the report credits it by (name_of, with the run's rows and the camera's menu tree as its main() gives them;
    a picker's twins told apart). A checklist line is under its box's two labels ("<box>: ticked", "<box>: unticked"),
    after saying which one its visit wrote; a radio button's under its two buttons' labels, after None."""
    p2.ROW_NAMES.clear()
    p2.MENU_NAMES.clear()
    proofs, skip, _, _, _ = p2.report_proofs(main)
    p2.ROW_NAMES.update(p2.norm(re.split(r" \[", p)[0]) for r in proofs for p in r.get("path") or [])
    tree = definitions.menu_tree_file(camera)
    p2.MENU_NAMES.update(p2.menu_names(tree if tree.is_file() else None))
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    for row, opts in p2.rows_of(main, proofs, skip).items():
        twins = p2.picker_names(opts)
        for i, o in opts.items():
            if not p2.credited(o) or o.get("label") is None:
                continue
            boxes = o.get("boxes") if isinstance(o.get("boxes"), list) else []
            box = next((b for b in boxes if isinstance(b, dict) and b.get("box") == o.get("index")), None)
            if o.get("kind") == "checklist" and box is not None:
                if box.get("radio"):
                    for lab in (box.get("label"), box.get("radio")):
                        out[row][str(lab)].append((o, None))
                    continue
                now = "ticked" if box.get("ticked") else "unticked"
                for state in ("ticked", "unticked"):
                    out[row][f"{box.get('label')}: {state}"].append((o, state == now))
                continue
            out[row][str(twins.get(i) or p2.name_of(o)[0])].append((o, None))
    return proofs, out


def own_run(r: dict) -> str:
    """The run folder a proof line's files are in (kit/pass2_report.py qualified)."""
    return r.get("run") or runs.MAIN_RUN


def frame_name(r: dict) -> str:
    """A proof line's chosen frame, by its name in its own run's shots/ (a qualified one without its run)."""
    f = str(r.get("chosen_frame") or "")
    q = p2.QUALIFIED.fullmatch(f)
    return q[2] if q else f


def line_kind(r: dict) -> str | None:
    """The census's kind of screen a proof line's name is read on (question_items' choice, before any frame is read)."""
    kind = r.get("kind")
    if kind == "list":
        lab = rc._bare(r.get("label"))
        return "star rating" if rc.STAR_LABEL.fullmatch(lab) else "scale" if r.get("scale") else "list"
    return (ITEM_KINDS.get(kind) or (None,))[0]


def find_lines(names: list, root: Path, report: list, lines: dict) -> dict:
    """Each name's proof line (Name.line, row, after, frame, kind), or why it has none (Name.why): of the lines the
    report credits with the value, one whose report source is the definition's, then one whose label is the published
    name, then the newest frame. Returns {(row, key): {a recorded label of the row, bare: {(the value the report
    credits it with on that record, its published name)}}}: the row's options as the definition names them."""
    credited = credits(report)
    called = {(n.key, n.value): n.name for n in names if n.name is not None}
    on_row = collections.defaultdict(lambda: collections.defaultdict(set))
    for (key, value), got in credited.items():
        for row, lab, _ in got:
            for line, after in lines.get(row, {}).get(lab, ()):
                if after is None and (key, value) in called:
                    on_row[(row, key)][rc._bare(line.get("label"))].add((value, called[(key, value)]))
    for n in names:
        if n.name is None:
            n.why = "the definition lists no name for it"
            continue
        found = []
        for row, lab, word in credited.get((n.key, n.value), ()):
            for line, after in lines.get(row, {}).get(lab, ()):
                found.append((row, lab, word, line, after))
        if not found:
            n.why = "no report line credits it"
            continue

        def rank(c, n=n):
            row, lab, word, line, after = c
            frame = root / own_run(line) / "shots" / frame_name(line)
            try:
                when = frame.stat().st_mtime if frame_name(line) else 0.0
            except OSError:
                when = 0.0
            return (reader_source(word) == n.source, after is not None or p2.same_label(lab, n.name), when)
        n.row, _, _, n.line, n.after = max(found, key=rank)
        n.kind = line_kind(n.line)
        n.frame = root / own_run(n.line) / "shots" / frame_name(n.line) if frame_name(n.line) else None
    return on_row


def in_scope(n: Name, sources, kinds, everything: bool) -> bool:
    return everything or n.source in sources or (n.kind is not None and n.kind in kinds)


# ------------------------------------------------------------------------------------------------ the frames

def items_for(root: Path, proofs: list, names: list, on_row: dict) -> None:
    """Each name's Item as reader_census.question_items takes its proof line (its kind of screen, the row's options),
    judged against the published name (judged, the row's options named as on_row says), and its question; or why
    there is none. question_items is given every line of the names' runs, so a row's options are all there, and only
    the names' own lines keep their frames, so only they give items (no line its notice: a notice names no value)."""
    live = [n for n in names if n.why is None]
    for n in live:
        if rc.identity_line(n.line):
            n.why = "an identity or connection row (decision 8)"
        elif n.frame is None or n.line.get("label") is None:
            n.why = "no frame kept"
        elif vlm.held_runs(n.frame):
            n.why = "a run no reader reads (decision 9)"
        elif not n.frame.is_file():
            n.why = "frame not on disk"
    live = [n for n in live if n.why is None]
    chosen = {id(n.line) for n in live}
    by_run = collections.defaultdict(list)
    for r in proofs:
        if rc.identity_line(r):
            continue
        line = {k: v for k, v in r.items() if k not in ("chosen_frame", "notice")}
        if id(r) in chosen:
            line["chosen_frame"] = frame_name(r)
        by_run[own_run(r)].append(line)
    items = collections.defaultdict(list)
    for run in sorted({own_run(n.line) for n in live}):
        for it in rc.question_items(root / run, by_run[run], {}):
            items[it.frame].append(it)
    from camkit.frames import load
    from camkit.live import black
    dark = {}
    for n in live:
        got = [it for it in items.get(n.frame, ()) if it.kind == n.kind and (
            n.kind not in LABEL_KINDS or it.truth == rc._bare(n.line.get("label")))]
        if not got:
            n.why = no_item(n.line)
            continue
        if n.frame not in dark:
            dark[n.frame] = black(load(n.frame))
        if dark[n.frame]:
            n.why = "a black frame"
            continue
        n.item, why = judged(n, got[0], on_row.get((n.row, n.key), {}))
        if n.item is None:
            n.why = why
            continue
        n.question = vlm.PROMPTS[reading.QUESTIONS[n.kind].prompt]
        n.local_only = bool(vlm.marked_runs(n.frame))


def no_item(r: dict) -> str:
    """Why reader_census.question_items took no question from a proof line's frame, as far as the line says."""
    kind = r.get("kind")
    if kind in ("list", "sidelist", "table", "dialog", "axis") and "shown" not in r:
        return "a line that read no option off its frame"
    if kind == "axis" and r.get("final"):
        return "a carousel's put-back visit"
    if kind == "checklist":
        return "a checklist longer than a screen or with boxes drawn alike"
    return "no question for its frame"


def tick_state(name) -> bool | None:
    """Whether a checklist value's name says its box is ticked ("Ticked", "On", "Included in DISP cycle") or not ("Not
    ticked", "Off", "Not included", "Unticked"): a name that starts with a no says not; None for no name."""
    t = re.sub(r"\s+", " ", str(name or "")).strip().lower()
    return None if not t else not NOT_TICKED.match(t)


def judged(n: Name, item, fixes: dict) -> tuple:
    """(the Item n's readings are judged by, or None, why not): its truth the published name in the kind's own form,
    its options the row's under their published names where the report credits them on n's record (fixes: {a
    recorded label, bare: {(value, published name)}}), several recorded readings of one option one option."""
    k = n.kind
    if k in LABEL_KINDS:
        def named(o):
            got = fixes.get(o) or set()
            return next(iter(got))[1] if len({name for _, name in got}) == 1 else o
        own = rc._bare(n.line.get("label"))
        options = list(dict.fromkeys([n.name if o == own else named(o) for o in item.options]))
        values = collections.defaultdict(set)
        for got in fixes.values():
            for value, name in got:
                values[name].add(value)
        if len(values.get(n.name, {n.value})) > 1:
            return None, "two values of its record share the name"
        n.part = part_of(own, n.name)
        return rc.Item(k, item.frame, n.name, options, None, item.box, item.old, item.extra), None
    if k == "checklist":
        if n.after is None:
            return None, "a radio button's name"
        state = tick_state(n.name)
        if state is None:
            return None, "a checklist name that says no tick state"
        label = item.extra.get("label")
        return rc.Item(k, item.frame, [(label, state if n.after else not state)], item.options, item.shown,
                       item.box, item.old, item.extra), None
    if k == "star rating":
        truth = rc.star_count(n.name)
    elif k in ("number field", "look"):
        truth = rc.number_of(n.name)
    elif k == "wb grid":
        truth = rc.wb_value(item.extra["axis"], n.name)
    else:
        return None, "no question for its frame"
    if truth is None:
        return None, "the published name is not what its kind of screen shows (a star count, a number)"
    options = item.options if truth in item.options else [*item.options, truth]
    return rc.Item(k, item.frame, truth, options, None, item.box, item.old, item.extra), None


def hosted_checks(names: list) -> None:
    """For a hosted reader: why each name's frame may not go to one (reader_census.hosted_refused, by OCR of the whole
    frame and the screen reader), in Name.hosted_why; fails closed, as the census does."""
    frames = list(dict.fromkeys(n.frame for n in names if n.item is not None))
    try:
        texts = reading.screen_texts(frames)
    except Exception:            # noqa: BLE001 - no OCR to judge with: every frame is refused
        texts = {}
    kinds = {}
    for n in names:
        if n.item is None:
            continue
        if n.frame not in kinds:
            kinds[n.frame] = rc.screen_kind(n.frame)
        n.hosted_why = rc.hosted_refused(n.item, texts.get(n.frame), kinds[n.frame])


# ------------------------------------------------------------------------------------------------ the readers

def readers_of(asked: list) -> list:
    """The readers' configs: each --reader by its name, else the second reader and every third one, a paid one only
    when named (reader_census --questions' choice)."""
    listed = vlm.readers(stop=True)
    if asked:
        cfgs = []
        for name in asked:
            cfg = next((r for r in listed if r.get("name") == name), None)
            if cfg is None:
                sys.exit(f"--reader {name!r}: private/config.json lists no reader of that name")
            cfgs.append(cfg)
        return cfgs
    wanted = []
    with contextlib.suppress(vlm.NoReader):
        wanted.append(vlm.role("second")["name"])
    with contextlib.suppress(vlm.NoReader):
        wanted += [r["name"] for r in vlm.voters()]
    cfgs = [r for r in listed if r["name"] in dict.fromkeys(wanted) and not vlm.paid(r)]
    if not cfgs:
        sys.exit("no reader to ask: private/config.json gives no second or third reader (a paid one is asked only when "
                 "named with --reader)")
    return cfgs


def family(cfg: dict) -> str:
    return reading.model_id(cfg.get("model") or cfg.get("name"))


def may_ask(cfg: dict, n: Name) -> bool:
    """A local-only run's frame to a local reader alone; a hosted reader never a frame hosted_refused refuses."""
    if n.local_only and not vlm.local_reader(cfg):
        return False
    return not (rc.is_hosted(cfg) and n.hosted_why)


def held(name, text) -> int:
    """How a name is held in a reading, as kit/pass2_report.py's contained() weighs a label held in another (kept():
    without case, spaces or OCR look-alikes, a point between digits kept): 2 as a whole word, 1 anywhere (three
    characters or more), 0 not."""
    k = p2.kept(name)
    if not k or k not in p2.kept(text):
        return 0
    if re.search(r"(?<![A-Za-z0-9])" + re.escape(str(name).strip()) + r"(?![A-Za-z0-9])", str(text), re.I):
        return 2
    return 1 if len(k) >= 3 else 0


def within(text, options: list) -> int | None:
    """The one option whose published name a reading holds best (held), else None: the camera draws a name the
    definition publishes as a part of its line (a carousel axis's value after its option, "DRO Bracket: Hi" for Hi; an
    option-only record's option before it; an icon in front)."""
    fits = [held(o, text) for o in options]
    best = max(fits, default=0)
    return fits.index(best) if best and fits.count(best) == 1 else None


def part_of(recorded: str, name: str) -> str | None:
    """How a published name stands in the label the run recorded for its option, where it is not the whole label
    (pass2_report.same_label): "after" (a carousel axis's value after its option and a colon: "Hi" of "DRO Bracket:
    Hi"), "before" (an option-only record's option: "DRO Bracket" of "DRO Bracket: Lo"), "held" (the name held in it
    otherwise: an icon OCR read in front, a word of the axis value left out), else None (the whole label)."""
    if p2.same_label(recorded, name):
        return None
    head, colon, tail = str(recorded).partition(":")
    if colon and p2.same_label(tail, name):
        return "after"
    if colon and p2.same_label(head, name):
        return "before"
    return "held" if held(name, recorded) else None


def spelled(n: Name, text: str) -> bool:
    """Whether a reading spells n's published name as the definition does, strictly (pass2_report.same_label: case,
    spacing, stops and the readers' look-alikes aside, every letter, digit and sign kept): the whole reading, or the
    part of it that stands where the name stands in the recorded label (Name.part: after or before its colon), or, held,
    the name as a whole word in it while no other option's name is held there at all."""
    if p2.same_label(text, n.name):
        return True
    head, colon, tail = text.partition(":")
    if n.part == "after":
        return bool(colon) and p2.same_label(tail, n.name)
    if n.part == "before":
        return bool(colon) and p2.same_label(head, n.name)
    if n.part == "held":
        return held(n.name, text) == 2 and not any(held(o, text) for o in n.item.options if o != n.name)
    return False


def reading_of(n: Name, got) -> tuple:
    """(the vote, the reading as the reader gave it, what other reading it names: a key two readings that name the
    same other thing share, or None) of one answer about n's frame. A name is "right" only where the reading spells it
    as published (spelled); a reading that picks its option by the census's rule (reader_census.judge: a loose likeness,
    an icon left out, the closest option; for a name published as a part of its line, first by the part of the reading
    in the name's place, then by the option whose name it holds alone, within) but spells it otherwise is "spelled
    otherwise"; else "another option", "no option" or
    "no answer". A star count, a number, a white balance readout and a checklist box's state are judged as the census
    judges them, which is exact."""
    value = rc.NEW_PICK.get(n.kind, rc._selected)(got, n.item)
    if value is None or (isinstance(value, str) and not value.strip()) or (isinstance(value, list) and not value):
        return "no answer", value, None
    if n.kind not in LABEL_KINDS:
        verdict = rc.judge(n.item, value)
        if verdict in ("right", "no answer"):
            return verdict, value, None
        if n.kind == "checklist":
            return verdict, value, ("box", "the other state") if verdict == "another option" else None
        text = str(value) if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""
        i = rc._index(rc.wb_value(n.item.extra["axis"], text), n.item.options) if n.kind == "wb grid" \
            else rc._named(n.item, text)
        return verdict, value, ("option", i) if i is not None else other_text(text)
    text = str(value) if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""
    if spelled(n, text):
        return "right", value, None
    head, colon, tail = text.partition(":")
    i = rc._named(n.item, {"after": tail, "before": head}[n.part]) if colon and n.part in ("after", "before") else None
    if i is None and n.part:
        i = within(text, n.item.options)
    if i is None:
        i = rc._named(n.item, text)
    if i is not None and n.item.options[i] == n.item.truth:
        return "spelled otherwise", value, other_text(text)
    if i is not None:
        return "another option", value, ("option", i)
    return "no option", value, other_text(text)


def other_text(text: str) -> tuple | None:
    """The key of a reading that names no option of the row, or its own spelling of the one it picks: two readings
    alike but for spacing, case and the punctuation that changes no meaning share it (camkit.reading.said_key)."""
    said = reading.said_key(text)
    return ("text", said) if said and said != "none" else None


def verdict_of(votes: dict) -> str:
    """The name's verdict from its families' votes ({family: (vote, reading, other)}): with one family, "one family"
    (spelled as published, or not); with two or more, "all agree" when every one spells it as published, "some agree"
    when some do, and where none does, "none agree, all on another reading" when they all name one other option or
    read one other text alike (the published name's own option spelled otherwise among them), "picks the option,
    spelled otherwise" when each picks its option but they spell it apart, else "none agree, apart"."""
    if not votes:
        return "not read"
    rights = sum(v == "right" for v, _, _ in votes.values())
    if len(votes) == 1:
        return "one family, spelled as published" if rights else "one family, not as published"
    if rights == len(votes):
        return "all agree"
    if rights:
        return "some agree"
    others = {o for _, _, o in votes.values()}
    if len(others) == 1 and None not in others:
        return "none agree, all on another reading"
    if all(v == "spelled otherwise" for v, _, _ in votes.values()):
        return "picks the option, spelled otherwise"
    return "none agree, apart"


# ------------------------------------------------------------------------------------------------ the run

def audit(root: Path, args) -> tuple:
    """(the counts, the ledger's lines) of one audit of the camera whose run root is root."""
    main = root / runs.MAIN_RUN
    if not (main / "report.json").is_file():
        sys.exit(f"{paths.shown(main / 'report.json')}: no pass-2 report (kit/pass2_report.py writes it); nothing audited")
    report = json.loads((main / "report.json").read_text(encoding="utf-8"))
    target = Path(args.definition) if args.definition else definitions.active()
    names = published(definitions.load(target))
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    cfgs = readers_of(args.reader)
    cache = rc.answers_folder(args.cache, [root])
    proofs, lines = option_lines(main, target.stem)
    on_row = find_lines(names, root, report, lines)
    scope = [n for n in names if in_scope(n, sources, kinds, args.all)]
    items_for(root, proofs, scope, on_row)
    if any(rc.is_hosted(c) for c in cfgs):
        hosted_checks(scope)
    read_only = (root / "_cache" / "vlm", *[Path(c).expanduser() for c in args.census_cache])
    asked, answers = {}, {}

    def say(s):
        print(s, file=sys.stderr, flush=True)
    for cfg in cfgs:
        name = str(cfg["name"])
        if vlm.paid(cfg) and not args.dry_run:
            say(f"{name!r} is a paid reader: each question to it costs money")
        asks = list(dict.fromkeys((n.frame, n.question, None) for n in scope if n.item is not None and may_ask(cfg, n)))
        answers[name], asked[name], _ = rc.ask_all(cfg, asks, args.minutes, cache, read_only, args.timeout, say=say,
                                                   max_questions=args.max_questions, dry=args.dry_run,
                                                   workers=args.parallel, fail_run=args.fail_run)
        asked[name]["questions"] = len(asks)
    counts = {"names": len(names), "in scope": len(scope), "readers": [str(c["name"]) for c in cfgs],
              "families": {str(c["name"]): family(c) for c in cfgs},
              "by source": dict(collections.Counter(n.source for n in scope).most_common()),
              "by kind": dict(collections.Counter(n.kind or "no proof line" for n in scope).most_common()),
              "left out": dict(collections.Counter(n.why for n in scope if n.why).most_common()),
              "asked": asked, "verdicts by source": {}, "verdicts by kind": {}}
    if args.dry_run:
        counts["dry run"] = True
    lines_out, read_by = [], collections.Counter()
    by_source = collections.defaultdict(collections.Counter)
    by_kind = collections.defaultdict(collections.Counter)
    for n in scope:
        if n.item is None:
            continue
        votes, said = {}, []
        for cfg in cfgs:
            got = answers[str(cfg["name"])].get((n.frame, n.question, None), rc.NOT_ASKED) if may_ask(cfg, n) \
                else rc.NOT_ASKED
            if got is rc.NOT_ASKED or got is rc.FAILED:
                continue
            v, value, other = reading_of(n, got)
            said.append({"reader": str(cfg["name"]), "model": str(cfg.get("model") or ""), "family": family(cfg),
                         "reading": value, "verdict": v})
            votes.setdefault(family(cfg), (v, value, other))     # one vote per family: the first that answered
        verdict = verdict_of(votes)
        by_source[n.source][verdict] += 1
        by_kind[n.kind][verdict] += 1
        read_by[len(votes)] += 1
        if verdict in LISTED:
            lines_out.append({"verdict": verdict, "key": n.key, "value": n.value, "name": n.name, "source": n.source,
                              "kind": n.kind, "row": n.row, "frame": n.frame.relative_to(root).as_posix()
                              if n.frame.is_relative_to(root) else str(n.frame), "families": len(votes),
                              "readers": said})
    counts["verdicts by source"] = {s: dict(c) for s, c in sorted(by_source.items())}
    counts["verdicts by kind"] = {k: dict(c) for k, c in sorted(by_kind.items())}
    # how many families' votes each name asked about stands on (of len(set(families)) asked): fewer where a reader
    # failed, ran out of time or may not be sent the frame
    counts["names by families that answered"] = {str(k): v for k, v in sorted(read_by.items())}
    lines_out.sort(key=lambda d: (VERDICTS.index(d["verdict"]), d["key"], d["value"]))
    return counts, lines_out


def write_ledger(root: Path, lines: list) -> Path:
    """The ledger (LEDGER under root), written whole, owner-only on POSIX: a 0700 folder and a 0600 file."""
    f = root / LEDGER
    f.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(f.parent, runs.PRIVATE_DIR)
    part = f.with_name(f.name + ".part")
    fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, runs.PRIVATE_FILE)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
        out.writelines(json.dumps(d, ensure_ascii=False) + "\n" for d in lines)
    if os.name == "posix":
        os.chmod(part, runs.PRIVATE_FILE)
    part.replace(f)
    return f


def show(counts: dict, ledger: Path | None) -> None:
    """The counts, as text: no reading, label, value or file name of a frame (decision 16)."""
    print(f"label audit: {counts['in scope']} of {counts['names']} value names in scope; readers "
          f"{', '.join(repr(r) for r in counts['readers'])} (counts only: no reading, label, value or file name is "
          "printed; docs/decisions/0016)")
    print("  by source: " + ", ".join(f"{k} {v}" for k, v in counts["by source"].items()))
    print("  by kind: " + ", ".join(f"{k} {v}" for k, v in counts["by kind"].items()))
    if counts["left out"]:
        print("  left out: " + ", ".join(f"{k} {v}" for k, v in counts["left out"].items()))
    for title, key in (("source", "verdicts by source"), ("kind", "verdicts by kind")):
        print(f"\n  verdicts by {title}:")
        for s, c in counts[key].items():
            print(f"    {s:24s} " + ", ".join(f"{v} {c[v]}" for v in VERDICTS if c.get(v)))
    print(f"\n  names by the model families that answered (of {len(set(counts['families'].values()))}): "
          + ", ".join(f"{k}: {v}" for k, v in counts["names by families that answered"].items()))
    print("\nasked: " + "; ".join(f"{r}: " + ", ".join(f"{k} {v}" for k, v in a.items())
                                  for r, a in counts["asked"].items()))
    if counts.get("dry run"):
        print("dry run: nothing was asked and nothing written ('would ask' is what a run would ask each reader; "
              "'from a cache' is free)")
    elif ledger is not None:
        print(f"the names not every family confirmed: {paths.shown(ledger)} (private: it holds the camera's labels "
              "and the readers' readings)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", help="a camera's run root (default: the camera the kit works on)")
    ap.add_argument("--sources", default=",".join(SOURCES),
                    help=f"the name sources audited, comma-separated, of {', '.join(NAME_SOURCES)} "
                         f"(default: {', '.join(SOURCES)})")
    ap.add_argument("--kinds", default=",".join(KINDS),
                    help=f"the kinds of screen audited whatever the source, comma-separated, of camkit.reading.QUESTIONS "
                         f"(default: {', '.join(KINDS)})")
    ap.add_argument("--all", action="store_true", help="every value name with a proof frame")
    ap.add_argument("--reader", action="append", default=[], help="a reader to ask, by its name in private/config.json "
                                                                  "(repeatable; default: the second and every third one)")
    ap.add_argument("--definition", default=None, help="the definition file (default: the camera's)")
    ap.add_argument("--cache", default=None, help="the folder the answers are kept in (default: the census's, in the "
                                                  "system's temporary folder; never in the runs)")
    ap.add_argument("--census-cache", action="append", default=[], help="another folder of answers looked in, never "
                                                                        "written (reader_census.py --questions' --cache; "
                                                                        "repeatable)")
    ap.add_argument("--parallel", type=int, default=4, help="questions asked at once of a reader whose config allows "
                                                            "it (default 4, at most 8)")
    ap.add_argument("--timeout", type=float, default=DEFAULTS["timeout"],
                    help=f"seconds a reader gets per question (default {DEFAULTS['timeout']:g})")
    ap.add_argument("--minutes", type=float, default=DEFAULTS["minutes"],
                    help=f"each reader's time; then only answers already kept are taken (default {DEFAULTS['minutes']:g}; "
                         "0: those alone)")
    ap.add_argument("--max-questions", type=int, default=None, help="ask each reader this many questions at most")
    ap.add_argument("--fail-run", type=int, default=rc.FAIL_RUN, help=f"failures in a row after which a reader is asked "
                                                                      f"nothing more (default {rc.FAIL_RUN})")
    ap.add_argument("--dry-run", action="store_true", help="ask nothing and write nothing: count, per reader, the "
                                                          "questions it would be asked and those already kept")
    ap.add_argument("--json", action="store_true", help="the counts as one JSON object")
    args = ap.parse_args(argv)
    if not 1 <= args.parallel <= 8:
        ap.error("--parallel: from 1 to 8")
    bad = [s for s in args.sources.split(",") if s.strip() and s.strip() not in NAME_SOURCES]
    if bad:
        ap.error(f"--sources: some of {', '.join(NAME_SOURCES)}")
    if {k.strip() for k in args.kinds.split(",") if k.strip()} - set(reading.QUESTIONS):
        ap.error(f"--kinds: some of {', '.join(reading.QUESTIONS)}")
    root = paths.run_path(args.root) if args.root else paths.run_root()
    if not root.is_dir():
        sys.exit(f"{root} is not a folder")
    # with --json, standard output carries the JSON alone: what the kit says on the way goes to standard error
    with contextlib.redirect_stdout(sys.stderr) if args.json else contextlib.nullcontext():
        counts, lines = audit(root, args)
        ledger = None if args.dry_run else write_ledger(root, lines)
    if args.json:
        print(json.dumps(counts, indent=1))
    else:
        show(counts, ledger)
    return 0


if __name__ == "__main__":
    sys.exit(main())
