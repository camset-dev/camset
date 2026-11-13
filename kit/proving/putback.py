"""What a row's put-back may leave differing from its start without failing: records the camera keeps once an
earlier option set them, a saved value the list does not offer, and copies of a checklist box's tick written from
the first save on. The session's upload puts them back; kit/pass2_report.py reads the notes (attempts.jsonl)."""


def put_back_leftovers(changes: list, history: list) -> dict | None:
    """Why records still differ from the row's start after the saved option is chosen back, when that is the camera's
    doing and no failure (2026-11-07), else None (the put-back went wrong: the row fails as before). `history` holds
    the row's downloads so far as {key: value} of the records differing from the start, the put-back's last.
      "kept"         the record took its value at an earlier option of this row and has held it since: the camera
                     keeps it (S&Q Shoot Mode's exposure-mode record once S&Q Motion was chosen, Rating Set's
                     touched flags, the keys Flexible Exp. Mode reassigns)
      "not_offered"  no download of the row holds the record's start value: the saved value is not among the options
                     the list offers here (Proxy Rec. Settings holding its reset value, 3, which no menu choice
                     writes; Flash Mode's Autoflash in Manual Exposure)
    The session's upload puts them back; the report credits a kept value to the option that first set it (carried
    over), never to the put-back."""
    kept, not_offered = [], []
    for ch in changes:
        values = [h.get(ch.key, ch.before) for h in history]
        first = next((i for i, v in enumerate(values) if v == ch.after), None)
        if first is not None and first < len(values) - 1 and all(v == ch.after for v in values[first:]):
            kept.append(ch.key)
        elif ch.before not in values:
            not_offered.append(ch.key)
        else:
            return None
    return {"kept": kept, "not_offered": not_offered}


def mirrored_boxes(changes: list, history: list, flips: list, labels: list) -> dict | None:
    """Leftover records of a checklist that mirror one box's tick on every save (1 when it is ticked and 0 when not,
    or the reverse) while the start file holds the other value: copies the camera writes from the first save of the
    screen on (Rating Set(Custom Key)'s second copies, 0 until then, 2026-11-07). `flips` holds, for each download of
    `history`, {box: ticked after} for the boxes that visit flipped; a box untouched by a visit is at its start state,
    so the record reads one constant on those. {"kept": [], "not_offered": [], "mirrors": {key: box label}} when
    every leftover is one ({"box": its label, "ticked": the value when the box is ticked}), else None."""
    mirrors = {}
    for ch in changes:
        values = [h.get(ch.key, ch.before) for h in history]
        found = None
        for pol in (1, 0):                             # pol: the value when the box is ticked; 1 (ticked = 1) first
            for b in range(len(labels)):
                touched, rest = False, set()
                for v, fl in zip(values, flips, strict=True):
                    if b in fl:
                        touched = True
                        if v != (pol if fl[b] else 1 - pol):
                            break
                    else:
                        rest.add(v)
                else:
                    if touched and len(rest) <= 1 and (not rest or next(iter(rest)) != ch.before):
                        found = {"box": labels[b], "ticked": pol}
                if found:
                    break
            if found:
                break
        if found is None:
            return None
        mirrors[ch.key] = found
    return {"kept": [], "not_offered": [], "mirrors": mirrors}


def say_put_back(name: str, why: dict):
    for what, keys in (("kept by the camera since an earlier option", why["kept"]),
                       ("the saved value is not offered here", why["not_offered"])):
        if keys:
            print(f"   {name}: {len(keys)} records still differ, {what}: {', '.join(keys)} (the session's upload "
                  f"puts them back)", flush=True)
    if why.get("mirrors"):
        # the boxes joined first: a quote reused inside an f-string's own quotes needs Python 3.12, the kit runs on 3.11
        boxes = ", ".join(f"{k} ({m['box']})" for k, m in why["mirrors"].items())
        print(f"   {name}: {len(why['mirrors'])} records still differ, each a copy of a box's tick written from the "
              f"first save on: {boxes} (the session's upload puts them back)", flush=True)
