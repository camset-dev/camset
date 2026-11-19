"""An option a list or a side list draws grey (prove_run.prove_row, proving.sidelists.prove_side_row; the owner,
2026-11-19: "your selecting grey out items and assuming they are changing in PP"): it is never chosen, and why it is
greyed is read once a row.

    what = greyed.judge(cam, name, label, k, saved, kind, back)
    ENTER   drawn white, or whether it is drawn grey cannot be told (said, option by option), or the value the row was
            saved on (its put-back): entered as before
    TRY     the row's first option drawn grey whose reason the camera's Help did not give: the one Enter of the row, to
            read the camera's notice (the owner's way, 2026-10-28: "if you hit center button to activate it, the popup
            says why"), never a second on that row in the run; not with NEVER_ENTER
    SKIP    drawn grey and its reason read, or NEVER_ENTER: no key at all on it; the line says greyed as drawn

The reason (REASONS, a row's for the run): first the camera's own Help on that first grey option, through the kit's
guarded Help alone (drive.help_refused: a menu or option screen whose footer draws the help button; help_run.guide:
C4, the popup's In-Camera Guide only, OK back onto the option; camkit.live and camkit.link judge the C4 as ever,
never in Playback), its blocker taken only from the refusal the kit knows ("not available as follows <row>":
coverage.blocker_of, never the value after it); on the a1 II the guide of a greyed row or option says only "This
function is currently disabled." (kit2_help), so then the notice of the one Enter gives it (coverage.blocker_of: the
row, the equipment or a remote session). A grey option that the Enter applies after all was misjudged: the row's
other grey options are entered as before. Whether an option is drawn grey: proving.screens.drawn_grey.
"""
import re
from typing import NamedTuple

from camkit import coverage

from .base import Failed
from .screens import drawn_grey

ENTER, TRY, SKIP = "enter", "try", "skip"
NEVER_ENTER = False         # --never-enter-grey (main sets it): no Enter on an option drawn grey, ever
REASONS: dict = {}          # {row name: Reason, or MISJUDGED} read this run: one try a row
LABELS: set | None = None   # the row labels a blocker is named by (labels(): the definition's and the page model's)
MISJUDGED = "misjudged"     # a grey option the camera applied: the row's others are entered as before
FOLLOWS = re.compile(r"not available as follows\b", re.I)


def _say(message: str) -> None:
    print(message, flush=True)


class Reason(NamedTuple):
    """Why a row's options are greyed, as read once: the blocker (coverage.blocker_of's: {"row"}, {"equipment"} or
    {"remote"}; None where none was named), where it was read ("help", "notice", or None: not read), the frame it was
    read on and the option it was read on."""
    blocker: dict | None
    by: str | None
    frame: str | None
    entry: str | None

    def said(self) -> str:
        """The reason as the run says it."""
        what = (f"blocked by {self.blocker.get('row') or self.blocker.get('equipment') or 'a remote session'}"
                if self.blocker else "no blocker named")
        where = {"help": "the camera's Help", "notice": "the camera's notice"}.get(self.by)
        return f"{what} ({where} on {self.entry!r}, {self.frame})" if where else f"{what} (no reason read)"

    def kept(self) -> dict:
        """What a proof line keeps of it: the blocker, and where it was read."""
        return {**({"blocker": self.blocker} if self.blocker else {}),
                **({"reason": {"from": self.by, "frame": self.frame, "entry": self.entry}} if self.by else {})}


def labels() -> set:
    """The row labels a blocker is named by: the definition's and the page model's (runner.known_labels), read once."""
    global LABELS
    if LABELS is None:
        try:
            from runner import known_labels

            from .nav import MODEL
            LABELS = set(known_labels(MODEL))
        except Exception:       # noqa: BLE001 (no labels: a blocker is named by its equipment or not at all)
            LABELS = set()
    return LABELS


def help_blocker(text) -> dict | None:
    """The blocker the camera's Help names, or None: only from the refusal the kit knows, "not available as follows
    <row>" (coverage.blocker_of on it, the row the kit knows, never the value after it). A guide's description names
    equipment and rows as what the function does ("Assigns functions to the function ring"), which is no blocker."""
    t = " ".join(str(text or "").split())
    m = FOLLOWS.search(t)
    return coverage.blocker_of(t[m.start():], labels()) if m else None


def by_help(cam, name: str, label: str, back) -> Reason | None:
    """The camera's own Help on the option under the cursor, by the kit's guarded Help alone, or None where Help is not
    allowed on this screen (drive.help_refused): help_run.guide (C4, the popup's In-Camera Guide, OK), and back() must
    then hold (the list back on that option), else the row fails, its screen cancelled. Its text is never kept."""
    from drive import help_refused             # drive imports the provers: here, not at the top
    from help_run import guide
    from .nav import cancel
    why = help_refused(cam.read().kind, cam.frame.image)
    if why:
        print(f"   {label!r}: no Help on it ({why})", flush=True)
        return None
    r = guide(cam, f"{name}: {label}")
    if not back():
        cancel(cam, None)
        raise Failed(f"{name}: after the guide of {label!r} the list is not back on it ({cam.frame.path.name})")
    return Reason(help_blocker(r.get("text")), "help", (r.get("frames") or [None])[0], label)


def judge(cam, name: str, label: str, k: int, saved, back, say=_say) -> str:
    """What the prover does with the option `label` (index k) under the cursor of the row `name` (ENTER, TRY or SKIP:
    the module's), `saved` the index of the value the row was saved on, back() whether the list is still on that
    option. Says, option by option, each one drawn grey and each one whose drawing cannot be told."""
    grey, p = drawn_grey(cam)
    if grey is None:
        if p is not None:
            say(f"   {label!r}: whether it is drawn grey cannot be told (its text reads {p:.0f}): entered as before")
        return ENTER
    if not grey:
        return ENTER
    if k == saved:
        say(f"   {label!r}: drawn grey, but it is the value the row was saved on: entered as its put-back, as before")
        return ENTER
    known = REASONS.get(name)
    if known == MISJUDGED:
        say(f"   {label!r}: drawn grey, but a grey option of this row applied: entered as before")
        return ENTER
    if known is not None:
        return SKIP
    say(f"   {label!r}: drawn grey: the camera's Help on it, to read why")
    reason = by_help(cam, name, label, back)
    if reason is not None and reason.blocker:
        REASONS[name] = reason
        say(f"   why greyed: {reason.said()}")
        return SKIP
    if reason is not None:
        say(f"   the camera's Help on {label!r} names no reason ({reason.frame})")
    if NEVER_ENTER:
        REASONS[name] = reason or Reason(None, None, None, label)
        say("   --never-enter-grey: no Enter on it to read the camera's notice")
        return SKIP
    say(f"   {label!r}: the one Enter of this row on an option drawn grey, to read why it is greyed, not to choose")
    REASONS[name] = reason or Reason(None, None, None, label)       # tried: never again this run, whatever comes after
    return TRY


def tried(name: str, label: str, notice: dict | None, applied: bool, say=_say) -> Reason | None:
    """After the one Enter (TRY) on `label`: the row's reason from the camera's notice, where it refused (its blocker:
    coverage.blocker_of, the row, the equipment or a remote session); where the choice applied after all, the drawing was
    misjudged and the row's other grey options are entered as before (None)."""
    if applied:
        REASONS[name] = MISJUDGED
        say(f"   {label!r} was drawn grey, yet the camera applied it: this row's other grey options are entered as before")
        return None
    text = (notice or {}).get("text") or ""
    REASONS[name] = Reason(coverage.blocker_of(text, labels()), "notice", (notice or {}).get("frame"), label)
    say(f"   why greyed: {REASONS[name].said()}")
    return REASONS[name]


def line(rec: dict, reason) -> dict:
    """A proof line for an option drawn grey that no key was pressed on (SKIP): `rec`'s fields (path, kind, index,
    label, shown, chosen_frame, vlm, base and the prover's own), no download and no diff, not applied, "greyed":
    "drawn", the row's reason where one was read."""
    return {**rec, "row_frame": rec.get("chosen_frame"), "dat": None, "changes": [], "notice": None, "applied": False,
            "greyed": "drawn", **(reason.kept() if isinstance(reason, Reason) else {})}


def leave(cam, name: str) -> None:
    """Out of the list with MENU, nothing chosen, back on the row's page (a menu or submenu page), else the row fails."""
    cam.press("menu")
    if cam.read().kind not in ("menu", "submenu"):
        raise Failed(f"{name}: MENU on the list left {cam.read().kind}, not the row's page ({cam.frame.path.name})")
