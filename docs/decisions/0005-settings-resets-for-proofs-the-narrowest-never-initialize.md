# 5. Settings resets for proofs: the narrowest, never Initialize

- **Date:** 2026-11-01; changed 2026-11-13
- **Status:** accepted
- **Rule:** For a proof, the narrowest reset, the file put back after; Reset Network Set. and SSID/PW Reset only as an
  owner decision's last press; Initialize never.

## Context

Some records only a reset writes. Initialize and Reset Network Set. also wipe the network setup and access
authentication, which takes the camera off the link; SSID/PW Reset does so for the camera's own network. On 2026-11-13
the owner asked for those resets to be possible on their a1 II too, done as a run's last press with the restore by hand.
What the camera does on Initialize is not known: it is an item of Setting Reset's dialog (kit2_csr, 00118_right.png),
and nobody has seen what Enter on it shows; nor has the kit seen what Right on Reset Network Set. or SSID/PW Reset shows.

## Decision

Camera Settings Reset, the narrowest reset that does the job, is allowed for proofs, with the owner's file put back
after. Initialize and Reset Network Set. are never pressed by default: `drive.py` refuses Enter while either is lit, and
on a screen that reads either unless the lit text is Camera Settings Reset; no `--allow` names them. SSID/PW Reset joins
that check (2026-11-13) for every camera, a stricter default, and so does the camera's own check
(`camkit.live.LiveCamera`) on a `--owner` run.

Initialize stays closed whatever is decided: no decision names it, and `drive.py`'s lit check refuses Enter on it. A
dated owner decision in the reviewed scope (`"lifts": "owner"`, decision 8) may name Reset Network Set. or SSID/PW Reset
by its path, under `"confirm"` too, with `"link_loss": true`, for `kit/drive.py --owner` alone. Since nobody has seen
what Right on them shows, their opening press is their armed last press: a run given `--confirm` sends it once, from
the row's own page in its own tab and group; the camera's own check sends it only when `drive.py` allowed that press for
that row and its own reading agrees. No step is ever named in them. Before such a run connects, as before every
`--owner` run given `--confirm`, the person at the terminal types the row's name after the run has printed its whole
place, what its last press does and the camera; a run with no terminal (standard input no TTY) or another answer sends
nothing, and no flag or environment variable answers it. The question stops a careless agent, not a determined one, so
the owner types the answer themselves (decision 4). Only a decision that says `"unattended": true` beside its
`"confirm"` waives the question, and the run says so (decision 4).

Every armed press that may drop the link (these openings, a never-choose option, a confirmation or a final step of a
reset that wipes the link) follows one rule:

- before the press is handed over, the run writes `RESTORE_BY_HAND.json`, naming its start file: the intent;
- refused before it went (`camkit.safety.Refused`, a STOP, or `camkit.link.CameraRefused`, a reply that said "not
  accepted": the camera did nothing), the file is taken away and the run closes with MENU and restores as any refusal
  does;
- any other failure (no reply, a timeout, a button left held, the run's own error) keeps the file: the run presses
  nothing more, tries no remote restore and exits with status 5;
- once the press went, the run reads the screen once; a read that fails, a black frame, a screen of no kind the kit
  reads or a text it cannot read keeps the file, and the run exits 5 having pressed nothing more;
- a screen that reads as the row's own question means nothing was done: a dialog or a notice that asks, with a "?" or
  a dialog's two buttons (Enter, OK or Execute with Cancel), and whose text is the action's confirmation (or, with a
  "?", reads as one); a notice that says the action was done ("Network settings have been reset. OK") asks nothing and
  is the next case. MENU alone cancels the question, never Enter, at most three times until the
  question is gone, and the run restores as ever; when the restore checks out the file is taken away, `drive.jsonl`
  says "question shown, cancelled" with the question's frame, the evidence that the row opens to a question, and the
  run exits with status 6 (`EXIT_NOT_CONFIRMED`): nothing was confirmed. When MENU does not clear it, the file stays,
  the run exits 5 and says that a person must cancel the question on the camera;
- any other screen, the link still answering: MENU alone back to the shooting screen and the remote restore; the file
  is taken away only when that restore checks out, else the run exits 5. `drive.jsonl` then says "pressed; the link
  answered", and nothing claims the press did nothing.

What `drive.jsonl` keeps of the screen read after such a press is what it keeps of every screen inside the owner row:
its field names and whole row labels, its text only where the decision says `"values": "logged"`. Every exit 5 tells
the owner to cancel by hand, with MENU or Cancel and never Enter or OK, whatever the camera still shows (a question, a
pairing, search or connection screen), before the start file goes back.

No link opens while that file is there, `kit/tools/upload_check.py`'s excepted for that very start file: it uploads it,
leaves out of the count the records no settings file sets back (the memory slots' registrations, 0x18cb's fourth slot,
0x1126), says them, and removes the file when nothing else differs. When records still differ it lists them and the
file stays; the owner, having looked at them on the camera, may accept them by naming them back, `--accept
0x1126,0x18cb` (`set1:0x023c` for one section's), which removes the file only when those are exactly the records that
differ: the owner's step, never an agent's, and never passed blind. Where `CAMSET_RUNS` points elsewhere, the file is
written, looked for and removed in the run's own runs folder and in the clone's `runs/` for the same camera key. The
file is per camera key: one under another camera's key is that camera's and holds no other. `kit/tools/chain.py` stops after status 5 and uploads
no end file, and stops after status 6 as after status 4. The maintainer, the a1 II's owner, decided this for their own
camera on 2026-11-13.

Before 2026-11-13 Initialize and Reset Network Set. were never pressed, whatever was decided.

## Consequences

A reset run ends with the start file uploaded and checked (0 records differ), except a decided link-wiping reset that
may have acted, whose start file goes back by hand before any other run. A first run on Reset Network Set. or SSID/PW
Reset whose Right only asks ends with status 6 and the question's frame: what Right shows there is then known.
