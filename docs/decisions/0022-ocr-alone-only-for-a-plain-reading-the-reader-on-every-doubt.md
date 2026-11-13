# 22. OCR alone only for a plain reading, the reader on every doubt

- **Date:** 2026-11-13
- **Status:** accepted in principle; in place in stages (below): the rule's functions and its census since
  2026-11-13, with no camera run deciding by them yet

## Context

The kit reads the camera's screen with OCR (Apple Vision on a Mac, RapidOCR elsewhere) and with a vision-language
model, the reader. Which of the two decides was settled tool by tool: about a hundred and fifty places call OCR
directly and some twenty helpers ask the reader, each with its own fallback. Eight tables mend the look-alike letters
OCR returns, each a little different. Some places take OCR alone whatever it read; some ask the reader only when OCR
read nothing; in some the reader alone decides. The docs say a reader is required (the playbook's section 5, "The
minimum"), and since 2026-11-13 a camera run that asks a reader stops before it opens the link when none is listed;
inside a run a reader that cannot answer is still taken as no answer, and the run goes on with OCR alone.

What OCR gets wrong is known. It returns Cyrillic and other look-alike letters (C.Temp./Filter read with a Cyrillic
ES for its C), accented ones for an icon read as a letter, and a Cyrillic ZE for the 3 of PP3. It drops short numbers,
one and two digits, more than it misreads them. And Apple's recognition changes with the system: since macOS 27.2 it misses a scale's end
number on many Creative Look frames. The readers make other mistakes: they invent answers on black frames, and a
question can make them read another thing on the screen (a button, the screen's title, a neighbouring row).

The owner's word, 2026-11-13: "a reader is required, preferred a VLM and OCR backup". Before it: use the reader more
often, so that bad letters and Cyrillic look-alikes are caught; the reader is right where Apple Vision drops short
digits; ask the reader before failing a row; a local reader stands in when the remote one is off.

## Decision

One rule for every place the kit reads the screen, in `kit/camkit/reading.py`:

1. **One cleaning for every reading.** Before a reading is compared it is cleaned one way: compatibility forms (a
   full-width letter, a no-break space), accents, Cyrillic and Greek look-alikes become the Latin letters they are
   drawn as, every dash a hyphen, the readers' quotation marks the camera's own, every run of spacing one space; case
   is kept. The camera's menus are in English ([camera support](../CAMERA_SUPPORT.md#the-cameras-menus-must-be-in-english)),
   so a letter outside Latin, or an accented one, is always a misread. The raw reading is kept beside the cleaned one.
2. **When OCR alone is enough.** Only for a plain reading: Latin letters, digits and the camera's own signs as read,
   four characters or more, naming exactly one of the options expected there.
3. **Everything else is a doubt:** a character the cleaning changed (a look-alike letter, a symbol spelled out in
   letters, an invisible character), or a letter with no Latin twin; a number or code of three characters or fewer (a
   word that short is counted apart); a letter OCR reads for a digit beside a digit ("PP1O"); nothing read where
   something is lit; a number with no digit; a reading that names no option, several, or one only loosely.
4. **On a doubt, the reader first**, before any press, proof line, guess or failure; then the tie-break below.
5. **A frame a press or a proof rides on is always read by the reader too**, doubt or not, and every proof reading
   records which eyes voted on which frame, with what, and which agreed.
6. **Guards keep their own rule, and may only add refusals.** Every eye's reading on every frame read is judged, the
   raw reading beside its canonical one and never the canonical one alone (a cleaning can hide a slip the raw reading
   shows), and any one refusing refuses. Any two eyes that read differently refuse: no vote settles a guard, and a
   third vote never outvotes a refusal. A guard is never read again on a fresh frame for a better answer. It refuses
   what no eye can read, a doubt the reader does not answer, and one reader's reading that no second, independent
   vote names too: nothing a guard cannot read is pressed.
7. **A reader is required** (the owner's rule: "a reader is required, preferred a VLM and OCR backup"). The reader is
   never asked about a black frame. With the reader unreachable a plain reading goes on, marked as OCR's alone; a
   doubtful one fails the row, and a guard refuses. No other check stands in for the reader: a site's own check (below)
   is one more vote beside the reader's, never a vote in its place.

**The tie-break** (the owner's decision, 2026-11-13), for a doubtful reading:

- **Two agree:** OCR's reading and the reader's name the same thing: the reading stands. No third vote is asked.
- **OCR read nothing** where something is lit, and the reader names exactly one of the options expected there: it
  stands as one reader's reading, and is recorded as such. For a press or a guard never on that alone: a second,
  independent vote must name the same option. With no options to name, a lone reader's reading never stands; nor
  does it once OCR and the reader were apart on an earlier frame: then it goes to the vote like the rest.
- **OCR and the reader name different things** (or OCR's reading names no option and the reader's does): a fresh
  frame is read and both are asked again; on it a plain OCR reading is one more vote, never a way out of the
  disagreement. Still apart, a third vote is asked, independent of the first two: first the second OCR engine
  (RapidOCR beside Apple Vision where both are installed), then the site's own check where it has one, then, where
  those settle nothing, a reader of a different model (the "third" role). The reading stands only when two of the votes
  name the same expected option and no other reading has as many; otherwise the row stops, naming every reading.
  Without options to name, votes back a reading only as a group whose every two members agree.
- **One source, one vote.** One OCR engine is one vote whatever name it is configured by: the kit knows two, "apple"
  and "rapidocr", and refuses any other name rather than count Apple Vision twice. Two readers of the same model are
  one vote, as is one reader asked twice; models are told apart by their configured ids, without case or surrounding
  spaces, so the same weights configured under two ids cannot be told apart and count as two (give one model one id).
  Each vote records the engine or the model that cast it.
- **The reader does not win a disagreement by itself.** "The vision model wins" was weighed and rejected: measured on
  the first camera's proofs, where OCR's reading named no option the reader's option was sometimes another one (a
  neighbouring row, a button), while where OCR had read nothing it was not.
- **Guards:** any eye reading a never-open row refuses; a third vote never outvotes that refusal.
- **A plain OCR reading the reader contradicts** is, at this stage, recorded in the proof and stands. It becomes a vote
  like any other once each kind of screen's question to the reader is fixed and the disagreement rate is measured low
  (below). This is the current stage, put to the owner for confirmation, not a final rule.

How two readings are compared depends on what is read there, and with the options expected there both must name the
same one of them. First, for a label, a number and a code alike, what the screen draws round an option and OCR reads
as text goes: a bullet, a radio ring read as "o" or as "0 " before it (before anything but a digit), a stop at its
end. Then, without options: a label by the kit's strict option key (`camkit.match.norm`, never its looser likeness
alone, which takes "Registered" for "Not registered"), with its runs of digits and its decimal points alike, letters
and spaces beside them aside (F1.1, or F1.l with OCR's l, is never F11; "b1" is B1, "10Sec" 10 Sec; a point beside a
letter, as in "S:12M" or "Del.Select", is no decimal point; a leading I or thin stroke before a digit is a 1, "I5 Sec"
15 Sec, never 5 Sec; a sign before a lone zero is the plus-minus sign), a number by its digits and signs (4:3 is not
43; a thin stroke is a 1, never left out: "1/|25" is 1/125), a short code with the digits' look-alikes (P, a Cyrillic
ER and a Cyrillic ZE read for PP3 are PP3; a point between two characters stays), a button or a text by what it says,
every sign and star counted. A reading that is one option's loose likeness and another's look-alike ("Shot MarkZ
Only") names neither, and a reading or an option with rating stars names only by the same stars, never by likeness.
Readings the same text allows two ways are left to the options: a zero and a space before a digit (`0 4"`: a ring
before 4", or 0.4" with its point read as a space), an I before a bare zero ("I0 EV": 10 EV, or the plus-minus zero),
an o glued after a digit ("1/25o": 1/25 with a ring, or 1/250), an O glued before a capital and a sign ("OS&Q Record
Setting"). Where the options hold one of them the reading names it; where they hold two, or there are no options, it
names neither, and the reader settles it. A zero glued to a digit (`04"`) names no option. Votes stand together only
as agree takes them (one predicate for both), so a reading that stands on votes always has two sources that agree.

Both directions are tested on the a1 II's definition. No two options of one setting agree, by any of these rules,
with their setting's options or without; no option with its digits read as look-alikes (every character the kit takes
for a digit, at every digit, one and two at once) names, or agrees with, another option of its setting; and every
option, written as readers and OCR write it (Cyrillic look-alikes, a stop after it, doubled or dropped spaces, another
case, a ring or a bullet before it, the plus-minus zero's other forms, the seconds mark's other forms, a space between a
letter and a digit), names itself and agrees with itself, except where that writing is also another option's (`0 4"`
where the setting holds 0.4"; with no options, a zero and a space before a digit, and an I before a bare zero): there
false agreement loses, and the test lists each such case with its reason.

**What the rule cannot catch:** a reading that is another option's own text. A point lost whole ("F11" read for F1.1,
or 13" for 1.3"), or a real 0 glued after a number ("1/25" read with a 0 after it is 1/250's text), cannot be told
from that option by any rule on the text; only the reader's reading and the third vote can, on a doubt.
A plain OCR reading so misread stands at this stage (the plain-reading bullet above), which is one reason a contradicted
plain reading is to become a vote.

A site may offer a check of its own that is no reader: it is one more vote where the readers are apart or one reader
stands alone, never one in the reader's place. It must be independent of this frame's OCR text and of the readers:
the marker's place on a Creative Look scale, a count of presses from a known start, pass-1 pictures of the option. A
check worked out from the same OCR text is no second source.

## Consequences

The rule comes in by stages, each tested on its own, and each changing what a run decides only once the one before
it has been measured.

- **In place since 2026-11-13; no run decides or presses differently.** `camkit.reading` holds the cleaning
  (`canonical`), the doubts (`doubts`), the comparison by kind (`agree`), what the first two votes make of a reading
  (`outcome`), the count of independent votes (`tally`, each vote with the engine or model that cast it) and one
  reading by the rule (`read`: the fresh frame, the third vote, the guards' refusals, every vote recorded). OCR, the
  readers and the third reader's model are asked in one place each (a memo per reader, frame and question, never a
  black frame, and a pause after a reader fails twice in a row, so that a server that is off costs one timeout, not
  one per doubt). Nothing calls `read` yet. The eight look-alike tables still mend as they did; the tests say, table
  by table, where the one cleaning agrees with each and where it differs, so that the next stage's changes are known
  before they are made. `kit/tools/reader_census.py` replays the rule over runs already made (proof lines, the
  readers' answers already given, page models) and counts, per kind of screen, the readings it would doubt, the
  reader calls it would add, what it would keep or refuse, and what a third vote by the second OCR engine would settle
  where a run kept that engine's reading (the page models do; the proof lines do not); it reads the runs and writes
  nothing there, and its counts are for the owner's terminal. A test lists the modules that still read the screen by
  themselves; the list only gets shorter. A camera run's start check now asks a real question (to read a small
  picture, as a run asks) of each local reader and of a paid second reader, and of a paid third reader only when no
  local one answered; it checks the OCR engines' names too, and stops the run before its link when no reader answers,
  when the second reader does not and no local reader may stand in, or when an engine is unknown
  (`kit/tools/reader_check.py` asks the same with no camera).
- **Next, after the census:** `camkit.match.key` and `page_model.key_text` take the one cleaning, and the other tables
  go. Finding a row must leave out first the icon OCR reads as letters in front of a row's label, as
  `page_model.same_text` does, or the reader would be asked about most rows for nothing.
- **Then, site by site, one change each:** finding a row asks the reader before taking the closest reading; a Picture
  Profile is entered by its name with the digits' look-alikes read (PP3); one OCR match with a doubt needs the reader's
  agreement; a look's number needs the reader to agree with OCR or with the marker, never to override both; side
  lists, checklists, the White Balance grid and table cells read through the rule; every proof line carries its
  `eyes`. Then the provers, `kit/provers/pp_reset_run.py` last. Then the guards, which may only add refusals: the
  never-open check asks the reader on any doubt, not only on an empty bar, and Enter on a notice judges the reader's
  reading too. Then the start of a run (`--ocr-only` to run without a reader on purpose; `kit/tiebreak.py` with one
  reader), the batch tools (pass 1's carousels and grids ask on a doubt), and the
  playbook's section 5, the quickstart and the porting notes, rewritten for the rule.
- **Not before they are measured:** agreement as a gate on every proof frame (the reader's question answers something
  else than the option on some screens: checklists, number fields, Creative Look panels, axes, star ratings; each needs
  a better question first), a confidence floor for OCR, Apple's recognition languages set to English, and new names for
  labels already recorded, which only the owner's word changes (proofs are keyed by their labels).
- Asking the reader more costs time, and money with a hosted reader; answers are kept by frame, question and model, so
  a frame is paid for once. With no reader reachable more rows fail, saying that a reader is needed, where before they
  went on with OCR alone.
