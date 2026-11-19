# Briefing for an AI agent

Camset reads, compares and edits Sony camera settings files (`CAMSET*.DAT`): the Camset Editor (`editor/`) shows
every setting in a file by name, and the mapping kit (`kit/`) proves on the camera what each record holds. The editor
knows a camera through its definition, a file the kit writes once it has mapped it; the one it ships with so far is
the ILCE-1M2 (a1 II)'s, firmware 4.00.

## What you will do

Map the owner's camera (the owner is the person whose camera it is, whom you work with) with the kit, and talk them through it. Check the body first, then scan its menus, crawl every
row read-only, prove each option on the camera (choose it, download the file, see which records changed; passes 1 to 3) and report:
the order is the playbook's [section 7](docs/REMAPPING_PLAYBOOK.md#7-order-of-work), and "done" is its
[section 15](docs/REMAPPING_PLAYBOOK.md#15-what-done-looks-like). The evidence (frames, downloads, `proofs.jsonl`, the
report, and the proof viewer, `kit/tools/proof_viewer.py`, which shows the owner each value beside the camera's own
screens and exists only where the kit has run) stays in `runs/`, never part of the submission. What is learned goes
into `data/<model>_fw<fw>/` ([the files and how each is made](docs/DATA_CONTRACTS.md#what-a-mapping-delivers),
[their shapes](docs/DATA_CONTRACTS.md)), with the notes the playbook's "What you deliver" names.
The last step is the camera's own definition: `kit/schema_update.py --write`,
with the owner's camera the one the kit works on, writes `editor/definitions/<model>_fw<fw>.json`
([decision 19](docs/decisions/0019-definitions-are-files-one-per-model-and-firmware.md)), never another camera's, lean:
how, when and in which run each thing was proved goes into `private/evidence/<model>_fw<fw>.json`, which stays with
the owner ([decision 16](docs/decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)); the
pre-commit hook never writes a definition. The owner then opens their files with it the same day, with no new editor:
Settings > Camera support & web page > Add definition… in the editor.

## Rules that are never broken

Each rule below is its decision record's Rule line, written here by `kit/tools/build_docs.py`; the record says why and
how the kit holds to it. They are the defaults for every camera. How an owner allows more on their own camera, what the
maintainer allowed on theirs, and the kit's own rules beside these are in the playbook's
[section 1](docs/REMAPPING_PLAYBOOK.md#1-rules-that-are-never-broken); never assume an allowance: ask the owner, and
the default is no. When a rule and progress conflict, stop and ask the owner.

<!-- the rules: written by kit/tools/build_docs.py from the records in docs/decisions/ marked "Never broken", each its record's Rule line; edit those -->

- Nothing that makes sound, light or motion is changed remotely (beeps, audio signals, volume, the AF illuminator, tally and other lamps, flash, modelling light, video light, the lens motor of Pre-AF and Eye-Start AF, Shutter When Pwr OFF's curtain, SteadyShot; the Screen Reader only as [decision 3](docs/decisions/0003-the-screen-reader-only-with-headphones-in.md) says): these change by the owner's hand. The one picture for the Playback rows is taken only on the owner's word, which they type themselves at their own terminal to `kit/tools/take_picture.py`, never an agent for them ([decision 2](docs/decisions/0002-nothing-that-makes-sound-light-or-motion-is-changed-remotely.md)).
- The camera's Screen Reader is changed remotely only with headphones in and its volume at the lowest first, and only with the owner's word each time: turned On only so, its other settings changed with it Off, and the owner's value put back last ([decision 3](docs/decisions/0003-the-screen-reader-only-with-headphones-in.md)).
- Never format or delete a card. The one exception is a camera whose owner has written a dated owner decision in its reviewed scope (so far the maintainer's a1 II): it names the row by its path, and only a `kit/drive.py --owner --confirm` run's armed last press opens or confirms it, after the person at the terminal has typed the row's name (asked before every `--owner --confirm` run; no flag answers it; only `"unattended": true` in the decision waives it). That question stops a careless agent, not a determined one: a program driving a pseudo-terminal can answer it, so the owner types the answer themselves, and an agent never answers it for them ([decision 4](docs/decisions/0004-never-delete-or-format-the-cards.md)).
- Never Initialize, Reset Network Set. or SSID/PW Reset; a reset for a proof only the narrowest, only if the owner allows it, with their file put back after. The one exception is a camera whose owner has written a dated owner decision in its reviewed scope (so far the maintainer's a1 II): with `"link_loss": true` it lets Reset Network Set. or SSID/PW Reset be a `kit/drive.py --owner --confirm` run's last press, once the person at the terminal has typed the row's name (never an agent for them: [decision 4](docs/decisions/0004-never-delete-or-format-the-cards.md)), `RESTORE_BY_HAND.json` written before it; the run exits 6 when that press only brought up the reset's question, cancelled with MENU and the start file restored, and otherwise, unless the link still answered and the restore checked out, exits 5, and then no link opens until `kit/tools/upload_check.py` has put its start file back. Initialize never ([decision 5](docs/decisions/0005-settings-resets-for-proofs-the-narrowest-never-initialize.md)).
- No hand-made settings files: the kit, and whoever maps a camera, changes settings on the camera and watches, never by editing a file, and uploads only files that camera wrote, each checked by its bytes against that camera's own downloads, wherever it sits. The editor, which writes a file its user edited, is that user's: a mapping, or an agent working for an owner, never writes a file through it ([decision 6](docs/decisions/0006-no-hand-made-settings-files.md)).
- C4 only as guarded Help, on a menu or option screen whose footer draws the help button: never in Playback or with a picture displayed, where it deletes, nor on the shooting screen, where it does whatever the body assigns to it; where the body lists its operating mode, C4 also needs the camera to give one that is not Playback, and it never goes where that mode, or whether the body lists it, cannot be read; C1-C3 and C5-C7 never ([decision 7](docs/decisions/0007-the-c4-key-only-where-it-is-safe.md)).
- No key but MENU on the shooting screen, where a key does what the body makes of it (a Custom Key, the focus frame, a dial's change to the live exposure, which no file puts back), unless the run names the key for that press: with `kit/drive.py --on-shooting KEY`, on the owner's word, or in a prover's own code where that press is its point, and then only on a body where it is known what that key does there (on another body, its owner's word first); and none but MENU with no screen read, named or not. A named key's change is not put back by the run's restore: the run names and presses the keys that undo it. A screen read as the shooting screen while the camera says it is in Playback is the playback view: there no key goes out but MENU, and the Playback button once, only to get back; never C4 or Delete ([decision 21](docs/decisions/0021-on-the-shooting-screen-no-key-but-menu-unless-it-is-named.md)).
- USB settings, language, NTSC/PAL, area and date, and the camera's network identity and connection settings (Wired LAN, Wi-Fi, Bluetooth, access authentication, FTP server) are changed by the owner's hand: no `--allow` opens one of them, whatever the owner said, and an option in one is chosen remotely only where the owner's dated decision names it, never in Language, NTSC/PAL or Area/Date/Time. In a row whose choice drops a link, starts a connection or a pairing, or changes what no file puts back, a `--network` run (a look lap) never chooses; a dated owner decision in the camera's reviewed scope chooses there only with `"link_loss": true`, as the armed last press of a `kit/drive.py --owner --confirm` run, after the person at the terminal has typed the row's name, never an agent for them. Auto Power OFF Temp. is changed by the owner's hand too, unless a run names that row with `--allow`, the owner's word ([decision 8](docs/decisions/0008-by-hand-only-usb-language-region-and-network-identity.md)).
- A look lap, a run of `kit/drive.py` or `kit/crawl_run.py` given `--network`, may open any row to look at, no decision naming it, with up, down and MENU alone, asking local readers only and keeping no screen's text; never what never opens (a firmware update, what loads, the sensor's, shutter's or lens's motion, Initialize, the Screen Reader); a row whose opening acts, or a format, delete or reset this body has not been seen to open, only by the owner's own run; a row not yet seen opened only under the first-open procedure. It chooses an option only where a dated owner decision names it. The body's serial number screen opens only on a look lap or the owner route, which save its frames black ([decision 24](docs/decisions/0024-a-look-lap-opens-every-row-to-look-at.md)).
- Credentials are never typed, read, OCR'd, screenshotted or stored: the user name and password live only in `~/.config/camset/network.json`, which the owner writes (mode 600 on macOS and Linux), never committed, and nothing is ever typed on the camera, a keyboard or an entry screen getting MENU alone. A credentials screen such as Access Authen. Info is opened only on a look lap, MENU alone pressed there and its frames saved black, nothing read or stored. The one exception is a camera whose owner has written a dated owner decision in its reviewed scope (so far the maintainer's a1 II): it may open a credentials screen for `kit/drive.py --owner`, nothing ever typed, its frames saved black unless it says `"values": "logged"`, which keeps its frames as they are in the run's `shots/` and their text in its `drive.jsonl`, never in the console, the proof viewer or a packed copy ([decision 9](docs/decisions/0009-credentials-are-never-read-or-stored.md)).
- The camera is free for tests, which run without asking: the owner is asked only for physical actions (switches, dials, turning the camera, cables, opening the screen, by-hand menu actions and resets) and visual checks, and menu routes are tried first ([decision 10](docs/decisions/0010-the-camera-is-free-for-tests.md)).
- Every run starts from a known file and ends restoring it: it downloads its start file first and, at its end, uploads it, waits for the camera's restart, downloads again and checks the records match, and live state the file does not hold is put back by hand and checked; a session ends with the owner's own file back, never a run's changes left on the camera. A run is stopped with its STOP file (a file named `STOP` in the run's folder, `runs/<model>_fw<fw>/<run>/STOP`, which the run checks; `kit/camkit/runs.py` names wider ones; see the playbook's [section 10](docs/REMAPPING_PLAYBOOK.md#10-recovering-from-a-stopped-run)) or, once its link is open, one Ctrl-C, after which it cancels and restores (a second Ctrl-C stops it at once, which is not safe); a run is never killed, nor the camera disconnected, with a dialog open: a dropped session can apply it ([decision 15](docs/decisions/0015-every-run-starts-from-a-known-file-and-ends-restoring-it.md)).
- The owner's values never reach a definition, the data files or the docs, which hold names and value meanings only: two owners who map the same model and firmware get the same definition. A value a camera held, and how, when, in which run or from which state each thing was proved, stay in the mapper's private evidence; a proof whose label would reveal the owner's choice (a picker's saved function) is not planned ([decision 16](docs/decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)).

<!-- end of the rules -->

The kit enforces most of them itself. On a body nobody has seen, what protects is the first-open procedure (a row not
yet seen opened opens only on the owner's blank-cards statement, `RESTORE_BY_HAND.json` written before it, the settings
checked after), the check that refuses to answer a question, and the blank cards; `kit/camkit/safety.py`'s never-open
list and the look lap's own lists (what never opens, what acts as it opens, a format, delete or reset) are a second
check, and its inputs never sent and confirmation check stay as they are: add the new body's names to its lists. `kit/drive.py` refuses Format,
Delete, Enter on Initialize and C4 off its screens, the one row a dated owner decision gives a `--owner` run aside,
whose armed last press `drive.py` and the camera's own check (`camkit.live`) each judge; `Link.press` refuses C4 on any screen but a menu, option, panel
or editor screen (the screen is the guard); `Link.upload` (`kit/camkit/link.py`) refuses any file whose bytes
are not one of the camera's downloads (each download's SHA-256 is kept in the camera's
`runs/<model>_fw<fw>/downloads.jsonl`), wherever it sits; `kit/tools/check_public.py` refuses a commit or pull request
that tracks `private/`, `runs/`, Sony's SDK, a settings file other than a definition's scrubbed sample or another
binary file, or that holds a MAC address, a private network address, a serial
number, an e-mail address or a home folder other than the docs' placeholders. Your name and the camera's help text
it finds only as far as your `private/` lets it ([CONTRIBUTING](CONTRIBUTING.md#what-a-contribution-must-keep) says
what to search for yourself).

## What only the person can do

- Download Sony's Camera Remote SDK under Sony's agreement and drop the zip into `kit/sdk/`, then `python3 kit/setup.py` builds the rest ([QUICKSTART](docs/QUICKSTART.md), step 1; the terms: [RELEASING](docs/RELEASING.md)). It is never committed or shared.
- Type credentials: the camera's user name and password into `~/.config/camset/network.json` ([decision 9](docs/decisions/0009-credentials-are-never-read-or-stored.md)), and a reader's API key into their own shell.
- Physical actions: the mode dial and the Still/Movie/S&Q switch, a flash, cables, headphones, turning the camera; one action per message ([playbook, section 9](docs/REMAPPING_PLAYBOOK.md#9-working-with-the-owner)).
- Put in cards that hold nothing they want kept, and answer `kit/tools/owner_statement.py cards` and `kit/tools/take_picture.py` in their own terminal; you never answer for them, nor write a statement yourself.
- Choose the vision-language model (VLM) that reads the camera's screen, and pay for it if it costs money: one on their own computer or server first (Qwen3.8 27B is what this project used), a smaller local model next, then a paid service that offers one ([Choosing a reader](docs/QUICKSTART.md#choosing-a-reader)).

## Order of work

1. [docs/QUICKSTART.md](docs/QUICKSTART.md), steps 0 to 3: ask which camera, how it connects and whether there is a
   capture dongle; once the person has put Sony's SDK zip into `kit/sdk/`, run `python3 kit/setup.py`, then check the
   body.
2. The playbook's [section 1](docs/REMAPPING_PLAYBOOK.md#1-rules-that-are-never-broken), the rules, before QUICKSTART
   step 4, the first command that opens the camera's link.
3. QUICKSTART steps 4 to 6; then, on a layout `identify.py` does not call KNOWN, the playbook's
   [section 16](docs/REMAPPING_PLAYBOOK.md#16-new-model-first-day), "New model: first day".
4. QUICKSTART steps 7 to 9, the first proved setting; then [the playbook](docs/REMAPPING_PLAYBOOK.md) from section 7's
   Phase 1, its other sections as the work reaches them.

## Where things go

- `private/`: the person's own folder, git-ignored: their config (`private/config.json`, copied from
  `kit/config.example.json`), their camera's files, the help text read off it. Never commit it
  ([decision 18](docs/decisions/0018-one-public-codebase-with-a-private-overlay.md)).
- `runs/<model>_fw<fw>/`: local only, never versioned: the camera's frames, downloads, logs and proofs, one folder
  per camera as `data/` has (a second body never writes into the first's). `kit/tools/identify.py --camera` starts
  it; name the camera in `private/config.json` (`"camera"`) or pass `--camera <model>_fw<fw>`
  ([QUICKSTART, "Where the runs go"](docs/QUICKSTART.md#where-the-runs-go)).
- `data/<model>_fw<fw>/`: the results.
- `editor/definitions/<model>_fw<fw>.json`: the camera's definition, which `kit/schema_update.py --write` writes from
  those results and the proofs.

## Sending the results back

A pull request with the submission bundle: the `data/<model>_fw<fw>/` folder, the camera's definition
(`editor/definitions/<model>_fw<fw>.json`, as `kit/schema_update.py --write` wrote it), its record names
(`docs/formats/sony_camset_ids_<model>_fw<fw>.ksy`; [what writes them](docs/DATA_CONTRACTS.md#what-a-mapping-delivers)),
the model's page, and pasted into the description the pass-2 report's counts and conflicts and the gate line
`kit/schema_update.py` prints without `--write` ("gate: … open questions …"); never another camera's definition, and
never the evidence file (`private/evidence/`). Every commit is signed off (`git commit -s`). [CONTRIBUTING.md](CONTRIBUTING.md) says what the maintainer
checks and what a contribution must keep; [the template](.github/PULL_REQUEST_TEMPLATE.md) holds the checklist.
