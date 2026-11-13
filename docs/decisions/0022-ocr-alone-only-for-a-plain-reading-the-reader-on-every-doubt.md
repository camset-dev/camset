# 22. OCR alone only for a plain reading, the reader on every doubt

- **Date:** 2026-11-13
- **Status:** accepted; in place in stages (see Consequences)
- **Rule:** OCR alone settles only a plain reading; on any doubt the reader is asked first, and where they differ a
  fresh frame and a third vote decide.

## Context

The kit reads the camera's screen with OCR (Apple Vision on a Mac, RapidOCR elsewhere) and with a vision-language
model, the reader. Which of the two decides was settled tool by tool, each with its own fallback and its own mending
of look-alike letters. Each eye fails in its own way: OCR returns Cyrillic and accented look-alikes, reads icons as
letters, drops short numbers and changes with the system's version; a reader invents answers on black frames, and a
question can make it read another thing on the screen (a button, the title, a neighbouring row). The owner asked for
the reader more often (for bad and look-alike letters, for the short digits Apple Vision drops, before a row fails, a
local reader standing in for a remote one), then on 2026-11-13: "a reader is required, preferred a VLM and OCR backup".

## Decision

One rule for every place the kit reads the screen, in `kit/camkit/reading.py`, whose docstrings say how a reading is
cleaned (one way, the raw reading kept beside it) and how two readings are compared:

- **OCR alone only for a plain reading:** Latin letters, digits and the camera's own signs, four characters or more,
  naming exactly one of the options expected there. Anything else is a doubt.
- **On a doubt, the reader first,** before any press, proof line, guess or failure. A frame a press or a proof rides
  on is read by the reader too, and every reading records which eyes voted on which frame, with what.
- **Two agree:** the reading stands. **OCR read nothing** and the reader names exactly one expected option: it stands
  as one reader's reading, never alone for a press or a guard. **They differ:** a fresh frame, then a third vote (the
  second OCR engine, the site's own independent check, a reader of another model, in turn); it stands only when two
  independent votes name the same option, else the row stops, naming every reading. One engine or model is one vote.
- **A guard refuses whenever two eyes differ;** no vote settles it, and it refuses a doubt the reader does not answer.
- **A reader is required,** never asked about a black frame. Without one a plain reading goes on, marked as OCR's
  alone, and a doubt fails the row. A paid reader plays only the roles the configuration names.

"The reader wins" was weighed and rejected. Measured on the first camera's proofs, where OCR's reading named no option
the reader's option was sometimes another one (a neighbouring row, a button), while where OCR had read nothing it was
not. So a lone reader may stand where OCR read nothing, never against OCR: there a third vote decides.

**What the rule cannot catch:** a reading that is another option's own text. A point lost whole ("F11" read for F1.1)
or a real 0 glued after a number ("1/25" read as 1/250) cannot be told from that option by any rule on the text; only
the reader and the third vote can, and only on a doubt.

## Consequences

- In place since 2026-11-13: the building blocks in `kit/camkit/reading.py`, the measuring tool
  `kit/tools/reader_census.py` and a run's start check (no reader answering, or an unknown OCR engine, stops it before
  the link). No run reads through `read()` yet: it comes in stages, each measured first, and meanwhile a plain OCR
  reading the reader contradicts stands ([the playbook's section 5](../REMAPPING_PLAYBOOK.md#5-readers-accuracy-before-speed)).
- Asking the reader more costs time, and money with a hosted reader; answers are kept by frame, question and model, so
  a frame is paid for once. With no reader reachable more rows fail, saying that a reader is needed, where before they
  went on with OCR alone.
