# The kit's design

How the mapping kit proves what each record of a settings file holds, and why it is built as it is. The steps to run
it are in the [playbook](REMAPPING_PLAYBOOK.md), which also holds the rules for someone else's camera (its section 1);
this project's own decisions, with their reasons and dates, are in [decisions/](decisions/index.md). What each session
found is in the maintainers' own log, which is not published.

This is the second kit, started 2026-10-27. The first is archived in the maintainers' own `private/` (decision 18), kept only as a
record of what went wrong and as a corpus of screenshots for testing; none of its code is carried over.

## Goal

The kit was written for the Sony a1 II but is meant for any body that a remote SDK can drive (screen capture plus button
presses) and that saves its settings to a file. For every setting the camera's menus can reach, it proves, with evidence:

- the menu row as the camera shows it (tab, group, page, row label);
- every option and field as the camera shows it (label, order, sub-panels, ranges);
- which `.DAT` records and values each option writes (proved by choosing it on the camera, pressing OK, downloading the settings file and diffing);
- when a row or option is greyed, hidden or limited, and by which other setting.

The results go into the camera's definition, `editor/definitions/<model>_fw<fw>.json`, the contract between the kit
and the editor, which only grows (decisions 11 and 19);
its fields are on [Data files and their schemas](DATA_CONTRACTS.md). Evidence (screenshots, files, which reader agreed)
stays in the kit's run folders and in `data/`, never in the definition.

## The methods underneath

Three established methods underlie it:

- **Model-based GUI testing (GUI ripping).** First build a complete model of every screen, field
  and transition. Then test against that model.
- **Differential analysis.** The standard method for reverse engineering file formats: change
  exactly one thing, then compare the whole file.
- **Traceability matrix with coverage criteria** (ISO/IEC/IEEE 29119 test documentation). Every
  item has a status and evidence, and coverage is a number with a known denominator.

Nothing counts as proved without evidence: the screenshot the label was read from, plus the file pair that shows the
change. A value with no proof of its own is marked inferred, never proved: the values between the proved ends of a
straight number range (below), and the cases in the playbook's "The proof, and how runs are shaped". Each pass below has
a known denominator, and the next starts only when the one before is complete or every gap has a recorded reason; the
[Status](STATUS.md) page counts them.

## Principles

The first kit's walker took its position from fuzzy OCR text, pressed to find out even when the result was predictable,
paid about 1 s for every look (an SDK screenshot over the LAN) and had no "confused, stop" rule; its last run's numbers
are in the maintainers' own log. These principles answer that.

1. **The camera tells us which keys matter.**
   - ▲ ▼ beside the option column: more options above or below.
   - ‹ › beside an option: a second axis (for example the Pixel Shift interval strip).
   - A › box: Right opens a sub-panel (for example the White Balance fine-tune).
   - The footer bar shows what Delete, MENU and OK do.
   - These symbols are matched as pixel templates before any key is pressed.
2. **Position comes from geometry, never from words.** The walker knows where it is from:
   - the screen type;
   - the highlighted row or icon slot;
   - the ▲▼ marks;
   - the `n/N` page counter.

   OCR and the VLM only read labels for the record.
3. **Predict, then check.** In a list of N options, Down from option i is expected to land on i+1, or wrap to the first. Only a failed prediction is investigated.
4. **Each (position, input) pair is tried once.**
   - Every result goes in a table of moves.
   - A known move is reused only to travel, by the shortest known route; it is never pressed again just to check.
   - Every input in a screen's input profile is still tried at every position (the maintainer's rule: "there could be an array").
5. **Fail closed.** The walker backs out to a known place, saves the evidence, flags the item and moves on when any of these happens:
   - it sees a screen it cannot identify;
   - it goes over the press budget;
   - it cannot confirm its position after one retry.

   It never improvises.
6. **Budgets come from what we already know.** Each item's expected option count comes from the Help Guide, the SDK value list and the values seen in files. An item stops at about twice that number of presses.
7. **Known routes run blind and are checked at the end.** Travel along known moves is sent as one burst, with one look at the end. If the position is wrong, the walker relocates from the page counter and breadcrumb.
8. **Never kill a run with a dialog open.** If the session drops, the camera applies the open dialog. Runs stop through a `STOP` file, which cancels any open dialog before exiting (decision 15).

## Screen types

| Type | How it is recognised | Complete walk | Done when |
|---|---|---|---|
| Shooting screen | no menu chrome | none; only MENU is pressed here (arrows are shortcuts that change settings) | — |
| Menu page | black top bar with breadcrumb and `n/N`; tab and group columns; orange row bar | Down through the rows; read label, value and greyed state | `n` advances |
| Option list | white dialog, left icon column with ▲▼, orange title line, footer | Down until it wraps | first option seen again and the count matches |
| Submenu page | breadcrumb with a second level; no tab or group columns; ‹ at the left; rows and orange bar from x 55; may have n/N pages and an info line | Down through the rows (they wrap: a repeated cursor slot + signature ends the page) | back at the first row's signature |
| List popup | framed panel (x 64–577) over the dimmed menu; radio rows; footer 🗑? and MENU ↩ | Down to the end; the scrollbar thumb (if any) gives the window and an option-count estimate | the cursor reaches the last row with the thumb at the bottom; the orange-centred radio is the saved value, read from pixels |
| Option with a side axis | ‹ › at the option, strip below | at each option, Left and Right across the strip | the strip ends or wraps |
| Option with a sub-panel | › box | Right opens it; walk it by its own type | the sub-panel's own rule |
| Number fields | title line y 53, footer line y 426 (MENU Cancel, ● OK); active field = orange-filled box, others grey-bordered on the same line; ▲/▼ boxes over/under the active field | per field: Up/Down to each end (an arrow box disappears at the end of the range), Left/Right between fields; sampled, not every value | both ends seen for every field |
| Creative Look panel | strip of 8 parameter cells (y 350–403), selected cell orange with ⌃/⌄ where it can still move; orange ▶ on a vertical scale marks the value | Left/Right across the cells; per cell Up/Down to each end; a cell with no ⌃/⌄ and no scale is fixed in that look (e.g. BW Saturation) | every cell's two ends seen, per look |
| Slider | − and + boxes mirrored about the centre, orange marker on a horizontal scale, value between ◂ ▸ | Left/Right to each end (◂ or ▸ disappears) | both ends seen |
| Multi-field dialog | several fields, one highlighted | per field: min, max, step, wrap (sampled, not every value) | the range is proven |
| 2-D grid (White Balance) | colour grid with △▽◁▷ boxes; orange dot = position (snapped to cells); A-B / G-M readouts give exact values | corners, axes, centre and diagonals (multi-selector) | an arrow box disappears at each end of its axis |
| Picture Profile side list | ↩ box at the left; rows on the right (orange bar x 303–597, 50 px pitch); dim scrollbar at x 607 | Down to the end | last row with the thumb at the bottom |
| Checkbox list | title and footer lines; solid light checkbox squares near the left edge (orange ✓ = ticked); OK/Cancel buttons under the rows or at the right; cursor = row bar, orange frame round a box, or an orange button; some boxes have radio sub-options | toggle each box once, then leave with MENU (Cancel); never Enter on a button | each box seen in both states |
| Checkbox grid (Focus Area Limit) | title and footer lines; subtitle names the area under the cursor; 7 columns × 2 visible rows of icons, a checkbox above each; cursor = 80×102 orange cell or a button | every cell toggled once, then MENU (Cancel) | each box seen in both states |
| Tile grid (Main, My Menu add) | tiles | row by row | every tile name seen |
| Notice | 1-px frame at x 30/609. Variants: a single orange OK; OK in the footer ("not available as follows \| blocker \| value"); no OK ("Connected to Remote Shooting"); a question with OK **preselected** and Cancel ("Adjust?") | read the text first; a blocker notice: note the blocker, press OK; a question: Cancel unless the plan says otherwise | back where it started |
| Text entry | keyboard | not walked; set through the SDK string where one exists | — |
| Action row | dot value, or on the never list | never opened | — |

## Inputs

These are all the inputs the SDK can send:

- the four arrows, Enter and Menu;
- the 8-way multi-selector and its Enter;
- Fn, Playback, Delete, Mode, C1 to C7, AEL, AF-On, Home, Display and Back;
- the control wheel, front dial, rear dial L and rear dial R, each turned in either direction.

The walker uses an allow-list (`kit/camkit/safety.py`):

- **Always:** the arrows, Enter, Menu, the multi-selector and the dials.
- **Guarded,** only where the caller names them and the screen shows they are safe: Fn, Playback, Delete, Display, Back
  and C4. C4 is the trash button: it opens the In-Camera Guide on a screen whose footer draws the help button (the SDK's
  Delete key does nothing there, 2026-11-01), and it is also Focus Area's SET and a Creative Look panel's Reset. It is
  never sent in Playback or with a picture displayed, where it deletes, nor on the shooting screen, where it does
  whatever the body assigns to it: `Link.press` sends it only on the menu, option, panel and editor screens (decision 7).
- **Never:** Movie, AF-On, AEL, Mode, Home, Thumbnail, C1–C3 and C5–C7.

## How a value is proved

Mapping and proving are separate passes over the same menu model. Changing a setting moves the menu itself: rows grey out, pages shift and option lists shrink. So the map is made first with nothing changed, and the proofs then run from it as a queue of jobs.

**Pass 1: map (read-only).**
- Every page, row and dialog is walked without pressing OK; dialogs are cancelled with MENU.
- For each option it records the label, position, route, screen type and frame signature.
- Greyed rows are opened only to read their "not available as follows" notice, which names the blocking setting and its value.
- **Help on every row.** The trash button (C4, above) opens the camera's own help.
  - **Rows that are not greyed.** A popup offers "Add to My Menu" and "In-Camera Guide".
    - Whether "Add to My Menu" is offered is recorded as the row's My Menu eligibility.
    - "Add to My Menu" is never chosen in pass 1, because adding writes the file. Enter is pressed only once the highlighted entry has been read as In-Camera Guide.
    - The guide frame is saved for the VLM pool to read off the camera loop. The guide closes with OK and the popup with MENU.
  - **Greyed rows.** The help text appears at once and ends "This function is currently disabled."
    - It does not name the blocker; the notice does.
    - Its description often states the condition. For example, RAW+J Save Image applies when File Format is "RAW & JPEG", and Output Resolution only once the Rec. Media dur HDMI Output setting is turned on. That gives pass 3 the value to try first.
  - **Where it is pressed:** only on a settled menu page with the cursor on a row; never on the shooting screen (C4 runs
    its assigned function there) or in playback (trash deletes images).
  - **Cross-check.** My Menu > Add Item is walked read-only, because it also covers greyed rows. It is cancelled before a location is chosen.
  - **Item codes.** The code My Menu stores for each item needs a real add, so it is a pass 2 job: add, download, diff, then put the start file back (My Menu holds 42 items). The old kit's way out, uploading an emptied copy, is a file made by hand and is not used (decision 6).
- A settings download after each page should show no change. If one does, a dialog on that page applies without OK.
- The owner reviews the map before anything is changed.

**Pass 2: prove (changes settings).** There is one job per option:
1. Go to the row and choose the option by its known route. Check the screen matches the frame pass 1 recorded for it, and keep that frame as the label evidence.
2. Press OK and wait for "Saving to the connected device" to finish.
3. Download the settings file and diff it against the previous one. Record (row, field, option label as shown) → {record, section, value}.
4. Wait `LOCK_S` before pressing MENU, because MENU too soon after a download locks the menu. MENU reopens at the same
   row (at the parent row inside a submenu).

- **Order within a row:** proofs start at the option after the current value and wrap round, so the last proof is the starting value. The row ends as it began with no extra restore step. If the last diff does not return to the starting bytes, the run stops.
- **Expected changes:** the first proof in a row finds its record, and later proofs are predicted to change only that record. Any other change is a side effect, kept as a dependency candidate.
- **Unexpected screens:** a screen after OK that pass 1 never saw, such as a warning or a confirmation, fails closed. The run cancels it, logs it and skips the row.
- **Options that blind the kit:** an option that turns off the monitor or the HDMI feed, or sleeps the camera, is
  proved last with the OSD feed as the eyes, or is left for doing by hand. Rows that drop one link are proved over
  the other (the playbook, Phase 2).
- **Resuming:** jobs resume after a STOP, and a failed row can be re-run on its own.

**Sampling long number ranges (decided 2026-10-29).** For an option set of numbers (zoom speeds 1–8, Black Level −15…+15, Saturation, Color Depth, number fields), prove the min, the max and the middle. If the middle lies on the straight line through the ends, in the label's number or in the camera's own option order, the other values are marked **inferred**, not proved. If it does not, prove them all. Text option sets are always proved in full. Two value orders were seen: Grid Line Display On=0, Off=1; Frame Rate Low Limit On=0, Off=2. Pass-1 "index" counts from where the walk started, so lines are checked in the camera's cyclic order. The rule closes a list of numbers in one unit the camera lists too (White Balance's colour temperature, 2500-9900 K: 2500, 3200, 6000 and 9900 K stored 0, 7, 35, 74), when both ends are among the samples and every value of the list lies on the line by its labels, and each White Balance grid, whose corners and inside point must lie on each axis's line within one preset and context (`pass2_report.scale_line`, `grid_lines`). The definition then holds that they lie on a line, never which they were nor how many (the evidence file keeps the count): one is the camera's own setting (`kit/writer/proofs.py`'s `sampled_scale`, decision 16).

**Pass 3: dependencies.**
- **Starting points:**
  - the blockers named in pass 1's notices;
  - the side effects found in pass 2;
  - rows the Help Guide lists that the map never saw (hidden rows).
- **Finding the unlocking value.** A notice names the blocking setting and its current value, not the value that turns the row on. Pass 3 tries the blocker's other values, all already proved in pass 2, until the row turns on. Checking a row's greyed state takes only the pixel reader, with no download.
- **Chains.** If the row is still greyed, its notice may now name a second blocker. Pass 3 follows the chain.
- **Full re-scan.** At each blocker value it re-scans all the pages for greyed rows, hidden rows and limited options. This catches every row the setting controls, not only the one that led there.
- **Proving and recording.** Map and prove the rows that opened, then restore both the row and the blocker. Each
  finding becomes the greyed setting's `inactive_when`: the blocking record, its values, and the value that unlocks
  it (`unlock`, `unlock_label`).
- **Blockers the kit cannot change** go on a "needs you" list, with the notice's own text:
  - Physical: the lens, a flash, the drive dial. The owner changes the hardware, then the kit maps the rows.
  - The kit's own remote session ("Connected to Remote Shooting. Cannot be executed."). The owner changes these by hand with the link closed, saving before/after files to the card.
  - A never-touch setting such as Bluetooth Function. These rows are done by hand.

The start file is reloaded after every pass 2 or pass 3 run, because some "remembered sub-option" records are restored only by an upload (decision 15).

**Beyond the menu.**
- **Custom keys, Fn and My Menu:** the functions each slot can take, by the picker walk (sampled: the playbook, Phase 2).
- **Memory sets:** register each slot (1–3; M1–M4 save to the card and leave the file alone), compare the files to prove
  which records each one holds, then recall each and check that the camera restores them.

Supporting proofs that need no screen:

- **SDK property sweep:** value lists and writability in each master state.
- **SDK set and diff:** proves record ↔ SDK value for about half of the 1,415 live records.

A batch "upload many values and read the menu pages" method was considered and dropped. The end goal is the label as the setting's own screen shows it, proved per option.

## Eyes and readers

- **Frames.** Every source is converted to the same 640×480 canonical layout (`camkit.frames`): `OsdFeed` (the SDK's
  GetOSDImage, the baseline: about 0.8 s for a session's first grab, then the camera renews the picture every
  0.25–0.37 s, measured over the LAN, so a screen counts as settled only after two renewals with the same picture)
  and `HdmiSource` (a USB HDMI capture dongle, optional and faster: 30–60 frames per second, with "settled" detected
  as soon as frames stop changing).
- **Pixel reader** (fast, deterministic, every frame): screen type, highlight position, glyphs, footer, and a signature of the position-defining pixels.
- **Text readers** (OCR and vision models) run in parallel and off the camera loop wherever possible. The camera loop
  waits for one only where safety needs a label, for example before pressing Enter on a row. Which readers, and how
  their readings must agree: the playbook, "Readers: accuracy before speed".

## Offline testing

- **Screenshot corpus.** About 10,900 screenshots in the a1 II's `runs/ILCE-1M2_fw4.00/explore_stills/shots`, plus older runs. The pixel reader is scored on this corpus before any camera run.
- **Menu twin.** Every press and its resulting frame are recorded. The walker logic replays them in tests at thousands of presses a second, so loops, zigzags and off-by-one rows are caught before the camera is touched.
- **Re-proof runs** (planned, not in the kit yet). A route that covers every known move once (route inspection / the "Chinese postman" problem) re-checks it after firmware updates.
