"""The camera's options as it lays them out: a carousel's main options, each with the choice it opens on its own
axis (Focus Area: Wide, Zone, Center Fix, Spot with its sizes, Expand Spot, Custom with its three slots, Tracking with
its start areas). kit/schema_update.py writes it into a definition as a setting's "option_tree" (docs/DATA_CONTRACTS.md,
"The camera's options, nested"), so the editor shows a setting's options as the camera does while "values" stays the
flat list every other consumer uses.

The camera decides, never the labels: a label of the shape "Main: Sub" is a nest only when the camera showed one. Pass
2 proves a carousel row's options as "dialog" proofs (the main options in the camera's order, each with the value its
axis held: "Spot: M") and the choices on an option's axis as "axis" proofs (the option they belong to in "option", the
camera's whole text in "label", the presses to the right from the held value in "index"), in its proofs.jsonl. From
them, a setting placed on that row ("row") gets a tree when its values are the row's whole choice: each of the row's
main options holds at least one of its values, each value is in exactly one, and at least one option holds two or
more. A value matches an option's axis by the camera's text for it, a plain option by its label, and a value left over
by the start of one option's name ("Self-timer" for Self-timer(Single)); signs, spaces and the screen readers' slips
("SpotS", Cyrillic look-alikes) do not count. Anything else gets no tree, and why_not says why: a list the camera
shows flat (White Balance's four Fluor. options are four options of its list) stays flat. A setting no run places on
a row shares the tree of one whose values are identical, in the same tab and group family (shared(): Registered AF
area's areas, Focus Area memory's values kept again).

An option's choices come in the camera's order along its axis (it wraps), from the one the setting lists first: Spot's
sizes XL, L, M, S, XS. A choice is labelled by its value's label without the option's name ("Spot: XL" under Spot is
"XL"), unless only a number would be left ("Custom 1" stays "Custom 1").
"""
import collections
import json
import re
import unicodedata
from pathlib import Path

from . import jsonl
from .match import LOOKALIKES


def clean(label) -> str:
    """The camera's text without the screen readers' slips: look-alike letters, "lmg" for "Img", doubled spaces."""
    t = unicodedata.normalize("NFKC", str(label or "")).translate(LOOKALIKES)
    t = re.sub(r"\blmg\b", "Img", t)
    return re.sub(r"\s+", " ", t).strip()


def norm(label) -> str:
    """A label as it is matched: letters, digits and "+" only ("Hi+" is not "Hi"), in lower case."""
    return re.sub(r"[^a-z0-9+]+", "", clean(label).lower())


Main = collections.namedtuple("Main", "name held subs")      # held: the dialog's labels; subs: the axis, or ()


def read_proofs(run: Path) -> list:
    """The proofs of a pass-2 run folder (proofs.jsonl), [] without one; a last line cut short by a crash is left
    out (camkit.jsonl)."""
    return jsonl.read(Path(run) / "proofs.jsonl")


def axis_name(option: str, labels: list) -> str:
    """An axis option's name: the proof's "option", or, when that is itself one of the choices (the held one: "Custom
    1"), the words every choice starts with ("Custom")."""
    if norm(option) not in {norm(x) for x in labels}:
        return clean(option)
    words = [clean(x).split(" ") for x in labels]
    common = []
    for ws in zip(*words):  # noqa: B905 (shortest label bounds the prefix)
        if len(set(ws)) > 1:
            break
        common.append(ws[0])
    return " ".join(common).rstrip(":").strip() or clean(option)


def rows(proofs: list) -> dict:
    """{row path (tuple): [Main, ...] in the camera's order} for every row with an axis proof: the main options from
    its dialog proofs, by the index the camera showed them at, each with the choices of its axis, if it has one. A row
    proved in several contexts (another shooting mode, the camera held another way) is read in the one that showed
    the most options, the first of them on a tie: another mode's menu may lack an option and so number the rest
    differently (Movie's White Balance has no Underwater Auto)."""
    dialogs = collections.defaultdict(dict)                                     # path -> context -> {index: [labels]}
    axes = collections.defaultdict(lambda: collections.defaultdict(dict))       # path -> option -> context -> {label: index}
    for p in proofs:
        path, ctx = tuple(p.get("path") or ()), json.dumps(p.get("context"))
        if p.get("kind") == "axis" and p.get("option"):
            seen = axes[path][clean(p["option"])].setdefault(ctx, {})
            seen.setdefault(clean(p["label"]), p.get("index", 0))
        elif p.get("kind") in ("dialog", "list") and isinstance(p.get("index"), int):
            labels = dialogs[path].setdefault(ctx, {}).setdefault(p["index"], [])
            if clean(p["label"]) not in labels:
                labels.append(clean(p["label"]))
    out = {}
    for path, options in axes.items():
        if path not in dialogs:
            continue
        cycles = {}
        for option, by_context in options.items():
            most = max(by_context.values(), key=len)        # the context that saw the most choices, first on a tie
            cycles[option] = sorted(most, key=lambda lab: most[lab])
        shown = max(dialogs[path].values(), key=len)
        mains = []
        for index in sorted(shown):
            held = shown[index]
            mine = [o for o, cyc in cycles.items() if ({norm(o)} | {norm(x) for x in cyc}) & {norm(h) for h in held}]
            if len(mine) == 1:
                mains.append(Main(axis_name(mine[0], cycles[mine[0]]), tuple(held), tuple(cycles[mine[0]])))
            else:
                mains.append(Main(held[0], tuple(held), ()))
        out[path] = mains
    return out


def sub_label(label: str, main: str) -> str:
    """A choice's label under its option: the value's label without the option's name and the colon or space after
    it, unless only a number would be left."""
    if label.startswith(main) and label[len(main):len(main) + 1] in (":", " "):
        rest = label[len(main) + 1:].strip()
        if rest and not rest.isdigit():
            return rest
    return label


def tree(values: list, mains: list) -> tuple:
    """(the option tree of a setting with these [value, label] pairs on a row with these main options, None) or
    (None, why not, in a few words)."""
    at = {}                                         # value -> the main options it matches
    for v, lab in values:
        n = norm(lab)
        for i, m in enumerate(mains):
            if m.subs and n in {norm(x) for x in m.subs}:
                at.setdefault(v, []).append(i)
    for v, lab in values:
        if v in at:
            continue
        n = norm(lab)
        for i, m in enumerate(mains):
            if n == norm(m.name) or n in {norm(h) for h in m.held}:
                at.setdefault(v, []).append(i)
    taken = {i for got in at.values() for i in got}
    for v, lab in values:                           # left over: the start of one option's name nothing matched yet
        if v not in at:
            n = norm(lab)
            fits = [i for i, m in enumerate(mains) if i not in taken and n and norm(m.name).startswith(n)]
            if len(fits) == 1:
                at[v] = fits
                taken.add(fits[0])
    twice = [lab for v, lab in values if len(at.get(v, [])) > 1]
    if twice:
        return None, f"{', '.join(twice)} match more than one option of the row"
    loose = [lab for v, lab in values if v not in at]
    if loose:
        return None, f"{', '.join(loose[:4])}{' …' if len(loose) > 4 else ''} match no option of the row"
    by_main = collections.defaultdict(list)
    for v, lab in values:
        by_main[at[v][0]].append((v, lab))
    empty = [m.name for i, m in enumerate(mains) if not by_main.get(i)]
    if empty:
        return None, f"the row's option(s) {', '.join(empty)} hold none of its values: it is a part of the row's choice"
    if all(len(by_main[i]) < 2 for i in by_main):
        return None, "each of its values is an option of its own on the row: the camera shows them flat"
    first = {v: k for k, (v, _) in enumerate(values)}
    nodes = []
    for i, m in enumerate(mains):
        got = by_main[i]
        if len(got) == 1:
            nodes.append({"label": got[0][1], "value": got[0][0]})
            continue
        cycle = [norm(x) for x in m.subs]
        off = [lab for _, lab in got if norm(lab) not in cycle]
        if off:
            # matched by the option's name or the label it held, but not one of the choices on its axis: the camera
            # gives such a value no place in the option's order, and a tree is never guessed
            return None, f"{', '.join(off)} {'is' if len(off) == 1 else 'are'} not on {m.name}'s axis"
        got.sort(key=lambda p: cycle.index(norm(p[1])))
        lead = min(range(len(got)), key=lambda k: first[got[k][0]])
        got = got[lead:] + got[:lead]
        nodes.append({"label": m.name, "options": [[v, sub_label(lab, m.name)] for v, lab in got]})
    return nodes, None


def nested_looking(s: dict) -> bool:
    """Labels of the shape "Main: Sub" with two or more under one main: what the audit lists when no tree is written."""
    mains = collections.Counter(lab.split(": ", 1)[0] for _, lab in s.get("values") or [] if ": " in lab)
    return any(n >= 2 for n in mains.values())


def family(s: dict) -> tuple:
    """A setting's tab and group family: its group up to the first " › " ("Focus Area" for "Focus Area › Spot")."""
    return s.get("tab"), (s.get("group") or "").split(" › ")[0]


def shared(doc: dict, found: dict, by_row: dict) -> dict:
    """{key: the key whose tree it shares} for the settings that get another's tree (trees()): a setting with two or
    more `values` and no range, not an option's own choice (`under_option`), on no row the proofs give main options
    for (its row's verdict, tree or none, stands), whose `values` are identical, number for number and label for
    label in the same order, to those of a setting with a tree in the same tab and group family (family()): the
    same record kept again where no run walked it (Registered AF area beside Focus Area memory). When the settings it
    matches give different trees it gets none. Values only alike (fewer, or the same labels numbered otherwise) are
    another record's choice, which the camera may show flat (Tracking's start areas), so they never share."""
    out = {}
    for s in doc["settings"]:
        values = s.get("values") or []
        if s["key"] in found or s.get("under_option") or s.get("range") or len(values) < 2 or tuple(s.get("row") or ()) in by_row:
            continue
        same = [o for o in doc["settings"] if o["key"] in found and o["key"] not in out and family(o) == family(s) and o.get("values") == values]
        if same and len({json.dumps(found[o["key"]]) for o in same}) == 1:
            out[s["key"]] = same[0]["key"]
    return out


def trees(doc: dict, proofs: list, shared_from: dict | None = None) -> tuple:
    """({key: option tree} for the settings of a definition that get one from these proofs, a row's own or one shared
    with a setting of the same values (shared(); `shared_from`, when given, gets {key: the key it shares with}),
    {key: why not} for those that sit on a row with an axis or whose labels look nested and get none)."""
    found, why_not = {}, {}
    by_row = rows(proofs)
    for s in doc["settings"]:
        values = s.get("values") or []
        mains = by_row.get(tuple(s.get("row") or ()))
        if mains is None:
            if nested_looking(s):
                why_not[s["key"]] = ("not placed on a menu row" if not s.get("row") else
                                     "its row has no carousel axis in the proofs: the camera lists these options flat")
            continue
        if s.get("under_option"):
            why_not[s["key"]] = f"the choice for the option {s['under_option']} (shown under it already)"
            continue
        if len(values) < 2 or s.get("range"):
            continue
        got, why = tree(values, mains)
        if got:
            found[s["key"]] = got
        else:
            why_not[s["key"]] = why
    for k, src in shared(doc, found, by_row).items():
        found[k] = found[src]
        why_not.pop(k, None)
        if shared_from is not None:
            shared_from[k] = src
    return found, why_not


def with_tree(s: dict, got) -> dict:
    """The setting with its option tree right after "values", and without one when it has none."""
    out = {k: v for k, v in s.items() if k != "option_tree"}
    if not got:
        return out
    placed = {}
    for k, v in out.items():
        placed[k] = v
        if k == "values":
            placed["option_tree"] = got
    return placed if "values" in out else {**out, "option_tree": got}


def shown(got: list) -> str:
    """A tree in one line, for the audit: "Wide, Spot [XL, L, M], Custom [Custom 1, Custom 2]"."""
    return ", ".join(n["label"] if "value" in n else f"{n['label']} [{', '.join(lab for _, lab in n['options'])}]" for n in got)
