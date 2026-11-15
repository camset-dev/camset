"""The camera owner says, at their own terminal, that every card in the camera holds nothing they want kept.

    .venv/bin/python kit/tools/owner_statement.py cards              # the owner answers its question
    .venv/bin/python kit/tools/owner_statement.py cards --withdraw   # a card the owner keeps is back in the camera

The answer is kept dated in the camera's reviewed scope, beside the owner decisions (camkit.statements; the scope is
started from data/pass2_scope_template.json where the camera has none yet). A row the kit has not yet seen opened on
this body opens only while the latest such statement says the cards are blank (camkit.first_open), and
kit/tools/take_picture.py needs it too. It lifts no guard: the kit still never formats or deletes a card.

Only the owner answers: the question takes a word typed at a real terminal, never a flag, a pipe or a shell an agent
started (camkit.statements.ask). Withdrawing asks nothing, since it only makes the kit stricter. Needs no camera.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, paths, statements  # noqa: E402
from runner import statements_scope_or_exit  # noqa: E402

TEMPLATE = ROOT / "data" / "pass2_scope_template.json"
QUESTION = ("The camera {camera}: every memory card in it holds nothing you want to keep, and these cards stay in it "
            "for the whole mapping. While mapping, the kit opens menu rows it has never opened on this body, and one of "
            "them could act on a card. This lifts nothing: the kit still never formats or deletes a card.")


def main(argv=None, read=None, tty=None, env=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["cards"])
    ap.add_argument("--withdraw", action="store_true", help="a card the owner keeps is back in the camera")
    a = ap.parse_args(argv)
    camera = (paths.camera() or (None,))[0]
    if camera is None:
        sys.exit(paths.no_camera_message())
    scope, f = statements_scope_or_exit("owner_statement.py")
    started = not scope
    if started:
        scope = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    if a.withdraw:
        entry = {"date": statements.today(), "cards": "withdrawn",
                 "why": "the owner withdrew it (kit/tools/owner_statement.py --withdraw)"}
    else:
        why = statements.ask(QUESTION.format(camera=camera), "blank", read=read, tty=tty, env=env)
        if why:
            sys.exit(f"owner_statement.py: {why}")
        entry = {"date": statements.today(), "cards": "blank",
                 "why": "the owner typed it at the terminal (kit/tools/owner_statement.py): every card in the camera "
                        "holds nothing they want kept, and the cards stay in for the mapping"}
    statements.add(f, scope, entry)
    print(f"written into {paths.shown(f)}: {json.dumps(entry)}"
          + (f" (the camera had no reviewed scope: it was started from {paths.shown(TEMPLATE)}; review it before "
             "pass 2)" if started else ""), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
