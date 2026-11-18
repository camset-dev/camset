# Changelog

What changed for the people who use Camset, newest first. The version is `editor/Cargo.toml`'s; a release is a tag
on GitHub with the editor's packages attached ([RELEASING](docs/RELEASING.md)).

## Unreleased

### Read first

- **`--network` now makes `crawl_run.py` and `drive.py` a look lap**: it opens every menu row to look at with no owner
  decision, but what never opens, a row whose opening acts, and a format, delete or reset not yet seen opened on the
  body (decision 24); a decision now only names the options a run may choose.
- **If you map a camera other than the a1 II and made a sample** (`editor/definitions/<model>_fw<fw>.DAT`), make it
  again: the older kit could leave the owner's own records in it, such as a registered lens list with each lens's
  serial number. List your camera's `personal_records` in its camera file first; `kit/tools/make_sample.py` and
  `kit/tools/check_public.py` now refuse a sample without them (docs/DATA_CONTRACTS.md, "Records that hold an
  owner's own data").
- **A kit run that asks a reader now needs one in `private/config.json` that answers a test question before the link
  opens**; otherwise it stops, nothing pressed, and says what to do, where it went on with OCR alone or stopped
  midway. The example config names no reader and no camera address until you fill them in, a paid reader plays only
  the roles you give it, and `kit/tools/reader_check.py` tests your readers with no camera (the quick start, step 3).
- **`crawl_run.py` and `drive.py` no longer exit 0 when they did not finish:** once the start file is back,
  `crawl_run.py` exits 7 after a refusal and 8 after any other failure or a short lap, `drive.py` exits 8 when it did
  not reach its first `--path` row, and `kit/tools/chain.py` stops on both. A crawl now skips a row whose label it may
  not open or cannot read ("skipped: refused" in `rows.jsonl`) and goes on, where it stopped.
- **The kit opens fewer rows, on every camera:** no `--allow` opens the Wi-Fi and Bluetooth settings, the screens that
  show the camera's network addresses or Display Serial Number, and the kit refuses Enter on SSID/PW Reset as on
  Initialize and Reset Network Set. Only a camera owner's dated decision opens more, as The mapping kit below says:
  network rows to look at with `--network`, or one never-open row per `drive.py --owner` run (decisions 4, 5, 8 and
  9).

### The project

- A download can be checked: each release from this one carries `SHA256SUMS`, the checksum of every package and of the
  definition viewer, and GitHub keeps each file's signed build provenance.
  `shasum -a 256 -c --ignore-missing SHA256SUMS` (`sha256sum` on Linux, `Get-FileHash` on Windows) shows that a file
  arrived whole, and
  `gh attestation verify <file> --repo camset-dev/camset --signer-workflow camset-dev/camset/.github/workflows/editor-release.yml`
  that the project's release workflow built it; neither is a code signature (the README, "Check a download").
- No Camset program is signed: SignPath Foundation declined the project's application for free code signing for now
  (2026-11: the project is too new), and the project will apply again later. A code signing policy on the docs site
  (Reference > Code signing policy) says what would be signed, who approves it, and that the editor sends nothing over
  a network unless asked.
- A security problem is reported through the repository's Security tab (Report a vulnerability) or, where that is not
  offered, a Bug report titled "Security contact" with no details; the security policy, the code of conduct and the
  new-issue page are written for the public repository and say so.
- The editor's crates and the kit's Python packages are checked every week against known vulnerabilities, and
  Dependabot proposes newer versions weekly. The first check found two high-severity advisories in `quick-xml`, which
  only the Linux editor takes in, through eframe: they are set aside until a newer eframe drops it, as the crate's
  source shows it is never called at run time (no built program was inspected).
- The release workflow builds only a tag on a commit of `main` (push `main` first, then re-run the job), and every
  build takes exactly the crates `editor/Cargo.lock` names.
- The kit's pinned packages move to anthropic 2.8.0 and zensical 0.1.1, which the next `python3 kit/setup.py`
  installs, and the editor takes pollster 1.0.1.

### The editor

- **The a1 II's Zone place for each way of holding the camera shows outside Expert mode,** one row per hold in each
  memory set. Its two other records, which the camera writes alike, are its copies in Expert mode and change with it.
- **The a1 II definition says how far each focus frame can travel** (`frame` on the records of each place: each spot
  size's limits at each Aspect Ratio, each Custom box's bounds, size records and each ratio's picture), measured level
  at all four aspect ratios and grip down and grip up at 3:2; the editor does not use it yet. A new hand table,
  `FRAME_TRAVEL`, records the same for any camera (docs/DATA_CONTRACTS.md); `FRAME_STEPS` holds every area's step
  under Standard and Large, and AF Frame Move Amt's note no longer calls Large's step twice Standard's.
- **The a1 II's Custom box sizes are measured:** each box's width runs 28 to 548 and its height 32 to 396, which the
  definition's range now says, a click 16 across or 12 up and down, and the notes no longer give the wrong steps of
  the first test. The travel rule holds at every size tried at 3:2, so the definition counts it proved across the
  whole range there, and at the default sizes only at the other aspect ratios.
- **The a1 II's focus frames in Movie and S&Q:** a frame's `in_modes` says how each shooting mode picks its limits,
  and the editor reads it (`Frame::picks`): the spots and the box in use take Stills' 16:9 limits in Movie, as measured,
  and in S&Q, as inferred from Movie. Custom 1-3's own places keep limits in Stills only, since their size records hold
  other numbers in a Movie memory.
- **The a1 II's Zone and Custom box position copies, and the spot size and Custom area AF Area Registration writes,
  say which way the camera was held** (horizontal, grip down, grip up or current, as the spot's do), from
  registrations made level, grip down and grip up; the Custom boxes' now show outside Expert mode, like the spot's.
  Record 0x04e2 is no longer called the camera's position, which it is not, and the Registered AF area notes say what
  Del. Regist. AF Area writes.
- **The a1 II's Proxy Rec. Settings names its third value as Sony does:** the code a Camera Settings Reset or
  Initialize leaves is 6M 4:2:0 8bit, XAVC S HD's setting; it is marked as one the menu does not offer, and its note
  says how the camera shows it under each proxy format.
- **The a1 II definition names twelve more records** (Expert mode): the spot size and the Custom area as the camera
  writes them when an AF area is registered. The notes of Exposure Comp.'s two copies now say what the camera's
  files and one test on the camera show: copy 1 always equals it, and copy 2 keeps the slider's position when MENU
  cancels the screen.
- **Playback's Image Index showed its two values the wrong way round** on the a1 II: 0 is 9 Images and 3 is
  30 Images. A firmware cross-check reported in issue 1 found it, and the frames kept from the day the row was
  changed by hand confirm it.
- **The a1 II's Different Set for Still/Mv is read and edited:** its seven boxes (Aperture, Shutter Speed, ISO,
  Exposure Comp., Metering Mode, White Balance, Picture Profile) are settings on the Setup tab, each proved on the
  camera. What the White Balance and Picture Profile boxes do to the stills and movie copies is proved too, in the
  states tried, and their notes say so in Expert mode; for the other five boxes it is not, and they change alone as
  before.
- **Unticking the a1 II's White Balance or Picture Profile box asks first,** in the window and on the web page, from
  wherever the change comes: on the camera, unticking also set that setting and both its copies to Auto or Off, and
  what the camera makes of a file where they differ is not known. Choose "Do as the camera does" (one step, one Undo),
  "Change this setting only" or Cancel; while a box is ticked, its setting's rows say that the camera then changes
  only the copy for the mode in use, which the editor does not follow.
- **The a1 II's Fn Menu places list only the functions their own picker offers on the camera,** where each listed
  every function seen on any picker, and its custom keys drop the few their picker never shows, so even Expert mode no
  longer offers them there. In Expert mode a value shown as "7 (no name yet)" now says that no choice on the camera
  wrote it and that the camera's list may not offer it.
- An installer for Windows beside the zip, `camset-editor-<version>-windows-x64-setup.exe`, installs the editor for
  you alone with no administrator rights, puts it in the Start menu and Windows' installed apps, updates it in place
  and never touches your own files. Neither is signed yet, so Windows SmartScreen warns the first time (More info,
  then Run anyway), and Smart App Control, where it is on, blocks them.
- The a1 II's notes claim only what holds for every a1 II, with nothing particular to its owner's camera, and Proxy
  Rec. Settings is corrected: its row follows the Proxy File Format, and its code 3, which no menu choice writes, is
  what Initialize and Camera Settings Reset write.
- On Windows, Settings > About names the Windows version and build ("Windows 11 build 26100"), as it does for macOS
  and Linux.
- On the web page, Open in Backups opens the copy you chose even when the editor kept more copies after the list was
  shown; a page left open from before this version asks to be reloaded first.

### The definition viewer

- A file the viewer refuses shows its size and first bytes as a hex dump, to paste into a problem report: the file was
  read in your browser and never left it, but check that the dump holds nothing of yours before pasting it anywhere
  public.

### The mapping kit

- **The kit no longer presses Enter on a screen that asks something, whatever its words or language, unless the run
  names that screen.** `drive.py --confirm` now takes the screen's text and covers one press, and formatting or
  deleting a card needs the owner route (`drive.py --owner`).
- **A menu row the kit has never opened on your camera now opens only once you have said your cards hold nothing you
  want kept (`kit/tools/owner_statement.py cards`), and so that a lost link can be put right; `kit/tools/take_picture.py`
  takes one picture for the Playback rows, only when you answer its question at your own terminal.**
- **A coverage ledger** (`kit/tools/coverage.py`, decision 23) says for every menu row, value and record what is
  settled and what is left (`--todo`); `--write` writes a public form and a seen file into the data folder, holding
  nothing of your camera's state, and once they are committed, run it again after each `kit/schema_update.py --write`,
  or `check_public.py` refuses the form. `drive.py`, `crawl_run.py` and `prove_run.py` print what it says of a row
  before pressing on it, and `crawl_run.py` or `prove_run.py` given `--skip-settled` leave settled rows out (never on
  the crawl that builds pass 1's map).
- `kit/tools/leads.py` reads your camera's own downloads and says which records no setting covers ever changed, and
  with which rows; `--write` gives the coverage ledger its private leads file (counts only, never a value).
- The writer reads every camera's own hand tables file (`data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json`), where
  it read only the a1 II's (now a data file, the pattern), and stops in plain words on a table it does not read yet or
  a file that breaks its schema. While your tables hold `FRAME_PROOFS`, `UNPROVED`, `NOT_OFFERED`, `PICKER_LISTS` or
  `KEEPS_APART` entries, `--write` needs your private hand evidence file, which `kit/writer/hand_evidence.py --check`
  checks (docs/DATA_CONTRACTS.md, "The hand evidence file").
- Two new hand tables: `PICKER_LISTS` cuts a picker's settings to the list walked whole on the camera, and
  `KEEPS_APART` records a switch that keeps a setting's stills and movie copies apart and what unticking it sets
  (written into the definition as `keeps_apart`, which the editor asks about). Each takes effect only with its private
  hand evidence, and a camera download that contradicts either, or a proof or sample holding a code outside a cut
  list, stops the write (docs/DATA_CONTRACTS.md).
- `kit/crawl_run.py` and `kit/prove_run.py` take `--info-ok "ROW=PHRASE"` (repeatable; never with `--network`) for a
  row whose screen sits behind an information notice, such as the a1 II's Different Set for Still/Mv: given the
  notice's whole text, the run takes its OK once, and only for a notice that explains and asks nothing. Anything else
  presses nothing, and a phrase that leaves part of the notice out prints the notice's text (the playbook, section 8).
- The safety guards now catch a never-open row or a confirmation whose words OCR ran together or split ("Forma t",
  "DeleteAll", "Formatthe memory card?"), on every run, and a decision or `--allow` permits only what reads so as
  written too. The camera's own check now refuses Enter on a notice or dialog that reads as a confirmation or reads
  nothing, unless `--confirm` judged that press, so a tool that OKs a notice it expects stops there instead, nothing
  pressed.
- White Balance > Cloudy no longer stops a run as a cloud-service row; cloud rows are still refused as written, run
  together or split.
- The menu navigation every run shares guesses less: it reads the lit group again instead of taking the first, finds a
  group bar or row read with a stray icon or a letter off, or a group bar read with its number (on OSD eyes a jump to
  group 10 or later stopped), never jumps into a group read one letter off a never-open one, and presses nothing where
  it cannot tell.
- `kit/tools/help_extras.py` and `kit/provers/customshoot_values.py --counted` read your own camera's shooting-mode
  record (the camera file's `live_mode`) and Focus Area order (from its definition; `--order-from` names the record),
  where they read the a1 II's on every body, and stop, saying what is missing, where yours has none.
- On macOS 27.2 and later, where Apple's text recognition often misses an end of a Creative Look parameter's scale,
  the proof reads a -9..+9 or 0..9 scale from its tick marks once it has read both ends beside the same ticks, and
  ends that do not match the ticks now stop it; a 1..5 scale, and RapidOCR on Windows and Linux, still stop the proof
  as before.
- Sony's list of what a settings file never holds is now data, the camera file's `save_load_excluded`, which the model
  page and the coverage ledger read; a definition never carries it.
- `--network` (`drive.py`, `crawl_run.py`, `prove_run.py --rows`) opens, to look at, a network row a dated owner
  decision names (`"lifts": "network"`), choosing only an option it names and none that may drop a link or start a
  connection. Credentials, resets, pairing and connection rows, Display Serial Number and IP Address Setting (it
  dropped the link) stay closed whatever it names, as do the USB rows, Language, NTSC/PAL and Area/Date/Time until
  seen to open safely over the link.
- `drive.py --owner` opens, one per run, a never-open row a dated owner decision names (`"lifts": "owner"`), the last
  label of `--path`: a card's Format or Delete, another action, a credentials screen, or the USB rows, Language,
  NTSC/PAL and Area/Date/Time at the owner's risk (none has been seen opened over the link), but never Initialize, a
  firmware update, anything that loads a file or settings, sound, light, motion or the Screen Reader. An action's last
  press needs `--confirm` and the row's name typed by the owner; one that may drop the link writes
  `RESTORE_BY_HAND.json` first and exits 6 if it only raised a question, which it cancels, else 5 unless the restore
  checks out, and after a 5 no link opens until `kit/tools/upload_check.py` puts the start file back (`--accept` names
  records left differing).
- A `--network` or `--owner` run asks local readers only and prints and keeps no screen text or value: only each
  screen's kind, the row labels the kit knows and field names, nothing that tells which option a row was saved on. The
  frames of a credentials or identity screen an owner decision opens are saved black unless it says
  `"values": "logged"`, which keeps them and puts their text in `drive.jsonl` alone; the run's folder and every file
  in it, what later tools write there included, are readable by you alone on macOS and Linux.
- Where the proof viewer is not built, its message and `kit/setup.py` now say that the definition viewer needs no
  runs: `kit/tools/proof_viewer.py --public --out site/viewer` builds it, and it is online at
  <https://camset-dev.github.io/camset/viewer/>.
- `kit/tools/reader_census.py` measures, over runs already made, how the coming rule for when OCR alone is trusted
  (decision 22) would treat each reading, and compares the reader's questions (`--questions`; `--claude-cli` asks
  Claude through Claude Code on your own plan, and no hosted reader is sent a frame that may name the network, an
  address or a credential). No run reads, decides or presses differently yet.
- `kit/provers/mode_switch.py` now takes the table the a1 II's Mode Dial Control Set opens, where it stopped before,
  and puts the Shooting Mode Dial's cell alone on Set with Menu once it has checked that the lit item is that cell.
  Anything it cannot check stops the switch with MENU alone, and the Set All buttons are never pressed.
- A camera helper (`kit/link/build/camlink`) built before an option a tool needs now says so, and that
  `python3 kit/setup.py` rebuilds it, instead of "camera link exited". `kit/tools/take_picture.py` then says the link
  never opened and nothing was sent, not that the start file is not known to be back.
- A screen read as the shooting screen while the camera says it is in Playback is now the playback view some Playback
  rows open, where the kit sends no key but MENU and the Playback button, once, to get back (decision 21). A first
  open's check and a run's end ask no download while the camera says Playback: where the view is not left, the run
  writes `RESTORE_BY_HAND`, says how to leave it by hand and exits 5, where the first look lap over the Playback tab
  asked for a download the camera refused.
- A look lap now keeps a row's own name wherever the camera's definition names that row, a Custom Key's function too
  (on the a1 II 4 top-level rows stay "(withheld)", not 78, so one failed first open no longer skips them all), and
  keeps what it kept of a screen's text. After a first open's check that leaves the menu on another page the scan
  knows, `crawl_run.py` goes back to its row once as `--start-label` would, and stops with exit 8 as before where it
  cannot.
- `drive.py` no longer refuses its `--path` row where OCR reads the row's icon as a letter or two before its label
  ("S Exposure Comp. +0.0"), or where the label ends in a stop before its value ("Exposure Comp. +0.0"): on the first
  press after the page scan went to that row, the bar is the row where the page scan read it so too and the value is
  one the kit knows.
- A `drive.py` run that presses anything but up, down or MENU inside a row is now recorded as a choice, so a record it
  changes no longer makes a row the camera has opened before count as never opened. A row's first open now goes on
  over a slider, number fields, a table or another option screen MENU leaves, and Enter refused for want of a readable
  cursor says that `--press 'enter!:REGEX'` vouches for it.
- A row whose first open showed a screen of its own that the kit cannot read, such as the playback view of the a1 II's
  Cont. Play for Interval, now counts as opened once its check comes out clean, so later laps open it normally. A row
  that only showed a notice, or did not respond, still has its next open checked.
- `kit/provers/framepos_run.py --grip down` (or `up`) shows which records one vertical orientation's registration of
  a focus frame writes: with the owner holding the camera that way, it sets Switch V/H AF Area to AF Point + AF Area,
  reads the turned screens upright and ends each area's summary with "grip down writes:" and the records' names, and
  `--grip level` does the same for the camera standing level ("level writes:"). Held vertically it judges no press's
  direction, stops at the first area that fails, and refuses `--zone-grid`; and `kit/provers/afreg_run.py` takes
  `--grip level` too, each grip's hold line naming every record the hold changed.
- With `--grip down` or `up`, `framepos_run.py` and `afreg_run.py` read Vertical Display from the start file: Off reads
  every screen level and says so in each line's context ("camera grip down, Vertical Display Off"), and On now finds
  the portrait shooting screen the camera's own picture shows, where a run waited five minutes at its start and gave
  up. A Focus Area dialog drawn in a way the kit does not know stops the area, saying what the frame shows.
- `framepos_run.py --edges` measures how far each movable focus frame can travel: pushed to its edges and brought back
  exactly, each record's edges and step per press read from slot 1's registrations, with Circ. of Focus Point set to
  Does Not Circulate and AF Frame Move Amt to Standard first. A frame whose start no press reaches is said with the
  difference and the run stops.
- Under `--frame-move-amt Large`, `framepos_run.py --edges` now brings each frame back under Standard, where a press
  that would cross the centre stops on it as the way back counts on, and Large crosses it; the Large way back left a
  frame out of place. `--put-back RUN` brings back each frame an edges run left out, through the far corner under
  Standard, checked by a registration.
- `framepos_run.py --zone-grid` now takes `--grip down` or `up`: the nine Zone places walked with the camera held that
  way, each place saying which orientation's records its registration wrote, and keys that move the zone turned said
  as a finding before the zone is put back and checked.
- An `--edges` area stopped by its STOP file once its frame moved now writes its line, and `--put-back` also finds an
  area an older run stopped in from its downloads, so the frame can be brought back. A start off the centre is put back
  only under the Aspect Ratio it was measured in, the place grid being stretched over the picture.
- `framepos_run.py` now works in Movie and S&Q when `--scan` names that mode's page scan: it plans from that mode's
  crawl and registers that mode's first memory, while a Stills run still stops on a camera left in Movie.
- Where the page scan knows a row only by one reader's reading and OCR garbles its icon on the lit bar (the a1 II's
  S&Q Settings in S&Q mode stopped `mode_switch.py`), the menu navigation now asks the vision reader once what the lit
  row is and goes on only where it reads exactly that row. A `--network` or `--owner` run asks a local reader only and
  prints nothing it read.
- The kit now reads a screen of boxed options alone, such as the a1 II's Image Index, where a row's first open stopped
  with `RESTORE_BY_HAND`: it looks at it and leaves it with MENU. Enter on it stays refused unless `--confirm` names
  the screen, since a question can be drawn the same way.

### The docs

- Three pages are folded into others: updating a clone into CONTRIBUTING, camera support into the quick start,
  where each fact lives into decision 14.
- The docs site uses the system's own fonts and no longer loads any from Google, so Google does not see its visitors;
  the header's star count still comes from GitHub, which hosts the site.
- The editor's guide says plainly that the camera login file holds the passwords in plain text, protected only by the
  file's permissions.
- The decision records say what holds now: a changed decision is rewritten in place, with a line saying what it said
  before and when, the decisions index gives each rule in one sentence, and no rule is weaker. Decision 7's keys never
  sent no longer include the multi-selector's centre, a menu key like Enter, and decision 22 is cut to its rule and
  why.

## 0.2.1 (2026-11-13)

The editor for Windows too, the definition viewer to download as one file and on the docs site, About in Settings,
the kit's plain words for a Python that cannot run it, and fixes.

### Read first

- **Writing an edited settings file to a camera is at your own risk.** A file edited by hand once put a camera into
  a restart loop in Movie mode, which ended when Initialize was run on the camera; Initialize also clears the network
  setup and the memories. The editor and the camera may refuse or change values. Always keep the camera's own backup,
  a settings file it saved itself, to load back: on the card and on your computer.
- This is an independent project, not affiliated with or endorsed by Sony. Sony and the camera names are used only
  to say what the files are.
- The editor's packages (the macOS app and disk image, the Linux tarball, the Windows zip) do not include the camera
  helper, which reading and writing a camera directly needs: the editor works on the files a camera saves to its
  card. The helper is built from Sony's Camera Remote SDK on your own computer under Sony's terms (the README, "The
  camera helper").
- Windows: the program is not signed, so Windows SmartScreen warns the first time it runs ("Windows protected your
  PC"): click More info, then Run anyway (the README, "Use the editor").

### The editor

- The editor's version is in the window's title and at the right end of the status bar, which opens Settings' new
  About tab on every system: the version and build, the system, the cameras it works with, whether the camera link
  program is there, links, Changes, the third-party licences, and Copy details for a problem report, with nothing of
  yours in it.
- The macOS disk image installs the macOS way: open it and drag Camset Editor onto Applications.
- A Windows package joins the macOS and Linux ones: a zip for 64-bit Windows 10 and 11 on Intel or AMD. Unpack it
  anywhere and run `camset_editor.exe` in the folder it makes, with the camera definitions and the licences beside
  it. The program is not signed, so Windows may warn the first time (More info, then Run anyway).
- On Windows, the editor takes this computer's time as local time, as the camera's is. It took it as UTC, so a read
  said the camera's clock and the computer's differed by the time zone's hours when they agreed, and the files the
  editor keeps were named by UTC.
- On Windows, the editor's tests built in release mode (`cargo test --release`) print their results in the console;
  only the app itself opens without a console window.
- On Windows, no console window flashes up when the editor talks to a camera: searching for cameras, reading and
  writing start the camera helper without one.
- On Windows, `camset_editor.exe` carries the editor's icon, so Explorer, shortcuts and a pinned taskbar button show
  it instead of Windows' plain program icon, and Properties > Details names Camset Editor, its version and its
  copyright line. A Windows build makes both itself, from the same picture the window and the macOS app use;
  nothing more needs installing.

### The web page

- The page names the editor's version at the right end of its status bar. Its Settings has the About tab too, which a
  click on that version opens, with the window's lines, links and Copy details, and Changes, which shows what changed,
  release by release. The third-party licences are opened from the desktop app.
- The page's windows stack by when they were opened or asked for, the newest at the top, under a question, which stays
  first: one opened while another is open (Changes from Settings > About, Settings from the status bar's version) is
  never below it out of sight on a phone, and Escape closes it first.

### The definition viewer

- A page anyone can open to look inside a settings file, with nothing to install: the definition viewer, at
  <https://camset-dev.github.io/camset/viewer/>, reads a `CAMSET*.DAT` in the browser, where it stays, and shows each
  setting by name in the camera's menu, as the editor does, with whether a proof checked each value and the file's
  layout byte by byte. `kit/tools/proof_viewer.py --public` builds it, `--single` as one file that needs no network.
- Each release carries the definition viewer as one file, `camset-viewer.html`, to download and open with no
  internet; the latest is always at <https://github.com/camset-dev/camset/releases/latest/download/camset-viewer.html>.
- The proof viewer says when a file is of another firmware than its definition, not only of another model; its file
  buttons answer Enter and Space and suit a touch screen, links read on the light theme, a file's header text is read
  as UTF-8 as the editor reads it, and a file framed with no section of settings is refused as damaged.

### The mapping kit

- `kit/setup.py` on Windows finds Sony's USB driver once it is installed, where the reminder came back forever, and
  gives every step that needs another window or administrator rights as numbered steps in Windows' own words. Without
  Python's UTF-8 mode it stops at once with the three steps that turn it on (`setx PYTHONUTF8 1`, a new terminal, the
  same command again there).
- `kit/setup.py` on every system carries on past a step marked DO (yours to do), says roughly how long each long step
  takes and shows its progress, says so when one takes unusually long, and stops cleanly on Ctrl+C; its last lines say
  that everything is in place or list what is left for you, in order.
- The kit's tests are fixed for Windows, and the kit's CI runs them there for every pull request and push to main; in
  the kit, `kit/tools/make_sample.py` refuses a result naming a download by an absolute path of any system, a chain
  file with a Windows path in double quotes says how to write it, and a read-only results file leaves no temporary
  file.
- A kit program started with a Python that cannot run it (macOS's own `python3`, or one without the kit's packages) no
  longer ends in a traceback: it says what is wrong and gives the command to run instead, with the kit's own Python
  (`.venv/bin/python`, on Windows `.venv\Scripts\python`). A program that needs none of the packages runs on the
  system's Python as before.

## 0.2.0 (2026-11-11)

The editor for macOS and Linux, the mapping kit, the docs and the ILCE-1M2 (a1 II) firmware 4.00 definition, in the
new lean form. It replaces 0.1.0, which is withdrawn.

### Read first

- **0.1.0 is withdrawn: use 0.2.0.** Its packages are no longer offered. If you have the 0.1.0 editor, replace it
  with this one.
- **Camera definitions are in a new, lean form (definition format 2).** This editor, which comes with the new ILCE-1M2
  definition, does not open a definition made for 0.1.0, nor the 0.1.0 editor the new ones. If you are mapping a
  camera with a clone of this repository, update it as [CONTRIBUTING](CONTRIBUTING.md) says first and write your
  definition afresh with the updated kit.
- **Writing an edited settings file to a camera is at your own risk.** A file edited by hand once put a camera into
  a restart loop in Movie mode, which ended when Initialize was run on the camera; Initialize also clears the network
  setup and the memories. The editor and the camera may refuse or change values. Always keep the camera's own backup,
  a settings file it saved itself, to load back: on the card and on your computer.
- This is an independent project, not affiliated with or endorsed by Sony. Sony and the camera names are used only
  to say what the files are.
- The editor's packages (the macOS app and disk image, the Linux tarball) do not include the camera helper, which
  reading and writing a camera directly needs: the editor works on the files a camera saves to its card. The helper is
  built from Sony's Camera Remote SDK on your own computer under Sony's terms (the README, "The camera helper").
- Windows: no package in this release; the editor builds from source there (the README, "Use the editor").

### The project

- Definitions are lean, definition format 2: they say what the camera is, the same for every owner who maps that
  model and firmware, and nothing of how, when or in which run it was proved (decision 16). An older editor says it
  needs a newer one to open them.
- `data/` holds only what is the same for any owner of a model and firmware: the menu tree, the accepted rulings and
  the record shapes are kept in `private/evidence/`, and the reset file lists only what a test could tell.
- Decision 21: on the shooting screen the kit presses no key but MENU unless the run names it, since the body does
  there whatever its owner assigned to the key. Other owners' settings files are named by their firmware only, and
  what they held is no longer told.
- A test fails the build when the editor's own code holds a setting key, a record id, a camera model or a
  definition's file name: the editor reads a camera's facts from its definition (decision 20).
- A daily workflow records the repository's stars, forks, watchers, open issues, release downloads and (with a `STATS_TOKEN` secret) traffic to CSV files on the `stats` branch ([RELEASING](docs/RELEASING.md)).

### The editor

- A value the camera keeps in more than one record stays in step: changing a setting (Picture Profile, ISO, White
  Balance, Metering Mode, ISO AUTO's limits, Exposure Comp.) changes the Stills and Movie copies that held its value,
  saying so first, and a file whose setting does not match the copy for the mode it was saved in is listed, with a
  fix, before a save or a write.
- Outside Expert mode only a setting proved on a camera can be changed. Any other is view only and says why: the
  ILCE-1M2's PP7 to PP9, which no menu of the body writes, among them.
- A frame rate of the other video system is no longer offered for a file saved on NTSC or PAL, nor copied by Compare.
- The sample, and any file saved from it, is never written to a camera, however it was opened; saving or downloading
  it says it must not be loaded into one.
- The Write and Before saving windows list every changed record they cannot vouch for, each under what it is, and
  show the all-clear only when nothing is listed. They judge against the file as first opened, across Save As and a
  recovery, and a write also against the camera's own copy read just before it.
- Each Main page shows its own mode's ISO, White Balance and Picture Profile.
- A definition whose `definition_format` is no format the editor knows is refused in plain words: "its
  definition_format is 0, which is not a format this editor knows (it reads format 2)".
- Compare keeps records the camera writes together in one row, and a copy of many rows leaves each place holding
  what the other file holds.
- The ILCE-1M2's Registered AF area records are proved for every area the camera registers, the Tracking areas and
  their start areas among them, in all three orientations. "Custom slot when Custom was last left" is proved for all
  three slots.
- The Zone's place in the vertical memory copies is proved for all nine places of its grid.
- The ILCE-1M2's Playback/Monitor. Vol. and Voice Memo Play Vol. are proved on the camera by the kit, every value of
  both scales, each value's name read off the camera, where a hand round had proved them before.
- So are its Audio Signal Volume, the Screen Reader's Volume and Monitor Brightness's manual level (-2 to +2), every
  value of the three scales: the pass-2 report proves 7631 options (7604 before), and 1194 value names come from a
  hand table (1221 before).
- So are its Finder Color Temp. and Viewfinder Bright.'s manual level (both -2 to +2), every value of the two scales,
  chosen with the finder in use.
- A menu row whose proofs name less of the camera's state than other proofs of the same row covering the same values
  is no longer listed beside them; no proved value or value name changes. A setting table's cells (Image Quality
  Settings, My Dial Settings) are named by their row alone, and the definition keeps no menu row of an older write
  that today's report does not list.
- The memory sets' records that keep the Custom 1-3 boxes' places (26, the box in use's and each box's copies) are in
  the definition, Expert mode only, and the notes of the focus frame records say where each area keeps its place: a
  Tracking area in its plain area's records.
- The notes of the ILCE-1M2's focus point and Custom box records and of AF Frame Move Amt give the step one press of
  the multi-selector moves a frame under AF Frame Move Amt Standard and Large: Large's step is up to twice Standard's,
  Spot XS's step is smaller than Spot M's across (and, under Large, up and down too), and the Custom 1 box has its
  own.
- Expert mode no longer shows how a value was proved (the marks beside option names, the evidence line, the refused
  options' line); what it lets you edit is unchanged.

### The web page

- The page follows the window in all of the above, and a request the editor refuses answers with the reason.

### The mapping kit

- `kit/schema_update.py --write` writes the lean definition and keeps how each thing was proved in
  `private/evidence/<model>_fw<fw>.json`, never committed. A definition an older kit wrote must be written again
  with `kit/schema_update.py --write` before the editor opens it or it is sent.
- `kit/drive.py --on-shooting KEY` names a key the operator may send on the shooting screen; without it only MENU
  goes out there. No `--allow` opens a row of the camera's identity, its connections or its region (decision 8).
- The custom-shoot provers, the My Menu prover, AF Area Registration's Fn hold and `kit/tools/card_actions.py` open
  what they open only with the owner's word for the run (`--allow`), and `drive.py`'s C4 as Focus Area's SET or a
  Creative Look's Reset with `--c4-press`. `card_actions.py` ends as every runner does, restoring its start file, and
  navigates by the page scan the provers take (`--scan`, as `memreg_run.py`'s).
- C4 is refused when the camera lists its operating mode and the mode cannot be read.
- `kit/provers/pp_reset_run.py`, with the owner's word (`--allow "Picture Profile Reset"`), resets each Picture
  Profile by its own Reset row in Stills or Movie (`--in`), once a control shows that a Reset writes the records a
  settings file saves; a run meant for the sample presses only on what both readers read, and every run stops on
  anything unexpected and restores the start file on every exit. Its guards are written for the ILCE-1M2 at firmware
  4.00 and fail closed on other screens.
- `kit/tools/make_sample.py --take FAMILY --from RESULT` takes a definition family's reset values into a sample, never
  record ids, only from finished, verified `pp_reset_run.py` results that reset every offered profile, each with its
  positive control and checked against its own downloads. `--allow-no-notice` takes a result from a body that shows no
  completion notice, and `--allow-unchanged` a family whose records no reset download changed.
- `kit/provers/scale_run.py --panel-row` needs its panel's setup row among the `--set` rows, so no proof rests on a
  state the camera was found in.
- A definition now says which records are copies of a setting and which mode each copy is for (`copies`, `copy_of`,
  `copy_for`, `camera.live_mode`), and which values belong to one video system (`video_system_values`), checked
  against the camera's downloads on every write. It no longer carries anything that told how a camera stood when it
  was proved (decision 16); a count of samples stays in the evidence file.
- The record shapes, kept in `private/evidence/`, hold only records no setting covers, and no value.
- `kit/provers/afreg_run.py` puts Drive Mode on Single Shooting before a Tracking area (`--drive-mode`), as the camera
  refuses Continuous AF under some drive modes (it says so in a notice when Focus Mode is set), and stops when a setup
  step is refused, the notice's words kept in the run's own log, never printed.
- `--allow "ROW"` on `kit/prove_run.py` and the scale prover opens one never-open row the owner allowed, never the
  cards, Initialize, Reset Network Set. or credentials; the proof lines carry the words (`allowance`), and the writer
  puts them in each setting's note evidence.
- Where OCR reads no number on a scale, the scale prover asks the vision reader, but a number only the reader read
  never decides alone, and a scale counts only when its footer shows OK, its ends are confirmed and every step checks
  out, or the row stops and leaves no lines. `--panel-row` proves a slider inside a panel, and `--set "ROW=OPTION"`
  puts a row on an option first, never one of decision 8's rows.
- `kit/pass2_report.py` leaves out a row's proofs made where the camera merely stood (`stood_out`) when proofs of the
  same row in a named state write each record alike and the report credits them with every value those credit (a
  slider proved again with `--panel-row` and its `--set`, a hold with its run's setup, a row walked again in pass 3's
  named states).
- A setting table's cell (`kit/proving/tables.py`, the report) is named by its row as all the row's cells read it:
  `kit/table_walk.py` reads a cell's row label up to the cell, so a cell further right read the values of the cells
  before it glued on, values the camera held.
- `kit/schema_update.py --write` over an older definition keeps of its proofs only a value that a proof line the
  report counts still wrote (a hold's option numbered apart in two sessions); never an older menu row, count of
  samples, or value no counted line wrote. A mapper with a definition written by an older kit writes it afresh.
- The kit reads the viewfinder's shooting screen (the eye sensor covered and the monitor folded in) as the shooting
  screen: the finder draws its battery smaller, further right and higher, and that icon is one of the
  battery templates, cut from the camera's own frame.
- New provers for Camera Set. Memory, with the owner's word: `kit/provers/memreg_run.py` checks that a registration
  copies live settings into the memory set (`kit/tools/set_twins.py` picks the rows), and `kit/provers/framepos_run.py`
  finds which records keep each focus area's frame, `--zone-grid` sweeping the Zone over its nine places. Their
  "registration mirror" lines are no report row; the writer reads them (`in_sets_proved`, and the Zone's places).
- `kit/provers/framepos_run.py --frame-move-amt Standard|Large` sets AF Frame Move Amt by the menu before any area,
  stops when the download after the setup does not hold it, and names it in each line's context; `--moves "Right 1"`
  (or `"Left 1,Up 1"`) moves the point and box areas by the presses given, so a step can be measured by one press each
  way.
- A run's end leaves out, by key, the records a settings file does not set that the run is known to write (a memory
  slot's registration marks), so they never fail the restore's check.
- `kit/page_scan.py` needs `--mode Stills`, `Movie` or `S&Q`, the mode the camera is in, and records it in the scan.
  It refuses a run folder that holds a scan recording no mode or another mode, before anything is sent.
- The provers and tools take by default the latest page scan of the mode they work in, once its lap is whole and its
  page model was built after it, and stop, listing the camera's scans, when no scan records that mode.
  `kit/page_model.py --mode MODE <run>` records the mode of a scan made before scans recorded it.
- A page scan made while a kept mode switch left the camera in Intelligent Auto is taken by default only while such a
  switch waits, never for P, A, S or M.
- `kit/provers/filter_run.py`, `kit/provers/mymenu_run.py` and `kit/provers/mode_switch.py` take `--in MODE`, the mode
  the camera is in.
- `kit/provers/mode_switch.py --forget --shows MODE` removes a switch record left over after the camera was put back
  another way, sending nothing: `--shows` is the mode the screen shows now, family first (`--shows "Stills M"`; a
  letter alone is refused), and it refuses the mode the switch went to, which only `--restore` puts back. A run that
  stops on a waiting switch says to look at the screen first.
- `--scan latest` on a command that works in no mode of its own (`prove_run.py`, `crawl_run.py`, `drive.py`) stops in
  plain words.
- `kit/tools/set_twins.py` needs `--evidenced <run>` (`--evidenced ''` for none).
- `kit/tools/menu_tree.py` writes the menu tree to `private/evidence/<model>_fw<fw>/`, and a menu tree, accepted
  rulings or record shapes still in `data/<model>_fw<fw>/` are moved there once with `kit/tools/move_evidence.py`: the
  commands that use them stop and name it until then. Without the menu tree the proof viewer lists every record under
  its tab and group, and says so.
- `kit/tools/check_public.py` refuses a tracked path holding a control character (a newline, a tab, NUL and the
  like), with `--all` and `--commits`.
- On a pull request, `kit/tools/check_public.py --commits BASE..HEAD` holds every file each commit adds or changes to
  the rules `--all` holds the tree to (paths, binary files, contents, lean data and definitions), so a file added in
  one commit and removed in the next is refused all the same.
- The reset file is one public file, lean (`schemas/settings-reset.schema.json`), written and edited by hand; the
  kit keeps no private copy in step with it, and refreshes only each setting's name and tab from the definition. One
  in the older whole shape is refused, and `kit/tools/move_evidence.py` keeps the whole once in `private/evidence/` and
  writes the lean one in its place.
- `kit/schema_update.py --write` stops before writing when evidence went stale in that run (`--accept-stale` writes
  anyway, kept aside; `--drop-stale` lists it, `--drop-stale --write` removes it). A write cut short leaves a marker,
  the next write stops and names `--finish-write`, which finishes only that write, and an evidence file newer than the
  definition (after a pull) is no longer taken for one.
- Hand evidence (`private/evidence/<model>_fw<fw>.hand.json`, format 2) only adds to the public hand tables: it never
  replaces a value there. A format-1 file is refused, naming `kit/writer/hand_evidence.py --convert`, which converts
  it once.
- A page scan made again in the same folder writes its lap from its own records only: one that stopped before its
  first record no longer makes the folder's old lap the newest default. A new scan's page model counts by the lap it
  was built from, not by file times.
- A new record's layout is read from the run's newest start file, not from the file whose name sorts last.

## 0.1.0 (2026-11-09)

Withdrawn on 2026-11-11 and replaced by 0.2.0: its packages are no longer offered.

The first release: the Camset Editor for macOS and Linux, the mapping kit, the docs and the ILCE-1M2 (a1 II)
firmware 4.00 definition.

### Read first

- **Writing an edited settings file to a camera is at your own risk.** A file edited by hand once put a camera into
  a restart loop in Movie mode, which ended when Initialize was run on the camera; Initialize also clears the network
  setup and the memories. The editor and the camera may refuse or change values. Always keep the camera's own backup,
  a settings file it saved itself, to load back: on the card and on your computer.
- This is an independent project, not affiliated with or endorsed by Sony. Sony and the camera names are used only
  to say what the files are.
- The editor's packages (the macOS app and disk image, the Linux tarball) do not include the camera helper, which
  reading and writing a camera directly needs: the editor works on the files a camera saves to its card. The helper is
  built from Sony's Camera Remote SDK on your own computer under Sony's terms (the README, "The camera helper").
- Windows: no package in this release; the editor builds from source there (the README, "Use the editor").

### The project

- The repository's public history starts afresh on 2026-11-09, because its first published commits carried settings
  values of the maintainer's own camera
  ([decision 16](docs/decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)); the packages were
  rebuilt from the corrected tree.
- A [security policy](SECURITY.md), a [code of conduct](CODE_OF_CONDUCT.md) and issue templates for bug reports and
  camera requests. The docs now say the camera must be set to English before mapping; other menu languages are not
  supported yet.
- The a1 II's sample settings file, which Explore a sample opens, is now made from the file the camera wrote right
  after Initialize, its personal text removed (the lens list cleared, the save time set to 1 January 2026). Initialize
  does not reset every record, so it is not a list of factory values.
- The a1 II's menu tree names each carousel's options by their own names ("Spot", "Custom", "Tracking", "Continuous
  Shooting"), no longer by the sub-choice each one was left on when the menus were walked, which was the camera's own
  setting; a test reads every camera's menu tree for such a label.

### The editor

- Outside Expert mode a setting offers the values its proofs on the camera show, no longer the lists of values camera
  files had held, which held owners' own settings. A value not yet checked is listed only with "Offer values not
  checked on the camera yet", its hover warning that the camera may refuse a file holding it; one the camera's menus
  never offer is not listed even then (the detail panel says why), and each Fn Menu place, Custom Key and dial offers
  the functions of its own list.
- A setting no proof on the camera can reach says why in a few words ("Not a menu setting: the camera keeps it", "Not
  proved (needs equipment)" and the like) instead of "Not proved on the camera yet", with the reason in full on hover,
  in the window and on the web page.
- A setting's proof names the run and the day of its latest proof ("Proved 2026-11-09 (kit2_afreg2)" on hover), where
  it was made outside the main mapping run, instead of that run's first day.
- The a1 II's definition offers more values checked on the camera, among them Exposure Comp. and Flash Comp. at every
  step, a Recall Custom hold's Exposure Comp., Shutter Speed and ISO, Movie's own colour temperature, HEIF in File
  Format (Slot 1), the Registered AF area records and each Playback Filter Condition box unticked; a memory-set record
  wrongly named AF Illuminator is unnamed now.
- A Picture Profile's page as on the camera, in the window and on the web page: PP1 to PP11 are marked "›" on the
  Picture Profile row, with a link to the chosen profile's page, laid out with the camera's headings and the stills
  and movie copies side by side, which the search and every jump to a profile's setting open.
- The detail panel and the web page show the mapping team's words (a setting's note, its records, what the camera
  writes with it) and the record number, proof and stored-number switches in Expert mode only; refused options go on
  one line per reason ("Not offered while …: A, B, C"), and a value with no name, a damaged file and the write check
  are said in plain words.
- The web page's Compare offers Show raw values in Expert mode only, as the window does, and the page's record
  number, proof and stored-number switches draw nothing while Expert mode is off.
- Compare: a value of file A can be changed in place, from the same choice Edit offers (the values checked on the
  camera, refused ones marked, nested options, numbers and text), with linked records, edit marks, undo and the write
  check as from Edit; file B stays read-only. The row stays put while the filters would hide it.
- Settings whose camera row is in another tab (the Custom Key cells, the white balance fine-tunes, Exposure Ctrl
  Type, the time-code presets) sit under that row in "As on the camera"; the Registered AF area settings share Focus
  Area's nested options.
- A camera whose clock is off no longer makes a read look doubtful: the report says the gap ("differ by 12 hours")
  as a caution and the read counts, since the helper has just made the download.
- Options nested as on the camera: a setting whose option opens a choice of its own (Focus Area's Spot and its
  sizes, Tracking and its areas) shows the main options and, under the chosen one, its choices; the flat label
  ("Spot: M") stays everywhere else. The camera's structure comes from the proofs, through the definition.
- "As on the camera" now places every setting the proofs can place: the sub-screens the definition kept as groups of
  their own (Recall Custom hold, Fn Menu, Dial/Wheel, My Dial, Recognition Target, Rating Set, DISP) sit under their
  real rows, and settings proved in Movie, S&Q or Time-lapse mode sit on those modes' rows under a heading naming the
  mode. "Flat list" is unchanged.
- My Menu: every place takes any of the camera's menu items, from a list with a filter, not only items a setting
  carries; the raw slot settings under Setup are Expert-only now. A "Not in the menus" entry after the tabs gathers the
  settings the camera's menus do not hold (the SDK-only records, the memory mirrors), in the camera layout.
- A help file is used only for the camera whose model and firmware it names, whatever it is called; Settings says
  when one was refused and why. Another camera's definition never shows the a1 II's help. Option help comes value by
  value, and each option's hover says whose words it shows.
- Header byte 0x38 of a settings file is the camera's video system (NTSC or PAL), not the firmware's last digit: a
  file saved on PAL opens with its firmware's definition, the badge says PAL or NTSC, and Compare notes when two files
  differ in it; a write is refused when the file and the camera differ (an untried case; a switch in the code allows
  it).
- The menu is laid out as on the camera, in the window and on the web page: each group's rows in the camera's order, a
  row's sub-rows and settings under it, and an option's own choice under it in the detail; "As on the camera / Flat
  list" switches back to the plain list, and settings not yet placed come last.
- My Menu has its own entry under Main, as on the camera: each page with its items in order, the value of the
  setting each one opens, a click to open it, Remove, and Move up or down. Every setting can now be reached from the
  side bar: the settings of a tab the definition does not list are under Other.
- After the camera confirms a write, settings that were read from the camera no longer count as unsaved edits: the
  file on screen starts from what the camera holds, and ↩ Put the camera back undoes the write. A file from disk keeps
  its edits and says "on the camera, not saved to" the file.
- Compare: a setting's name opens it in Edit, in the memory it was compared in, and ← Back to Compare returns to its
  row.
- A value shown as "7 (no name yet)" says why where it is shown: that value was not chosen on the camera when the
  setting was mapped. A setting with no named values at all shows the plain number.
- Camera times are the ones this computer has seen: a read says how long the last reads took over that link, and the
  check after a write starts when the camera is usually back (about 30 seconds on the a1 II), not after a fixed minute.
- Found cameras: "Use this one" is the first column, so it is in view at any window width.
- Help text for 1,548 of the a1 II's settings, in Camset's own words, comes with its definition; the hover says
  whether a help text is Camset's or the camera's own (a help file on your computer).
- Camera definitions are files, one per model and firmware, never built into the program: the built-in ones sit beside
  it, yours in `definitions/` in the editor's own folder (Settings > Camera support & web page > Add definition…),
  replacing a built-in one of the same model and firmware. A camera mapped with the kit works the same day with no new
  editor; a definition made for a newer editor is refused, saying so.
- A file is read with the definition of the model and firmware its header names, another firmware of the model with
  the nearest one, said beside the file's name; a file whose checksums do not hold is never edited, and in Expert mode
  Open with… reads a file with any definition, a save or a write saying so.
- The program holds no camera facts: the memory copies, the memories' names and columns, the link's words and
  timing, the Main and exposure pages' wording and the sample come from the definition.
- Opening a file on Linux no longer freezes the window: the file dialogs run beside it, and the window carries an
  application id that its menu entry matches.
- Reopening the last files at start is off until you turn it on.
- A camera read or write that fails says why in plain words: no user name and password saved, or refused; a USB
  cable still in; no answer at the address; no camera on USB; no USB permission on Linux; the camera held by another
  program. The camera helper's own messages show only in Expert mode.
- Known cameras: each camera you pick or connect to keeps a name of your own, its serial number, its MAC address and
  its own user name and password, so the editor names it wherever it names the camera and the same body is
  recognised over USB and over the network.
- Camera search: a camera that answers at the address you entered, though the search did not list it, says so, with
  its MAC address from this computer's network table; a USB camera shows its serial number; the name box keeps its
  width and the tables scroll sideways.
- Connect to the camera and Settings show the same camera cards, in the same order.
- A switch in Settings shows whether each setting was proved on the camera; it is off until you turn it on.
- Compare: columns are named by file and section (A · Live, A · Memory 1, B · Live), small arrows between two columns copy a
  value into file A, and a right-click copies only into the shown columns of file A.
- Unsaved edits are never thrown away without a question: opening a file, a kept copy or the sample, reading the
  camera, closing the file and closing the window ask first (Save As…, Discard edits or Cancel). After Save As the
  window works on the saved file, its edits counted as saved.
- Writing to the camera: only a file the editor may edit, of the definition's model, never the sample, and only the
  file the Write window checked, once the camera's own copy read just before checks out; a write the camera did not
  confirm says it may have been written and offers Put the camera back. The Write window says in plain sight what a
  write replaces and to save the camera's own copy first.
- Copies between columns, Merge, Whole sets, Recall and Register leave alone a setting a file holds in another shape
  than it was mapped in, and say how many; Recall, Register and Whole sets copy the whole memory whatever the search.
- The light theme is readable everywhere; your edits are orange with a pencil, a difference a pale amber fill.
- A File menu (Open…, Recent, Save As…, Export CSV…, Backups…, Edit history…, Close file), keyboard shortcuts listed
  in Settings, Backups that compare a copy with the open file, a two-line status line with the last messages, and
  plain words for photographers throughout; record numbers and file paths only in Expert mode.
- Open starts in a camera card's settings folder; Save As offers the next free `CAMSETnn.DAT` in the opened file's
  folder.
- Without the camera link program, the welcome page and the top bar lead with files, and Connect to the camera says
  how to set the program up. A file from another camera model says so, its values greyed.
- The camera's login goes only to a camera this computer trusts: its fingerprint is kept at the first connection
  (`~/.config/camset/known_cameras.json`), and a changed one gets no login. The editor's own files (preferences,
  kept copies, `probe.log`) are readable by this user only, and the camera link program is looked for only where it
  is put.
- Edits not saved survive a crash: a couple of seconds after each edit the editor keeps a copy in its `recovery/`
  folder, and the next start after a crash, a power cut or a forced quit offers to open them or discard them. An
  error that stops the editor leaves a short `crash.log` without your folders or name.
- A damaged or hand-made settings file never stops the editor: random bytes, a file cut short or with a damaged
  header, record count or record size is refused or opened view-only, and a file of unusual sections or record shapes
  opens with every page of the window and the web page drawn.
- The foot of Settings names the version (and, for a build from the repository, its commit), with Changes, this list
  built into the program, and Third-party licences, which opens the licences page the packages carry; the Linux
  install copies that page beside the program.
- Every pull request and every push to main builds and tests the editor on Linux, macOS and Windows, with clippy's
  warnings as errors (`.github/workflows/editor-ci.yml`).
- Screen readers hear a name for every control: the search box, the address and login fields, number and list
  boxes, the Main page's tiles with their values, the welcome cards, the copy arrows and the symbol buttons.
- A camera that refuses to give its settings or to take a file, an address that is not one, a file to send that is
  not a camera's settings file, and a connection that fails for no reason the camera link can name each get their
  own plain sentence.
- Quiet text is readable in both themes: tile captions, the welcome cards, "Works with", the Exposure page's notes,
  the hints under settings and the foot of Settings are at least 4.5:1 on the window, the panels and the tiles. On the
  light theme an unticked checkbox or radio button, a text field and a button have an outline.
- The Exposure page's columns share the window's width, their words wrapped, so the last memory is never cut off; a
  long value in a menu's list ("S-Gamut3.Cine/S-Log3") is cut short at its column, in full on hover.
- A setting's note says what it is and how it behaves; what proves it (the mapping runs and the days it was seen on
  the camera) shows under it in Expert mode only.
- Folders are named one way, as you would type them, with your home folder as `~`, in Settings and Backups as on
  the web page.
- Settings > Third-party licences says "not in a development build" when the build carries no licences page,
  instead of being greyed out without a word.
- As on the camera, a choice that opens beside an option with Right (Drive Mode's continuous speed, White Balance's
  fine-tune, a Creative Look's parameters) is no longer a row of its own: the row's detail shows the chosen option's
  choices, each with its control, and the search, F3, All edits and Compare open the row with that choice marked, on
  the web page too. A number shown other than as stored is typed so too ("75 %" for 7500).

### The web page

- The page speaks to photographers: mapping notes, records, the record number, proof badge, stored number and count of
  known settings show in Expert mode only, and a row's details start with its help, say "Kept in the memories too" and
  "Not on this camera's menu" in plain words, and group refused options by reason ("Not offered while …").
- The page's Settings name the editor's version, as the window's do.
- The page's Write reads the camera first, as the window's does: "Reading the camera, to list what this write
  changes…", then what the write changes against the camera now, and only then Write to camera, which keeps that
  read as the copy from just before; a read that fails ends the write with the Camera link report.
- The page names the definition the open file is read with, and how it was picked.
- The editor's small web page, off until turned on, now does what the window does from a browser on a tablet, a phone
  or another computer: the same pages, a setting's details, Connect to the camera, Settings, Backups, the edit
  history, the camera report, and Compare with file B, copies and merges.
- Files go up and come down through the browser: Open… and Compare's files are uploaded, and Download file,
  Export CSV… and Describe for support… download.
- The camera's user name and password are entered in the desktop app only, and never cross the network from the
  page.
- The access code is new each time the page is turned on, a session lasts 12 hours unused, and Sign out ends it; the
  page answers only its own requests and counts wrong codes per device. It cannot turn on Expert mode, raw edits or
  Edit anyway, change the camera link's address, or write a file the Write window did not check, and its polled state
  names no folder, address or serial number.
- The page's light theme is readable in daylight, its toolbar fits one row on a phone, its windows are real dialogs
  with fingertip-sized targets, an edit is drawn in place, and a refused change puts the real value back.
- The page's Memories shades a value that differs from the live settings and keeps orange with a pencil for your
  edits, as the window does. The welcome page, the theme's "Follow the system" and the foot of Settings use the
  window's words, and the status line says the page is on without its address, which the desktop app's Settings
  show.

### The proof viewer

- A value proved more than once shows its newest proof first, the earlier ones folded under it as before (the proofs file keeps every proof; the page never drops one).
- Sub-rows the menu tree never read are shown from the proofs' own paths, as the definition has them, so the viewer
  and the editor place every setting on the same row.
- No page without the camera's own runs: the viewer refuses to build for a camera the kit has not run on, and setup
  says so; the page is for whoever ran the kit on their camera, never part of a submission.
- A proof's pictures in reading order: the after-OK picture first, each captioned so the orange bar (the cursor) and
  the round dot (the value held) are explained.
- The menus of the camera's other shooting modes: a group's Movie-only rows follow its Stills rows under "In Movie
  mode", with the records proved there.
- Help where you look: a setting's help on hover in the rows and the file layout's inspector, each option's help under
  it, and the camera's guide for rows with no setting of their own. With the camera's runs on the computer each help
  text links the guide screen it was read from, with both readings where the two readers differ, and each text says
  whose words it is.
- A My Menu tab: the shown file's pages, each item linked to the setting it opens, and every item name by its code
  with the camera screen that proved it where one was kept. A Main entry: each mode's tiles with the value each
  shows, the records it reads, and the camera's own Main page beside them.
- Settings proved through an option of their row (Drive Mode's speeds, White Balance's and Focus Area's own choices)
  hang on that row instead of "More settings".
- Every clone builds it (in the camera's folder, `runs/<model>_fw<fw>/_viewer/`), `--open` opens it, and `--pack`
  puts the page and its pictures in one folder to copy to another computer.
- It is one definition's page (`--definition`, else the active camera's, else the ILCE-1M2's), and its file layout
  view reads a download through that definition's container block; the Kaitai reader is no longer built in.
- A value's pictures say which two prove it: the option lit before OK, and the row after OK.
- The chosen range on the file map is outlined in bright cyan, and choosing a record's own fields moves the map to
  their memory set.
- Every row of the file layout's structure (the file, a section, a block, a record, its fields and elements) outlines
  its bytes on the map and picks them out in the hex, the record around them shaded faintly; the inspector names a
  block and lists its records.

### The mapping kit

- `kit/provers/afreg_run.py` proves AF Area Registration: each Focus Area chosen in the menu, Fn held on the shooting
  screen, the downloads around the hold diffed; a record a hold copies from the camera's own setting is named a side
  effect, changed or not, and never credited to the area. `kit/provers/filter_run.py --untick` proves each Playback
  Filter Condition box's value when unticked.
- `kit/drive.py` takes `enter!:REGEX`, an Enter the operator vouches for on a screen that lights nothing the kit can
  read, with the camera owner's word only; it is refused on a menu, the Main tiles and the shooting screen, on a
  screen whose text reads nothing or names a never-open row, and wherever a plain Enter is.
- The pass-2 report reads the camera's other proof runs beside the main one, never crediting a record a proof names as
  a side effect (`--alone` reports the main run by itself), and `kit/schema_update.py` gives each record proved there
  the run and day of its latest proof, or why no proof can reach it where a hand table says so.
- `kit/tools/menu_tree.py` names a carousel's options by their own names, never by the sub-choice the walk read them
  on; `--carousel-names` does so for an existing tree and changes nothing else.
- The rows the pass-2 report listed as failed are finished (2026-11-07): `kit/provers/mode_switch.py` puts the camera
  in another shooting mode through the menu, never a memory recall, for the runs that need that mode's menu
  (`--restore` puts the stills file back), and a put-back that leaves records differing is no failure where the prover
  can say why.
- Picker functions that open a setup screen of their own (a Recall Custom hold's registration, Rating Set, Recog.
  Target Select and others) are proved like any other since 2026-11-07, credited with the key's record alone. S&Q
  Shoot Mode is proved with the owner's switch on S&Q, `kit/provers/filter_run.py` proves Playback Filter Condition's
  choosers, and `prove_run.py --list` says how many of a cell's options are still to prove.
- `kit/provers/mymenu_run.py` proves My Menu's item codes on the camera by Add Item for every item the picker offers,
  the start file put back between fills, each name settled against the camera's own row names and twins numbered by
  their place in the picker (`--relabel` renames a run's proofs by that rule without the camera); `--redo` proves a
  named row's options again.
- My Menu's items are proved on the camera one by one (`kit/provers/mymenu_run.py`: Add Item for every item the
  picker offers); `kit/schema_update.py` names each proved code alike in all 42 My Menu slots, proving only the slot
  that took it.
- A setting proved on the page an option of a row opens ("Picture Profile > PP2 > Black Gamma > Level") gets its place
  on that page (`row`, `row_at`, `under_option`), each option's page taking the shape of the one the walk opened: the
  a1 II's Picture Profile parameters on the profiles its menu offers now have a place, and PP7-PP9, which the menu
  never offers, stay unplaced.
- The pass-2 report credits an option that changed nothing with the start value of its own base file, so a put-back
  made in a session of its own no longer shows as a conflict, and the prover takes the Custom Key screen's one-time
  notice and a frozen OSD picture in its stride;
  `kit/provers/customshoot_values.py --prepare "Shoot Mode=Manual Exposure"` first puts a Recall Custom hold into a
  mode whose items the camera offers.
- `kit/tools/replay_proofs.py` diffs every proof of a run again with today's parser and lists each one whose changes
  now differ, and any missing file; the kit's tests check the shipped definition against itself and the proofs, and CI
  validates the accepted file against its schema.
- `kit/schema_update.py --write` refuses, listing each, while pass 2's report holds a conflict, a new record it does
  not add, a record not one to one (marked `disputed`), a name dispute or a carried-over value that the camera's
  `data/<model>_fw<fw>/accepted_<model>_fw<fw>.json` does not accept with why (`--force` writes anyway, loudly). Each
  proved value's name says what backs it (`proved.names`), and a number the camera shows scaled gets `shown_as` ("75%"
  stored 7500).
- The pass-2 report names a value by the map's label unless the vision model backs the bar's OCR instead, so OCR no
  longer wins alone; the new `report.md` lists name disputes, values a record carried over from the option before (no
  longer credited) and a picker's twins, and `kit/tools/reread_proofs.py` asks the vision model about saved frames
  with no reading of their own, with no camera.
- `kit/prove_run.py --first "ROW / OPTION=VALUE"` proves a carousel axis from another value, so the one it held is
  proved too, and a list that opens with a single option is proved by its display (XAVC HS 8K's frame rate under PAL).
  The prover presses MENU again after the lock that follows a download, and Right when the menu reopens in the group
  column.
- `kit/prove_run.py --every` proves a number scale at every value instead of its lowest, middle and highest, and
  `--list` prints what a run would prove, with no camera. A number field the first OCR engine leaves unread is read by
  the second engine, else enlarged, before the row can fail on it.
- Nothing is pressed while the menu is still sliding: the kit waits for it to come to rest before a screen counts or
  the scan and the prover step into the rows (a Right sent to a moving menu had changed Drive Mode, 2026-11-06), and
  the prover cancels with MENU if that Right opens a row all the same.
- The page scan downloads the settings first and puts the start file back on when a press changed anything, waits
  out "Saving to the connected device..." before its first MENU, and cancels with MENU whatever it stopped on before
  disconnecting. `kit/page_model.py --vlm --reader NAME` asks a configured reader by name when the usual one is away.
- The helper says "no answer" while a camera restarts, not "camera not trusted"; the definition writer is repeatable
  (notes added once, a rerun writing the same file, notes never starting with a space); placement reaches
  rows in other tabs (`row_tab`) and shares an option tree between settings with identical values.
- The web page's script has tests of its own (`kit/tests/test_page_script.py`, under node, no npm package).
- Each setting's place now covers rows in other groups (`row_group`) and other modes (`row_mode`); the menu tree
  holds the other modes' menus (`modes`), which `kit/tools/menu_tree.py --mode` writes from that mode's scan and
  crawl. The camera's option trees (`option_tree`) are read from the proofs by `kit/schema_update.py --option-trees`.
- The a1 II's frame rates under PAL are named (50p, 25p, 100p; S&Q's 100fps to 3fps; Time-lapse's two rates), proved
  on the camera with `kit/pass3_run.py --only "PAL …"` and `kit/provers/boxes_run.py`. A row's starting option is
  proved from another start (`"first"` in pass 3's table, `--first BOX=VALUE` in the two-box prover), and
  `kit/pass1_map.py --own` writes one walk's map without touching pass 1's.
- The container block names the video-system byte (`video_system`) and the firmware is its two bytes
  (`major_minor`); NTSC and PAL downloads of one firmware are one camera to the kit.
- The project's own help text for the a1 II (1,548 settings) ships in its definition; the private file of the
  camera's own guide text is used only when its model and firmware match.
- A definition says where each setting sits on the camera (`row`, `row_at`, `under_option`), worked out from the menu
  tree and the proofs by the placement the proof viewer uses; `kit/schema_update.py --from-data --write` writes it.
- `link_timing.restart_s` is how long after a write the camera is usually back: the editor's first read-back starts
  then. The a1 II's is 30, measured.
- `python3 kit/setup.py` sets the kit up in one command once Sony's SDK zip is in `kit/sdk/`: it unpacks the SDK,
  checks the tools, makes the Python environment, builds the camera link and the camera helper, and runs the tests.
- One folder of runs per camera, `runs/<model>_fw<fw>/`, as `data/` has: `--camera` on any command,
  `CAMSET_CAMERA`, or `"camera"` and `"cameras"` in `private/config.json` name the camera the kit works on, and
  `kit/tools/migrate_runs.py` moves runs from before 2026-11-05 under their camera.
- The kit writes one definition per camera, `editor/definitions/<model>_fw<fw>.json`: `kit/schema_update.py --write`
  writes the active camera's, a new camera's started from its `data/` folder and its proofs, with its format, its
  camera section and the Expert marks; `kit/tools/build_docs.py --definitions` brings every definition's parts from
  `data/` up to date without runs.
- The kit reads every file through its camera's container block (the camera file's `file`), the same vocabulary as
  the editor's; `kit/tools/identify.py` says which block reads a file and prints a draft for one none reads.
- A commit never rewrites a definition: the pre-commit hook leaves them as they are, and checks every definition and
  every data folder against its JSON Schema, as CI does.
- A note's evidence (the runs and the days that prove it) is kept apart from what the note says, in `note_evidence`,
  on every run and by `--from-data`; the definitions' JSON Schema names it.
- Uploads are checked by provenance: every download's SHA-256 goes into the camera's `runs/<model>_fw<fw>/downloads.jsonl`, and `Link.upload`
  and `upload_check.py` send only a file whose bytes are a download's (`upload_check.py --adopt` takes in older
  downloads a run logged). Pass 3's switching by file is retired.
- The guards fail closed: Enter is refused when the lit row cannot be read or reads Initialize, the never-open list
  is longer, C4 goes out only on a menu, option or panel screen (never on the shooting screen, in Playback or with a
  picture displayed: the screen is the guard, with no per-camera consent), and Ctrl-C stops a run cleanly.
- One body's proofs per definition: `pass2_report.py` and `schema_update.py` refuse a run from another body or
  firmware, and only finished attempts count.
- Paths with spaces and Windows line ends reach the camera link intact; the commit hooks run on Windows; the kit
  reads and writes UTF-8 everywhere. The kit no longer falls back to the example config's addresses.
- The publish guard (`check_public.py`) refuses MAC and private network addresses, serial numbers, e-mail addresses
  and home folders in every tracked file, and runs on every pull request with the kit's tests and the camera
  helpers' own test (`.github/workflows/kit-ci.yml`). The kit's packages are pinned, and the Linux udev rule gives
  the camera to the user at the seat.
- The definition speaks to photographers outside Expert mode: settings with a mapping word in their name, and the
  fields of the memories' live copy, are Expert-only, "Other (from SDK)" is "Other settings", three settings on camera
  rows have plain names, a refused option's reason no longer ends with the dialog's "• OK", and a test fails when
  anything a photographer reads holds a word of the mapping.

### The docs

- The README shows the editor's Main page as it is now, and the web page on a phone.
- The README and the editor's guide say how a settings file goes from the card to the editor and back, what to do if
  a camera restarts over and over, that no release has been made yet, and how macOS's Open Anyway works for an app
  that is not notarized.
- The quick start installs before it checks the body, shows `CAMSET_USB=1` for USB, and lists the software needed;
  the example config watches the camera's own screen (`"eyes": "osd"`).
- The vision-language model the kit needs is named, with a model on your own computer first.
- Which data files a mapping delivers, and how each is made, are in one table (Data files and their schemas).
- A mapped camera's definition is part of what a mapping delivers and of the pull request: AGENTS.md, the README,
  the playbook and the quick start no longer say a second camera's definition cannot sit beside the a1 II's. The
  editor's guide explains definitions, and the data files page the container block.
