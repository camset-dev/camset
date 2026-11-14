# 4. Never delete or format the cards

- **Date:** 2026-11-01; changed 2026-11-13
- **Status:** accepted
- **Rule:** No Format or Delete row is opened or confirmed remotely unless a dated owner decision names it by its path;
  only a --confirm run's last press confirms it.

## Context

The owner: "Please don't delete the cards." Format and Delete cannot be undone, and Playback's C4 deletes. On
2026-11-13 the owner, with generic cards in the camera, allowed more on their own a1 II: "I have generic sd cards in so
you can format, delete, etc". The kit cannot know, for a body nobody has watched, whether Enter on a slot formats at
once or only asks: a step it takes for harmless can be the press that formats.

## Decision

By default no Format or Delete is sent remotely and Playback > Delete is never opened: no `--allow` names a Format or
Delete row (`safety.allow_refused`), and the checks on the camera refuse the row however a run named it
(`safety.never_lifted`). Every camera keeps that default unless its owner writes a dated owner decision in its reviewed
scope.

A dated owner decision in the camera's reviewed scope (`"lifts": "owner"`, decision 8) may name such a row, and only by
its path ("Shooting > Media > Format", "Playback > Delete > Delete"), since the names recur inside rows the kit never
opens. Only `kit/drive.py --owner` uses it, for the row its `--path` ends on, one per run. The run goes to the row in
that tab and group and opens it only where the camera's screen reads the decision's place: the top-level page's
breadcrumb its tab and group; for a row deeper than its top-level row, each parent's lit bar before its Right and the
title of the page that Right opens, the last of them read again at the opening. Anything there that cannot be read
refuses, and so does a page that a Right left in the position it was in (the Right ignored or drawn late). Between the walk and the opening only Up and Down go out, and from then on no Right or Enter goes out, in
`drive.py` or in the camera's own check, but the opening of that row and the presses inside it, whatever a lit row
reads as. The kit has not seen what Right on Format
or Delete shows: no frame the repository names records either opening (`kit/tools/card_actions.py` offered Format from
2026-10-28 to 2026-11-01 and records no look at it; the Format and Delete questions in the tests are written for the
confirmation check). So their opening press is the run's armed last press, as for every action the kit has not seen
open to look (`safety.opens_to_look`, decision 8): it needs the row under `"confirm"` and a run given `--confirm`, goes
from the row's own page, is armed once, and nothing is pressed in the row after it but MENU; a decision naming a step
(`"options"`) for such a row is refused. Once a run's frame shows that Right on the row at that place opens its slots or
a question, its place joins `safety.opens_to_look`, citing that frame, and the row then opens with Right alone, to look.
Inside a row that opens to look every Enter may be the final one. An Enter on a step the decision names (`"options"`: a
slot, never a button's or a go-ahead's word, the action's own name or what reads as a confirmation) goes before the
run's last press only where the decision also marks that step seen (`"steps_seen"`: the owner has seen Enter on it only
lead to a question on this camera), the screen is no dialog or notice, reads as no question and shows no dialog's two
buttons (Enter, OK or Execute with Cancel), and another Enter follows in the run. Any other Enter in the row, the first
one when nothing is marked seen, is the run's armed last press: it needs the row under `"confirm"` and a run given
`--confirm`, is armed once, and, where it lands on the action's question rather than a step, only with a confirm button
lit (Enter, OK, Execute, Yes, the action's name) and the whole text, as read, that action's question. The camera's own
check presses each such Enter only when `drive.py` allowed that press for that row and its own reading agrees. The
run's `--confirm` covers only the presses those checks judged a step or its armed press, never another. Before any
`--owner` run given `--confirm` connects, whatever its row, it prints the row's whole place, what its last press may do
and the camera, and asks for the row's name, which the person at the terminal types (Format, Delete); the prompt never
prints the name as the word to type. A run with no terminal (standard input no TTY) or another answer sends nothing,
and no flag or environment variable answers it: the decision is a local file and `--confirm` a flag, both of which an
agent can write. The question stops a careless agent, not a determined one: a program driving a pseudo-terminal can
answer it, so the owner types the answer themselves and never leaves it to an agent. The decision may waive the
question only by saying `"unattended": true` beside its `"confirm"` (or beside a never-choose row's `"options"` with
`"link_loss"`, decision 8), and the run then says that the owner waived it. Deleting never goes through C4, which stays
as decision 7 says. `kit/tools/card_actions.py` keeps its own `--allow` route and
refuses Format and Delete as before. The maintainer, the a1 II's owner, decided this for their own camera on 2026-11-13.

Before 2026-11-13 no decision opened a Format or Delete row.

## Consequences

Card actions are the owner's, by hand, unless their decision names the row; a run that confirms one ends with it, and
its restore puts the settings back as after any run (the cards' contents are not settings: nothing puts them back).
The first run on Format or Delete is no look: its Right is its armed last press, and that Right may itself format the
card or delete at once, since nobody has seen what it does; Format is under `"confirm"` to run it at all, so it is run
only on a card the owner is ready to lose. What Right showed there is the frame that lets the place join the rows that
open to look. Looking at Format's question and cancelling it is no run of its own:
the step that reaches it is followed by the confirmation or is itself the last press.
