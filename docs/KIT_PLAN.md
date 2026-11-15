# The kit's design

How the mapping kit is put together, and what is still open in it. The steps to run it are in the
[playbook](REMAPPING_PLAYBOOK.md), the rules and their reasons in [decisions/](decisions/index.md), and how each part
works in its module's docstring.

## Goal

For every setting the camera's menus reach, the kit proves, with evidence:

- the menu row as the camera shows it (tab, group, page, label);
- every option and field as the camera shows it (label, order, sub-panels, ranges);
- which `.DAT` records and values each option writes;
- when a row or option is greyed, hidden or limited, and by which other setting.

The results go into the camera's definition, `editor/definitions/<model>_fw<fw>.json` (its fields:
[Data files and their schemas](DATA_CONTRACTS.md)). The evidence stays in `runs/` and `private/evidence/`, never in
the definition (decision 16).

## The methods underneath

- **Model-based GUI testing (GUI ripping):** first a complete model of every screen, field and transition, then tests
  against that model.
- **Differential analysis:** change exactly one thing, then compare the whole file.
- **A traceability matrix with coverage criteria** (ISO/IEC/IEEE 29119): every item has a status and evidence, and
  coverage is a number with a known denominator, the coverage ledger
  ([decision 23](decisions/0023-a-ledger-says-what-is-settled-and-a-proof-is-made-once.md)).

Nothing counts as proved without evidence: the frame the label was read from and the file pair that shows the change.
A value with no proof of its own is marked inferred, never proved. A pass starts only when the one before is complete
or every gap has a recorded reason.

## Principles

1. **The camera tells which keys matter.** ▲▼ beside the options (more above or below), ‹ › beside an option (a
   second axis), a › box (Right opens a sub-panel) and the footer (what Delete, MENU and OK do) are matched as pixel
   templates before any key is pressed.
2. **Position comes from geometry, never from words:** the screen type, the lit row or slot, the ▲▼ marks and the
   `n/N` page counter. OCR and the vision models only read labels for the record.
3. **Predict, then check.** Down from option i lands on i+1 or wraps to the first; only a failed prediction is looked
   into.
4. **Each (position, input) pair is tried once.** Every result goes into a table of moves, reused only to travel.
   Every input in a screen's input profile is still tried at every position ("there could be an array").
5. **Fail closed.** On a screen it cannot identify, past its press budget, or when one retry cannot confirm its
   position, the walker backs out to a known place, saves the evidence, flags the item and moves on. It never
   improvises.

The pixel reader (`kit/camkit/screen.py`) gives the screen type and position from every frame; the camera loop waits
for a text reader only where safety needs a label, such as before Enter on a row (the playbook's
[section 5](REMAPPING_PLAYBOOK.md#5-readers-accuracy-before-speed)). How each screen type is walked is in
`kit/camkit/walk.py`; the inputs the kit may send, in `kit/camkit/safety.py`.

## How a value is proved

Mapping and proving are separate passes over the same menu model, because changing a setting moves the menu itself:
rows grey out, pages shift, option lists shrink. The map is made first with nothing changed, and the proofs run from it
as a queue of jobs. The commands are in the playbook's [section 7](REMAPPING_PLAYBOOK.md#7-order-of-work), the shape of
a proof and a run in its section 6.

**Pass 1: map (read-only).** Every page, row and dialog is walked without OK and left with MENU; each option's label,
position, route, screen type and frame signature are recorded. A greyed row is opened only to read its notice, which
names the blocking setting and its value. A settings download after each page must show no change. The owner reviews
the map before anything is changed.

**Pass 2: prove (changes settings).** One job per option: choose it by its known route, check that the screen matches
pass 1's frame (kept as the label's evidence), press OK, download the settings file and diff it. A row's proofs start
at the option after its current value and wrap round, so the last one puts the row back. A change outside the row's
own record is kept as a dependency candidate; a screen pass 1 never saw fails closed.

**Sampling long number ranges.** For an option set of numbers (zoom speeds 1 to 8, Black Level -15 to +15, number
fields), prove the lowest, the highest and the middle. If the middle lies on the straight line through the ends, by
the label's number or by the camera's own option order, the values between are marked inferred, not proved; if not,
prove them all. Under three values there is no line to test. Text option sets are always proved in full. Lines are checked in the camera's cyclic order, since pass
1's index counts from where the walk started. The rule also closes a list of numbers in one unit that the camera lists
in full (White Balance's colour temperature) when both ends are among the samples and every listed value lies on the
line, and each White Balance grid, whose corners and inside point must lie on each axis's line
within one preset and context (`pass2_report.scale_line`, `grid_lines`). The definition then says only that the values lie on a line, never which
were proved nor how many, since one of them is the owner's own setting (`kit/writer/proofs.py`, `sampled_scale`;
decision 16).

**Pass 3: dependencies** (`kit/pass3_run.py`). For each blocker listed in `pass3_run.BLOCKERS` (from pass 1's
notices), the kit sets the listed value that frees the row in the menu, walks and proves the rows that opened, then
restores the blocker and the start file. Each
finding becomes the greyed setting's `inactive_when`, with the value that turns it on (`unlock`, `unlock_label`).
Blockers the kit cannot change go to the owner: hardware (the lens, a flash, a dial), the kit's own remote session
("Connected to Remote Shooting"), and settings the kit never touches. The owner changes them by hand, with a download
before and after (the playbook's Phase 5).

Custom keys, Fn, My Menu and the memory sets have provers of their own in `kit/provers/`, each described in its
docstring.

## Offline testing

- **Screenshot corpus:** the pixel reader is scored on the a1 II's archived frames (`kit/tests/score_screen.py`)
  before any camera run.
- **Menu twin** (`kit/camkit/twin.py`): recorded presses and their frames replay the walker logic at thousands of
  presses a second, catching loops and off-by-one rows before a camera run.

## Still open

- **Budgets from what is known:** each item's press budget taken from its expected option count (the Help Guide, the
  SDK value list, the values seen in files), at about twice that. Today each walk has a fixed budget.
- **Known routes run blind:** travel along known moves sent as one burst, with one look at the end, and a wrong
  position found again from the page counter and breadcrumb. Not built.
- **Pass 3 by search:** today its blockers and the values that free them are listed by hand (`pass3_run.BLOCKERS`).
  Trying a blocker's other values until the row turns on, following a chain when the notice then names a second
  blocker, starting from pass 2's side effects and the Help Guide's unseen rows, and re-scanning every page at each
  blocker value are not built.
- **Re-proof runs:** a route that covers every known move once (route inspection, the "Chinese postman" problem), to
  re-check a definition after a firmware update.
