"""Set live exposure values through the Camera Remote SDK, each read back (2026-10-31).

    .venv/bin/python -u kit/tools/sdk_set.py ShutterSpeed=66036 FNumber=800

The live shutter speed and aperture are in no settings file, so a restored file does not put them
back: set them back here at the end. Only exposure properties are accepted (camkit.safety.SET_PROPERTIES, which
Link.set enforces too); values are the SDK's (ShutterSpeed: numerator << 16 | denominator, 1/250 is 65786; FNumber:
F x 100).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import safety  # noqa: E402
from camkit.link import Link, LinkError  # noqa: E402
from camkit.runs import Run  # noqa: E402

ALLOWED = safety.SET_PROPERTIES
# what to do when the camera answers "not writable now": the mode dial decides which exposure values it sets itself
NOT_WRITABLE = {
    "ShutterSpeed": "on the mode dial's A, P or Auto the camera sets ShutterSpeed itself: turn the dial to S or M",
    "FNumber": "on the mode dial's S, P or Auto the camera sets FNumber itself: turn the dial to A or M",
    # kit/provers/sdk_run.py's two (unseen-values plan, Session B): the flash is a physical action, the mode is not
    "FlashCompensation": "the camera takes FlashCompensation only with a flash on the shoe, switched on: ask the owner "
                         "to switch it on (one action), and off again after; no prover fires it",
    "ExposureBiasCompensation": "the camera takes ExposureBiasCompensation in P, A and S (and in M with ISO AUTO): put "
                                "it in A by the menu (kit/provers/mode_switch.py --to A --keep), then try again",
}


def not_writable_hint(name: str) -> str:
    return NOT_WRITABLE.get(name, f"the camera does not take {name} in its present mode: check the mode dial and the "
                                  f"settings that set {name} automatically, then try again")


def main():
    pairs = []
    for arg in sys.argv[1:]:
        name, _, value = arg.partition("=")
        try:
            number = int(value, 0)
        except ValueError:
            number = None
        if name not in ALLOWED or number is None:
            sys.exit(f"{arg!r}: give NAME=VALUE with NAME one of {sorted(ALLOWED)} and VALUE a number (the SDK's)")
        pairs.append((name, number))
    if not pairs:
        sys.exit("nothing to set")
    with Link(Run("kit2_sdk_exposure")) as link:
        for name, value in pairs:
            before = link.get(name).get("current")
            try:
                r = link.set(name, value)
            except LinkError as e:                  # the camera refused the set: say so, never a traceback
                print(f"{name}: {before} -> {value} not set ({e})", flush=True)
                if "not writable" in str(e):
                    print(not_writable_hint(name), flush=True)
                sys.exit(1)
            print(f"{name}: {before} -> {r.get('current')} ({'ok' if r.get('ok') else r.get('error')})", flush=True)
            if not r.get("ok"):
                sys.exit(1)


if __name__ == "__main__":
    main()
