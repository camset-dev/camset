# Changelog

What changed for the people who use Camset, newest first. The version is `editor/Cargo.toml`'s; a release is a tag
on GitHub with the editor's packages attached ([RELEASING](docs/RELEASING.md)).

## Unreleased

### Read first

- **If you map a camera other than the a1 II and made a sample** (`editor/definitions/<model>_fw<fw>.DAT`): on any
  body but the a1 II the kit zeroed in it only the records whose value reads as text (its list of the a1 II's own
  personal records applied to the ILCE-1M2 alone), and the text check misses a name packed against other bytes, so a
  registered lens list, with each lens's serial number, and other records of the owner's own could be left in. Add
  your camera's `personal_records` to its camera file and make the sample again (docs/UPDATING.md, "Your camera
  file: what the kit reads in it now").

### The project

- The docs site has a code signing policy (Reference > Code signing policy), linked from the README's and the docs
  home page's download parts: what will be signed once SignPath Foundation accepts the project's application for free
  code signing (the editor's Windows program and its installer, built from a release tag by the release workflow on
  GitHub's runners), who approves it, and that the editor sends nothing over a network unless asked. Nothing is signed
  yet.
- The release workflow builds only a tag on a commit of `main`: a tag on any other commit, or one pushed before `main`
  was, stops it before anything is built, with a message that says what to do (push `main`, then re-run the job). Its
  builds and tests, and the packaging scripts', take the crates `editor/Cargo.lock` names (`--locked`), or stop.
- The security policy, the code of conduct and the new-issue page are written for the public repository: a security
  problem goes through the repository's Security tab (Report a vulnerability), or, where that is not offered, a Bug
  report titled "Security contact" with no details, and the new-issue page points there and to the documentation.

### The editor

- On Windows, Settings > About names the version of Windows as it does macOS's and Linux's, in the window, on the web
  page and in Copy details: "Windows 11 build 26100 (x86_64)" (or Windows 10, or Windows Server), where it said
  "Windows (x86_64)". Windows itself gives the numbers, with no console window and nothing more to install.
- An installer for Windows, beside the zip: `camset-editor-<version>-windows-x64-setup.exe` installs the editor for
  you alone, with no administrator rights, puts it in the Start menu (and on the desktop, if you tick that) and in
  Windows' installed apps, where you uninstall it; a newer installer updates it in place. Updating or uninstalling
  never touches your own files: your preferences, the definitions you added and the copies the editor keeps stay in
  the editor's own folder (`%APPDATA%\camset_editor` as a rule). Take the installer unless you would rather install
  nothing; the zip holds the same program and runs from wherever you unpack it. Neither is signed yet, so Windows
  SmartScreen warns the first time ("Windows protected your PC": More info, then Run anyway), and Smart App Control,
  where it is on, blocks them with no Run anyway, until code signing is arranged. The installer's Properties > Details
  name Camset Editor and the program's version, as the program's do.

### The definition viewer

- A file the definition viewer refuses shows, under the message that refuses it, what the file starts with: its size
  and its first 256 bytes as a classic hex dump (offset, hex, text), to paste into a report of the problem. It says
  that the file was read in the browser and never left it, and to check before pasting it anywhere public that it
  holds nothing of yours; a file that is read shows none.

### The mapping kit

- A copy of `kit/config.example.json` names nothing to contact until it is filled in: its camera address is empty and
  it lists no reader. Its first reader was a server at an example address on the local network, to which a copy left
  as it was sent pictures of the camera's screen; the readers it shows are all under `readers_examples` now.
- A run that asks a reader (the crawl, the proofs, the walks, the provers, `drive.py`, `mode_switch.py --to` and
  `--set`, `card_actions.py`) with no reader listed in `private/config.json`, or with no `private/config.json`, stops
  before it opens the link, saying what to put there: nothing is pressed. With an empty list such a run used to go on
  with OCR alone, and with no config at all (over USB) it stopped at its first question to a reader, the menus left
  open. A run that asks no reader (the page scan, the self-test) and a restore run as before; `prove_run.py --start`
  with nothing left to prove puts its start file back with no reader. Inside a run, a reader that cannot be asked is
  taken by each question to it as no answer, and the run goes on with OCR alone as before; only one that reaches a
  session's own body ends the run, with the menus closed and the start file put back. `pass1_labels.py` and
  `tiebreak.py` say in a sentence when no reader fits.
- When the proof viewer is not built (the kit has never run on the camera here, or it works on another camera), its
  message, and `kit/setup.py`'s line for it, also say that the definition viewer needs no runs:
  `kit/tools/proof_viewer.py --public --out site/viewer` builds it, and it is online at
  <https://camset-dev.github.io/camset/viewer/>.
- Creative Look proofs on a Mac: since macOS 27.2, Apple's text recognition often misses one of the numbers at the
  ends of a look parameter's scale (the "+9" at the top of -9..+9, the "0" at the bottom of 0..9), and the proof
  stopped with the scale "not readable". The kit now counts the scale's tick marks. Once the run has read both ends
  of a parameter's scale beside the same number of ticks, that parameter's -9..+9 or 0..9 scale with an end missing
  is read from its ticks, and its proofs say so (`"range_from": "ticks"`, else `"ends"`). The proof still stops, as
  before, on a 1..5 scale (Sharpness Range) with an end missing, since five ticks fit several scales, on a parameter
  whose ends the run has not yet read both of, and with RapidOCR (Windows and Linux), which reads neither end of
  0..9 or 1..5. Ends that do not match the ticks beside them (a tick read as a plus would make 1..5 read as -5..+5)
  now stop the proof instead of being taken as read.
- A camera's records that hold an owner's own data, every record that changes when the owner's own things change,
  text or not, are named in its own camera file, `personal_records` (records zeroed whole, records set back to the
  camera's default, records of numbers never read as text, and the camera's own words kept; each record as the
  record keys write it, "0x167c"), no longer only in the kit and only for the a1 II. `kit/tools/make_sample.py`
  scrubs a sample by them and refuses, before writing anything, a camera file without them, a record listed twice, a
  record the file does not hold and a default of another length than its record, saying what to add or correct;
  `kit/tools/check_public.py` checks every published sample (a file of its definition's own model and firmware) by
  its camera file's list in the same way, names what it finds by the record or a text by its length, never by a
  value, and refuses for the maintainer's eye a pull request that weakens a camera's list against the range's base:
  a record taken out, a default's bytes changed, a record moved to or newly set to a default, or a new camera file of
  a model already mapped that lists less. Both say when a list names no record to zero or set back. The a1 II's
  camera file carries what the kit held before, and its published sample comes out byte for byte the same
  (docs/DATA_CONTRACTS.md, "Records that hold an owner's own data").
- `kit/provers/customshoot_values.py --counted` names a hold's Focus Area rows in the Focus Area order of the camera
  the kit works on, read from its own definition when the run starts (`--order-from` names the record, and is refused
  without `--counted`), no longer the a1 II's order read when the prover was imported; a camera without one stops
  before the camera is touched, saying what to prove first.
- `kit/tools/help_extras.py` reads a drive's shooting mode by the camera file's `live_mode`, no longer by the a1 II's
  record, and stops plainly where the camera file names none or its start file holds no such record.
- Two notes of the a1 II's definition no longer publish what was particular to its owner's camera on the day:
  the lens-name record (0x167c) says a teleconverter's name is added after the lens's without naming the one used,
  and the registration stamp (0x0c09) no longer gives the number seen as a fact. They reach the definition the next
  time the maintainer writes it with `kit/schema_update.py --write`.
- The a1 II's hand tables (the names, notes and value tables its mapping found by hand, the values its menus never
  offer, its copies, why a record cannot be proved) were Python code in the kit; they are its data file now,
  `data/ILCE-1M2_fw4.00/hand_tables_ILCE-1M2_fw4.00.json`, edited by hand, with a JSON Schema
  (`schemas/hand-tables.schema.json`) that the commit hooks and CI check and that refuses a hand proof's evidence in an
  entry, and `kit/tools/check_public.py` refuses a run or a day in it as in any file of a camera's data folder.
  `kit/writer/hand_tables.py` reads a camera's file, refusing in plain words one for another camera, a table it does
  not know or a key given twice, and puts the mapper's private hand evidence back as before: the definition the kit
  writes is the same. A camera without the file has every table empty, and any camera but the a1 II still takes the
  plain pass, which reads none of them yet: nothing to do for whoever maps another body (docs/DATA_CONTRACTS.md, "The
  hand tables file").

### The docs

- The docs site draws its text in the system's own fonts. It loaded Inter and JetBrains Mono from Google Fonts on
  every page, so Google saw each visitor; a test keeps it so. The repository box in its header still asks GitHub's
  API for the star count, from the visitor's browser: GitHub hosts the site anyway.
- The editor's guide says plainly that the camera login file holds the passwords in plain text, protected only by the
  file's permissions, and names the two things there for developers: the camera address taken from a clone's
  `private/config.json` at start, and `CAMSET_NETTEST=1`.

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

- The editor's version is easy to find: in the window's title and at the right end of the status bar. Settings has an
  About tab, the last, which the status bar's version opens on every system, so it is found on Windows and Linux too,
  which have no menu bar. It gives the version and build, the system the editor runs on, the cameras it works with by
  model and firmware (one you added says so), whether the camera link program is there, the licence and copyright
  line, links to the project page, the documentation and Report a problem, Changes, the third-party licences and Copy
  details, which copies those lines for a message about a problem, with no file, folder, name or address of yours. The
  macOS app's own About panel, in its application menu, shows its version and copyright line.
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

- A page anyone can open to look inside a settings file, with nothing to install: the definition viewer, on the docs
  site at <https://camset-dev.github.io/camset/viewer/>. Open your settings file… reads a `CAMSET*.DAT` in the
  browser, where it stays, finds its camera among every definition Camset has, as the editor does, and shows each
  setting by name in the camera's menu, the same tabs, groups and rows as the editor's (a setting's choices for an
  option, which the editor shows beside the option, under its row; an Expert switch shows every setting the
  definition holds), with whether a proof checked each value, and the file's layout byte by byte. Until a file is
  open it shows the camera's sample, not your camera. A file of another firmware is read with the nearest one's
  definition, and says so; one of a camera with no definition yet, laid out like the files of a camera the viewer
  knows, shows its structure only, with no names, and how a camera gets mapped; any other file is refused, naming the
  cameras it reads. `kit/tools/proof_viewer.py --public` builds it from the public definitions alone (the docs site's
  build does), and `--public --single --out site/camset-viewer.html` makes it one file that opens from disk with no
  network. The proof viewer, with the camera's own screens, stays with whoever mapped the camera.
- Each release carries the definition viewer as one file, `camset-viewer.html`, to download and open with no
  internet; the latest is always at <https://github.com/camset-dev/camset/releases/latest/download/camset-viewer.html>.
- The proof viewer's Open settings file… also says when a file is of another firmware than its definition, not only
  of another model; its file buttons answer Enter and Space, and are 44 pixels tall on a touch screen; a tab's count
  says on hover what it counts; links read on the light theme; a file's header text is read as UTF-8, as the editor
  reads it; a file framed with no section of settings is refused as damaged.

### The mapping kit

- `kit/setup.py` on Windows, after its first run on a Windows 11 PC: it finds Sony's USB driver once it is installed
  (`pnputil /enum-drivers`, no administrator rights needed) and says OK, where the reminder used to come back
  forever; until then it gives the install as numbered steps, with the driver's whole path, as the administrator
  window opens elsewhere. Without Python's UTF-8 mode it stops at once with the three steps that turn it on (`setx
  PYTHONUTF8 1`, a new terminal, the same command again there) instead of going on to steps that would fail. Every
  step that needs another window or administrator rights comes as numbered steps, and Windows commands are in
  Windows' words (`move`, backslashes, a new terminal after a winget install).
- `kit/setup.py` on every system: it says that it does not wait for a DO and carries on; each long step says roughly
  how long it takes (the tests: about 3 minutes on a fast Mac, not "under a minute") and shows a progress line while
  it runs (the tests' percentage, the build's count, the package pip is fetching), says so when a step takes
  unusually long, and stops cleanly on Ctrl+C. Its last lines, after the table, say that everything is in place or
  list what is left for you, numbered in order, ending "Then run ... again".
- The kit's tests, first run on a Windows 11 PC (10 of 2129 failed there), are fixed for Windows, and the kit's CI
  now runs them on Windows too, for every pull request and push to main. In the kit: `kit/tools/make_sample.py` refuses a result that names a
  download by a path absolute on any system (a POSIX one, a drive, a network share, a leading slash or backslash),
  on every system; a chain file with a Windows path in double quotes stops with the way to write it; a read-only
  results file that Windows will not replace leaves no temporary file. The other failures were the tests' own Unix
  habits, and two things Windows cannot hold (a file name with a newline in git, Unix permission bits) are skipped
  there with the reason (docs/PORTING.md, "Seen on Windows / Linux").
- A kit program started with a Python that cannot run it (macOS's own `python3`, or any Python without the kit's
  packages) no longer ends in a traceback such as "No module named 'numpy'": it says what is wrong and gives the
  command to run instead, with the kit's own Python (`.venv/bin/python`, on Windows `.venv\Scripts\python`), from the
  camset folder, with the same arguments. A program that needs none of the packages runs on the system's Python as
  before.

## 0.2.0 (2026-11-11)

The editor for macOS and Linux, the mapping kit, the docs and the ILCE-1M2 (a1 II) firmware 4.00 definition, in the
new lean form. It replaces 0.1.0, which is withdrawn.

### Read first

- **0.1.0 is withdrawn: use 0.2.0.** Its packages are no longer offered. If you have the 0.1.0 editor, replace it
  with this one.
- **Camera definitions are in a new, lean form (definition format 2).** This editor does not open a definition made
  for 0.1.0, and the 0.1.0 editor does not open the new ones; this editor comes with the new ILCE-1M2 definition. If
  you are mapping a camera with a clone of this repository, follow [Updating your clone](docs/UPDATING.md) before
  going further, and write your definition afresh with the updated kit.
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

- A value the camera keeps in more than one record stays in step: a setting in use and its Stills and Movie copies
  (Picture Profile and its parameters, ISO, White Balance with its fine-tune values and colour temperature, Metering
  Mode, ISO AUTO's limits, Exposure Comp.). Changing a setting changes the copies that held its value when the file
  was opened, and says so first; a copy that held another value is changed alone. A file in which a setting does not
  match the copy for the mode it was saved in is listed before a save or a write, with a fix, whether or not it was
  edited here.
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
  chosen with the finder in use: the pass-2 report proves 7641 options (7631 before; Monitor Brightness's proofs made
  again with `--set` on 2026-11-10 stand in for its older ones, which named no state of its setup row), and 1185 value
  names come from a hand table (1195 before, the review round of 2026-11-10 having moved it from 1194).
- A menu row whose proofs name less of the camera's state than other proofs of the same row that prove every value
  it proves, option by option, is no longer listed beside them: the pass-2 report proves 7616 options of 1315 rows
  (7643 of 1324 before, AF Area Registration's two areas proved again by the kit on 2026-11-11 among them), and no
  proved value or value name changes. A setting table's cells (Image Quality Settings, My Dial Settings) are named by
  their row alone, and the definition keeps no menu row of an older write that today's report does not list.
- The memory sets' records that keep the Custom 1-3 boxes' places (26, the box in use's and each box's copies) are in
  the definition, Expert mode only, and the notes of the focus frame records say where each area keeps its place: a
  Tracking area in its plain area's records.
- The notes of the ILCE-1M2's focus point and Custom box records and of AF Frame Move Amt give the step a press of the
  multi-selector moves a frame, measured under AF Frame Move Amt Standard and Large: Large's step is up to twice
  Standard's, Spot XS's step is smaller than Spot M's across (and, under Large, up and down too), and the Custom 1 box
  has its own, measured by one press each way, Large's twice Standard's both ways.
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
  Profile by its own Reset row, in Stills or Movie (`--in`), after a control on one profile that shows its Reset
  writes the records a settings file saves. Both readers read the panel's title before Reset, the question, the
  completion notice and each panel's title in the verify pass, and a run meant for the sample opens Reset or confirms
  on no reading of one reader alone; only that profile's own question is accepted; after OK the camera's "Complete."
  is expected, or the profile's panel straight back, recorded as such and refused for a sample unless allowed;
  anything else stops the run. A verify pass confirms each panel it enters by its title and checks that entering the
  panels alone moves nothing, and every exit restores the start file (`--peek`, `--profiles`, `--dry-run`). Its
  guards are written for the ILCE-1M2 at firmware 4.00 and fail closed on other screens.
- `kit/tools/make_sample.py --take FAMILY --from RESULT` takes a definition family's reset values into a sample, only
  from finished, verified `pp_reset_run.py` results that reset every offered profile, one in Stills and one in Movie
  (one alone only when it shows its resets write the other mode's copies too); never record ids. A result needs its
  positive control: one parameter of one profile moved, only that profile's element, in the record in use and the
  copy of the run's mode, and written back by that profile's Reset. Each result is checked against its own downloads:
  every list of changed records and the control are recomputed from them, and the downloads must be one session's,
  consecutive in the camera's downloads manifest. `--allow-no-notice` takes a result whose profiles showed no
  completion notice (a body that shows none); `--allow-unchanged` takes the family when no reset download holds any
  of its records unlike its run's start file, the control being then what shows a Reset writes them.
- `kit/provers/scale_run.py --panel-row` needs its panel's setup row among the `--set` rows, so no proof rests on a
  state the camera was found in.
- A definition now says which records are copies of a setting and which mode each copy is for (`copies`, `copy_of`,
  `copy_for`, `camera.live_mode`), and which values belong to one video system (`video_system_values`); every write
  checks them against the camera's downloads. It no longer carries what told how a camera stood when it was proved
  (decision 16): which values no option wrote, the records each proof wrote together, a state "as found", the value
  a blocking setting stood on, nor how many samples were taken from where a list stood (that count is kept in the
  evidence file).
- The record shapes, kept in `private/evidence/`, hold only records no setting covers, and no value.
- `kit/provers/afreg_run.py` puts Drive Mode on Single Shooting before a Tracking area (`--drive-mode`), as the camera
  refuses Continuous AF under some drive modes (it says so in a notice when Focus Mode is set), and stops when a setup
  step is refused, the notice's words kept in the run's own log, never printed.
- `--allow "ROW"` on `kit/prove_run.py` and the scale prover opens one never-open row the owner allowed, never the
  cards, Initialize, Reset Network Set. or credentials; the proof lines carry the words (`allowance`), and the writer
  puts them in each setting's note evidence.
- Where OCR reads no number on a scale, or text that is no number (a letter for a digit), the scale prover asks the
  vision reader, one question a frame; a number only the reader read never decides alone, and a frame neither reads
  stops the row, naming the frame. Whoever reads, the scale counts as open only with an OK in its footer (OCR's, or
  the reader's where OCR drops it on a fresh frame too), every end of the scale is confirmed by one more press, a
  press that seems to change nothing is read again on a fresh frame, whole numbers must step evenly, a scale has two
  values at least, and each choice must open on the value chosen last and land where the count of presses puts it, or
  the row stops. A row's lines count in the report only once the value put back last leaves nothing changed, so a row
  that stops leaves none. The proof lines say which read the value chosen (`read_by`); `kit/pass2_report.py` counts a
  line the reader alone read as one reader, the vision model, and an OCR-read line as two readers only when the vision
  model read the same number. `--panel-row` proves a slider inside a panel (Monitor Brightness, Viewfinder Bright.:
  its setup row must read Manual, then Down), a scale around zero is labelled -2, -1, ±0, +1, +2 whoever read it, and
  `--set "ROW=OPTION"` puts a row on an option before the first row, the proofs naming that state, never one of
  decision 8's rows.
- `kit/pass2_report.py` leaves out a row's proofs made where the camera stood (`stood_out`): a row that says nothing
  of another row whose state lines of the same row name ("Row = option" in their context or their run's `setup`, or
  in words, "Row option", for a row the proofs walk), when for each record and value each of its lines changed a line
  of those, chosen with the same option, changed it alike or left it as its own base download held it, none of them
  writes it otherwise under that option, and the report credits every value and value name it credits to them too (a
  panel's slider proved again with `--panel-row` and its `--set`; a hold proved again with its run's setup; a row
  walked again in pass 3's named states).
- A setting table's cell (`kit/proving/tables.py`, the report) is named by its row as all the row's cells read it:
  `kit/table_walk.py` reads a cell's row label up to the cell, so a cell further right read the values of the cells
  before it glued on, values the camera held.
- `kit/schema_update.py --write` over an older definition keeps of its proofs only a value that a proof line the
  report counts still wrote (a hold's option numbered apart in two sessions); never an older menu row, count of
  samples, or value no counted line wrote. A mapper with a definition written by an older kit writes it afresh
  ([UPDATING](docs/UPDATING.md)).
- The kit reads the viewfinder's shooting screen (the eye sensor covered and the monitor folded in) as the shooting
  screen: the finder draws its battery smaller, further right and higher, and that icon is one of the
  battery templates, cut from the camera's own frame.
- New provers for Camera Set. Memory, with the owner's word: `kit/provers/memreg_run.py` checks that a registration
  copies live settings into the memory set (`kit/tools/set_twins.py` picks the rows), and `kit/provers/framepos_run.py`
  finds which records keep each focus area's frame, `--zone-grid` sweeping the Zone over its nine places. Their
  "registration mirror" lines are no report row; the writer reads them (`in_sets_proved`, and the Zone's places).
- `kit/provers/framepos_run.py --frame-move-amt Standard|Large` sets AF Frame Move Amt by the menu before any area,
  stops when the settings file downloaded after the setup does not hold that option, and names it in every line's
  context; its summary keeps the last line of each area in each context, so a run with both settings keeps both.
  `--moves "Right 1"` (or `"Left 1,Up 1"`) moves the point and box areas by the presses given, so a step can be
  measured by one press each way; the zones keep their own, and the context names the moves.
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
  another way, sending nothing. `--shows` is the mode the camera's screen shows now (look, or ask its owner), the
  family first and the exposure mode after it when you say one (`--shows Movie`, `--shows "Stills M"`; a letter alone
  is refused, as Movie's and S&Q's screens show one too): it refuses while that is the mode the switch went to, which
  only `--restore` puts back. The renamed record keeps what
  was said and when, and the command says how to undo it. A run that stops on a waiting switch says first to look at
  the screen, and what `--restore` would undo.
- `--scan latest` on a command that works in no mode of its own (`prove_run.py`, `crawl_run.py`, `drive.py`) stops in
  plain words.
- `kit/tools/set_twins.py` needs `--evidenced <run>` (`--evidenced ''` for none).
- `kit/tools/menu_tree.py` writes the menu tree to `private/evidence/<model>_fw<fw>/`. A menu tree, accepted rulings
  or record shapes still in `data/<model>_fw<fw>/` are moved there once with `kit/tools/move_evidence.py`, and only
  by it: the commands that read or write those files (the report, the writers, `menu_tree.py`, `set_twins.py`,
  `mymenu_run.py`) stop and name it while one is there, and `check_public.py` prints it.
  Without the menu tree the proof viewer lists every record under its tab and group instead of on the camera's menu
  rows, and says so.
- `kit/tools/check_public.py` refuses a tracked path holding a control character (a newline, a tab, NUL and the
  like), with `--all` and `--commits`.
- On a pull request, `kit/tools/check_public.py --commits BASE..HEAD` holds every file each commit adds or changes to
  the rules `--all` holds the tree to (paths, binary files, contents, lean data and definitions), so a file added in
  one commit and removed in the next is refused all the same.
- The reset file is one public file, lean (`schemas/settings-reset.schema.json`), written and edited by hand; the
  kit keeps no private copy in step with it, and refreshes only each setting's name and tab from the definition. One
  in the older whole shape is refused, and `kit/tools/move_evidence.py` keeps the whole once in `private/evidence/` and
  writes the lean one in its place.
- `kit/schema_update.py --write` stops before writing anything when evidence went stale in that run (a proof's, or
  more than five settings', say after a setting's key was renamed); `--accept-stale` writes it anyway, kept aside.
  After a write one line says when the evidence file has a "stale" section; `--drop-stale` lists it by setting and
  field, and `--drop-stale --write` removes it. A write leaves a marker beside the evidence file until the definition
  is in place; while one is left, the last write was cut short, the next write stops and names `--finish-write`,
  which writes the definition that write was writing only when it is the one the marker names. An evidence file
  newer than the definition (after a pull, say) is no longer taken for a write cut short.
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

- Outside Expert mode a setting offers the values its proofs on the camera show, no longer the old lists of the values
  camera files had held (which held the camera owner's own settings, so a definition no longer carries them, and one
  that still does is refused by the definition's schema and read without them). A value not checked on the camera yet
  is listed only with "Offer values not checked on the camera yet" (in italics in the window, "(not checked)" on the
  web page; the value the file holds now is shown as it is), its hover saying the camera may refuse a file holding
  it. A value the camera's menus never offer is left out even then, and the detail panel says why on one line per
  reason ("Not on the camera's list: …"); a factory value the camera writes itself stays offered. Every My Menu place
  can be emptied, and each Fn Menu place, Custom Key and dial offers the functions its own list on the camera has.
- A setting no proof on the camera can reach says why in a few words instead of "Not proved on the camera yet": "Not
  a menu setting: the camera keeps it", "Written only by the camera's own saves", "Not proved (needs equipment)", "Not
  proved (network, by hand only)" or "Not proved (nothing tried moved it)", with the reason in full on hover, in the
  window and on the web page alike. A kind of reason the editor does not know shows "No proof possible".
- A setting's proof names the run and the day of its latest proof ("Proved 2026-11-09 (kit2_afreg2)" on hover), where
  it was made outside the main mapping run, instead of that run's first day.
- The a1 II's definition offers more values checked on the camera: Exposure Comp. and Flash Comp. every step, in
  thirds and in halves; a Recall Custom hold's Exposure Comp. every step, its Shutter Speed every speed from BULB to
  1/32000 (hold 3's list checked whole, holds 1 and 2 named from it), and hold 1's ISO at every value; Movie's own
  colour temperature (C.Temp./Filter) every temperature from 2500 K to 9900 K; HEIF in File Format (Slot 1); the
  exposure mode a memory registration stores, in S and M too; the Registered AF area records for every area
  registered so far (its kind, its area and a Tracking area's start area); the Spot size Focus Area remembers on
  leaving Spot, at every size; and each Playback Filter Condition box unticked. A memory-set record named AF
  Illuminator, which a registration showed it is not, is unnamed now, its values numbers. The Registered AF area's
  Tracking start area does not count as proved a value a hold copied from the camera's own setting.
- A Picture Profile's page as on the camera: PP1 to PP11 are marked "›" on the Picture Profile row, with a link
  "Open the PP1 page" under the chosen one (and the one under the pointer) in the window and the web page; the page is
  a group of its own after Color/Tone, laid out with the camera's headings (Black Gamma > Range, Level; Knee > Auto
  Set; Color Depth; Detail > Adjust), the stills and movie copies side by side. The search and every jump to a
  profile's setting open its page; the Picture Profiles table stays, and the flat list is unchanged.
- The detail panel and the web page no longer show the mapping team's words outside Expert mode: a setting's note,
  the records it lives in, what the camera writes together with it, the hidden-values count and the layout's note
  are Expert-only, and the record number, proof and stored-number switches moved from Appearance to under Expert
  mode. Refused options go on one line per reason ("Not offered while …: A, B, C"), a setting the camera's menu does
  not show says so, and a value with no name, a damaged file and the write check are said in plain words.
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
  file saved on PAL opens as firmware 4.00 with its definition, the badge says "PAL" or "NTSC", Compare notes when
  two files differ in it, and a write is refused when the file and the camera differ (an untried case; a switch in
  the code turns it on).
- The menu is laid out as on the camera: each group's rows in the camera's order, a row's sub-rows under it, and
  each setting under the row it belongs to (Cont. Shooting Speed's rates under Cont. Shooting Speed, not at the end of
  the group). An option's own choice shows under it in the detail: Drive Mode on Continuous Shooting shows the speed.
  "As on the camera / Flat list" above the rows switches back to the plain list. Settings the definition does not
  place yet come last, under "More settings in this group". The web page does the same.
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
- Camera definitions are files, one per model and firmware, never built into the program: the ones that come with
  the editor sit beside it, and yours in `definitions/` in the editor's own folder. Settings > Camera support & web
  page lists every one, with Add definition…, Open folder and Reload; yours replaces a built-in one of the same model
  and firmware, and the sample keeps the built-in one. A camera mapped with the kit works the same day, with no new
  editor. A definition made for a newer editor is refused with a message saying so.
- A file is read with the definition of the model and firmware its header names, through that definition's
  container block; another firmware of the model opens with the nearest one, said beside the file's name; a file
  whose checksums do not hold under its block is never edited. In Expert mode, Open with… reads a file with any
  definition, and a save or a write says so.
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
- Writing to the camera: only a file the editor may edit, of the camera definition's model, never the sample, and
  only the file the Write window checked; the camera's copy read just before is checked first (model, layout, a
  copy cut short), and a write the camera did not confirm says it may have been written and offers Put the camera
  back. The Write window says in plain sight what a write replaces and to save the camera's own copy first.
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
- A damaged or hand-made settings file never stops the editor: random bytes, files cut short and files with a byte
  of their header, record counts or record sizes damaged are refused or opened view-only, and a file of no sections,
  more sections or records of other shapes opens with every page of the window and the web page drawn. The web
  page's Unmapped records and Record map no longer stop the editor on a file that holds no sections.
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
  fine-tune, a Creative Look's parameters) is no longer a row of its own: the row's detail panel shows every choice
  of the option chosen now, each with its control and Revert, and the search, F3, All edits and Compare open the
  row with that choice marked; the web page does the same. A number the definition shows other than as stored is
  shown and typed so ("75 %" for 7500), and Expert mode marks an option name that two readers did not agree on and a
  setting whose proofs disagree. The record-number, proof and stored-number switches draw nothing with Expert mode off.

### The web page

- The page speaks to photographers: a setting's mapping notes, records, what the camera writes with it, the record
  number, the proof badge, the stored number and the count of known settings show in Expert mode only, and the
  three "Names and values" switches sit under Expert mode. A row's details start with its help, say "Kept in the
  memories too" and "Not on this camera's menu" in plain words, and group the options the camera refuses into one
  line per reason ("Not offered while …").
- The page's Settings name the editor's version, as the window's do.
- The page's Write reads the camera first, as the window's does: "Reading the camera, to list what this write
  changes…", then what the write changes against the camera now, and only then Write to camera, which keeps that
  read as the copy from just before; a read that fails ends the write with the Camera link report.
- The page names the definition the open file is read with, and how it was picked.
- The editor's small web page, off until turned on, now does what the window does from a browser on a tablet, a
  phone or another computer: the same pages (Main, the tabs, Memories, Exposure, All edits, and in Expert mode
  Unmapped records and the Record map), a setting's details, Connect to the camera, Settings, Backups, the edit
  history, the camera report, and Compare with file B, a base file, copies and merges.
- Files go up and come down through the browser: Open… and Compare's files are uploaded, and Download file,
  Export CSV… and Describe for support… download.
- The camera's user name and password are entered in the desktop app only, and never cross the network from the
  page.
- The access code is new each time the page is turned on; a browser then keeps a session for 12 hours unused, and
  Sign out ends it. The page answers only its own requests (Host and Origin checked) and counts wrong codes per
  device. It cannot turn on Expert mode, raw edits, unobserved values or Edit anyway, point the camera link at a new
  address, or write a file the Write window did not check. The state it asks for every few seconds names no folder,
  address or serial number; the camera's details come only when Connect to the camera asks for them.
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
- Help where you look: a setting's help on hover in the rows and in the file layout's inspector, and each option's
  help under it and on hover. With the camera's runs on the computer, every help text read off the camera links the
  guide screen it was read from, and a text the two readers read differently is marked, with both readings. Rows with
  no setting of their own (actions, submenus) show the camera's guide for the row. Each text says whose words it is.
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
- Every row of the file layout's structure chooses its bytes, outlined on the map: the file, a section, a block of
  records, a record, its fields and its elements; the inspector names a block and lists its records. In the hex the
  chosen bytes stand out in their own colours (bright cyan on the dark theme, blue on the light), with the record
  around them shaded faintly.

### The mapping kit

- `kit/provers/afreg_run.py` proves AF Area Registration: each Focus Area chosen in the menu, Fn held on the shooting
  screen, the downloads around the hold diffed; a record a hold copies from the camera's own setting is named a side
  effect, changed or not, and never credited to the area. `kit/provers/filter_run.py --untick` proves each Playback
  Filter Condition box's value when unticked.
- `kit/drive.py` takes `enter!:REGEX`, an Enter the operator vouches for on a screen that lights nothing the kit can
  read, with the camera owner's word only; it is refused on a menu, the Main tiles and the shooting screen, on a
  screen whose text reads nothing or names a never-open row, and wherever a plain Enter is.
- The pass-2 report reads the camera's other proof runs beside the main one (the runs a prover marks as one), each
  proof's files named with its run, and never credits a record a proof names as a side effect; `--alone` reports the
  main run by itself into a file of its own. `kit/schema_update.py` gives each record proved there the run and day of
  its latest proof, and a reason why no proof can reach it where a hand table says so.
- `kit/tools/menu_tree.py` names a carousel's options by their own names, never by the sub-choice the walk read them
  on; `--carousel-names` does so for an existing tree and changes nothing else.
- The rows the pass-2 report listed as failed are finished (2026-11-07). `kit/provers/mode_switch.py` puts the camera
  in another shooting mode through the menu (Mode Dial Control Set = Set with Menu, then Shoot Mode's carousel, never
  a memory recall) and leaves it there for the prove runs that need that mode's menu, the stills file put back with
  `--restore`: Flash Mode's Autoflash and Flash Off (Intelligent Auto alone offers them), ISO AUTO Min. SS (not in
  M), and the Movie menu's rows. A put-back that leaves records differing is no failure when the prover can say why:
  kept by the camera since an earlier option, a saved value the list does not offer here, or a checklist's copy of a
  box's tick written from the first save on (Rating Set(Custom Key)); the attempt is recorded finished with the
  reason and the session's upload puts the records back. An information screen with buttons after a list choice
  (Exposure Ctrl Type = Flexible Exp. Mode) is taken with its OK. A carousel that opens on a word of its automatic
  position's scale (ISO AUTO Min. SS on "Standard") is matched to that position; a vision reading that ends with a
  label names it ("ISO ASS 2"" for 2"); seconds marks compare alike however drawn (2", 2″, 2”).
- Picker functions that open a setup screen of their own (a Recall Custom hold's registration, Rating Set, Recog.
  Target Select, and the Send, Sync. Release, Cnt Sht Spd Bst and My Dial functions the kit kept out by name) are
  proved like any other since 2026-11-07: the key takes the function, the prover leaves the screen with MENU and goes
  on, and the report credits the function with the key's record alone, the screen's own records (the hold copied into
  its registration working copy) credited to nothing. A saved Recall Custom hold is still left for the session's
  upload to put back. `prove_run.py --list` says how many of a cell's options are still to prove. S&Q Shoot Mode is
  proved with the owner's switch on S&Q (Time-lapse, S&Q Motion). `kit/provers/filter_run.py` proves Playback Filter
  Condition, a checklist whose boxes open a chooser each and whose conditions the camera writes to the file: each
  chooser's options as a list row of its own, the start file back between items.
- `kit/provers/mymenu_run.py` proves My Menu's item codes on the camera: My Menu Setting > Add Item for every
  item the picker offers (268 on the a1 II), one download per add, six pages filled in turn and the start file put
  back between fills; the report counts the slot an add filled and gives an add no held value. The item's name is
  settled against the camera's own row names (the menu tree's rows and the Help Guide's menu list) from the lit row's
  OCR and the vision reader's words, for the OCR carries icon noise and a page's group name and the reader now and
  then answers with the group's name ("AF/MF" for Preset Focus/Zoom); twins the screen tells apart by an icon alone
  (the Still and Movie "Fn Menu Settings") are numbered by their place in the picker, and `--relabel` names a run's
  proofs again by that rule without the camera. On an Add Item proof the report leaves out a vision reading that is
  another row's or a group's name, as it does a row's name over an option, and the writer keeps the fuller of the
  table's name and the proof's when they are alike ("Shot Mark with Shutter Button" over the OCR's "with Shutter
  Button"; "Fn Menu Settings" over "Menu Settings"), dropping a glued icon glyph ("SISO Range Limit"). The 42 slots'
  table names 268 proved codes and the empty slot. The prover's ways round what a settings reset changes: the
  Custom Key screen's one-time notice is OKed, the Dial/Wheel page's "Separate M mode and other modes" box is ticked
  before its dials are proved (with a fresh base after it, so the proofs show the dial alone), a never-open group left
  lit in the group column is stepped off before Right, the jump by the tab and group columns reads the lit group
  instead of assuming the first, a frozen OSD picture is waited out on the Fn Menu tiles, `--redo` proves a named
  row's options again, and `customshoot_values.py --prepare` puts a hold into a mode whose items the camera offers.
- My Menu's items are proved on the camera one by one (`kit/provers/mymenu_run.py`: Add Item for every item the
  picker offers); `kit/schema_update.py` names each proved code alike in all 42 My Menu slots, proving only the slot
  that took it.
- A setting proved on the page an option of a row opens ("Picture Profile > PP2 > Black Gamma > Level") gets its
  place on that page: `row` is the row, the option, then the page's rows, `row_at` adds the option's index (a
  family's column) before the page's places, and `under_option` names the option, while the setting keeps its own
  group. Every option's page takes the shape of the one the walk opened, so the a1 II's Picture Profile parameters on the
  profiles its menu offers (PP1-PP6, PP10, PP11: 600 settings, stills and movie copies alike) now have a place; PP7-PP9,
  which the menu never offers, stay unplaced (2026-11-07).
- The pass-2 report credits an option that changed nothing with the start value of its own base file, read from
  the file when no proof of that session moved the record: a put-back made in a session of its own (the saved
  function alone, after a picker tile was proved in two sessions) was credited with the first session's start value
  and showed as a conflict. The prover OKs the camera's one-time notice before the Custom Key screen (after a
  settings reset), waits out a frozen OSD picture while walking the Fn Menu tiles instead of failing the cell, names
  a second-screen table cell by its job key with `--rows`, and `kit/provers/customshoot_values.py --prepare
  "Shoot Mode=Manual Exposure"` first puts a Recall Custom hold into a mode whose items the camera offers (the
  shutter speed and aperture items are refused while a hold is in P). A second Fn Menu tile per screen, a second
  My Dial slot and the holds' shutter speeds are proved in full or at three points (2026-11-07).
- `kit/tools/replay_proofs.py` diffs every proof of a run again with today's parser and lists each proof whose
  changes now differ from the stored ones, and any missing file. `kit/tests/test_consistency.py` checks the shipped
  definition against itself and the proofs: the Recall Custom holds' shared labels and bracket places, picker slots
  against the slot proved in full, repeated labels against a reasoned list, the movie copies against their stills
  twins, scaled numbers against what the camera showed, what backs each name, and the accepted file. CI validates the
  accepted file against its schema.
- `kit/schema_update.py --write` refuses, listing each, while pass 2's report holds a conflict it leaves standing, a
  new record it does not add, a record not one to one, a name dispute or a carried-over value that the camera's new
  `data/<model>_fw<fw>/accepted_<model>_fw<fw>.json` does not accept with why (`--force` writes anyway, loudly). A
  record not one to one loses its old proof and is marked `disputed`; each proved value's name says what backs it
  (`proved.names`: two readers, one reader, the vision model, a hand table, the kept schema label, a rule's copy,
  held, sampled); a number the camera shows scaled gets `shown_as` from its proofs (the 66 Knee Point settings, "75%"
  stored 7500); a picker's reading is never snapped to a name with other numbers ("Custom Look 1" for "2"). The
  JPEG/HEIF copies written with their main record are Expert-only, and the Focus Area and Free Size memories are
  named "remembered". A picker family names each code once in every slot (no head the camera never shows, no name
  cut short or misread: "Fixed Speed STBY", "Face Priority in Multi Metering"); a value two options write alike gets
  one name ("HEIF"); an icon's capitals give way to the words beside them ("Extra fine"); an unproved value follows
  its siblings' form ("Manual Exposure", "120fps"); a Picture Profile's movie and stills copies share their values;
  the WB fine-tunes and the Creative Look parameters sit under their preset and look on the camera's rows; the
  settings reset file's names follow the definition. The pass-2 report no longer counts a vision reading of one part
  of a name, or one beside two agreeing readers, as a dispute (44 disputes down to 7).
- The pass-2 report names a value by the map's label unless the vision model backs the bar's OCR instead; the OCR no
  longer wins alone (it had named a slot-icon option "1/7 This Image"). Each value's readers are in `report.json`,
  and the names they argue over (`name_disputes`), the values a record kept from the option before while others
  moved (`carried_over`, no longer credited to the option) and a picker's twins ("AEL hold (2)") are listed in the
  new `report.md`. Tables and carousels' axes are checked one to one too, and a short definition label only agrees
  inside the camera's when no other proved label holds it. `kit/tools/reread_proofs.py` asks the vision model about
  the saved frames of proofs that have no reading of their own, with no camera, for the report to weigh.
- `kit/prove_run.py --first "ROW / OPTION=VALUE"` proves a carousel axis from another value, so the one it held is
  proved too; a list that opens with a single option is proved by its display (both readers on the label, the
  value from the file), for rows such as XAVC HS 8K's frame rate under PAL. The prover presses MENU again after the
  lock that follows a download and Right when the menu reopens with the focus in the group column.
- `kit/prove_run.py --every` proves a number scale at every value instead of its lowest, middle and highest (scales
  of up to 64 values), to check that a family's straight line holds at every step; `--list` prints what a run would
  prove and stops, with no camera. A number field the first OCR engine leaves unread is read by the second engine,
  else from the field alone enlarged, before the row can fail on it.
- Nothing is pressed while the menu is still sliding: the screen reader gives a menu page no focus while its rows
  panel is between its two places, the OSD eyes wait two of the SDK image's renewals (0.75 s) before a screen counts
  as at rest and give a press 1.5 s to show, and the scan and the prover look again until the menu stops before
  stepping into the rows (a Right sent to a moving menu had opened the Drive Mode row and the next Down moved the
  drive mode, 2026-11-06). The prover cancels with MENU if that Right opens a row all the same.
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
  on the camera with `kit/pass3_run.py --only "PAL …"` entries over the OSD and `kit/provers/boxes_run.py`. A row's
  starting option is proved from another start: `"first"` in pass 3's table, `--first BOX=VALUE` in the two-box
  prover. `kit/pass1_map.py --own` writes one walk's map without touching pass 1's; pass 3 uses the third reader.
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
- The definition speaks to photographers outside Expert mode: a setting on no camera row whose name holds a mapping
  word ("numerator", "record", the SDK's "Unknown") and the fields of the memories' live copy are Expert-only (183
  settings now, 63 more); "Other (from SDK)" is "Other settings"; three settings on camera rows have plain names
  ("Drive Mode (menu choice)", "Drive Mode Limit: Single Shooting", "S&Q Shoot Mode: Motion or Time-lapse"); a
  refused option's reason no longer ends with the dialog's "• OK"; a display rule carries no record number. A test
  fails when any name, group, help, display rule or reason a photographer reads holds a word of the mapping.

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
