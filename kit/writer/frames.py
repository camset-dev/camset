"""How far each movable focus frame travels: the camera's hand table FRAME_TRAVEL written as "frame" on each record that
holds a coordinate of a frame's centre (docs/DATA_CONTRACTS.md, the hand tables file; schemas/definition.schema.json,
a setting's frame).

A FRAME_TRAVEL entry is one kind of frame, in one of two shapes: measured area by area (its places, the [X, Y] record
pairs that hold the centre, and its limits, where the centre stops, by area), or boxes whose size the file holds (the
bounds the whole box stays inside, the sizes the rule was tried at, and each box's areas, size records and places).
Where the limits depend on another setting (the a1 II's Aspect Ratio), the entry names it ("by") and each limit the
values it is for ("when"); boxes then give, for each value, the part of the grid's span the picture covers on each axis
("pictures", with the grid's span). Each record of a place gets, for its own axis:

    {"axis": "x", "with": <the place's other record>, "by": <setting>,
     "limits": [{"areas": [...], "when": [...], "range": [low, high]}, ...]}
    {"axis": "x", "with": ..., "by": ..., "limits": [{"areas": [...], "inside": [low, high], "size": <width record>,
     "grid": 640, "pictures": [{"when": [...], "fraction": [n, d], "sizes_tried": [...] or "sizes_range": [low, high]},
     ...]}]}

limits that differ only in their values merged into one ("when" the values of all). An editor that places a frame
keeps it, for the area in use (and the value the section holds of "by"), within its range, or for a box within the
limits box_limits gives from the size its size record holds in the same section. An entry is written only where the
hand evidence shows what measured it ("evidence": the ILCE-1M2's pass has it put back into the entry, the plain pass
reads it apart); the evidence reaches no field of the definition (docs/decisions/0016). An entry that cannot take
effect is printed, "not applied", and left out whole (frame_problem). Keys, areas and limits only: nothing a camera's
file held."""
import math
from fractions import Fraction

AXES = ("x", "y")
# the fields of a frame in the order the definition writes them
FRAME_FIELDS = ("axis", "with", "by", "limits")


def _merged(limits: list, key) -> list:
    """`limits` (each with "when", or none) with those alike but for their values merged, the values joined in order;
    `key` gives what must be alike. The first's place in the list kept."""
    out, at = [], {}
    for lim in limits:
        k = key(lim)
        if "when" in lim and k in at:
            at[k]["when"] = sorted(set(at[k]["when"]) | set(lim["when"]))
            continue
        at[k] = lim
        out.append(lim)
    return out


def placed(e: dict) -> list:
    """[(X key, Y key, {axis: [limit]})] for every place of the FRAME_TRAVEL entry `e`, each limit as the definition
    writes it for that axis: a measured frame's places each with every limit (areas, when, range), those alike on the
    axis but for their values merged; a box's places each with the rule and that box's size record (areas, inside, size,
    and sizes_tried, or the grid and each value's picture with its sizes tried or the range they were tried across,
    those alike on the axis merged)."""
    out = []
    if "places" in e:
        per = {a: _merged([{"areas": list(lim["areas"]), **({"when": list(lim["when"])} if "when" in lim else {}),
                            "range": list(lim[a])} for lim in e["limits"]],
                          lambda lim: (tuple(lim["areas"]), tuple(lim["range"]))) for a in AXES}
        return [(kx, ky, {a: [dict(lim, **({"when": list(lim["when"])} if "when" in lim else {})) for lim in per[a]]
                          for a in AXES}) for kx, ky in e["places"]]
    tried = e.get("sizes_tried") or {}

    def pictures(a: str) -> list:
        pics = [{"when": list(p["when"]), "fraction": list(p[a]),
                 **({"sizes_tried": sorted(p["sizes_tried"][a])} if "sizes_tried" in p else {}),
                 **({"sizes_range": list(p["sizes_range"][a])} if "sizes_range" in p else {})} for p in e["pictures"]]
        return _merged(pics, lambda p: (tuple(p["fraction"]), tuple(p.get("sizes_tried") or ()),
                                        tuple(p.get("sizes_range") or ())))
    for box in e["boxes"]:
        for kx, ky in box["places"]:
            lims = {}
            for i, a in enumerate(AXES):
                lim = {"areas": list(box["areas"]), "inside": list(e["inside"][a]), "size": box["size"][i]}
                if "pictures" in e:
                    lim.update(grid=e["grid"][a], pictures=pictures(a))
                elif a in tried:
                    lim["sizes_tried"] = sorted(tried[a])
                lims[a] = [lim]
            out.append((kx, ky, lims))
    return out


def _nearest(x: Fraction, centre: Fraction) -> int:
    """`x` to the nearest whole number, a half toward `centre`."""
    low = math.floor(x)
    if x - low != Fraction(1, 2):
        return math.floor(x + Fraction(1, 2))
    return low + 1 if x < centre else low


def box_limits(lim: dict, size: int, value: int | None = None) -> tuple | None:
    """(lowest, highest) a box's centre takes on one axis, by a box limit as the definition writes it (`lim`): the whole
    box, `size` wide on that axis, stays inside the bounds ("inside") and inside the picture, which covers the part of
    the grid's span "fraction" gives, centred, for the `value` of the frame's "by" ("pictures"; the whole span without
    them); the grid stretched over the picture, the bounds and the size measured on the whole span, each end rounded to
    the nearest whole number, a half toward the centre. None when no picture is for `value`."""
    lo_in, hi_in = (Fraction(str(v)) for v in lim["inside"])
    half = Fraction(size, 2)
    if "pictures" not in lim:
        return _nearest(lo_in + half, (lo_in + hi_in) / 2), _nearest(hi_in - half, (lo_in + hi_in) / 2)
    pic = next((p for p in lim["pictures"] if value in p["when"]), None)
    if pic is None:
        return None
    c, f = Fraction(lim["grid"], 2), Fraction(*pic["fraction"])
    lo_s, hi_s = max(lo_in, c - c * f) + half, min(hi_in, c + c * f) - half
    return _nearest(c + (lo_s - c) / f, c), _nearest(c + (hi_s - c) / f, c)


def frame_problem(e: dict, by_key: dict, areas: set, want: dict) -> str | None:
    """Why the FRAME_TRAVEL entry `e` cannot take effect in the definition (`by_key`, its settings by key; `areas`,
    every value name its settings give; `want`, {key: (axis, other record, by, its areas by value)} the entries before
    it placed), in words, or None: each record of a place a setting of the definition that holds a number (no named
    values), each limit within its range where it has one (a box's bounds, for its centre stays inside them), each size
    record a setting of the definition, each area one some setting names as a value, the setting its limits depend on
    ("by") one of the definition's and each value a limit or a picture names one of that setting's, and a record placed
    twice (by this entry or one before it) only on the same axis with the same other record and setting, none of its
    areas given limits twice for one value."""
    by = e.get("by")
    if by is not None:
        s = by_key.get(by)
        if s is None:
            return f"the definition lacks {by}, the setting the limits depend on"
        codes = {v for v, _ in s.get("values") or []}
        named = {v for lim in e.get("limits") or e.get("pictures") or [] for v in lim["when"]}
        if named - codes:
            return f"{by} has no value {sorted(named - codes)[0]}"
    seen = dict(want)
    for kx, ky, lims in placed(e):
        for axis, k, other in (("x", kx, ky), ("y", ky, kx)):
            s = by_key.get(k)
            if s is None:
                return f"the definition lacks {k}"
            if s.get("values"):
                return f"{k} names values, so it holds no position"
            lo, hi = s.get("range") or (None, None)
            for lim in lims[axis]:
                span = lim.get("range") or lim["inside"]
                if lo is not None and not lo <= span[0] <= span[1] <= hi:
                    return f"{k}'s limits {span} are outside its range [{lo}, {hi}]"
                if "size" in lim and lim["size"] not in by_key:
                    return f"the definition lacks {lim['size']}, the box's size"
                missing = [a for a in lim["areas"] if a not in areas]
                if missing:
                    return f"no setting of the definition names the area {missing[0]!r} as a value"
            new = {(a, v) for lim in lims[axis] for a in lim["areas"]
                   for v in (lim.get("when") or [None] if "pictures" not in lim else [p for pic in lim["pictures"] for p in pic["when"]])}
            had_axis, had_other, had_by, had = seen.get(k, (axis, other, by, set()))
            if (had_axis, had_other) != (axis, other):
                return f"{k} is placed twice, once as the {had_axis} of {had_other}"
            if had_by != by:
                return f"{k} is placed twice, its limits depending once on {had_by} and once on {by}"
            twice = {a for a, v in had for b, w in new if a == b and (v == w or v is None or w is None)}
            if twice:
                return f"{k} is given limits twice for {sorted(twice)[0]!r}"
            seen[k] = (axis, other, by, had | new)
    return None


def with_frames(doc: dict, table: dict, evidence: dict | None = None) -> int:
    """The camera's hand table FRAME_TRAVEL written as "frame" on each record of each place of each entry (placed),
    in the table's order, and taken off every other setting. An entry is written only where the hand evidence shows
    what measured it: its "evidence", in the entry itself (the ILCE-1M2's pass, the hand evidence put back) or in
    `evidence`, the plain pass's FRAME_TRAVEL part of the hand evidence read apart ({name: {"evidence": ...}}). An
    entry that cannot take effect (frame_problem) is printed, "not applied", and left out whole. Returns how many
    settings carry a frame."""
    by_key = {s["key"]: s for s in doc["settings"]}
    areas = {lab for s in doc["settings"] for _, lab in s.get("values") or []}
    want, by_of, values_of = {}, {}, {}
    for name, e in table.items():
        why = frame_problem(e, by_key, areas, {k: (f["axis"], f["with"], by_of[k], values_of[k]) for k, f in want.items()})
        if why is None and not (e.get("evidence") or ((evidence or {}).get(name) or {}).get("evidence")):
            why = "nothing in the hand evidence shows what measured it (its \"evidence\" in FRAME_TRAVEL)"
        if why:
            print(f"  frame travel {name}: {why}; not applied")
            continue
        for kx, ky, lims in placed(e):
            for axis, k, other in (("x", kx, ky), ("y", ky, kx)):
                frame = want.setdefault(k, {"axis": axis, "with": other, **({"by": e["by"]} if "by" in e else {}),
                                            "limits": []})
                frame["limits"] += lims[axis]
                by_of[k] = e.get("by")
                values_of[k] = values_of.get(k, set()) | {
                    (a, v) for lim in lims[axis] for a in lim["areas"]
                    for v in (lim.get("when") or [None] if "pictures" not in lim else [p for pic in lim["pictures"] for p in pic["when"]])}
    for s in doc["settings"]:
        if s["key"] in want:
            s["frame"] = {f: want[s["key"]][f] for f in FRAME_FIELDS if f in want[s["key"]]}
        else:
            s.pop("frame", None)
    if want:
        print(f"frame travel: {len(want)} settings hold a focus frame's place, with how far it travels "
              f"({len(table)} kinds of frame in the hand table)")
    return len(want)
