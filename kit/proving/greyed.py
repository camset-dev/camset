"""An option a list, a side list or a carousel draws grey (prove_run.prove_row, proving.sidelists.prove_side_row; the
owner, 2026-11-19: "your selecting grey out items and assuming they are changing in PP"): it is never entered to choose
it, and why it is greyed is read once a row (the row's one Enter for that, which the camera may still apply: TRY).

    what = greyed.judge(cam, name, label, k, saved, back)
    ENTER   drawn white, or whether it is drawn grey cannot be told (said, option by option), or the value the row was
            saved on (its put-back): entered as before
    TRY     the row's first option drawn grey whose reason the camera's Help did not give: the one Enter of the row, to
            read the camera's notice (the owner's way, 2026-10-28: "if you hit center button to activate it, the popup
            says why"), never a second on that row in the run but where the camera applied the first, which only the
            other eye had told grey (Misjudged); not with NEVER_ENTER
    SKIP    drawn grey and its reason read, or NEVER_ENTER: no key at all on it; the line says greyed as drawn

Whether an option is drawn grey, two eyes tell, each on the frame the cursor stands on (drawing): the pixels
(proving.screens.drawn_grey, on a list and a side list) and the second reader, asked the kind of screen's question that
also asks it (camkit.reading.QUESTIONS' ".grey" versions, its "greyed": reader_grey; the owner, 2026-11-19: "the VLM
text needs to include which text is grey"). Either one saying grey makes it grey; where the pixels cannot tell (a
carousel, whose pixels are not judged; a measure in between), the reader decides; a reader that does not answer changes
nothing. So a reader calling an option white never makes the kit press on one the pixels call grey: the reader only
ever adds care. The reader is asked, in line, only where its answer can change what is pressed (unasked): never on the
value the row was saved on, on an option the pixels already call grey, nor on a row where it misjudged an option. judge's answer (Verdict) says which eyes told it grey ("pixels", "reader" or "both": told) and carries
both readings (Drawing.kept), which every line it judged keeps ("grey_readings"), a grey one with "greyed_by" beside
"greyed": "drawn" (line, marks).

The reason (REASONS, a row's for the run): first the camera's own Help on that first grey option, through the kit's
guarded Help alone (drive.help_refused: a menu or option screen whose footer draws the help button; help_run.guide:
C4, the popup's In-Camera Guide only, OK back onto the option; camkit.live and camkit.link judge the C4 as ever,
never in Playback), its blocker taken only from the refusal the kit knows ("not available as follows <row>":
coverage.blocker_of, never the value after it); on the a1 II the guide of a greyed row or option says only "This
function is currently disabled." (kit2_help), so then the notice of the one Enter gives it (coverage.blocker_of: the
row, the equipment or a remote session). A grey option that the Enter applies after all was misjudged, by the eyes that
told it grey (Misjudged): those are not heard again on that row, whose other options they alone call grey are entered
as before, while an option the other eye calls grey is still judged grey. So a reader's misjudgement never makes the
kit enter an option the pixels call grey, and the pixels' never one the reader does without its own Help and one try.
"""
import re
from typing import NamedTuple

from camkit import coverage, reading

from .base import Failed
from .screens import drawn_grey

ENTER, TRY, SKIP = "enter", "try", "skip"
NEVER_ENTER = False         # --never-enter-grey (main sets it): no Enter on an option drawn grey, ever
REASONS: dict = {}          # {row name: Reason, or Misjudged} read this run: one try a row
LABELS: set | None = None   # the row labels a blocker is named by (labels(): the definition's and the page model's)
FOLLOWS = re.compile(r"not available as follows\b", re.I)
EYES = ("pixels", "reader")
# the kinds of screen a list prover meets, and the kind whose question (camkit.reading.QUESTIONS) asks, beside the lit
# item's text, whether it is drawn grey
ASKED = {"list": "list", "sidelist": "side list", "dialog": "carousel"}


def _say(message: str) -> None:
    print(message, flush=True)


class Reason(NamedTuple):
    """Why a row's options are greyed, as read once: the blocker (coverage.blocker_of's: {"row"}, {"equipment"} or
    {"remote"}; None where none was named), where it was read ("help", "notice", or None: not read), the frame it was
    read on and the option it was read on; eyes, the eyes that told grey the option the row's one Enter went to (until
    tried() hears whether it applied), and deaf, the eyes that misjudged an option of this row before (Misjudged)."""
    blocker: dict | None
    by: str | None
    frame: str | None
    entry: str | None
    eyes: frozenset = frozenset()
    deaf: frozenset = frozenset()

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


class Misjudged(NamedTuple):
    """A row where an option drawn grey was applied by the camera after all: the eyes that had told it grey, which are
    not heard again on that row."""
    eyes: frozenset


class Drawing(NamedTuple):
    """How the option under the cursor is drawn, as each eye tells it on the frame on show: pixels (drawn_grey: True,
    False or None where it cannot be told), level (its measure, or None), reader (the second reader's "greyed": True,
    False or None where it gave no answer or was not asked) and asked (what the line keeps of the reader's side: the
    question, the reader's name, its reading of the item, why it gave no answer; or, not asked, why: "not_asked")."""
    pixels: bool | None
    level: float | None
    reader: bool | None
    asked: dict

    def grey_by(self, deaf=frozenset()) -> frozenset:
        """The eyes that tell it grey, but those in deaf."""
        return frozenset(e for e, said in zip(EYES, (self.pixels, self.reader), strict=True) if said and e not in deaf)

    def kept(self) -> dict:
        """What a proof line keeps of both readings ("grey_readings")."""
        return {"pixels": self.pixels, **({"level": round(self.level, 1)} if self.level is not None else {}),
                "reader": self.reader, **self.asked}


class Verdict(str):
    """What judge says to do with an option (ENTER, TRY or SKIP, and equal to that word), with told, the eyes that told
    it grey ("pixels", "reader" or "both"; None where it is not taken for grey), and drawing, the Drawing judged by."""
    told: str | None
    drawing: Drawing | None

    def __new__(cls, what: str, told: str | None = None, drawing: Drawing | None = None):
        v = super().__new__(cls, what)
        v.told, v.drawing = told, drawing
        return v


def told(eyes) -> str | None:
    """"both", "pixels", "reader", or None for no eye."""
    eyes = set(eyes)
    return "both" if eyes >= set(EYES) else next(iter(eyes)) if eyes else None


def reader_grey(cam) -> tuple:
    """(whether the second reader says the option under the cursor is drawn grey: True, False, or None where it gives no
    answer; what the line keeps of its side): asked the question of the screen's kind that also asks it (ASKED,
    camkit.reading.QUESTIONS, read by camkit.reading.greyed_of), through camkit.reading.ask (camkit.vlm.ask_role: a
    stand-in for the second reader where it will not connect, never about a black frame, nothing while its reader is
    down), with a press's time (camkit.reading.TIMEOUTS). Any failure is no answer. (None, {}) on a screen no question
    of the kind asks it of."""
    read = getattr(cam, "read", None)
    kind = ASKED.get(getattr(read(), "kind", None)) if callable(read) else None
    if kind is None:
        return None, {}
    q = reading.QUESTIONS[kind]
    try:
        got = reading.ask(cam.frame, q.grey_prompt, reading.TIMEOUTS["press"])
    except Exception as e:      # noqa: BLE001 - no answer: the pixels decide, as before
        return None, {"question": q.grey_prompt, "why": f"the question could not be asked ({type(e).__name__})"}
    said = reading.greyed_of(got.answer, q)
    read = got.answer.get(q.field) if isinstance(got.answer, dict) else None
    return said, {"question": q.grey_prompt, **({"reader_name": got.name} if got.name else {}),
                  **({"read": str(read)} if isinstance(read, (str, int, float)) and not isinstance(read, bool) else {}),
                  **({"why": got.why or "the answer says nothing of grey"} if said is None else {})}


def unasked(k: int, saved, deaf, pixels) -> str:
    """Why the reader is not asked about option k, where its answer cannot change what is pressed on it ("" where it
    can): the value the row was saved on (entered as its put-back, whatever either eye says); a row where the reader
    misjudged an option (its answer is not heard there); an option the pixels call grey on a row where they are heard
    (grey, whatever the reader says)."""
    if k == saved:
        return "the value the row was saved on, entered as its put-back whatever is said"
    if "reader" in deaf:
        return "the reader misjudged an option of this row, and is not heard on it"
    if pixels and "pixels" not in deaf:
        return "the pixels tell it grey, which no answer changes"
    return ""


def drawing(cam, why_not=None) -> Drawing:
    """The option under the cursor as both eyes tell it on the frame on show (Drawing): the pixels always, then the
    reader unless why_not, a function of the pixels' verdict, says why it is not asked (unasked), which the line then
    keeps as "not_asked"."""
    grey, level = drawn_grey(cam)
    why = why_not(grey) if why_not is not None else ""
    said, asked = (None, {"not_asked": why}) if why else reader_grey(cam)
    return Drawing(grey, level, said, asked)


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


def _deaf(known) -> frozenset:
    """The eyes not heard on a row: those that misjudged one of its options."""
    return known.eyes if isinstance(known, Misjudged) else known.deaf if isinstance(known, Reason) else frozenset()


def seen(what) -> str:
    """How the run says which eyes told an option grey (a Verdict's told and drawing), "" where none did."""
    d, who = getattr(what, "drawing", None), getattr(what, "told", None)
    if not isinstance(d, Drawing) or not who:
        return ""
    level = f", its text reads {d.level:.0f}" if d.level is not None else ""
    return {"both": f" (told by both: the pixels{level}, and the reader)", "pixels": f" (told by the pixels{level})",
            "reader": " (told by the reader" + (f"; the pixels cannot tell{level}" if d.pixels is None
                                                else f"; the pixels read it white{level}") + ")"}[who]


def judge(cam, name: str, label: str, k: int, saved, back, say=_say, drawn: Drawing | None = None) -> Verdict:
    """What the prover does with the option `label` (index k) under the cursor of the row `name` (ENTER, TRY or SKIP:
    the module's, as a Verdict), `saved` the index of the value the row was saved on, back() whether the list is still
    on that option, drawn the option's Drawing where the caller has it (else drawing(cam), on the frame on show, the
    reader asked only where its answer can change what is pressed: unasked). Says, option by option, each one drawn grey
    and by which eyes, and each one whose drawing no eye could tell."""
    known = REASONS.get(name)
    deaf = _deaf(known)
    d = drawn if drawn is not None else drawing(cam, lambda grey: unasked(k, saved, deaf, grey))
    by = d.grey_by(deaf)
    if not by:
        if d.grey_by():
            say(f"   {label!r}: drawn grey, told by the {told(d.grey_by())} alone, which misjudged an option of this row "
                "that the camera applied: entered as before")
        elif d.pixels is None and d.reader is None and d.level is not None:
            say(f"   {label!r}: whether it is drawn grey cannot be told (its text reads {d.level:.0f}): entered as before; "
                "the reader gave no answer")
        elif d.pixels is None and d.reader is False and d.level is not None:
            say(f"   {label!r}: the pixels cannot tell whether it is drawn grey (its text reads {d.level:.0f}); the reader "
                "reads it white: entered")
        return Verdict(ENTER, None, d)
    what = Verdict(ENTER, told(by), d)
    if k == saved:
        say(f"   {label!r}: drawn grey, but it is the value the row was saved on: entered as its put-back, as before"
            + seen(what))
        return what
    if isinstance(known, Reason):
        return Verdict(SKIP, what.told, d)
    say(f"   {label!r}: drawn grey: the camera's Help on it, to read why" + seen(what))
    reason = by_help(cam, name, label, back)
    if reason is not None and reason.blocker:
        REASONS[name] = reason._replace(deaf=deaf)
        say(f"   why greyed: {reason.said()}")
        return Verdict(SKIP, what.told, d)
    if reason is not None:
        say(f"   the camera's Help on {label!r} names no reason ({reason.frame})")
    if NEVER_ENTER:
        REASONS[name] = (reason or Reason(None, None, None, label))._replace(deaf=deaf)
        say("   --never-enter-grey: no Enter on it to read the camera's notice")
        return Verdict(SKIP, what.told, d)
    say(f"   {label!r}: the one Enter of this row on an option drawn grey, to read why it is greyed, not to choose")
    # tried: never again this run, whatever comes after (tried() hears whether it applied)
    REASONS[name] = (reason or Reason(None, None, None, label))._replace(eyes=by, deaf=deaf)
    return Verdict(TRY, what.told, d)


def tried(name: str, label: str, notice: dict | None, applied: bool, say=_say) -> Reason | None:
    """After the one Enter (TRY) on `label`: the row's reason from the camera's notice, where it refused (its blocker:
    coverage.blocker_of, the row, the equipment or a remote session); where the choice applied after all, the eyes that
    told it grey misjudged it (Misjudged): the row's other options they alone call grey are entered as before (None)."""
    before = REASONS.get(name)
    eyes = (before.eyes if isinstance(before, Reason) else None) or frozenset(EYES)    # not known: every eye
    deaf = _deaf(before)
    if applied:
        REASONS[name] = Misjudged(deaf | eyes)
        say(f"   {label!r} was drawn grey, yet the camera applied it (told by {'the ' + told(eyes) if len(eyes) == 1 else 'both'}): this row's other options "
            + ("drawn grey are entered as before" if len(eyes) > 1 else
               f"only the {told(eyes)} call grey are entered as before, those the other eye calls grey still judged"))
        return None
    text = (notice or {}).get("text") or ""
    REASONS[name] = Reason(coverage.blocker_of(text, labels()), "notice", (notice or {}).get("frame"), label, deaf=deaf)
    say(f"   why greyed: {REASONS[name].said()}")
    return REASONS[name]


def readings(what) -> dict:
    """What every line judge judged keeps of both eyes' readings ({"grey_readings": Drawing.kept}), {} for none (a
    network row's, which judge never sees)."""
    d = getattr(what, "drawing", None)
    return {"grey_readings": d.kept()} if isinstance(d, Drawing) else {}


def marks(what) -> dict:
    """What a line of an option drawn grey says of it: "greyed": "drawn", and which eyes told it ("greyed_by")."""
    who = getattr(what, "told", None)
    return {"greyed": "drawn", **({"greyed_by": who} if who else {})}


def line(rec: dict, reason, what=None) -> dict:
    """A proof line for an option drawn grey that no key was pressed on (SKIP): `rec`'s fields (path, kind, index,
    label, shown, chosen_frame, vlm, base and the prover's own), no download and no diff, not applied, "greyed":
    "drawn" and which eyes told it (marks), the row's reason where one was read, both eyes' readings (readings)."""
    return {**rec, "row_frame": rec.get("chosen_frame"), "dat": None, "changes": [], "notice": None, "applied": False,
            **marks(what), **(reason.kept() if isinstance(reason, Reason) else {}), **readings(what)}


def leave(cam, name: str) -> None:
    """Out of the list with MENU, nothing chosen, back on the row's page (a menu or submenu page), else the row fails."""
    cam.press("menu")
    if cam.read().kind not in ("menu", "submenu"):
        raise Failed(f"{name}: MENU on the list left {cam.read().kind}, not the row's page ({cam.frame.path.name})")
