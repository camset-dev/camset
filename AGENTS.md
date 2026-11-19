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

The playbook's [section 1](docs/REMAPPING_PLAYBOOK.md#1-rules-that-are-never-broken) holds them as the defaults for
someone else's camera, stricter where the maintainer allowed more on their own, and the kit's own rules beside them.
When a rule and progress conflict, stop and ask the owner.

- Nothing that makes sound, light or motion is changed remotely; the one picture for the Playback rows is taken only on the owner's word typed at their terminal ([decision 2](docs/decisions/0002-nothing-that-makes-sound-light-or-motion-is-changed-remotely.md)).
- The camera's Screen Reader only with headphones in and its volume at the lowest first, with the owner's word each time ([3](docs/decisions/0003-the-screen-reader-only-with-headphones-in.md)).
- Never format or delete a card. The one exception is a camera whose owner has written a dated owner decision in its reviewed scope (so far the maintainer's a1 II): it names the row by its path, and only a `drive.py --owner --confirm` run's armed last press opens or confirms it, after the person at the terminal has typed the row's name (asked before every `--owner --confirm` run; no flag answers it; only `"unattended": true` in the decision waives it). That question stops a careless agent, not a determined one: a program driving a pseudo-terminal can answer it, so the owner types the answer themselves, and you never answer it for them ([4](docs/decisions/0004-never-delete-or-format-the-cards.md)).
- Never Initialize, Reset Network Set. or SSID/PW Reset; a reset for a proof only the narrowest, only if the owner allows it, with their file put back after. The one exception is a camera whose owner has written a dated owner decision in its reviewed scope (so far the maintainer's a1 II): with `"link_loss": true` it lets Reset Network Set. or SSID/PW Reset be a `drive.py --owner --confirm` run's last press, once the person at the terminal has typed the row's name, `RESTORE_BY_HAND.json` written before it; the run exits 6 when that press only brought up the reset's question, cancelled with MENU and the start file restored, and otherwise, unless the link still answered and the restore checked out, exits 5 and no link opens until `kit/tools/upload_check.py` has put its start file back. Initialize never ([5](docs/decisions/0005-settings-resets-for-proofs-the-narrowest-never-initialize.md)).
- No hand-made settings files: only files the camera wrote are uploaded ([6](docs/decisions/0006-no-hand-made-settings-files.md)).
- C4 only as guarded Help, on the menu, option and panel screens whose footer draws it: never in Playback or with a picture displayed, where it deletes, nor on the shooting screen, where it does whatever the body assigns to it; C1-C3 and C5-C7 never ([7](docs/decisions/0007-the-c4-key-only-where-it-is-safe.md)).
- No key but MENU on the shooting screen, where a key does what the body makes of it (a Custom Key, the focus frame, the live exposure), unless the run names the key for that press ([21](docs/decisions/0021-on-the-shooting-screen-no-key-but-menu-unless-it-is-named.md)).
- USB, language, NTSC/PAL, area and date, and network identity are changed by the owner's hand; a look lap (`--network`) may open such a row to look at, keeping none of its text, and an option is chosen only where the owner's dated decision names it ([8](docs/decisions/0008-by-hand-only-usb-language-region-and-network-identity.md), [24](docs/decisions/0024-a-look-lap-opens-every-row-to-look-at.md)).
- Credentials are never typed, read, OCR'd, screenshotted or stored; a credentials screen such as Access Authen. Info is opened only on a look lap, its frames saved black, nothing typed, read or stored. The one exception is a camera whose owner has written a dated owner decision in its reviewed scope (so far the maintainer's a1 II): it may open a credentials screen for `drive.py --owner`, nothing ever typed, its frames saved black unless it says `"values": "logged"`, which keeps its frames as they are in the run's `shots/` and their text in its `drive.jsonl`, never in the console, the proof viewer or a packed copy ([9](docs/decisions/0009-credentials-are-never-read-or-stored.md)).
- The camera is free for tests: ask the owner only for physical actions and visual checks, menu routes first ([10](docs/decisions/0010-the-camera-is-free-for-tests.md)).
- Every run starts from a known file and ends restoring it; stop a run with its STOP file (a file named `STOP` in the run's folder, which the run checks; see the playbook's [section 10](docs/REMAPPING_PLAYBOOK.md#10-recovering-from-a-stopped-run)), never kill it with a dialog open ([15](docs/decisions/0015-every-run-starts-from-a-known-file-and-ends-restoring-it.md)).
- The owner's values never reach the schema or the docs ([16](docs/decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)).

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
