# 22. OCR alone only for a plain reading, the reader on every doubt

- **Date:** 2026-11-13
- **Status:** accepted; in place in stages (see Consequences)
- **Rule:** OCR alone settles only a plain reading; on any doubt the reader is asked first, and where they differ a
  fresh frame and a third vote decide.

## Context

The kit reads the screen with OCR and with a vision-language model, the reader, and each fails in its own way: OCR
returns look-alike letters, reads icons as letters and drops short numbers; a reader invents answers on black frames
and can read a neighbouring thing. Which of them decided was settled tool by tool. The owner, on 2026-11-13: "a reader
is required, preferred a VLM and OCR backup".

## Decision

One rule wherever the kit reads the screen, in full in `kit/camkit/reading.py`'s docstrings. OCR alone settles only a
plain reading: Latin letters, digits and the camera's own signs, four characters or more, naming exactly one expected
option. On anything else, and always on a frame a press or a proof rides on, the reader is asked first, before any
press, proof line, guess or failure. Where OCR read nothing, the reader's one option stands, never alone for a press or
a guard; where they differ, a fresh frame and a third, independent vote follow, and a reading stands only where two
independent votes name the same option, else the row stops (one engine or model is one vote). A guard refuses whenever
two eyes differ, and no vote settles that. Without a reader a doubt fails the row.

"The reader wins" was rejected: on the first camera's proofs, where OCR's reading named no option the reader's was
sometimes another, while where OCR had read nothing it was not.

**What the rule cannot catch:** a reading that is another option's own text ("1/250" for 1/25); only the reader and a
third vote can, and only on a doubt.

## Consequences

It comes in by stages, each measured first
([the playbook's section 5](../REMAPPING_PLAYBOOK.md#5-readers-accuracy-before-speed)); no run decides or presses by
it yet, and meanwhile a plain OCR reading the reader contradicts stands. A run's start check already stops a run when
no reader answers or an OCR engine is unknown.
