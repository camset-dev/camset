# 21. On the shooting screen, no key but MENU unless it is named

- **Date:** 2026-11-10
- **Status:** accepted
- **Rule:** On the shooting screen no key but MENU goes out unless the run names that key for that press, since there a
  key does whatever the body assigns to it.

## Context

On the shooting screen a key does what the body makes of it, never what it does in a menu. In the a1 II's shipped
definition the control wheel's Center, Left, Right and Down buttons and the multi-selector's centre are Custom Keys
there, whose lists hold Movie Shooting, Wireless Test Flash, FEL Lock, AF On, FTP Transfer, Send and Interval
Shooting; the multi-selector's four directions move the focus frame; a dial changes the live exposure, which no
settings file holds and no restore puts back. The kit took all these keys for menu inputs, allowed on any screen: a
Right meant for a menu landed on the shooting screen on 2026-10-29 and opened ISO, and was mended in that one caller.
[Decision 7](0007-the-c4-key-only-where-it-is-safe.md) already reasons this way for C4, the one key it guarded by its
screen.

## Decision

On a screen read as the shooting screen no key but MENU goes out, unless the caller names the key for that press,
which it does only where pressing it there is the point. The rule does not rest on which keys a given body lets its
owner assign, which differs by body. With no screen given at all, no key but MENU goes out, named or not. The guard
sits where C4's does, at the link's one choke point: the screen read last travels with every press and every dial
(`Link.press` and `Link.dial`, with `camkit.safety.shooting_refused`). The keys named so far: the multi-selector's
directions, which move a focus frame (`kit/provers/framepos_run.py`, `kit/provers/orient_run.py --af-point`), and Fn
held to register a focus area (`kit/provers/afreg_run.py`). `kit/drive.py` refuses a hand-written press that meets the
shooting screen unless `--on-shooting KEY` names it, the owner's word, said in the console, the run's `events.jsonl`
and `drive.jsonl`; a key so named is judged there by that naming, the shooting screen having no row to open. Naming C4
never sends it there (decision 7). Cleanup presses (MENU after a STOP) go as before. A key named for the shooting
screen changes what no settings file holds (a focus frame's place, the live exposure), so the run's restore does not
put it back: the operator names, and presses, the keys that do (2026-11-10: a named ms_left on the camera, its ms_right
refused by drive.py's older check of an unread row, left a frame moved, put back by hand; that check no longer meets a
named key there).

## Consequences

- A stray key on the shooting screen is refused before it goes out, and the run takes its error path (the camera
  closed, the start file put back), instead of doing what the body makes of the key or changing the live exposure.
- The screen judged is never one the camera has left behind the kit's back: the link counts what can move the screen
  (a download, an upload, any press or dial), and when that count has moved since the last read, the screen is read
  afresh before the press is judged.
- A shooting screen the reader takes for another kind is not covered: a DISP mode that draws no battery reads as
  "unknown", and the kit presses on unknown screens on purpose (the memory slots read as one). A black frame (HDMI
  blanked) is judged on the camera's own picture of the screen (`camkit.live`), and when that picture cannot be read,
  no key but MENU goes.
- `framepos_run.py` and `orient_run.py --af-point` name the multi-selector's directions in their own code, since moving
  the focus frame is their purpose, and on the a1 II those directions move it and are no Custom Key: they ask no owner's
  word beyond what each run already needs. `framepos_run.py` runs only with `--allow "Camera Set. Memory"`, for its
  registrations, and puts the frame back by the reversed presses, which a third registration checks.
  `orient_run.py --af-point` runs with the owner holding the camera vertically, and leaves the AF point where its
  presses took it: no settings file holds it, and the run does not put it back.
- `afreg_run.py` names Fn: held on the shooting screen with AF Area Registration On it registers the focus area, a
  registration of the kind the playbook's rule 2 names, so the run asks the owner's word for it, `--allow "Fn hold on
  the shooting screen"`, and carries it on every proof line.
- A prover for another body names a key on the shooting screen only once it knows what that key does there.
