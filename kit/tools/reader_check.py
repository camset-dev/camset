"""Ask each reader private/config.json lists the question a camera run asks it at its start, with no camera.

    .venv/bin/python kit/tools/reader_check.py            # the readers a run would ask at its start, as it asks them
    .venv/bin/python kit/tools/reader_check.py --all      # every reader listed, the paid ones too (each costs money)
    .venv/bin/python kit/tools/reader_check.py --local    # never a paid one (kit/setup.py runs it so)

The same check as a camera run's start (camkit.vlm.check_readers): each reader is asked to read "MENU 42" off a small
picture drawn in code, through the request a run's question makes (its endpoint, its model, the same question), with
the time a proof's question gets to answer, at once. A hosted, paid reader (Claude, or a service named with
"api_key_env") plays only the roles the config gives it and never stands in for another: as the second reader it is
asked with the local ones, as a run asks it on every proof; as the third only when no local reader answered, and the
tool says so first; one with no role is never asked by a run. --all asks every reader listed.
Nothing is cached: every reader is asked afresh, every time.

It prints, per reader listed: its name, kind and model (the model the server says answered beside it, when that is
another id), the roles it plays, and whether it answered, how long it took, or the error (the HTTP status and the
server's own short message, "HTTP 507 Insufficient Storage: ..."); then whether a camera run would start. Addresses and
keys are taken out of all it prints (camkit.vlm.scrub), and a model id that is a path shows its last part. It opens no
camera link, needs no camera, and writes nothing under runs/.

Exit status: 0 when a camera run would start (a reader answered; the second reader's own, or a local one that may
stand in for it), 1 when it would stop, 3 when there is nothing to ask (no private/config.json, or no reader listed in
it), 4 with --local when only paid readers are listed, 5 when private/config.json cannot be read (not JSON, not the
kit's settings) or its readers cannot be read as readers (an entry with no "name", two with one name, "roles" that is
no object of names or gives a role to no reader listed), said in one sentence that names no path and nothing it holds;
6 when the check itself failed (a fault in the kit, said as "reader_check failed: <type>: <message>", never blamed on
the config).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ConfigMissing, vlm  # noqa: E402

NOTHING_TO_ASK = 3          # the exit status with no private/config.json or no reader listed (kit/setup.py reads it)
ONLY_PAID = 4               # the exit status of --local when every reader listed is a paid one (kit/setup.py reads it)
UNREADABLE = 5              # the exit status when private/config.json or its readers cannot be read (kit/setup.py)
FAILED = 6                  # the exit status when the check itself failed, a fault in the kit, not the config (kit/setup.py)
MODES = {"all": "all", "local": "never"}        # --all, --local: vlm.start_check's ask_paid


def table(checks: list) -> list:
    """One line per reader: name, kind, model (and the server's, where it names another), roles, and what came of it."""
    rows = [("reader", "kind", "model", "roles", "result")]
    for c in checks:
        if not c.asked:
            result = f"not asked: {c.not_asked}"
        elif c.ok:
            result = f"answered in {c.seconds:.1f} s: {c.said!r}"
        else:
            took = f" after {c.seconds:.1f} s" if c.seconds is not None else ""
            result = f"NO ANSWER{took}: {c.error}"
        model = (c.model or "-") + (f" (server: {c.served})" if c.served else "")
        rows.append((c.name, c.kind + (", paid" if c.paid else ""), model, ", ".join(c.roles) or "-", result))
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    return ["  " + "  ".join(r[i].ljust(widths[i]) for i in range(4)) + "  " + r[4] for r in rows]


def as_a_run_sees_them(checks: list) -> list:
    """The Checks a camera run's start would have: with --all, a paid reader's answer counts only where a run would ask
    it (the second reader; the third when no local reader answered)."""
    local_ok = any(c.ok and not c.paid for c in checks)
    return [c for c in checks if not c.paid or "second" in c.roles or (c.roles and not local_ok)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    paid = ap.add_mutually_exclusive_group()
    paid.add_argument("--all", action="store_true", help="also ask the paid readers, and those no run asks")
    paid.add_argument("--local", action="store_true", help="never ask a paid reader")
    ap.add_argument("--timeout", type=float, default=vlm.CHECK_TIMEOUT,
                    help=f"seconds each reader gets to answer (default {vlm.CHECK_TIMEOUT:g}, a run's)")
    a = ap.parse_args(argv)
    mode = MODES["all"] if a.all else MODES["local"] if a.local else "needed"
    print(f"reader check: each reader is asked to read {vlm.CHECK_TEXT!r} off a small picture, as a camera run asks it "
          f"at its start, with {a.timeout:g} s to answer", flush=True)
    try:                            # the config read: its faults are the config's, said in one plain sentence
        listed = vlm.readers(stop=True)
    except ConfigMissing as e:
        print(e, flush=True)
        return NOTHING_TO_ASK if vlm.NO_READER in str(e) or "No private/config.json" in str(e) else UNREADABLE
    except vlm.CONFIG_FAULTS as e:
        print(vlm.unreadable(e), flush=True)
        return UNREADABLE
    try:                            # any other fault is the kit's, never blamed on the config
        vlm.role_players()          # a role given to no reader listed: ConfigMissing, the config's
        if a.local and all(vlm.paid(r) for r in listed):
            print(f"only paid readers are listed ({', '.join(repr(r['name']) for r in listed)}): none is asked with "
                  "--local. kit/tools/reader_check.py --all asks them, each question costing money.", flush=True)
            return ONLY_PAID
        checks = vlm.start_check(ask_paid=mode, timeout=a.timeout, say=lambda s: print(s, flush=True))
        stand_ins, why = vlm.verdict(as_a_run_sees_them(checks))
    except ConfigMissing as e:
        print(e, flush=True)
        return UNREADABLE
    except Exception as e:       # noqa: BLE001 - the tool's own fault: said as itself, scrubbed, never as the config's
        print(f"reader_check failed: {type(e).__name__}: {vlm.scrub(e)}", flush=True)
        return FAILED
    print("\n".join(table(checks)), flush=True)
    asked = [c for c in checks if c.asked]
    answered = [c for c in asked if c.ok]
    unasked_second = next((c for c in checks if "second" in c.roles and not c.asked), None)
    if why:
        verdict_words = (f"no local reader answered, and the second reader, {unasked_second.name!r}, is paid and not "
                         "asked with --local: a camera run would start only if it answers" if unasked_second else
                         f"a camera run would stop before its link ({why})")
        print(f"{len(answered)} of {len(asked)} readers asked answered: {verdict_words}. Start each reader's server, or "
              "give it what it says it lacks (an HTTP 507 is the server short of memory or disk, a 503 one still "
              "loading its model), and check its \"url\" and \"model\" in private/config.json (docs/QUICKSTART.md, "
              "\"Choosing a reader\").", flush=True)
        return 1
    subs = "".join(f"; {sub['name']!r} would stand in as the {name} reader" for name, sub in stand_ins.items())
    note = (f"; the second reader, {unasked_second.name!r}, is paid and not asked with --local: a run asks it at its "
            "start, a local reader that answered standing in if it does not answer" if unasked_second else "")
    print(f"{len(answered)} of {len(asked)} readers asked answered: a camera run would start{subs}{note}.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
