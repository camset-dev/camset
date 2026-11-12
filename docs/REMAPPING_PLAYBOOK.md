# Remapping a Sony camera's settings file: playbook for an agent

This is for an AI agent asked to map the CAMSET `.DAT` settings file of a Sony body other than the
one this project was built on: an a1 II (ILCE-1M2, firmware 4.00), mapped October 2026. Read all of
it before touching the camera. Read the safety rules twice. A mapping begun with an older clone is
updated first ([UPDATING.md](UPDATING.md)).

**Goal:** for every record in the file, prove on the camera which menu setting it holds and what
each stored value means. Then record those facts in the model's `data/<model>_fw<fw>/` folder, from which the kit
writes its definition for the editor, `editor/definitions/<model>_fw<fw>.json`.

A record counts as "proved" only when the camera itself showed the option and wrote the value.
Nothing is copied from another model or from documentation without proof.

**What you deliver:**
- The `data/<model>_fw<fw>/` folder ([which files, and how each is made](DATA_CONTRACTS.md#what-a-mapping-delivers))
  and the model's page (below).
- The model's definition, `editor/definitions/<model>_fw<fw>.json`
  ([decision 19](decisions/0019-definitions-are-files-one-per-model-and-firmware.md)): `kit/schema_update.py --write`
  writes it last, with that camera the one the kit works on (Phase 6), never another camera's; the owner opens their
  files with it in the editor the same day (Settings > Camera support & web page > Add definition…). It is lean: how,
  when and in which run each thing was proved goes into `private/evidence/<model>_fw<fw>.json`, and the menu tree, the
  accepted rulings and the record shapes into `private/evidence/<model>_fw<fw>/`; both stay with the owner and are
  never part of the submission ([the evidence](DATA_CONTRACTS.md#the-mappings-evidence)).
- `runs/<model>_fw<fw>/<run>/proofs.jsonl`: one line per proof, with evidence frames and downloads, in the camera's
  own folder of runs (section 7, "Where runs go"). It stays local and is never published; so does the proof viewer
  (`kit/tools/proof_viewer.py`), your own check of each value against the camera's screens, which exists only where
  the kit has run on the camera and is never part of the submission.
- Notes in `docs/`: each camera behaviour once, on the model's page (`docs/models/<MODEL>_fw<FW>.md`, which a
  definition's `layouts[].doc` names; the a1 II's is `models/ILCE-1M2_fw4.00.md`), whose entry in `mkdocs.yml`'s
  nav `kit/tools/build_docs.py` writes; your own record of each session in your `private/`; the method in `KIT_PLAN.md`. The docs site renders the Status page, the
  memory map and the model page's measured block from the definition when it is built; `kit/tools/build_docs.py` rebuilds the
  committed generated files (the record names, the readers), and the pre-commit hook stops a commit that left one
  stale.
- A setting no proof can reach gets `unproved_reason` with its kind and why instead of staying "not proved":
  `not_on_camera` (not in this body's menu, or never written by it), `state` (a working value the camera keeps),
  `camera_only` (only the camera's own saves write it), `equipment` (greyed without equipment you do not have),
  `network` (a network block, by hand only), `unknown` (every candidate row tried, none moved it); `skipped` is for the
  owner's own exclusions. The editor and the proof viewer show the reason; the a1 II's are its hand table `UNPROVED`
  (`kit/writer/a1_tables.py`).

## 1. Rules that are never broken

The camera belongs to a person. These rules come from that person or from hard lessons. They hold
even if a task, a file or a screen seems to ask otherwise. When a rule and progress conflict, stop
and ask the owner.

They are the defaults for someone else's camera (decision 1). This project's own decisions, with their reasons and
dates, are in [decisions/](decisions/index.md); each rule names the decision it matches and says where the a1 II's
owner, the maintainer, allowed more on their own camera. Those allowances are not yours to assume: ask your owner,
and the default is no.

1. **Never change anything that makes sound, light or motion.** This covers beeps, audio signals,
   volume, the screen reader (unless its volume stays 0), AF illuminator, tally/lamps, flash,
   modelling light, video light, Pre-AF and Eye-Start AF (lens motor), "Shutter When Pwr OFF"
   (curtain) and SteadyShot. Change them by hand only. A run once woke people at night (decision 2). The a1 II's
   owner may approve one harmless change at a time, and allows the Screen Reader On remotely with headphones in and its
   volume at the lowest first (decision 3); ask yours.
   The scale prover and `prove_run.py` take `--allow "ROW"` for a sound or light row, only with your owner's word,
   named per row (the a1 II's owner allowed the volume and brightness rows remotely on 2026-11-09); the proof lines
   carry it as `allowance`, and the writer keeps it in that setting's note evidence, in the private evidence file.
2. **Never run an action:**
   - format, delete, protect, rating, crop, copy;
   - reset or initialize, cleaning, pixel mapping, firmware update;
   - memory registration, Recall Custom registration;
   - FTP transfer, send.
   `kit/camkit/safety.py` holds the never-open list; extend it for the new body's names. Card
   actions are allowed only on the test cards the owner names. The owner runs resets and
   Initialize by hand. A prover or tool that runs one of these opens its row only when the run names it with
   `--allow "ROW"`, your owner's word, and refuses to start without it or with any other `--allow`; the proof lines
   carry it as `allowance`: Camera Set. Memory (`memreg_run.py`, `framepos_run.py`), Reg. Custom Shoot Set
   (`customshoot_run.py`, `customshoot_values.py`), My Menu's Add Item (`mymenu_run.py`), a card row
   (`kit/tools/card_actions.py`, which judges each press as `drive.py` does and ends restoring as every runner
   does) and Picture Profile Reset (`pp_reset_run.py`, each profile's own Reset row; it writes no proof line, and its
   result carries the words). (Decisions 4 and 5. The a1 II's owner allows no Format or Delete remotely on any card,
   and allowed Camera Settings Reset, the narrowest reset, for proofs with their file put back after, and each
   Picture Profile's own Reset for the sample; never Initialize or Reset Network Set. Ask yours: the default is no
   reset.)
3. **By hand only:** network identity and connection settings (Wired LAN, Wi-Fi, Bluetooth, access
   authentication, FTP server), USB connection mode, language, NTSC/PAL, area and date, and Auto
   Power OFF Temp. (Decision 8. The a1 II's owner allowed Auto Power OFF Temp. remotely from 2026-11-02; ask yours.)
   No `--allow` opens the camera's identity, its connections or its region, whatever the owner said: `drive.py`,
   `card_actions.py` and every prover refuse such a label before anything connects (`safety.allow_refused`), and the
   checks on the camera refuse the row however a run named it (`safety.never_lifted`).
4. **Credentials:**
   - Never type, read, OCR, screenshot or store a password. That includes the camera's own Access
     Authen. Info screen: never navigate the kit there, because every frame is kept as evidence.
   - The owner puts the user name and password in `~/.config/camset/network.json` (mode 600).
     It is never committed (decision 9).
5. **Every run starts from a known file and ends by restoring it.**
   - Restoring means uploading the start file, waiting for the camera's restart, downloading
     again and checking the records match.
   - At the end of the session the owner's own file goes back.
   - Never leave a run's changes on the camera (decision 15).
6. **Never kill a camera run while a dialog is open.** Stop it with a STOP file
   (`runs/<model>_fw<fw>/<run>/STOP`; `runs/<model>_fw<fw>/STOP` stops every run of that camera, `runs/STOP` every
   run). Never disconnect with a dialog open: a dropped session can apply it (decision 15).
   Once a run's link is open, one Ctrl-C (or a tool's SIGTERM) stops it the same way: camlink runs in a process
   group of its own and finishes the command in progress, and the run cancels and restores. A second Ctrl-C stops
   at once, which is not safe.
7. **Long runs go through the tool's background mode, never `&`.** Never pipe a camera run through
   `head`: SIGPIPE kills it mid-run.
8. **A press happens only on a screen the reader recognises.**
   - Fail closed: an unknown screen gets MENU (cancel), never Enter.
   - Enter only where the screen's text is not a confirmation (`safety.confirmation`). That is each caller's check
     (drive.py's `press_decision`, each prover before its OK): the press choke point (`LiveCamera.press`,
     `Link.press`) does not make it.
   - Never press Enter on table buttons ("Set All", "Rec. Media Settings") or on a "Don't show
     this again" box.
   - A dial turns only on a screen a regex names: on the shooting screen a dial changes the live
     exposure.
9. **Never act on a stale picture.** An HDMI frame older than 2 s raises an error
   (`HdmiSource.STALE`). When HDMI goes black, the kit checks the SDK's OSD image instead.
10. **Values from the owner's camera never go into a definition, the data files or the docs.**
    - A definition holds names and value meanings.
    - The value a row held at the start of a run is filled from a sibling record's labels, so a
      gap cannot reveal it.
    - A picker proof whose label would reveal the owner's saved function is not planned (decision 16).
11. **Ask the owner only for physical things or visual checks.** That means switches, dials,
    turning the camera, cables, opening the screen, by-hand menu actions and resets. Otherwise
    the camera is free for tests (decision 10).
12. **Upload only files the camera wrote.** Settings are changed on the camera and watched; a run uploads only
    the link's own downloads: each one's SHA-256 goes into the camera's `runs/<model>_fw<fw>/downloads.jsonl`, and
    `Link.upload` and `kit/tools/upload_check.py` refuse any file whose bytes are not a download of that camera's,
    whatever folder it is in
    (`upload_check.py --adopt` takes in downloads that the runs' logs show were made before the manifest existed). A
    file edited by hand put the a1 II into a restart loop in Movie mode on 2026-11-01 (decision 6;
    [what ended it](EDITOR.md#if-the-camera-restarts-over-and-over)).
13. **C4 only where it is safe.** C4 is the trash button: in Playback, or wherever a picture is displayed, it deletes
    the picture; on the shooting screen it does whatever the body assigns to it, a change the kit must not make. Send
    it only as guarded Help, on a menu or option screen whose footer draws the help button. The screen is the guard:
    `Link.press` sends C4 only when the screen read last is a menu, option, panel or editor screen, and refuses it on
    the shooting screen, in Playback and with a picture displayed (decision 7, amended 2026-11-06). Whether the body
    lists its operating mode (CameraOperatingMode) is learnt from `props`, once per open link, the first time C4 is
    judged; a `props` that fails or cannot be read refuses C4. When the mode is listed, C4 goes only when `get` gives
    an integer mode that is not Playback: any other answer refuses it, whatever its words, since camlink answers
    "unknown property" for a failed read as for a property not listed. When it is not listed, the screen alone
    decides. The a1 II's owner also allowed it as Focus Area's SET and a Creative Look panel's Reset (decision 7):
    `drive.py`'s `c4set` and `c4reset` presses, each sent only when the run names it with `--c4-press c4set` or
    `--c4-press c4reset`, your owner's word for that run, which the log and `drive.jsonl` keep; ask yours. C1-C3 and
    C5-C7 are never sent.
14. **On the shooting screen, no key but MENU.** There a key does what the body makes of it: on the a1 II the control
    wheel's Center, Left, Right and Down buttons and the multi-selector's centre are Custom Keys, the multi-selector's
    four directions move the focus frame, and a dial changes the live exposure, which no file puts back; which keys a
    body lets its owner assign differs by body, and the rule does not rest on it. `Link.press` and `Link.dial` send no
    key but MENU on a screen read as the shooting screen unless the caller names that key for the press, and none but
    MENU with no screen given, named or not (decision 21). Named so far: the multi-selector's directions that move a
    focus frame (`framepos_run.py`, under its own `--allow "Camera Set. Memory"`; `orient_run.py --af-point`) and the
    Fn hold that registers an area (`afreg_run.py`, with your owner's word: `--allow "Fn hold on the shooting
    screen"`). `drive.py` refuses a press that meets the shooting screen unless `--on-shooting KEY` names it, your
    owner's word, which the log and `drive.jsonl` keep; a key so named is judged there by the naming, since the
    shooting screen has no row to open. A key named for the shooting screen changes what no settings file holds (a
    focus frame's place, the live exposure): the run's restore does not put it back, so name and press the keys that
    do (`ms_right` after `ms_left`). The screen judged is read afresh when the camera may have
    moved behind the kit's back (a download, an upload, a press sent straight through the link). Not covered: a
    shooting screen the reader takes for another kind (a DISP mode that draws no battery reads as unknown); a black
    frame is judged on the camera's own picture of the screen.

## 2. What carries over to a new model, and what does not

**First, can the kit drive the body at all?** `kit/tools/body_check.py` says (section 4); what its answers mean, and how to
build the table it reads from your own SDK, is in `CAMERA_SUPPORT.md`.

**Carries over (the kit):**
- the file reader and writer (`kit/camkit/camset.py`) and the camera link (camlink, `kit/link/`, on Sony's
  SDK);
- the screen reader's screen types (`kit/camkit/screen.py`);
- the scan, crawl and prove pipeline and every special prover;
- the report and definition tools;
- all the pitfalls below.

Bodies with the 2021-and-later menu system (`CAMERA_SUPPORT.md`, "Menu system") share the same screens, so most
readers should work unchanged.

**Does not carry over (prove again):**
- **Record ids, counts and value codes.** Treat every a1 II mapping as a hypothesis for the new
  body, at most a hint of where to look.
- **The menu's pages, rows and labels.** Scan and crawl again; each mode (Stills, Movie, S&Q) has
  its own menu.
- **Screen geometry and templates, if the UI resolution or layout differs.** That means the HDMI
  crop, row pitch and battery glyph templates. Check them with `kit/tools/selftest.py` and
  `kit/tests/score_screen.py`, and recut templates from the new camera's own frames.
- **Which settings Camera Settings Reset leaves alone, which records a file cannot set, and which
  records the camera writes only once.** Measure them again.

## 3. The file

The layout is the camera file's container block ([the container block](DATA_CONTRACTS.md#the-container-block-file));
the ILCE-1M2's is on [the file format](formats/index.md) page too, as a Kaitai spec. Check every number on the new
body: `kit/tools/identify.py` says whether a known block reads its files, and prints a draft when none does. `camset.read` and `camset.diff` are all a run needs. Keep the a1
II's lessons about records in mind (its own record ids are on [its page](models/ILCE-1M2_fw4.00.md), "The file"):

- **Volatile records** change on every save, or follow the camera rather than the file
  (`camset.VOLATILE`).
  Find the new body's by downloading twice with no change, and by turning the camera.
- **Records a file cannot set.** Upload a download and download again: anything that does not match
  was never loaded.
- **First-use records** hold 0 until their feature is used, then keep a value.
- **Copies and linked records.** One menu choice often writes two to seven records: copies, an
  "in use" record plus a per-mode record, or alternate numberings. The prover records all of them;
  the report names each record by its own row.
- **Arrays** carry per-slot values: Picture Profile (11 profiles), Creative Look (18 looks), the
  Fn and Custom Key slots, and the memory tables. A definition keys them `global:0x....[i]`.
- **The memory sets** hold copies of the live settings taken at registration.

## 4. Setup

**First:** `.venv/bin/python kit/tools/body_check.py --model ... --link ... --eyes ...` with the owner's answers
(which camera, how it connects, whether there is a capture dongle), after `kit/tools/sdk_support.py --json`
(`QUICKSTART.md`, step 1). It says from the SDK's tables whether the kit can drive the body (`CAMERA_SUPPORT.md`).

**Hardware:**
- the camera, with the lens cap on (so the live view behind dialogs is plain black) and test cards in both slots;
- **eyes**, one of:
  - an HDMI capture dongle (Elgato Cam Link 4K) at 1080p59.94, with HDMI Info. Display On, calibrated in `private/config.json`
    `"hdmi"` (crop to the 640x480 canonical layout). Use a micro-to-full cable for micro-HDMI
    bodies;
  - no dongle: `"eyes": "osd"` (or `CAMSET_EYES=osd`), and every script watches the SDK's OSD
    image. It was tested on the a1 II (its page, "Connection and capture"). Scan the menu with the same eyes the
    runs will use;
- the network (Wired LAN with access authentication) or a USB-C data cable to the computer.

**Software,** as `QUICKSTART.md` step 1 installs it: the Sony Camera Remote SDK (`kit/sdk/`, v2.02) and the link;
Apple Vision OCR on the Mac and RapidOCR everywhere, which miss different rows, so the page model counts them as two
votes (`PORTING.md` has the comparison; on Windows and Linux RapidOCR is the only OCR); and the VLMs in
`private/config.json` `"readers"` (section 5).

**Connecting:**
- **Over the network:** the camera's IP is `camera_ip` in `private/config.json`, the credentials
  file is the owner's, and the camera's Remote Shoot Function must be On.
- **Over USB:** `export CAMSET_USB=1` in the shell, for every script; the config has no USB setting.
  The camera's USB Connection Mode must be PC Remote, and the computer must see the camera: `ioreg -p IOUSB` lists
  it on a Mac, `lsusb | grep 054c` (Sony's USB vendor id) on Linux, and Device Manager shows "Sony Remote Control
  Camera" on Windows (`PORTING.md`).

**Mac quirks already solved:** `QUICKSTART.md` step 1, "On macOS".

**Before anything else:** the offline tests and the self-test (`QUICKSTART.md` steps 1 and 6).

## 5. Readers: accuracy before speed

Every name and value label in a definition comes from at least two independent readings that agree.
The kit is built around that rule, so it needs reading tools. **More readers, and stronger ones,
give better labels. This project chose accuracy over time:** a slower run with more readers is the
right trade.

**The readers and what each is good and bad at:**
- **OCR** (Apple Vision, `kit/ocr`, local, about 0.1-0.3 s a frame): exact characters, numbers and
  punctuation. It reads icons as letters ("S&d", "MR", "(V)", "#") and confuses Latin with Cyrillic
  look-alikes ("30р", "ОК"). It clips short words ("Aut") and merges neighbours ("15" for the ◂ and
  the 5). **RapidOCR** (PaddleOCR's models on ONNX Runtime, every OS, about 0.2 s a frame) is
  the second engine. It reads icons as letters less often but drops a letter now and then
  ("Create Still mage"). The page model counts the two as separate votes (`ocr`, `ocr2`), and on
  Windows and Linux RapidOCR is the first engine (`PORTING.md`).
- **Vision-language models (VLMs)** (any OpenAI-compatible `/v1` server, `private/config.json`
  `"readers"`: name, url, model, parallel): they read meaning and ignore icons, and they read turned
  screens. But they **invent answers on black or blank frames**: Framing Stabilizer's black preview
  frame became "Auto", titled White Balance. They also drop marks ("Spot S" for "Spot: S") and
  sometimes answer with the icon's text. This project used Qwen3.8 27B (`RedHatAI/Qwen3.8-27B-INT4`),
  INT4 on a GPU server through vLLM (8 parallel, about 1 s a frame), plus the same model 4-bit
  through omlx on the Mac as the third reader.
- **Claude** (`kit/camkit/claude_reader.py`, through the Anthropic Messages API): a reader entry
  with `"kind": "anthropic"`, for example
  `{"name": "claude", "kind": "anthropic", "model": "claude-opus-5-5", "parallel": 4, "effort": "medium"}`.
  - It needs no GPU of your own: a strong second or third reader where no local server exists.
  - Credentials come from the environment (`ANTHROPIC_API_KEY`, or `ant auth login`). The kit never
    stores a key.
  - Each frame is paid for once and cached; refusals are not cached.
  - Requests opt into server-side fallbacks, so a declined request is re-run on another model.
- **The agent's own eyes** on the saved frame, where the readers disagree. It goes in
  `checked_labels.json`, naming the frame, and never counts as the owner's word.
- **The owner** (`user_labels.json`): only what they confirmed themselves.

**Which reader plays which role** is set in `private/config.json` `"roles"`, for example
`{"second": "claude", "third": "omlx"}`. The second reading is asked on every proof; the third
breaks ties. Without `"roles"`, the first two readers listed play them. When the second reader will not connect (a
server on another machine switched off, 2026-11-06), the next local reader that answers stands in for the rest of
the run, never a hosted one by itself; `kit/page_model.py --vlm --reader NAME` names one outright. The reader also
decides where OCR leaves a number box unread (Apple Vision skipped "11 sec" on a frame it had read "10" on): it has
been right every time it was checked against the screen, so it comes before the second OCR engine.

**The minimum** is OCR plus one VLM, a local one first where the hardware allows (the
order: the quickstart's [Choosing a reader](QUICKSTART.md#choosing-a-reader)). **Better** is OCR
plus two VLMs from different families or servers, so that a third reader breaks ties
without the agent's eye. A **VLM-only setup** (two different models agreeing) gives
high-quality labels too. It is slower, and loses OCR's exactness on numbers and punctuation, so
keep OCR if you can.

**Where the kit reads, and with whom:**

| Step | Readers |
|---|---|
| Page labels (`page_model.py`) | two of OCR, each VLM, eye and owner must agree |
| Option labels (`pass1_labels.py`, `tiebreak.py`) | OCR under the cursor plus vLLM, the third reader on disagreement; carousels and grids trust OCR of their orange line |
| During proofs (`prove_run.py`) | OCR finds the option; the VLM keeps a second reading in every proof record (`vlm`) and decides when OCR is unsure. `boxes_run` and `orient_run` keep one too, and `scale_run` keeps one where OCR read the number (two readers only when the VLM read the same number); where OCR reads none, the VLM's number is the only reading (`read_by`: `reader`), one reader, and never decides alone: a choice stands by the count of presses too (section 7, **Scales**) |
| Picker function names (report) | sure only when OCR and the VLM agree |
| Value names (report) | the map's label, unless the VLM backs the OCR's reading instead; OCR never wins alone |

`kit/pass2_report.py` names each proved value from three readings: the pass-1 map's label, the bar's OCR at OK time
(`shown`, the weakest) and the VLM's (`vlm`). The VLM breaks ties and never overrides alone (it can read another row
or a button), so a value it reads far from both, or one the OCR reads unlike the map with no VLM reading, keeps the
map's label and goes into the report's `name_disputes` (listed in full in `report.md`, with the frame to check); each
value's source is in `report.json` (`names`). Proofs written while the VLM was off carry no reading:
`kit/tools/reread_proofs.py --reader omlx` reads their saved frames again (no camera, restartable, `--limit N` for a
trial) into `readings.jsonl`, which the report takes as their `vlm`.

**Rules:**
- Never settle a disagreement by picking the likelier reading silently. Use a majority of three,
  else the eye with a note naming the frame, else ask the owner.
- Never ask a VLM about a black or near-black frame. Check the frame's brightness first.
- **A second reading kept in a proof is a check only if it reads the option chosen.** Count how
  often it names the proof's label. On the a1 II, the Recall Custom hold prover read the screen
  with the cursor already on Register, and the reading named the label in 1 of 235 proofs. Read
  the option before OK, or the screen that shows the value just chosen (a hold's own row shows its
  new value).
- **Matching an option to a label is strict** (`camkit.match.same`, `prove_run.option_key`):
  - digits must match exactly ("1/4000" is not "1/400", "F1.1" is not "F11": keep the decimal point);
  - a close reading must end on the same word, and a short last word must match exactly. "Cont.
    Shooting: Hi+" is 0.9 like "Cont. Shooting: Lo" by ratio, and taking one for the other registers
    the wrong option. A put-back is held to the same rule: it must register the hold's own value;
  - Cyrillic look-alikes are folded to Latin before comparing ("С.Temp");
  - a radio ring is read before or after a short label ("o 4", "4 O").
- Answers are cached by image, prompt and model (`runs/<model>_fw<fw>/_cache/vlm`), so re-reads are free. A new
  model reads everything again.
- Run page and option reading off the camera loop, while the camera does something else.

## 6. The proof, and how runs are shaped

One proof works like this:
1. Download a base file.
2. Open the row, choose one option and press OK.
3. Download again.
4. The records that differ are what that option wrote.

The option the row held at the start is proved last. Its download must equal the base, which
proves the row went back.

**A list with a single option** (XAVC HS 8K's Rec Frame Rate under PAL) has nothing to choose, so no download can
differ. `kit/prove_run.py` proves it by its display instead: it reads the option off the screen with both readers
(OCR and the vision model must both name the map's label), leaves the list with MENU, nothing chosen, and writes
one proof line with `"proof": "display"`, the label, both readings and `"held"`: the values the row's records hold
in the download the proof starts from (its `dat` and `base`). The records are the definition's settings proved
through that row in the state closest to the run's `--context` (`display_records`: a proof context wholly part of
the run's, naming the most of it), so the row must have been proved by choosing in another state first; otherwise
the row fails. `kit/pass2_report.py` takes each held value as the one the label writes, a seen value, and
`kit/schema_update.py` writes it from the report like any other.

**Each run:**
1. Checks the camera against its start file (`--start`), uploading the start file if they differ.
2. Proves rows.
3. Uploads the start file when anything differs from it and checks it took: `kit/camkit/session.py`, which every
   runner ends through (`finish`, then `check_restore`).

A row whose state cannot be put back fails, and the session restores at once.

- **Context.** A proof made in a switched state (Movie mode, a blocker turned off, the camera held
  grip down) carries `--context`, and the report treats it as another row. Each mode or state gets
  its own start file, downloaded in that state.
- **Evidence.** Every frame and download is numbered within the run folder, and nothing is ever
  overwritten.

**Seen, or inferred.** A value is *seen* when choosing its option changed the record to it. A
row's own start is inferred (its visit changes nothing), and that is sound: one option per row.
When two or more options of a row leave a record alone, all but one of them were taken from
"nothing changed": the report lists them (`inferred`, in the run's `report.json`), and the definition
does not: one of them is the record's start, the owner's own value (decision 16), so a value taken from
"nothing changed" is proved and named by its readers like any other. The report's rules for "nothing changed":
- **A record only some options write** keeps its value under the others: a hold's continuous speed
  (0x0bf1) when a bracket is registered. Name it from the options that write it
  (`pass2_report.WRITTEN_BY`), or every other option is credited with the speed held.
- **A row proved in two runs has two starting values**: an option that changed nothing holds its
  own run's.
- **A label seen to change the record outranks the same label from a visit where nothing
  changed**: a visit can miss its option (the self-timer read "Single Shooting" after OK).
- **A two-value axis has one test visit**, where nothing can differ: the option's own records are
  the ones the carousel's own proof of that option wrote (`own_records`). Its held value is credited under its
  reader, as the next rule says; to see that value written too, prove the axis again in a state where it holds the
  other value (a start file the camera wrote, never one made by hand: decision 6).
- **An axis's held value** is its last visit's, as a list's own start is: the visit put the axis back and changed
  nothing, so on a record only the axis writes (none the carousel's own options write, in any state, and no live
  readout) its label takes the value from before in the visits of its own attempt, else from that attempt's base file,
  unless another label was seen writing it (`held_axis_value`). Focus Area's full-memory records hold the option the
  carousel opened on, so they take none, and a carousel whose own rows have no proofs credits none.

**Checking the evidence offline.** The saved frames and downloads are enough to re-check labels
with no camera: what each proof's frames show against its label, and the report's rules against
the proofs. Do it before calling a model done; on the a1 II it found the useless second reading and
two report rules, and no wrong label in the definition.

**Running unattended: `kit/tools/chain.py`.** Steps go in a TOML file (`kit/chains/`; `stills_brackets.toml` there
is a worked example), each an argument list with its own log, the lines to echo, a time limit and the run's STOP
file. A step over its limit is asked to stop through that file; the runner never kills a step, since a camera left
in a dialog is worse than a late chain. `STOP_CHAIN` in the camera's `runs/<model>_fw<fw>/` ends the chain
between steps (a chain runs on one camera, and its file's paths are in that camera's runs), and the owner's file
(`--end`) is uploaded last whatever happened, after the last step has exited. Shell scripts did this before; one
waited 2.5 hours on a black HDMI feed and one lost its prover calls to shell word splitting.

## 7. Order of work

Every kit command here runs with the venv's Python, as `.venv/bin/python -u kit/page_scan.py …`
(`.venv\Scripts\python` on Windows): the scripts are not executable on their own.

**Where runs go.** Each camera's runs are in a folder of their own, `runs/<model>_fw<fw>/`, named as its
`data/<model>_fw<fw>/` folder is: the run folders (`kit2_*`), the proof viewer (`_viewer/`), the readers' answers
(`_cache/`) and the downloads manifest (`downloads.jsonl`). The kit works on one camera at a time: `"camera"` in
`private/config.json`, else the one camera in `runs/`; `--camera <model>_fw<fw>` on any command, or `CAMSET_CAMERA`,
works on another (QUICKSTART, "Where the runs go"). A run named on a command line (`<scan>`, `<crawl>` below) is a
folder in that camera's runs: `kit2_page_scan`, `kit2_crawl/map.json`. Runs left at the top of `runs/` from before
2026-11-05 stop every kit command that reads or writes runs (the commit hook goes on) until
`kit/tools/migrate_runs.py` has moved them under their camera's folder.

### Phase 1: map the menu

1. **Page scan.** Only Down is pressed, one full lap:
   `kit/page_scan.py --mode Stills|Movie|S&Q --run kit2_page_scan[_movie|_sq]`. It stops without pressing on any
   screen it does not know, and closes plain menu pages itself. `--mode` is the mode the camera is in, which the scan
   records: the provers take by default only the latest whole scan of the mode they work in (its lap written, and its
   page model built after it), and a scan that records none (made before 2026-11-11) only by `--scan <scan>` or once
   `kit/page_model.py --mode <mode> <scan>` has recorded it. A folder that holds a lap or page model of a scan
   recording no mode or another mode is refused before anything is sent: each mode's scan has a run of its own. A
   folder whose scan records the same mode is scanned again, and is no default until the new lap is whole.
2. **The cycle file.** `page_scan.py` writes `scan_rekeyed.json` after a full lap; check that it
   printed `cycle written`. Without a full lap it writes none, and no prover takes the scan by default: scan again.
3. **Page labels.**
   - Run `kit/page_model.py --vlm <scan>`.
   - Labels the readers disagree on are read by eye off the frame into `checked_labels.json`, as
     `{page: {slot: {label, frame, note}}}`.
   - The owner's own confirmations go in `user_labels.json`. Keep the two apart.
4. **Crawl.** This opens every safe row and walks its options, read-only, with MENU to cancel and
   a download diff before and after that must be empty:
   `kit/crawl_run.py --scan <scan> --run kit2_crawl[_mode]`. Use `--tabs Playback` for the
   Playback tab, and `--start-label ROW --limit 1` for a single row.
5. **Option labels and the map:**
   1. `kit/pass1_labels.py <crawl>`
   2. `kit/tiebreak.py <crawl>`, the third reader on disagreements
   3. `kit/pass1_map.py <crawl> [<crawl> ...]` (`--dry-run` first), which writes each crawl's `map.json` and every
      crawl's rows into `kit2_pass1/map_all.json`, the map Phase 2 reads

   Fix any label that came off a black or wrong frame by hand in `map.json`, and say how in the
   entry's `by` field; making the map again keeps it.
6. **Scope.** In `kit2_pass1/pass2_scope_draft.json` (shared by every map of the camera), exclude rows the
   rules forbid. Rows that change or blank HDMI go in the OSD group; anything that governs the
   remote session is excluded. Write each decision with its date and reason in `decisions`.

### Phase 2: prove

- **The map** every prover reads is `kit2_pass1/map_all.json`: `kit/pass1_map.py <crawl> [<crawl> ...]` writes it.
- **Second axes, first** (‹ › beside a carousel option, as Spot: Standard / Large): walk them read-only with
  `kit/axis_walk.py [--rows ROW ...]`, into `kit2_axes/axes.json`. `prove_run.py` on pass 1's map adds an axis
  job for every value it lists; without the file no second axis is proved.
- **Ordinary rows** (lists, carousels, number fields, checklists, side lists):
  `kit/prove_run.py [--scan S --map M --context C] --start FILE [--rows ROW ...]`.
  Without `--rows` it resumes: rows already proved, or failed, are skipped (use `--retry-failed`).
- **Assignment screens** (Fn Menu, Custom Key/Dial, My Dial, Image Quality tables):
  - Walk them read-only first with `kit/table_walk.py --rows ...`.
  - Then prove with `kit/prove_run.py --tables --picker-sample`: one full list per identical
    picker, and three functions on each other slot.
  - A function that opens a setup screen of its own when chosen (a Recall Custom hold's registration, Rating Set,
    Recog. Target Select, the My Dial functions' My Dial Settings) is proved like any other: the key takes the
    function, the prover leaves the screen with MENU (its footer's Cancel; nothing on it is pressed, since Register
    would write the hold) and goes on. A radio list open on its saved option over the picker (Cnt Sht Spd Bst
    Settings, the speed the function uses) is left with Enter on that option, the choice it already holds. An
    information notice before the screen is taken with its OK first. The report credits such a function with the
    key's record alone: the records only such functions write are the screen's (the hold copied into its
    registration working copy). A saved Recall Custom hold is never chosen back to put the key as it was, because
    that copy outlives an upload; its proof is the key's record as the start file holds it, and the session's upload
    puts the key back. A function whose screen is not left with the key on its cell is learned into `own_screen.json`
    and passed over from then on.
- **Creative Look panels:** `--looks`. **White Balance fine-tune grids:** `--wb`, then
  `--wb-corners`. **Picture Profile side lists:** `--pp PP1,PP2,...`.
- **Rows that change or blank HDMI** (HDMI Resolution, HDMI Output Settings, HDMI Info. Display, CTRL FOR HDMI,
  frame rate, file format, Framing Stabilizer, Auto Framing, Select Finder/Monitor, Auto Monitor OFF): `--eyes osd`. The way to the row goes over HDMI, and the
  proof watches the SDK's OSD. `--eyes osd-all` does not work, because OSD frames do not match a
  scan made over HDMI. A run in OSD mode (`"eyes": "osd"`, scanned through the OSD) has no such
  rows.
- **Rows that drop one link** are proved over the other: rows that drop the LAN link over USB, rows that drop USB
  over LAN. The owner swaps the cables; batch the rows by the link they need, so there is one swap per batch
  (decided 2026-10-29).
- **Scales** (a number between − and + boxes): `kit/provers/scale_run.py --row ...`. A scale counts as open only
  with an OK in its footer, read by OCR or, where OCR drops it on a fresh frame too, by the reader. Every end of the
  scale is confirmed by one more press (at the high end one Left press must then read the number before it), whole
  numbers must step evenly, a scale has two values at least, and each choice must open on the value chosen last and
  land where the count of presses puts it; anything else stops the row, and a stopped row's lines count for nothing
  in the report. A slider inside a panel (Monitor Brightness, Viewfinder Bright.: a Brightness Setup row first, the
  slider below it only on Manual) is given with `--panel-row` instead, with its setup row among the `--set` rows
  (`--set "Monitor Brightness > Brightness Setup=Manual" --panel-row "Monitor Brightness"`): the run puts the setup row
  on Manual through the menu, so every proof's context names it and none tells what the camera stood on (rule 10), and
  a `--panel-row` without it is refused before anything connects, with the `--set` to add; Down goes to the slider; a
  plain scale given so, or a panel given as `--row`, stops before any choice. A scale with negative numbers is
  labelled as the camera writes it around zero (-2, -1, ±0, +1, +2).
  `--set "ROW=OPTION"` (repeatable; `"A > B=OPTION"` for a submenu's or a panel's row) puts a row on an option
  through the menu before the first row, the proofs' context naming it; a never-open row needs its own `--allow`, and
  the rows of decision 8 are never set so. The finder's rows are greyed with the HDMI cable in: they are run with
  it out and `CAMSET_EYES=osd`, from `kit2_page_scan_osd3`.
- **A live exposure value no menu list proves on a line** (Exposure Comp. and Flash Comp., whose codes mix 1/3 and 1/2
  steps): `kit/provers/sdk_run.py --property ExposureBiasCompensation --row "Exposure Comp." --values missing
  --context "..."` sets each value the camera offers through the SDK's own setter (camkit.safety.SET_PROPERTIES only),
  reads it back, downloads and diffs it as a menu proof would, sets the start's value back last and restores;
  `--list` prints the plan with no camera. Not writable now (the mode, a flash switched off): it says what to change
  and sets nothing.
- **Two-box screens** (S&Q or Time-lapse frame rates):
  `kit/provers/boxes_run.py --row ... --boxes "Left name,Right name"`; the value a box opened on is proved with
  `--first BOX=VALUE` (section 8).
- **Turned dialogs** (camera held vertically): `kit/provers/orient_run.py --grip down|up [--only ...]`.
- **Checkbox grids** (Focus Area Limit): `kit/provers/grid_run.py [--row ROW]`, one cell flipped per visit.
- **Shoot Mode set with the menu** (Mode Dial Control Set's Set with Menu): `kit/provers/shootmode_run.py --start FILE`,
  from a start file holding that setting; every proof ends by uploading it again.
- **Rows another mode's menu offers** (Movie, S&Q, or a stills exposure mode: Flash Mode's Autoflash in Intelligent
  Auto alone, ISO AUTO Min. SS not in M): `kit/provers/mode_switch.py --to Movie [--mode M] --keep` puts the camera
  there through the menu (Mode Dial Control Set = Set with Menu, then Shoot Mode's carousel; never a memory recall),
  keeping the stills start file's name; the prove runs that follow (`--eyes osd-all`, that mode's own OSD scan and map,
  `--context` naming the mode) take the camera as they find it and put that back; `mode_switch.py --restore` uploads
  the stills file and checks it took. That file is the camera's settings from before the switch: whatever was changed
  on the camera since is undone too, so a switch record left over after the camera was put back another way (by hand,
  or by a later session's restore) is removed with `mode_switch.py --forget --shows <mode> --run <run>`, which renames
  it and sends nothing: first look at the camera's screen, or ask the owner, which mode it shows, and say that, the
  family first (Stills, Movie or S&Q) and the exposure mode after it when you say one (P, A, S, M or Auto):
  `--shows Movie`, `--shows "Stills M"` (a letter alone is refused: Movie's and S&Q's screens show one too); it refuses
  while the screen shows the mode the switch went to, and says how to undo it (rename the record back). Every run stops on a waiting switch of another mode, saying both. A state a row needs on top of the mode
  (Exposure Ctrl Type = Flexible Exp. Mode for the Auto/Manual switches, proxy recording on for its settings) is set
  the same way,
  `mode_switch.py --set "ROW=OPTION" [--set "Submenu > Row=OPTION"] --scan <that mode's scan>`, while the switch
  waits; the one `--restore` covers it all. A mode's page scan must be of the menu as it is now: the page counter is
  part of every page's key, so a scan from another day's state (two pages fewer, 2026-11-07) knows none of them, and
  `kit/page_scan.py --mode <mode> --run <scan>` then `kit/page_model.py --vlm <scan>` take ten minutes. Intelligent
  Auto's menu is not known to be P/A/S/M's: a scan made while a kept switch to Auto (`--to Auto`, or a family's Auto)
  waits records it, and is the default only while such a switch waits, when the plain Stills scans are not.
- **A put-back that leaves records differing** is no failure when the prover can say why (`put_back_leftovers`,
  2026-11-07): a record the camera has held since an earlier option of the row ("kept": S&Q Shoot Mode's exposure
  mode, the keys Flexible Exp. Mode reassigns), a saved value no option of the list gives back ("not offered": Flash
  Mode's Autoflash outside Intelligent Auto, a Proxy Rec. Setting of another format), or a checklist's copy of a box's
  tick written from the first save on (`mirrored_boxes`: Rating Set(Custom Key)). The attempt is recorded finished
  with the reason, the session's upload puts the records back, and the report credits a kept value to the option that
  first set it. Anything else still fails the row.
- **Recall Custom holds** (Reg. Custom Shoot Set, a never-open action: only with your owner's word, given as `--allow
  "Reg. Custom Shoot Set"`): `kit/provers/customshoot_run.py --allow "Reg. Custom Shoot Set" --hold N` for the items'
  ticks, then `kit/provers/customshoot_values.py --allow "Reg. Custom Shoot Set" --hold N --items "ITEM,..."` for their
  values.
- **Playback Filter Condition** (a checklist whose boxes open a chooser each, and which answers "There are no target
  images." to every box while the playback target holds no image): `kit/provers/filter_run.py [--items ...]` proves
  each condition's chooser as a list row of its own (Protect, Still Images/Movies, Shot Mark, the transfer states,
  Voice Memo), the start file back between items; Date's calendar and Folder's list are data on the card, Rating's
  star boxes are noted, and Execute Filter, Cancel Filter and Fn (Reset Condition) are never pressed. `--untick` also
  proves each box's value 0: Enter on the ticked box in the box column, a download before and after; the report takes
  that proof as the item's row in the state "box ticked", apart from the chooser's options.
- **AF Area Registration** (a Focus Area registered by holding Fn on the shooting screen, a registration: only with your
  owner's word, rules 2 and 14): `kit/provers/afreg_run.py --allow "Fn hold on the shooting
  screen" --areas missing` (`--list` alone touches no camera and needs none) chooses each area in Focus Area's menu,
  holds Fn and diffs the downloads around the hold;
  `--proved` prints what its lines proved. A Tracking area needs Focus Mode on Continuous AF, which the run sets
  through the menu (the Focus Mode dial set with the menu), and the camera refuses Continuous AF under some drive
  modes (it says so in a notice when Focus Mode is set), so the run first puts Drive Mode on Single Shooting the same
  way (the Drive Mode dial set with the menu; `--drive-mode auto|menu|leave`) and the restore puts the file's own
  back; a setup step the camera refuses ("not available as follows") stops the run, the notice's words kept in the
  run's `events.jsonl` and never printed (a notice can name another setting's value). Its proofs stay in a run of their
  own (`kit2_afreg2`), marked as a proof run, which the report reads beside `kit2_pass2` (Phase 6). A non-Tracking
  area's hold copies the Tracking start area in use, the camera's own setting: its lines name those records as side
  effects, changed or not, and the report credits a side effect to no option.
- **A memory's copies** (Camera Set. Memory, a never-open action: only with your owner's word, given as `--allow
  "Camera Set. Memory"`): `kit/tools/set_twins.py` groups the memory set's records with the live records of the same
  id and picks plain list rows to change, no camera; `kit/provers/memreg_run.py [--list]` registers memory slot 1,
  changes those rows in their menus, registers it again and checks that each copy took the new value. A filled slot
  only: registering an empty one would mark it filled for good, and the three registration records no settings file
  sets back are said by key and left out of the restore's check. Its lines (`"kind": "registration mirror"`) are no
  row's proof: the report keeps them out of its rows and the writer marks each live setting whose copy took
  (`in_sets_proved`, in the evidence file). The run is marked as a proof run.
- **Where a focus frame's place is kept** (also Camera Set. Memory, `--allow` as above): `kit/provers/framepos_run.py
  [--areas ...] [--list]` chooses each area whose frame moves, registers slot 1, moves the frame with the
  multi-selector, registers it again and diffs the two (the console and `framepos_summary.txt` give each record's
  delta, never what it held; `framepos.jsonl` keeps both values, as the run's evidence in runs/, which is never
  published), then puts the frame back and checks a third registration matches the first; `--summary` prints the
  lines with no camera. `--frame-move-amt Standard|Large` sets AF Frame Move Amt by the menu with the other setup rows,
  checks in the download after the setup that the camera took it, and names it in the context every line carries, so
  a step's size is measured under a setting the run set, never the camera's own; give a step run its own `--run`, and
  read a step only from an area whose put-back matched. For a frame that stands near the limit of its travel, which
  three Left presses run into the limit (the delta cut short; a press at the limit still counts as taken, so the
  put-back goes past where the frame was, and the check-back, the registration after it not matching the first, is
  what shows it), `--moves "Right 1"` (a direction and one to nine presses each, comma-separated, never a direction
  with its opposite) moves the point and box areas by those presses instead of Left 3 and Up 2, and the check-back
  tells whether they stayed clear; the zones keep their own one-step moves and a default run's context, and the
  context names the moves, so each set of moves keeps its own summary lines. `--zone-grid` leads the Zone over its
  nine places with Switch V/H AF Area Off, registering at each, so one sweep proves every grid copy, the vertical ones
  too, without turning the camera; its lines (`zone_grid.jsonl`, and registration mirror lines in `proofs.jsonl`, the
  run marked as a proof run) give the writer each place as proved. A record family the deltas show that the definition
  has no setting for gets no name from a run: map it with proofs first.
- **Picture Profiles' own Reset** (Picture Profile Reset, a never-open action: only with your owner's word, given as
  `--allow "Picture Profile Reset"`): a definition's sample is a download taken right after Initialize, scrubbed by
  `kit/tools/make_sample.py`. Initialize leaves some records as they were. Of those, only the Picture Profile
  parameters are checked so far (the reset file lists what Initialize puts back for the settings tested); for them
  the sample takes the values the camera holds after each offered profile's own Reset, in Stills and in Movie.
  `kit/provers/pp_reset_run.py --peek` first (it opens the first profile's question and cancels), then a one-profile
  trial (`--profiles PP1`), then the run in Stills, `kit/provers/mode_switch.py --to Movie --keep`, the run `--in
  Movie`, and `mode_switch.py --restore`. A run first shows on one profile that its Reset writes the records a
  settings file saves: it changes one parameter, downloads, resets, and requires the changed records to be written
  (the run's control: one parameter of one profile, which must move only that profile's element, in the record in use
  and in the copy of the run's mode, and which that profile's Reset must write back). Then each profile the camera's
  list offers is reset by its own Reset row. The panel's title before Reset, the question, the completion notice and,
  in the verify pass, each panel's title are read by both readers, and a run meant for the sample refuses to open
  Reset or confirm on one reader alone; the carousel's labels are read by both too, and one read by one reader alone
  may be taken, since no press acts on a label; the lit row (Reset, the control's Black Level) is read by OCR and must
  read as that row's name. Only that profile's own question is accepted. After OK the camera's completion notice is
  expected; the profile's panel coming straight back with no notice is recorded as such and refused for a sample
  unless allowed (`--allow-no-notice`); anything else stops the run. A verify pass enters each panel again, confirms
  each by its title and checks that no profile's parameter moves by that alone, and every exit restores the start
  file (`--dry-run` prints the plan). Then `kit/tools/make_sample.py <base> --take "Picture Profile PP" --from <the
  Stills result> --from <the Movie result>`, which recomputes each result's lists and its control from its own
  downloads and takes those downloads only as one session's, in the camera's downloads manifest. When no reset
  download holds any of the family's records unlike its run's start file, make_sample stops; --allow-unchanged takes
  the records then, the run's control being what shows a Reset writes them (one parameter of one profile). That is
  the limit of the evidence: the control shows it for one parameter of one profile; for the rest the evidence is the
  camera's own completion notice. A
  profile the body keeps records for but no menu offers (the a1 II's PP7-PP9) cannot be reset by a menu and keeps
  what the base file held: a limit of the sample. The tool's guards are written for the screens and wording of the
  ILCE-1M2 at firmware 4.00 ("Reset PPn to the default setting?", "Complete.") and fail closed on any other; on any
  camera, a peek and a one-profile trial come before a full run.
- **Bracket fields** (Drive Mode's Cont. / Single Bracket step and images): `kit/provers/bracket_run.py --option
  "Cont. Bracket" --look` first, then without `--look` (`--sample N` for a long list).
- **Anything else, by hand-written presses:**
  `kit/drive.py --path ROW --press right --press "enter:REGEX"`. Enter needs a lit text the kit can read; on a screen
  that lights nothing it can read (the a1 II's MR Memory slots) `--press "enter!:REGEX"` is Enter you vouch for, once
  you have looked at the frame yourself and the regex pins that screen. Only with your owner's word: the a1 II's owner
  allowed it on their own camera (2026-11-09), and rule 8's default is no Enter on an unknown screen. Even then
  `drive.py` refuses it on a menu, submenu, the Main tiles or the shooting screen, on a screen whose text reads
  nothing, on a screen whose text names a never-open row (`--allow` lifts its own row's name, never the cards,
  Initialize, Reset Network Set., credentials or the camera's identity, a connection or its region), and wherever
  plain Enter is refused; the log says "vouched". A press
  that meets the shooting screen is refused unless `--on-shooting KEY` names it, your owner's word (rule 14). Then
  record the proof yourself, keeping side effects (records an information screen's OK also rewrote) out of `changes`:
  into `kit2_pass2`'s `proofs.jsonl` with `"run"` naming the run whose `dat/` holds its files, or into that run's own
  `proofs.jsonl` with the run marked as a proof run (a `proof_run.json` in its folder, `camkit.runs.mark_proof_run`;
  AF Area Registration's holds of 2026-11-02 are in `kit2_afreg`'s, recorded from its downloads in the shape
  `afreg_run.py` writes).

### Phase 3: settings greyed by another setting

`kit/pass3_run.py` turns each blocker off in the menu (using greyed-row reasons from pass 1), walks and proves
what that opened, then restores. Each walk builds a map of its own (`kit/pass1_map.py --own`, with `kit/tiebreak.py`
as the third reader where the first two differ) and leaves pass 1's `map_all.json` as it is. An entry's `"first"`
lists states chosen in the menu before its own switch (a File Format before that format's Rec Frame Rate); the
restore puts them all back. Entries marked `on_request` run only when `--only` names them. Its blockers that were
switched by writing values into a file and uploading it are retired, and the script refuses them (rule 12). Some of the context runs need a start file in another state, such as
File Format slots swapped, or a Picture Profile gamma that allows Black Gamma: set that state on the camera, download
it, and prove from it with `kit/prove_run.py --start` (rule 12).

### Phase 4: other modes

The Still/Movie/S&Q switch is physical, so the owner moves it.

1. Download in the new mode. That file is the mode's start file, and its diff from stills shows
   the mode's own records.
2. Page-scan and model the mode's menu.
3. Crawl it if the rows differ. S&Q's menu equalled Movie's except for greyed rows, so Movie's map
   served there.
4. Prove the rows no stills proof covers.
5. Prove again the rows "Different Set for Still/Mv" splits: each keeps a stills record and a movie record beside
   the record in use (the a1 II's: its page, the Movie / stills row).

### Phase 5: sessions with the owner

Each step is one physical action, then `kit/tools/upload_check.py --diff REF TAG` (when a download is refused:
section 8).

- **The mode dial:** P, A, S, M in each mode give the exposure-mode records.
- **Holding the camera grip down and grip up** gives the per-orientation Focus Area sets (the
  dialog turns with the camera).
- **Registering memories in two modes and two dial positions** gives the memories' own records.
- **DISP on the monitor and in the finder** gives the display layouts.
- **A state only the owner sets** (NTSC/PAL Selector, rule 3): the owner switches it by hand, and a download in
  that state shows what it moved. The kit then walks and proves the rows whose lists change in it through
  `kit/pass3_run.py --only` entries, one per File Format chosen in the menu, over the OSD (`CAMSET_EYES=osd`, with an
  OSD scan of the mode; a change of rate changes the HDMI signal), each entry restoring its start file. The two-box
  screens (S&Q and Time-lapse Frame Rate Settings) are proved in that state with `kit/provers/boxes_run.py`. The
  option every list opened on after the switch is proved only from another start (section 8). Then the owner
  switches back, and a download checks the camera is as before.
- **Camera Settings Reset, then Initialize,** run by the owner, show what each one really resets: download before
  and after each. Set the test values on the camera through the menus, never by a file (rule 12): menu-proved
  records at another proved value, never sound, light, motion, network, keys or dials. (The a1 II's owner allowed
  Camera Settings Reset only, decision 5; ask yours.) Then write `data/<model>_fw<fw>/settings_reset_<model>_fw<fw>.json`
  by hand, lean, from the downloads: `about` (a sentence on what the file is), and under `records`, by the
  definition's setting key, the setting's `name` and `tab` and `result` (Camera Settings Reset) and `initialize`
  (Initialize), each `resets` or `keeps`. Leave out a setting whose test value might equal the factory value, the
  value the reset gives: a reading of it would only tell what the camera held before. Notes about the tests (their
  dates, how many settings, what was tried) go in your own notes in `private/`, never in this file. It is the one
  file the kit reads; correct it there, and a setting's name or tab in the definition, which `kit/schema_update.py
  --write` copies into it ([DATA_CONTRACTS](DATA_CONTRACTS.md#the-reset-file-what-each-reset-puts-back)).

### Phase 6: report and definition

1. `kit/pass2_report.py`: per row, records and value labels against the definition (agrees, wording,
   missing, conflict, new). It reads `kit2_pass2`'s proofs and the camera's other proof runs, the run folders marked
   as one (`proof_run.json`: `afreg_run.py` marks its run, `filter_run.py` the one `--run` names, `memreg_run.py` and
   `framepos_run.py --zone-grid` theirs once they wrote a registration mirror line), each run's
   unfinished attempts left out by its own attempts and failures, a row's lines made where the camera stood left out
   where they say nothing of another row whose state lines of the same row name (`Row = option` in their context or
   their run's `setup`, or in words, `Row option`, for a row the proofs walk), when for each record and value each of
   them changed a line of those chosen with the same option changed it alike or left it as its own base download held
   it, none writes it otherwise under that option, and those lines are credited every value and value name they are
   (a panel's slider proved again with `--panel-row` and its `--set`; an AF Area Registration hold proved again with
   `afreg_run.py`'s setup; a row walked again in pass 3's named states: the older lines, by being there or by the
   records they wrote, told that row's state as the camera was found; nothing proved is lost, only their menu row), a
   setting table's cell named by its row as all the row's cells read it (a cell's own reading carries the values of
   the cells before it), each proof's files named
   with its run so two runs' files of one name are never one, and a proof found in two folders counted once; `--alone`
   reads `kit2_pass2` only,
   into `report_alone.json`, leaving the `report.json` the writer reads as it is. A run made to check the kit is never
   marked (`kit2_review_list`; remove the mark from one a prover made for a check): it proved rows again in whatever
   state the camera was in then, a state its proofs do not name, and taken in beside the mapping's they would tell
   that state (decision 16).
   `kit/tools/replay_proofs.py` diffs every proof's two downloads again with today's parser (`kit2_pass2`'s and the
   other proof runs' the report reads, a proof's named side effects aside) and exits 1 when one
   no longer says what its stored `changes` say, or a file is gone: run it after any change to the parser, the
   container block or the volatile list, before the report.
2. `kit/schema_update.py`, a dry run, then `--write` when its changes read right (or
   `kit/tools/build_docs.py --write-schema`, which runs it and then rebuilds the generated files). It writes the
   definition of the camera the kit works on, `editor/definitions/<model>_fw<fw>.json` (decision 19), lean, with its
   evidence in `private/evidence/<model>_fw<fw>.json`, which the kit reads back with it, and refuses proofs from
   another body or firmware. A new model's first run starts its definition from its `data/` folder and the
   run's newest download, with every setting the report proves named by its menu row; later runs write over it, and
   of the proofs it held keep only a value a proof line the report counts still wrote (`kept_proof`, listed as "kept
   from the definition"), never an older menu row, count of samples or value no counted line wrote. A definition an
   older kit wrote is written afresh instead ([UPDATING.md](UPDATING.md)). Its
   parts from `data/` (the camera section, the project's own help) and its own rules over them (the Expert marks, each
   note's evidence apart in `note_evidence`, for the evidence file) are written on every run, and `kit/tools/build_docs.py --definitions`
   writes only them, with no runs, after a camera file was edited. A setting on no camera row whose name still holds
   a mapping word ("record", "numerator", "slot memory", "mirror", "(inferred", the SDK's) is marked Expert-only, as
   are the fields of the memories' live copy; a setting on a row gets a photographer's name in `RECORD_FIXES`
   instead, and the kit tidies groups and refused options' reasons (`SETTING_GROUPS`, `with_plain_words`, in
   `kit/writer/fromdata.py`, the writer's data-only part).
   `kit/tests/test_definitions.py`'s "mapping words" test fails while any text a photographer reads outside Expert
   mode (a name, group, help, display rule or refused option's reason) holds a record number, a pass, the owner or
   another word of the mapping; fix the kit's rules or tables, never the definition by hand. The writer's body is in
   `kit/writer/` (`kit/schema_update.py` stays the command), and the ILCE-1M2's own corrections live in its hand
   tables, `kit/writer/a1_tables.py`, which apply to its definition alone. The tables are public and hold names, value
   tables and facts; how each was proved (a hand proof's values, run and day, a sample's count, the owner's word, what
   shows a not-offered mark) is the mapper's, in `private/evidence/<model>_fw<fw>.hand.json`, which
   `kit/writer/hand_evidence.py` puts back; without it `--write` refuses
   ([the mapping's evidence](DATA_CONTRACTS.md#the-mappings-evidence)). The evidence file (format 2) only adds to
   the tables, and carries a note's evidence only as a suffix, `"note+"`, after the table's note; the public words and
   values live in the table alone, so reword a note or mend a value there and nowhere else (evidence that would
   replace a public value is refused, naming the table, key and field; a format-1 file is converted once with
   `kit/writer/hand_evidence.py --convert`). A write stops, writing nothing, when evidence went stale in that run (a
   proof's, or more than five settings': after a setting's key was renamed, say); `--accept-stale` writes it anyway,
   and `--drop-stale` shows the evidence file's "stale" section by key and field and removes it:
   - `LABEL_FIXES` (OCR slips: a spelling, no evidence of the code; a mended name on a value no proof or rule names
     stays the old schema's, `schema kept`, which an editor does not offer outside Expert mode);
   - `RECORD_FIXES` (names and notes);
   - `VALUE_FIXES`;
   - `NEW_LIKE` (a new record shaped like a sibling);
   - `NEW_RECORDS` (records found by hand);
   - `KEEP_LABELS` (a flag several options share);
   - `HOLD_TABLES` (a Recall Custom hold's copy of a live setting, named by the live table once that is proved in full
     and every proof of the hold fits it, the code itself or mirrored; a hold item proved in full on one hold names
     the other holds that agree with it, whatever the item; until then a hold's Exposure Comp. code no proof chose is
     named by `EV_DOWN_FROM_20`'s quarter-stop count, `counted`, which an editor does not offer outside Expert
     mode);
   - `NOT_OFFERED` (values the camera's menus never offer, each with why in plain words: a mark is written only while
     its evidence (in the hand evidence file) holds, every row it names (each a walk of the whole list, as its
     evidence says) never writing the
     value, or every picker list of a table-walk screen walked round to its start without it; a factory value the
     camera writes itself is `held` and stays offered). An
     option refused under another setting is never this: the proof runs' refusals (`menu_blocked`) stay in the
     evidence ([the field](DATA_CONTRACTS.md));
   - `MY_MENU_EMPTY` (My Menu's empty place, "(empty)" in every slot, below);
   - `CONTEXT_WORDS` (a proof context in other words: one reworded in `runs/` after it was written, or a state as
     found that the proof does not need, which the runs still hold ("S&Q mode (…)" is "S&Q mode"); a pattern and its
     new words, renamed where a row enters the definition and in the rows the definition kept, or the old row would
     stay beside the new).

   My Menu's slots (`camera.my_menu.records`, seven per page) share one code table. `kit/provers/mymenu_run.py --allow
   "Add Item"` (a never-open action: only with your owner's word) adds every item the Add Item picker offers, one
   download each, and its proofs say which page and slot took which code (`my_menu`); the writer reads those proofs,
   not the report's row, and names each code in every slot: the slot that took it is proved, the others hold the
   same name as derived. The item's name is settled against the camera's
   own row names (the menu tree's rows, the Help Guide's menu list) from the lit row's OCR and the vision reader's
   words, twins numbered by their place in the picker ("Fn Menu Settings (2)"); a name the table already holds stays
   when it is the fuller of two alike readings. `mymenu_run.py --relabel` names a run's proofs again by that rule
   from the readings they kept, touching no camera. The empty place's code, the camera file's `my_menu.empty`, is
   "(empty)" in all 42 slots by a hand table (`MY_MENU_EMPTY`): every place the Add Item proofs filled held it before,
   and the location screen showed the places after a page's items blank.

   `--write` refuses (exit 1, the list printed) while the report holds a question it does not settle that
   `private/evidence/<model>_fw<fw>/accepted_<model>_fw<fw>.json` does not accept: a conflict whose label it keeps
   against the camera's reading, a new record it does not add, a record not one to one (which loses its proof and is
   marked `disputed`), a name dispute or a carried-over value. Settle each with a proof, or look at it (report.md, the
   proof viewer) and add an entry with why ([the file's shape](DATA_CONTRACTS.md)); the file stays with you, and the
   pull request carries the gate's count line. `--force` writes anyway, loudly, for a look only. The evidence keeps what backs each proved value's name
   (`proved.names`: two readers, one, the vision model alone, a hand table, the schema's kept label, a rule's copy,
   sampled), and a proof's `values` in the definition are those the camera's own word backs; a number the camera
   shows scaled ("75%" stored 7500) gets `shown_as` from its proofs.

   After `--write`, stage the definition (`git add editor/definitions/<model>_fw<fw>.json`), run the report and
   `--write` again: `git diff --exit-code editor/definitions/<model>_fw<fw>.json` must print nothing (the writer is
   repeatable; its dry run still lists the labels it sets on every run).
3. Run `cd editor && cargo test`, then `.venv/bin/python kit/tools/build_docs.py` (the committed generated files;
   without `--write-schema` or `--definitions` it never writes a definition, and the pre-commit hook passes neither) and
   `.venv/bin/zensical build --strict`: the Status page, the memory map and the model page's measured block are
   rendered from the definition when the site is built.

## 8. Pitfalls already paid for

- **A press sent to a menu still sliding in.** The menu reopens where a hand left it, and its rows slide in over
  about half a second; the OSD image renews only every 0.25-0.37 s and shows a press 0.33-0.65 s after it was sent,
  so "unchanged for 0.2 s" was one picture seen five times, not a screen at rest. A page scan read a mid-slide frame
  (no row bar yet) as the group column, sent the Right that steps into the rows, and the camera, by then at rest
  with the cursor on the Drive Mode row, opened the row; the next Down moved the drive mode (2026-11-06; the start
  file went back on). Now: the OSD eyes wait two renewals with the same picture (`OsdSource.QUIET`), the reader
  gives a menu no focus while its rows panel is between its two places (`screen._panel_x`), and the scan and the
  prover look again until the menu is at rest before any press, cancelling with MENU if a Right opened a row all the
  same. The scan also downloads the settings first and puts the start file back on when anything moved, and waits
  out "Saving to the connected device..." before its first MENU.

Each line is a symptom, then its cause, then the fix now in the kit.

**Screens and reading:**
- **An unknown screen after Right** → a screen type the reader lacks. The row fails closed. Look
  at the frame, then add a reader or a special prover.
- **A big orange cell or Main tiles read as a menu page** → Movie mode's Main pages have different
  grids. Count grid lines in the top rows and the bottom rows too.
- **The shooting screen read as unknown or as a keyset** → the camera is held vertically and the
  shooting screen turned with it. Use the rotated battery templates, checked first.
- **The shooting screen read as a notice** → Focus Map tints live view red. Check the battery
  before the notice frame.
- **The Focus Area dialog is unreadable when the camera is held vertically** → menus stay level,
  but dialogs turn. Read OCR on the frame turned upright (`orient_run`); keys follow the turned
  picture.
- **OCR noise:**
  - Cyrillic look-alikes ("30р", "ОК") → translate them before comparing.
  - Icons read as letters ("S&d", "sad", "#", "4e", "MR ", "(V)") → read the frame by eye into
    checked labels.
  - Tick marks or arrows beside a number ("3•", "15") → read only digit-tall text centred on the
    value.
- **The VLM invents an answer on a black frame** (section 5) → read that row through the OSD.
- **A label carries state, not a name** ("User1: (No Import)", "Spot: Standard") → strip the
  state, or use `VALUE_FIXES`.

**HDMI and the link:**
- **HDMI black** → Auto Framing On, a Framing Stabilizer preview, or the rear screen folded in.
  The prover now looks at the OSD. With the screen folded in, the camera also refused the remote
  session until it was opened.
- **The capture dies after a frame-rate change** → the HDMI format followed the movie settings.
  The feed restarts once, otherwise it raises. Restores need no HDMI.
- **MENU unanswered just after a download** → the menu is locked for about 4.5 s. Wait `LOCK_S`,
  look again, and press once more. Never press MENU twice on a slow menu.
- **The menu reopens after a download with the focus in the group column** → the position matches no page of the
  scan. A session that opens the menu that way presses Right once, onto the page's rows, before it matches the scan;
  a menu that still matches no page fails closed ("the menu opened on a screen the scan does not know") and the
  restore puts the start file back; run it again.
- **No HDMI frames, and no OSD image either, at the start of a session** → the camera's monitor is asleep (or the
  HDMI cable is out): the capture gives no frames while the monitor sleeps or the cable is out, and the SDK's OSD
  image is unavailable while the monitor sleeps. A session the owner runs by hand starts with the camera awake: ask
  them to wake it by hand first, and to check the cable.
- **The a1 II's viewfinder rows (Viewfinder Bright., Finder Color Temp.) answer "This function is currently
  disabled."** → the HDMI cable is in. With it out they open only with the finder in use, which needs the eye sensor
  covered (or an eye at the finder) and the monitor folded in: a monitor flipped out keeps the monitor on and the
  finder off, even on VF(Manual). With the finder not in use, Finder Color Temp. showed "Look at the viewfinder while
  setting the color temperature of the viewfinder." and went back to the menu. These are physical actions, the owner's, one per message
  (section 9).
- **"Connect_SSH_GetFingerprintFailed"** → SSH port 22 is closed. Remote Shooting is off, or bound
  to USB, or the camera is asleep, or the screen is folded in.
- **"camera does not allow a settings download now"** → the dial is on 1-3, or the camera just
  woke.
- **Evidence numbers collided past 99,999** → numbering read only 5 digits. Read 5 or more.

**Proving and restoring:**
- **A row's starting option has no proof** → a row's last proof is the option it opened on, chosen again, which
  changes nothing by design. Prove that option from another start: a pass-3 entry with `"first"` (another option
  chosen in the menu before the row is walked), `kit/provers/boxes_run.py --first BOX=VALUE` on a two-box screen, or
  `kit/prove_run.py --first "ROW / OPTION=VALUE"` for a carousel option's second axis (`--rows` naming that axis
  job). Both `--first` options compare every later proof with the download made after that choice and still put the
  start file back.
- **Every row fails on the way to it ("a screen was not the one the scan recorded") after a camera reset** → a reset,
  or any change that adds or removes menu pages, changes the page count, and every stored page scan is stale: the
  a1 II's 65 pages became 63 after the owner's reset. Make the scans again (Phase 1, steps 1 to 3, for each mode's
  scan) before any run.
- **"Back on the saved value, records still differ"** → a first-use record, a record written on
  every OK, or a one-way flag. Note it as found; the upload restores the camera.
- **An information screen after OK** (it may have a "Don't show this again" box) → take its OK
  only if the text is not a confirmation, never ticking the box (`info_notice_ok`). A notice that
  starts "not available as follows" is a refusal: the proof records it as not applied.
- **A choice that also rewrites key assignments or other rows** (Flexible Exp. Mode) → keep those
  records as side effects, not as the row's changes.
- **The table walk got lost** → buttons can keep hidden columns. Re-plan after every press and
  route around unsure cells.
- **Picker lists differ between keys** → the lists are turned round from each key's saved
  function. Compare them allowing for rotation and OCR slips; identify options by page and row.
- **Recall Custom registration left a working slot changed that the upload did not restore** →
  never choose own-screen functions. If it happens, opening another hold's registration puts it
  back.
- **The definition got wrong labels for linked records** → a shared flag (`KEEP_LABELS`), or side
  effects recorded as changes.
- **A list look ended early and a later visit registered the wrong option** → two options matched
  by ratio. Strict matching (section 5); the home visit's diff must be empty, so a change there is a
  red flag to stop on.
- **Guessed labels were backwards** → 84 Movie white-balance fine-tune labels, copied by analogy,
  were wrong until proved. Labels by analogy stay unproved in the definition until a proof names them.

**Running unattended:**
- **A crawl waited 2.5 hours for the shooting screen** → Auto Framing blanks HDMI. Waits now read
  the OSD on a black frame and give up after `WAIT_LIMIT`.
- **Every prover step of a shell chain failed at once** → zsh does not split `$V` into words. Use
  `kit/tools/chain.py` (argument lists, no shell).
- **A wait loop never ended** → `pgrep -f name` matched the waiting shell's own command line. Wait
  on the process number.

## 9. Working with the owner

- **One physical action per message,** said exactly, for example: "Turn the mode dial to **A** and
  tell me." Wait for their reply, then download and check. Say what you found before the next
  step, and say what to undo at the end.
- **Say up front what an action costs.** Initialize wipes the network setup, the FTP settings and
  the memories. Registering a memory overwrites it. Cables may need moving. HDMI goes off
  while the viewfinder is in use.
- **The owner sometimes does something other than what was asked** (the dial on S, not A). The
  download says what happened; read it, never assume.
- **A refused download, or HDMI black with the rear screen folded in** (section 8), is not a fault; tell the owner
  what to change.
- **The owner decides the scope.** Ask before long runs or anything that changes their setup;
  never decide that something is "good enough" for them.

## 10. Recovering from a stopped run

A run whose cleanup presses could not get back to the shooting screen restores all the same when its last screen is
one the reader knows (a menu, list, table, panel or notice) and reads as no confirmation, since a restore over an open
option list checked out on the camera (2026-11-08, `kit/runner.py` close_for_restore); on any other screen, or one it
cannot read, it stops with exit status 4 and leaves the camera to these steps.

1. Do not start anything new. Look at the camera:
   - HDMI (`HdmiSource.grab`), and the OSD (`link.osd`) if HDMI is black;
   - is a dialog open?
2. **A plain menu page or submenu:** opening a fresh connection usually closes it; otherwise press
   MENU. **A dialog:** MENU cancels it. Never Enter.
3. Run `kit/tools/upload_check.py START.DAT`. It must end with 0 differences, or only the records a file
   cannot set, each listed by name.
4. Read the log: which row, which press, which screen. Fix the cause in the kit (and add a test from
   the saved frame) before running that row again. Resume with `--rows` for what is left.

## 11. Time, power and heat

- **Time:**
  - A full menu scan takes about 2 min; a crawl about 25 min per mode.
  - Proofs take 14-30 s per option, most of it the download and the menu lock after it (`LOCK_S`), so a stills
    pass is roughly 2,500 proofs over 10-20 h.
  - Picker-heavy screens are sampled (one list in full, three functions on the other slots).
  - The whole first stills mapping (scan, crawl, labels, proofs, report) takes about two days of camera time,
    mostly unattended; each extra mode takes a few hours more. This section is the one place these figures are kept.
  - Plan overnight runs only with the owner's agreement.
- **Power:** use mains power for the camera if the owner has it. Mention the battery level when it
  is low; the a1 II's battery showed 36% after a day of runs.
- **Heat:** stop and let the camera cool if it warns of temperature. Auto Power OFF Temp. is by hand (rule 3).

## 12. Records and definitions, for reference

**A proof record** (`runs/<model>_fw<fw>/<run>/proofs.jsonl`, one line):

```json
{"path": ["Center Marker"], "kind": "list", "index": 1, "label": "On", "shown": "On", "vlm": "On",
 "chosen_frame": "118317_down.png", "row_frame": "118318_enter.png", "dat": "118319_Center-Marker-1.DAT",
 "base": "118303_Marker-Display-1.DAT", "changes": [{"key": "global:0x0324", "before": 0, "after": 1}],
 "notice": null, "applied": true, "context": "Movie mode"}
```

**A setting in a definition** (`editor/definitions/<model>_fw<fw>.json` `settings`). Fields are additive: the
editor ignores fields it does not know.

```json
{"key": "global:0x0324", "area": "global", "id": 804, "name": "Center Marker",
 "tab": "Shooting", "group": "Marker Display", "values": [[0, "Off"], [1, "On"]], "note": "",
 "in_sets": true, "scalar": true, "size": 1, "count": 1, "modes": "movie, S&Q",
 "proved": {"values": [0, 1]}}
```

The proof's run, day, menu rows and name sources are in the evidence file, under the same key.

Notes say what a person needs, in the definition's own words: which records move together, what a file
cannot set, which mode or orientation writes the record, and what is unknown.

## 13. A round trip at the end

A map is only useful if a file the editor writes loads on the camera as intended:
1. Edit a downloaded file with the editor (several settings, including an array slot and a
   memory-set record).
2. Write it with the editor's "Write to camera", with the owner's word: the kit's own upload refuses an edited file
   (rule 12). The editor reads the camera back after its restart and lists every record that differs from the file
   sent (`EDITOR.md`, "The camera link").
3. Check that every edit took and nothing else moved. Anything rejected or rewritten goes into the
   definition's notes.

The first such test on the a1 II passed on 2026-10-23 (a file-name prefix edit).

## 14. Hints from the a1 II (to prove, never to copy)

`data/ILCE-1M2_fw4.00/` holds what this body taught. Use it to know where to look and what to expect on a body of
the same generation, never as proof:
- `camera_<model>_fw<fw>.json`;
- `settings_reset_<model>_fw<fw>.json`, which settings Camera Settings Reset leaves alone;
- `help_guide_menu_<model>_fw<fw>.jsonl`, the Help Guide's menu list;
- the definition's menu list and each setting's place (`row`, `row_at`, `row_tab`, `row_group`, `under_option`): the
  menus' rows in the camera's order;
- value ladders: ISO, aperture, shutter and bracket codes;
- the a1 II's page, `docs/models/ILCE-1M2_fw4.00.md`: behaviour worth testing again, such as Different Set for
  Still/Mv, orientation sets, first-use records and the memories' records.
- Recall Custom holds keep values the hold's screen never shows (the a1 II's page: the Reg. Custom Shoot Set and
  Recall Custom rows). Look for such copies with a start file, downloaded, in which the live setting differs.

## 15. What "done" looks like

- Every row of every mode's map is proved, or excluded with a written reason: rule, by hand, an
  action, an info screen, or not in the file.
- `kit/pass2_report.py` shows no unexplained conflict or missing value, and `kit/schema_update.py` (without
  `--write`) prints its gate line with every open question accepted. Every proved record has
  value labels the camera showed, and the inferred ones (section 6) are only on readouts and flags.
- The evidence was re-checked offline (section 6): the proofs' frames against their labels.
- Records only the owner can change (dial, orientation, registration, resets) are proved in
  sessions, and the definition's notes say how.
- Records a file cannot set are recorded with a note saying so, so the editor can show them
  read-only.
- The `data/<model>_fw<fw>/` folder holds the files [Data files](DATA_CONTRACTS.md#what-a-mapping-delivers) lists as
  required, and the model's page is in `docs/models/` with its entry in `mkdocs.yml`'s nav (`kit/tools/build_docs.py` writes it). The model's definition,
  `editor/definitions/<model>_fw<fw>.json`, is as `kit/schema_update.py --write` wrote it, it opens the owner's files
  in the editor (Add definition…), and no other camera's definition changed. It is lean
  (`kit/tools/check_public.py --all` exits 0), and its evidence file stays in `private/`. Its record names,
  `docs/formats/sony_camset_ids_<model>_fw<fw>.ksy`, go with it ([Data files](DATA_CONTRACTS.md#what-a-mapping-delivers)
  says what writes them).
- The menu tree is written by `kit/tools/menu_tree.py --crawl <crawl> [--crawl ...]` (`--dry-run` first), into
  `private/evidence/<model>_fw<fw>/menu_tree_<model>_fw<fw>.json`, and each other shooting mode's menu beside it from
  that mode's page scan and crawls: `kit/tools/menu_tree.py --mode Movie --scan <the Movie page scan> [--crawl <its
  crawl>]` (S&Q likewise), so the settings proved in Movie mode find their rows.
- The camera holds the owner's own file again: an upload, then a download that differs only in
  the records a file cannot set.
- The tests pass (`kit/tests`, `cargo test` in `editor/`), and the notes and the memory map are
  current.

## 16. New model: first day

1. **Read the model and firmware** with the SDK (`SoftwareVersion`), and take the layout
   fingerprint of a downloaded file: every record's id, size and count, in order (`kit/tools/identify.py`,
   the same signature as the editor's).
2. **Read the model's whole Help Guide,** every page, not only its menu list (decided 2026-11-01). It
   names each item's options, the modes it appears in, what greys it out, the default-value and reset
   lists, and what Save/Load Settings leaves out. Keep your notes from it in your `private/`
   (decisions 13 and 18: Sony's text is never published), to plan runs, set press budgets and order the
   work, never as proof. Only its menu list goes in `data/`: `help_guide_menu_<model>_fw<fw>.jsonl`, one
   line per item with its tab, group, name and modes. On the a1 II only the menu list and a few pages
   were read, and rows the list leaves out (Forced File Number Reset) were found on the camera.
3. **Keep the model's results apart.** Its results go into its own `data/<model>_fw<fw>/` folder, proofs and
   definition (`editor/definitions/<model>_fw<fw>.json`, which `kit/schema_update.py --write` writes for the camera
   the kit works on); files from different bodies or firmware are never mapped with another's definition. When no
   known container block reads its files, `kit/tools/identify.py` prints a draft: correct it into the camera file's
   `file` by hand ([the container block](DATA_CONTRACTS.md#the-container-block-file)) before anything else. The second body's runs get a folder of their own,
   `runs/<model>_fw<fw>/`, which `kit/tools/identify.py --camera` starts (section 7, "Where runs go"): name it in
   `private/config.json` (`"camera"`, with `"cameras"` listing both bodies and their own addresses) or pass
   `--camera` to each command, so the first body's runs, viewer and downloads are never mixed with the second's.
   `build_docs.py --write-schema` writes the active camera's definition only, never the a1 II's while another camera
   is the active one.
4. **Check the screens.** Run `kit/tools/selftest.py`, open one screen of each type by hand while
   `kit/tools/hdmi_watch.py` records, and score the readers on those frames. Recalibrate the HDMI crop
   and recut templates where they miss.
5. **Download twice with nothing changed, and once after turning the camera,** to find the
   volatile records, and write them into the new body's `data/<model>_fw<fw>/camera_<model>_fw<fw>.json`
   (`volatile_records`) before Phase 1: a diff ignores only its own body's volatile records, so without them every
   row fails its last diff. Upload the download back and download again to find the records a file
   cannot set.
6. **Then Phase 1.** How long the work takes is in section 11.
7. **Read the camera's own help** for every row (`kit/help_run.py`) and every option
   (`prove_run --help-text`) once Phase 1's maps exist: C4 opens it where the footer draws the help
   button, and the kit sends it on no other screen (decision 7, rule 13). Then
   `kit/help_reads.py` reads every saved guide frame again with the VLM readers, where OCR slips. For the ILCE-1M2,
   `schema_update.py --write` puts the text they settled on into your `private/help/` (decision 13); for a new model
   it stays in its `runs/<model>_fw<fw>/` until that model's help reading is wired into its definition (the
   ILCE-1M2's tables do it for that body only).
