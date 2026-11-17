"""How far each movable focus frame travels: the camera's hand table FRAME_TRAVEL written as "frame" on each record that
holds a coordinate of a frame's centre (docs/DATA_CONTRACTS.md, the hand tables file; schemas/definition.schema.json,
a setting's frame).

A FRAME_TRAVEL entry is one kind of frame, in one of two shapes: measured area by area (its places, the [X, Y] record
pairs that hold the centre, and its limits, where the centre stops, by area), or boxes whose size the file holds (the
bounds the whole box stays inside, the sizes the rule was tried at, and each box's areas, size records and places).
Each record of a place gets, for its own axis:

    {"axis": "x", "with": <the place's other record>, "limits": [{"areas": [...], "range": [low, high]}, ...]}
    {"axis": "x", "with": ..., "limits": [{"areas": [...], "inside": [low, high], "size": <width record>,
                                           "sizes_tried": [...]}]}

so an editor that places a frame keeps it, for the area in use, within its range, or for a box within the bounds less
half the size its size record holds in the same section. An entry is written only where the hand evidence shows what
measured it ("evidence": the ILCE-1M2's pass has it put back into the entry, the plain pass reads it apart); the
evidence reaches no field of the definition (docs/decisions/0016). An entry that cannot take effect is printed, "not
applied", and left out whole (frame_problem). Keys, areas and limits only: nothing a camera's file held."""

AXES = ("x", "y")
# the fields of a frame in the order the definition writes them
FRAME_FIELDS = ("axis", "with", "limits")


def placed(e: dict) -> list:
    """[(X key, Y key, {axis: [limit]})] for every place of the FRAME_TRAVEL entry `e`, each limit as the definition
    writes it for that axis: a measured frame's places each with every limit (areas, range), a box's places each with
    the rule and that box's size record (areas, inside, size, sizes_tried where the entry gives them)."""
    out = []
    if "places" in e:
        for kx, ky in e["places"]:
            out.append((kx, ky, {a: [{"areas": list(lim["areas"]), "range": list(lim[a])} for lim in e["limits"]]
                                 for a in AXES}))
        return out
    tried = e.get("sizes_tried") or {}
    for box in e["boxes"]:
        for kx, ky in box["places"]:
            out.append((kx, ky, {a: [{"areas": list(box["areas"]), "inside": list(e["inside"][a]), "size": box["size"][i],
                                      **({"sizes_tried": sorted(tried[a])} if a in tried else {})}]
                                 for i, a in enumerate(AXES)}))
    return out


def frame_problem(e: dict, by_key: dict, areas: set, want: dict) -> str | None:
    """Why the FRAME_TRAVEL entry `e` cannot take effect in the definition (`by_key`, its settings by key; `areas`,
    every value name its settings give; `want`, {key: (axis, other record, its areas)} the entries before it placed),
    in words, or None: each record of a place a setting of the definition that holds a number (no named values), each
    limit within its range where it has one (a box's bounds, for its centre stays inside them), each size record a
    setting of the definition, each area one some setting names as a value, and a record placed twice (by this entry or
    one before it) only on the same axis with the same other record, none of its areas given limits twice."""
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
            new = {a for lim in lims[axis] for a in lim["areas"]}
            had_axis, had_other, had = seen.get(k, (axis, other, set()))
            if (had_axis, had_other) != (axis, other):
                return f"{k} is placed twice, once as the {had_axis} of {had_other}"
            if had & new:
                return f"{k} is given limits twice for {sorted(had & new)[0]!r}"
            seen[k] = (axis, other, had | new)
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
    want = {}
    for name, e in table.items():
        why = frame_problem(e, by_key, areas, {k: (f["axis"], f["with"], {a for lim in f["limits"] for a in lim["areas"]})
                                               for k, f in want.items()})
        if why is None and not (e.get("evidence") or ((evidence or {}).get(name) or {}).get("evidence")):
            why = "nothing in the hand evidence shows what measured it (its \"evidence\" in FRAME_TRAVEL)"
        if why:
            print(f"  frame travel {name}: {why}; not applied")
            continue
        for kx, ky, lims in placed(e):
            for axis, k, other in (("x", kx, ky), ("y", ky, kx)):
                frame = want.setdefault(k, {"axis": axis, "with": other, "limits": []})
                frame["limits"] += lims[axis]
    for s in doc["settings"]:
        if s["key"] in want:
            s["frame"] = {f: want[s["key"]][f] for f in FRAME_FIELDS}
        else:
            s.pop("frame", None)
    if want:
        print(f"frame travel: {len(want)} settings hold a focus frame's place, with how far it travels "
              f"({len(table)} kinds of frame in the hand table)")
    return len(want)
