"""Prove a live exposure setting's values through the Camera Remote SDK: the camera's own setter takes each value, it
is read back, a settings download is diffed against the start, and a proof line goes to the run's proofs, as a menu
proof's would. For a setting no menu list proves on a line (Exposure Comp.'s codes mix 1/3 and 1/2 steps, so every
value must be seen; Flash Comp. likewise): unseen-values plan, Session B, 2026-11-08.

    .venv/bin/python -u kit/provers/sdk_run.py --property ExposureBiasCompensation --row "Exposure Comp." \\
        --values missing --context "Shoot Mode A (dial set with the menu)"
    .venv/bin/python -u kit/provers/sdk_run.py --property FlashCompensation --row "Flash Comp." --values missing --list

--property: only the live exposure the link may set (camkit.safety.SET_PROPERTIES; Link.set refuses any other too).
--row: the menu row the proofs stand for, " > " between submenus; the definition's settings proved through it give
the values. --values: "missing" (the definition's values the row has not proved), "all", or a list of the SDK's own
values (EV x 1000, signed: -1000, 300). --list prints the plan and touches no camera.

First the camera's answer for the property: the values it offers now and whether it takes a set. Not writable: the
hint, and nothing is set or downloaded. Then the start download (kit2_pass2/dat, where kit/tools/replay_proofs.py finds
it), each value the camera offers in turn (set, read back, download, diff against the start, one proof line
{path, kind "list", index, label, via "SDK <property> = <value>", dat, base, changes, applied, final}), the value held
at the start set back last (its proof "final", the start's own value, no change expected), and the session's restore
(camkit.session.finish: the start file uploaded when anything still differs, then checked). A restore that raises or
does not check out exits EXIT_UNRESTORED, so kit/tools/chain.py stops there (runner.restoring, as every prover).

The value held at the start is never named as such, by its number or its label, whatever stops the run (a STOP, a
dropped link, a set back the camera refuses, a restore that does not take): the plan is printed before the camera is
asked, the records that still differ from the start file are counted, not listed, and a refusal is said without the
command. It is the owner's own setting, and only runs/ holds it, in the final proof line and the link's own log of
each command (docs/decisions/0016). The one trace on screen: a planned value it equals has no line of its own, the set
back proving it.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, definitions, safety, session  # noqa: E402
from camkit.runs import Run  # noqa: E402
from runner import EXIT_UNRESTORED, changes_of, proofs_file, read_json, restore_checked, restoring  # noqa: E402

# the properties whose values the definition's labels name, and how: an Exposure Comp. or Flash Comp. label ("+0.3 EV",
# "-1.0 EV") is the SDK's EV x 1000; the others (the live shutter speed, aperture and ISO are in no settings file
# anyway) take a list of the SDK's own values
EV_PROPERTIES = frozenset({"ExposureBiasCompensation", "FlashCompensation"})
EV_LABEL = re.compile(r"\s*([+\-−±]?)\s*(\d+(?:\.\d+)?)\s*EV\s*")


def sdk_value(prop: str, label) -> int | None:
    """The SDK's value for a definition's label: EV x 1000 for the EV properties ("+0.3 EV" is 300, "-4.7 EV" -4700,
    "±0.0 EV" 0), None for any other label or property."""
    m = EV_LABEL.fullmatch(str(label)) if prop in EV_PROPERTIES else None
    if not m:
        return None
    return round(float(m[2]) * 1000) * (-1 if m[1] in ("-", "−") else 1)


def row_settings(doc: dict, row: str) -> list:
    """The definition's settings proved through `row` (its proved.menu holds it, a context after it allowed), the one
    with the most values first: the row's own record, whose values the plan reads."""
    rows = re.compile(re.escape(row) + r"(?: \[[^\]]*\])?$")
    found = [s for s in doc["settings"] if any(rows.fullmatch(m) for m in (s.get("proved") or {}).get("menu") or ())]
    return sorted(found, key=lambda s: (-len(s.get("values") or []), s["key"]))


def planned(doc: dict, prop: str, row: str, values: str) -> list:
    """[(sdk value, label, code)] the run would set, in the definition's order: "missing", the row's own record's values
    not in its proved.values; "all", every value; else the SDK values listed ("-1000,300"), each with the definition's
    label and code when one has that value (else a label made from it, code None)."""
    own = (row_settings(doc, row) or [None])[0]
    named = [(sdk_value(prop, lab), lab, v) for v, lab in (own or {}).get("values") or []]
    named = [n for n in named if n[0] is not None]
    if values in ("missing", "all"):
        if own is None:
            sys.exit(f"sdk_run: no setting of the definition is proved through {row!r}: give the values as a list")
        if not named:
            sys.exit(f"sdk_run: {own['key']}'s labels are not {prop}'s values: give the values as a list")
        done = set((own.get("proved") or {}).get("values") or ()) if values == "missing" else set()
        return [n for n in named if n[2] not in done]
    by_value = {n[0]: n for n in named}
    try:
        wanted = [int(x, 0) for x in values.split(",") if x.strip()]
    except ValueError:
        sys.exit(f"sdk_run: --values {values!r}: missing, all, or the SDK's values, comma-separated (-1000,300)")
    return [by_value.get(x) or (x, f"{x / 1000:+.1f} EV" if prop in EV_PROPERTIES else str(x), None) for x in wanted]


def proof_line(row: str, code, label: str, prop: str, value: int, dat: Path, base: Path, changes, applied: bool,
               final: bool) -> dict:
    """One proof as kit/pass2_report.py reads a list row's: the row's path, the option by its code in the definition
    (a value the definition lacks by "SDK <value>", which no code is: pass2_report keeps the latest proof per index, so
    a number could stand for another option's code), the label, how it was set, the files and what differed."""
    return {"path": row.split(" > "), "kind": "list", "index": code if code is not None else f"SDK {value}",
            "label": label, "via": f"SDK {prop} = {value}", "dat": dat.name, "base": base.name,
            "changes": changes_of(changes), "applied": applied, "final": final}


def told(e: Exception, prop: str) -> str:
    """An exception as the output says it: its type and message, without the command Link._must puts in front ("set
    ExposureBiasCompensation 500: camera kept another value"), so no value set, the start's among them, is printed."""
    text = re.sub(rf"^set {re.escape(prop)} -?\d+:?\s*", "", str(e)).strip()
    return f"{type(e).__name__}: {text}" if text else type(e).__name__


def label_of(plan: list, prop: str, value) -> tuple:
    """(label, code) for a value the camera holds: the plan's, else made from the value (code None)."""
    hit = next((p for p in plan if p[0] == value), None)
    return (hit[1], hit[2]) if hit else (f"{value / 1000:+.1f} EV" if prop in EV_PROPERTIES else str(value), None)


def prove(link, prop: str, row: str, plan: list, out, labels: list) -> tuple:
    """The camera's part, with the link open: its answer for the property (printed, its current value never), the
    start download, each planned value it offers (a set it refuses is a proof with applied false, as a menu's refusal
    is), the start's value set back last, then the session's end (session.finish, the records that differ counted,
    not listed), whatever stopped the values. A STOP or a dropped link stops the values; when the start's value cannot
    be set back, the restore's upload puts it back; a restore that raises exits EXIT_UNRESTORED (runner.restoring).
    Returns (the session's Ending, the start file); (None, None) when the property is not writable now, before
    anything is downloaded or set."""
    from camkit.link import LinkError
    from tools.sdk_set import not_writable_hint
    info = link.get(prop)
    offered = [int(v) for v in info.get("values") or []]
    print(f"{prop}: the camera offers {offered}; writable: {bool(info.get('writable'))}", flush=True)
    if not info.get("writable"):
        print(not_writable_hint(prop), flush=True)
        return None, None
    original = info.get("current")
    todo = [p for p in plan if p[0] in offered and p[0] != original]
    left = [p for p in plan if p[0] not in offered]
    if left:
        print(f"not offered now, left for another state: {', '.join(lab for _, lab, _ in left)}", flush=True)
    start = link.download(f"{prop}-base")
    print(f"start file: {start.name}", flush=True)
    try:
        for value, label, code in todo:
            try:
                ok = bool(link.set(prop, value).get("ok"))
            except LinkError as e:                      # the camera's setter refused it: no change, said
                print(f"  {label}: the camera refused it ({told(e, prop)})", flush=True)
                ok = False
            back = link.get(prop).get("current")
            dat = link.download(f"{prop}{value}")
            ch = camset.diff(camset.read(start), camset.read(dat))
            applied = ok and back == value
            out.write(json.dumps(proof_line(row, code, label, prop, value, dat, start, ch, applied, False)) + "\n")
            out.flush()
            print(f"  {label}: {'set' if applied else 'NOT taken'}, {len(ch)} records "
                  f"{[(c.key, c.after) for c in ch][:4]}", flush=True)
    except Exception as e:                              # a STOP, a dropped link: the restore still runs
        print(f"stopped: {told(e, prop)}", flush=True)
    # the value held at the start goes back last, as a list row's start option is proved last; its line says what it
    # is only in runs/, and the output says only whether the camera came back to its start
    try:
        if original is not None:
            link.set(prop, original)
            dat = link.download(f"{prop}-back")
            ch = camset.diff(camset.read(start), camset.read(dat))
            label, code = label_of(labels, prop, original)
            out.write(json.dumps(proof_line(row, code, label, prop, original, dat, start, ch, True, True)) + "\n")
            out.flush()
            print(f"  the start's value set back: {len(ch)} records differ from the start file", flush=True)
    except Exception as e:                              # the camera refused it, a STOP: the command is not printed
        print(f"the start's value was not set back ({told(e, prop)}); the restore puts the start file back", flush=True)
    with restoring("sdk_run's restore"):
        return session.finish(link, start, show=0), start


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--property", required=True, choices=sorted(safety.SET_PROPERTIES),
                    help="the SDK property (the live exposure only, camkit.safety.SET_PROPERTIES)")
    ap.add_argument("--row", required=True, help="the menu row the proofs stand for (\"Exposure Comp.\")")
    ap.add_argument("--values", default="missing", help="missing, all, or the SDK's values (EV x 1000: -1000,300)")
    ap.add_argument("--context", default=None, help="the state the proofs are made in (proofs.jsonl's context)")
    ap.add_argument("--list", action="store_true", help="print the plan only; no camera")
    a = ap.parse_args(argv)
    doc = definitions.with_evidence(read_json(definitions.active()), definitions.active())
    plan = planned(doc, a.property, a.row, a.values)
    every = planned(doc, a.property, a.row, "all") if a.values != "all" and row_settings(doc, a.row) else plan
    print(f"{a.property} through {a.row!r}: {len(plan)} values to set "
          f"({', '.join(f'{lab} = {v}' for v, lab, _ in plan) or 'none'})", flush=True)
    if a.list or not plan:
        return 0
    from camkit.link import Link
    run = Run("kit2_pass2")
    with proofs_file(run, a.context) as out, Link(run) as link:
        ending, start = prove(link, a.property, a.row, plan, out, every)
    if start is None:
        return 1                                        # not writable: nothing was downloaded or set
    return 0 if restore_checked(run, ending, start, show=0) else EXIT_UNRESTORED


if __name__ == "__main__":
    sys.exit(main())
