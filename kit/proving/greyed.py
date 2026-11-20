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

Whether an option is drawn grey, two eyes can tell, each on the frame the cursor stands on (drawing): the pixels
(proving.screens.drawn_grey: a list's and a side list's lit band, a carousel's lit icon) and the second reader, never
a third nor one standing in for the second (the owner, 2026-11-19: "the VLM text needs to include which text is
grey"). On a list and a side list the reader's flag for the option comes from its answer about the whole list on show
(Flags: camkit.vlm's entries.v2, asked in the background when the list opens and again where the cursor reaches an
option no screenful asked showed, never once an option), matched to the option by its label; on a carousel, from its
question about the lit option (carousel.v2.grey), asked in line and only where the lit icon cannot tell. Either eye
saying grey makes it grey; where the pixels cannot tell, the reader's flag decides (waited for); where they read white,
an answer already in is taken and none is waited for; a reader that gives no flag changes nothing, so a reader calling
an option white never makes the kit press on one the pixels call grey: the reader only ever adds care. Its answer is
not taken where it cannot change what is pressed (unasked): on the value the row was saved on, on an option the pixels
call grey, on a row where it misjudged an option, on a carousel option its icon tells. judge's answer (Verdict) says
which eyes told it grey ("pixels", "reader" or "both": told) and carries both readings (Drawing.kept), which every line
it judged keeps ("grey_readings"), a grey one with "greyed_by" beside "greyed": "drawn" (line, marks).

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
import contextlib
import re
from typing import NamedTuple

from camkit import coverage, reading, vlm

from .base import Failed
from .screens import drawn_grey

ENTER, TRY, SKIP = "enter", "try", "skip"
NEVER_ENTER = False         # --never-enter-grey (main sets it): no Enter on an option drawn grey, ever
REASONS: dict = {}          # {row name: Reason, or Misjudged} read this run: one try a row
LABELS: set | None = None   # the row labels a blocker is named by (labels(): the definition's and the page model's)
FOLLOWS = re.compile(r"not available as follows\b", re.I)
EYES = ("pixels", "reader")
# What the second reader is asked whether an option is grey, by the kind of screen (reader census, 2026-11-19):
# - a list and a side list (LISTS): the whole list, every entry with its flag (entries.v2: Flags), once a screenful,
#   in the background. Asked about the lit item alone, Qwen3.8-27B and GLM-4.6V-Flash called none of 60 grey side-list
#   entries grey, while the menu question's per-row flag matched the pixels on 99% of rows; asked the whole list, Qwen
#   (the second reader) called grey 90.8% of the 142 grey side-list entries the cursor was not on and 59.5% of the 37 it
#   was on, and no white entry grey (272 and 72), 7.5 s an answer at four at once. The third readers are never asked
#   about grey: Gemma (26B) called 9.2% and GLM-4.6V-Flash 16.2% of those 142 grey, and neither one lit grey entry of 37
# - a carousel (ASKED): its lit option, carousel.v2.grey, only where its lit icon's red cannot tell (icon_grey: 102-124
#   on all 13 refused options, 209-255 on all 221 applied carousel frames); Qwen called 8 of 13 grey options grey and 6
#   of 60 white, carousel.v2.grey2 (pinned, the census's alone) fewer grey (6 of 13) and as many white
ASKED = {"dialog": "carousel"}
LISTS = {"list", "sidelist"}
# The kinds of screen whose options listen to the second reader's whole-list flag (Flags), measured by the reader
# census (--variants entries, Qwen3.8-27B): on side lists it called 90.8% of 142 grey entries the cursor was not on grey
# and no white one (272 and 72 right), so side lists listen; on lists (2026-11-20) it called 3 in 100 lit white entries
# grey (97.1% of 136 right) and 8 in 100 unlit ones (91.9% of 371), where the pixels told every grey list frame, so a
# list is told by its pixels alone: it makes no Flags, asks no whole-list question and queues nothing. A reader measured
# at 99% or more on both white figures can be switched on for lists by adding "list" here.
WHOLE_LIST = {"sidelist"}
ON_PIXELS_ALONE = ("a list's options are told by their pixels alone: the whole-list flag called 8 in 100 white "
                   "entries grey on lists (reader census, 2026-11-20)")
ENTRIES = "entries.v2"      # camkit.vlm's whole-list question
NO_STAND_IN = "the second reader is away: a reader standing in for it is never asked whether an option is grey"
ICON_TELLS = "the carousel's lit icon tells it, which no answer changes"
_POOL: list = []            # one worker for the whole-list questions, apart from the evidence question's (_pool)


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


def _screen_kind(cam):
    read = getattr(cam, "read", None)
    return getattr(read(), "kind", None) if callable(read) else None


def _own_second():
    """(the second reader's configured entry, {} where it cannot be told; whether a reader standing in plays the role
    now): a stand-in is never asked about grey (NO_STAND_IN)."""
    try:
        own = dict(vlm.role("second"))
    except Exception:           # noqa: BLE001 - no config to tell by: camkit.reading.ask says what is wrong
        return {}, False
    stand = vlm.standing_in("second")
    return own, stand is not None and stand.get("name") != own.get("name")


def not_its_own(got, own: dict) -> bool:
    """Whether an answer came from another reader than the second's own: another configured name, or a model of
    another family than the role's configured one (camkit.reading.model_id: a server that answered the second reader's
    name with another family's model). Where either side does not say, it is taken as the second's."""
    if own.get("name") and got.name and got.name != own["name"]:
        return True
    return bool(own.get("model") and got.model) and reading.model_id(got.model) != reading.model_id(own["model"])


def ask_entries(frame) -> reading.Asked:
    """The second reader's answer to the whole-list question (camkit.vlm's entries.v2) about frame, through
    camkit.reading.ask with a proof's time; no answer where a reader stands in for it, or another reader or another
    model family answered for it (NO_STAND_IN, not_its_own). Run on the grey worker (_pool), never in line."""
    own, standing = _own_second()
    if standing:
        return reading.Asked(None, None, None, NO_STAND_IN)
    got = reading.ask(frame, ENTRIES, reading.TIMEOUTS["proof"])
    if not_its_own(got, own):
        return reading.Asked(None, got.name, got.model, NO_STAND_IN)
    return got


def _pool():
    if not _POOL:
        from concurrent.futures import ThreadPoolExecutor
        _POOL.append(ThreadPoolExecutor(max_workers=1, thread_name_prefix="grey"))
    return _POOL[0]


def _flag(v) -> bool | None:
    """A JSON true or false, or the strings "true" and "false" in any case; None for anything else."""
    if isinstance(v, bool):
        return v
    return {"true": True, "false": False}.get(v.strip().lower()) if isinstance(v, str) else None


def band_options(cam, labels) -> list:
    """[the option of `labels` OCR names on each band the list or side list on show draws, an index or None (none, or
    two named)], top to bottom (proving.screens.grey_rows, the bands with ink; OCR's lines of the frame, which the
    prover read already, proving.screens.frame_lines); [] on any other screen."""
    from camkit.ocr import text_in

    from .screens import OPTION_X, _matches, frame_lines, grey_rows
    bands = [b for b in grey_rows(cam) if b[4] is not None]
    if not bands:
        return []
    try:
        lines = frame_lines(cam)
    except Exception:           # noqa: BLE001 - no OCR: no band named, so none covered
        lines = []
    x0, x1 = OPTION_X[_screen_kind(cam)]
    out = []
    for t, b, *_ in bands:
        hits = _matches(text_in(lines, (x0 - 20, t - 2, x1 + 20, b + 2)), labels)
        out.append(hits[0] if len(hits) == 1 else None)
    return out


class Ask(NamedTuple):
    """One whole-list question: the frame it was asked about, how many option bands that frame draws, the options OCR
    named on them, and the answer to come (a Future of camkit.reading.Asked)."""
    frame: str | None
    bands: int
    seen: frozenset
    future: object


class Flags:
    """A list's or side list's whole-list answers for one visit of its row (the provers make one a row, labels its
    options): the second reader asked entries.v2 about a screenful in the background (look), once where the option the
    cursor stands on is on no screenful asked yet, and each answer read for an option's flag (flag) by its label, never
    by its place. An answer whose list is not as long as the screen it was asked about draws, garbled, empty, or not in
    yet, gives no flag; nor does an option it lists twice or not at all."""

    def __init__(self, labels):
        self.labels = [str(x) for x in labels]
        self.asks: list = []

    def _named(self, entries) -> dict:
        """{option index: [the entries naming it]} by the provers' comparison of option labels (screens._matches)."""
        from .screens import _matches
        out: dict = {}
        for e in entries:
            hits = _matches(str(e.get("label") or ""), self.labels)
            if len(hits) == 1:
                out.setdefault(hits[0], []).append(e)
        return out

    def _entries(self, ask: Ask) -> tuple:
        """(the entries of a done question's answer, or None; why None)."""
        try:
            got = ask.future.result(timeout=0)
        except Exception as e:  # noqa: BLE001 - a question that raised is no answer
            return None, f"the question failed ({type(e).__name__})"
        entries = got.answer.get("entries") if isinstance(got.answer, dict) else None
        if got.answer is None:
            return None, got.why or "no answer"
        if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
            return None, "the answer holds no list of entries"
        if len(entries) != ask.bands:
            return None, f"its list has {len(entries)} entries where the screen drew {ask.bands}"
        return entries, ""

    def covered(self) -> set:
        """The options on a screenful asked about: those OCR named on its bands, and those a done answer names."""
        out = set()
        for a in self.asks:
            out |= a.seen
            if a.future.done():
                entries, _ = self._entries(a)
                out |= set(self._named(entries or []))
        return out

    def look(self, cam, k: int) -> None:
        """Ask about the frame on show, in the background, where option k (the cursor's) is on no screenful asked yet
        and the frame draws a list: never twice about one frame."""
        if k in self.covered():
            return
        name = getattr(getattr(cam.frame, "path", None), "name", None)
        if name is not None and any(a.frame == name for a in self.asks):
            return
        bands = band_options(cam, self.labels)
        if bands:
            self.asks.append(Ask(name, len(bands), frozenset(j for j in bands if j is not None),
                                 _pool().submit(ask_entries, cam.frame)))

    def close(self) -> None:
        """The row's visit has ended: its questions not started yet are dropped, so that the next row's are not queued
        behind them and a run's end waits on no more than the one being asked (its press's time at most)."""
        for a in self.asks:
            a.future.cancel()

    def flag(self, k: int, wait: float = 0.0) -> tuple:
        """(option k's flag: True, False or None; what the line keeps): from the newest answer that lists it once, among
        the questions about a screenful that showed it (else any); a question not answered yet waited for up to `wait`
        seconds in all (0: only answers already in)."""
        import time
        if not self.asks:
            return None, {"question": ENTRIES, "why": "no screenful of the list was asked about"}
        mine = [a for a in self.asks if k in a.seen] or list(self.asks)
        deadline, why = time.monotonic() + wait, "the answer was not in yet"
        for a in reversed(mine):
            if not a.future.done():
                left = deadline - time.monotonic()
                if left > 0:
                    with contextlib.suppress(Exception):     # late or failed: no flag from it
                        a.future.result(timeout=left)
                if not a.future.done():
                    continue
            entries, why_not = self._entries(a)
            if entries is None:
                why = why_not
                continue
            named = self._named(entries).get(k, [])
            if len(named) != 1:
                why = "the option is not listed" if not named else "the option is listed twice"
                continue
            said = _flag(named[0].get("greyed"))
            if said is None:
                why = "its flag is no true or false"
                continue
            got = a.future.result(timeout=0)
            return said, {"question": ENTRIES, "asked_on": a.frame, "read": str(named[0].get("label")),
                          **({"reader_name": got.name} if got.name else {})}
        return None, {"question": ENTRIES, "why": why}


def reader_grey(cam, k: int | None = None, flags: Flags | None = None, wait: float = 0.0) -> tuple:
    """(whether the second reader says the option under the cursor is drawn grey: True, False, or None where it gives no
    answer; what the line keeps of its side). On a side list (WHOLE_LIST), option k's flag in the row's whole-list
    answers (Flags.flag, waiting up to `wait` seconds for one asked about a screenful that showed it); on a list, which
    listens to none, nothing (ON_PIXELS_ALONE). On a carousel (ASKED), its question about the lit option
    (camkit.reading.QUESTIONS' grey_prompt, read by camkit.reading.greyed_of), asked in line through camkit.reading.ask
    with a press's time, never of a reader standing in for the second (NO_STAND_IN). Any failure is no answer; (None,
    {}) on any other screen."""
    kind = _screen_kind(cam)
    if kind in LISTS:
        if kind not in WHOLE_LIST:
            return None, {"not_asked": ON_PIXELS_ALONE}
        if flags is None or k is None:
            return None, {"not_asked": "no whole-list answers kept for this row"}
        return flags.flag(k, wait)
    if kind not in ASKED:
        return None, {}
    q = reading.QUESTIONS[ASKED[kind]]
    own, standing = _own_second()
    if standing:
        return None, {"not_asked": NO_STAND_IN}
    try:
        got = reading.ask(cam.frame, q.grey_prompt, reading.TIMEOUTS["press"])
    except Exception as e:      # noqa: BLE001 - no answer: the pixels decide, as before
        return None, {"question": q.grey_prompt, "why": f"the question could not be asked ({type(e).__name__})"}
    if not_its_own(got, own):
        return None, {"question": q.grey_prompt, "why": NO_STAND_IN}
    said = reading.greyed_of(got.answer, q)
    read = got.answer.get(q.field) if isinstance(got.answer, dict) else None
    return said, {"question": q.grey_prompt, **({"reader_name": got.name} if got.name else {}),
                  **({"read": str(read)} if isinstance(read, (str, int, float)) and not isinstance(read, bool) else {}),
                  **({"why": got.why or "the answer says nothing of grey"} if said is None else {})}


def unasked(k: int, saved, deaf, pixels, kind=None) -> str:
    """Why the reader's answer is not taken for option k, where it cannot change what is pressed on it ("" where it
    can): the value the row was saved on (entered as its put-back, whatever either eye says); a row where the reader
    misjudged an option (its answer is not heard there); an option the pixels call grey on a row where they are heard
    (grey, whatever the reader says); a carousel option its lit icon tells (ICON_TELLS)."""
    if k == saved:
        return "the value the row was saved on, entered as its put-back whatever is said"
    if "reader" in deaf:
        return "the reader misjudged an option of this row, and is not heard on it"
    if pixels and "pixels" not in deaf:
        return "the pixels tell it grey, which no answer changes"
    if kind in ASKED and pixels is not None and "pixels" not in deaf:
        return ICON_TELLS
    return ""


def drawing(cam, why_not=None, k: int | None = None, flags: Flags | None = None) -> Drawing:
    """The option under the cursor as both eyes tell it on the frame on show (Drawing): the pixels always, then the
    reader unless why_not, a function of the pixels' verdict, says why its answer is not taken (unasked), which the
    line then keeps as "not_asked". On a list or side list the screenful on show is asked about only then (Flags.look,
    where no screenful asked showed option k): never for an answer that could not be taken. A list's flag is waited for
    only where the pixels cannot tell; where they read white, only an answer already in is taken."""
    grey, level = drawn_grey(cam)
    why = why_not(grey) if why_not is not None else ""
    if why:
        return Drawing(grey, level, None, {"not_asked": why})
    if flags is not None and k is not None and _screen_kind(cam) in LISTS:
        flags.look(cam, k)
    said, asked = reader_grey(cam, k=k, flags=flags, wait=reading.TIMEOUTS["press"] if grey is None else 0.0)
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


def judge(cam, name: str, label: str, k: int, saved, back, say=_say, drawn: Drawing | None = None,
          flags: Flags | None = None) -> Verdict:
    """What the prover does with the option `label` (index k) under the cursor of the row `name` (ENTER, TRY or SKIP:
    the module's, as a Verdict), `saved` the index of the value the row was saved on, back() whether the list is still
    on that option, drawn the option's Drawing where the caller has it (else drawing(cam), on the frame on show, the
    reader's answer taken only where it can change what is pressed: unasked), flags the row's whole-list answers on a
    list or side list (Flags: the screenful on show asked about first, in the background, where its answer can be
    taken for option k and no screenful asked yet showed it). Says, option by option, each one drawn grey and by which
    eyes, and each one whose drawing no eye could tell, or why the reader's answer was not taken."""
    known = REASONS.get(name)
    deaf = _deaf(known)
    kind = _screen_kind(cam)
    d = drawn if drawn is not None else drawing(cam, lambda grey: unasked(k, saved, deaf, grey, kind), k, flags)
    by = d.grey_by(deaf)
    if not by:
        if d.grey_by():
            say(f"   {label!r}: drawn grey, told by the {told(d.grey_by())} alone, which misjudged an option of this row "
                "that the camera applied: entered as before")
        elif d.pixels is None and d.reader is None and d.level is not None:
            why = d.asked.get("not_asked")
            say(f"   {label!r}: whether it is drawn grey cannot be told (its text reads {d.level:.0f}): entered as before; "
                + (f"the reader's answer not taken: {why}" if why else
                   f"the reader gave no flag ({d.asked.get('why') or 'no answer'})"))
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
