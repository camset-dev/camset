# Changelog

What changed for the people who use Camset, newest first. The version is `editor/Cargo.toml`'s; a release is a tag
on GitHub with the editor's packages attached ([RELEASING](docs/RELEASING.md)).

## Unreleased

### Read first

- **The coverage ledger's public form is no longer committed:** `kit/tools/coverage.py --print` prints it from the
  public sources and the seen file, the same in any clone, and `check_public.py` refuses a copy in `data/`. A mapping
  branch that tracks `data/<model>_fw<fw>/coverage_<model>_fw<fw>.json` takes it out with `git rm` after merging `main`
  (decision 23).
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

- **Compare lists the settings only the memories keep:** a memory's focus frames, stored exposure and mode are rows
  whenever a memory of the menu shown is one of the columns, in the window and on the page, as Edit lists them for that
  memory, with their differences counted between the memories (the live settings hold none of them). A search that
  finds them with no such column says why none is shown, and a copy never reaches the live settings.
- **Collapse all and Expand all by the keys, and reverts that keep groups whole:** Cmd/Ctrl+Shift+↑ and ↓ fold and
  open every foldable group of the view in front from any pane, in the window and on the page (Edit's tabs, Compare,
  search, My Menu, Exposure, the record map, and the Memories page, which now folds), each view with its own buttons,
  and a single heading folds by the keyboard too. Outside Expert mode, All edits, History and the page's requests put
  My Menu back as one list and a fraction's two parts back together, and a Compare row's note names the other menus as
  Compare shows them.
- **The camera's menu in each shooting mode, and Edit's Menu in Compare:** where a definition lists its camera's menus
  (`camera.menus`, each setting's `row_menus` and `row_places`), the window and the web page show one at a time under
  Camera menu:, opening on the file's mode, each row titled as the camera draws it, with that mode's value and a note
  naming the other menus an edit changes too; Edit is otherwise as before, and picking a menu changes nothing in the
  file. For every definition Compare has Edit's Menu on its left, so All settings (and its CSV) also holds My Menu's
  places, changed on its page only, and every record a Main tile shows, a fraction's two parts being copied together
  or not at all.
- **"Unmapped" says what it means:** on the Unmapped records page and the record maps, in the app and the page, and in
  the docs and the ledger's public form, the mapping found no menu row that changes such a record, so it does not know
  what the record holds, and a change to it is unproved and at your own risk. Which unmapped records never changed
  stays in the mapper's private ledger, never listed or counted in a public file (decision 27).
- **The a1 II's definition lists the camera's three menus, Still, Movie and S&Q,** and the menus each of its 1380 placed
  settings stands in, read from each mode's own menus; 165 settings take the row they lacked, among them Camera Set.
  Memory's records, the focus positions under Focus Area and Preset Focus/Zoom's. It also names 340 values as the camera
  draws them, says why eight rows are greyed (Focus Mode, ISO AUTO Min. SS, Select LUT, Aspect Marker Level), and adds
  Save HEIF Size, the Recall Custom holds' Exposure step, Playback DISP Mode and whether Lock Operation Parts holds.
- **The a1 II's definition proves Bracket Type's Cont. Bracket and Single Bracket whole,** each of their 60 choices
  and no longer a sample. Six rows take the names the camera draws (Proxy Recording, Proxy File Format, Proxy Rec.
  Settings, with Shutter Button, S&Q's Record Setting and the movie Recording Media row), and two value names are
  corrected to "Disp Specified Time Img." and "FTP Trans. (This Img.)".
- **The a1 II's definition takes the evening's proofs of 2026-11-19:** S&Q's Record Setting for XAVC HS 4K at 24p and
  120p and XAVC S HD at 30p, 24p and 120p, each a record of its own (the two named before for every rate are the 60p
  ones), and Framing Stabilizer's On: Center or On: Manual, the row greyed while Touch Operation is Off. A record that
  follows NTSC/PAL carries a reason in place of a proof, and the movie Recording Media row, Bracket Type's options and
  Playback's Aspect Marker Disp. take the camera's own places.
- **The a1 II's definition takes the afternoon's proofs of 2026-11-19:** Bracket Type and its options' own records
  (proved with the drive mode dial on BRK), the movie rows of Recording Media and of Dial/Wheel's Separate M mode box,
  single-slot JPEG/HEIF Quality and Image Size, and Playback's Aspect Marker Level, until now an unknown record. Focus
  Bracket's Number of Shots takes 2 to 203, and each Custom box's size times 1000 is named as that box's, Custom 1's
  no longer taken for the box in use.
- **The a1 II's definition takes the proofs of 2026-11-19:** ISO AUTO's movie Minimum and Maximum are walked in
  Movie mode (ISO 100 to ISO 32000, a Maximum set below the Minimum pulling it down there too), Color Mode is proved
  on each profile with its Gamma on HLG, and My Menu's empty place and the Playback Filter flags' "Never set" are
  offered as values the camera holds from the factory. ISO in use and a memory-set flag the camera writes itself carry
  a reason in place of a proof, and 138 settings say part of their list was proved on another setting of the same kind.
- **A setting whose list was proved partly on another setting of the same kind is never called checked on the
  camera** (its definition's `proved.shared`): it still offers every listed value, and its proof line, the Exposure
  page and the Write and Before saving windows say what is true of the list.
- **The a1 II's ISO AUTO Maximum set below the Minimum pulls the Minimum down,** as the camera did in Stills mode:
  the editor no longer calls that untried for the setting and its stills copy, and still does for the movie copy.
- **The a1 II's ISO Range Limit is proved value by value, its lower end named "ISO Range Limit (lower)",** and its two
  ends and ISO AUTO's Minimum and Maximum (with each mode's copies) carry the order the camera keeps between them.
- **Two limits the camera keeps in order stay in order:** setting one past the other (the a1 II's ISO Range Limit,
  ISO AUTO Minimum and Maximum) moves the other to the same value in the same step, as the camera does, and says what
  moved, or that the camera was not seen to do it. A file holding a pair out of order is listed before saving and
  writing under "Limits out of order" with a one-step fix, and the Exposure page marks it instead of swapping the two.
- **The a1 II's Zebra Level Custom boxes are listed as the camera draws them, Type first,** and Time-lapse's Record
  Setting under XAVC S 4K 60p names 200M 4:2:2 10bit and 150M 4:2:0 8bit as the camera does. A memory set shows the
  exposure mode last registered once, in its own record.
- **A setting the camera keeps in several records moves together in every view:** the Main page's tiles, their
  rows and Revert now change all its records (Drive Mode, Focus Mode and their twins), and the page's Drive Mode tile
  no longer writes the wrong drive mode. A value one of those records has no name for is made where asked, said, and
  listed under "Kept in several places, now apart" before a save or a write.
- **Every list of edits names settings:** Edit history, All edits and the Write window, in the window and on the
  page, show each changed setting by its own name and value ("PP3 Black Level"), not its record's raw array. Revert
  in Edit history puts back that one setting, leaving later edits to the record's other settings.
- **Compare and the CSV export:** Compare refuses a file B or base of another camera model, saying what it is; one
  from another firmware of the same camera is compared with a line saying a setting that firmware keeps elsewhere can
  read wrong and only settings kept alike are copied. A set's CSV export writes every setting (PP2 to PP11 and the
  Recall Custom holds were missing), its record numbers, raw values and mapping notes in Expert mode only.
- **Plain words where a file is refused:** a file whose header checksum fails says it may be damaged and what to do,
  instead of "this firmware has not been checked yet" and an "Edit anyway…" button it never gets, and Add definition
  says why it refuses a file, the reader's own text in Expert mode only. My Menu's rows keep mapping notes for Expert
  mode, as every other view does.
- **The a1 II's Exposure Comp. has a stills and a movie copy, as White Balance does:** the movie copy is new, with
  what Different Set for Still/Mv's Exposure Comp. box does to the pair, and the slider's own copy moves to Expert
  mode. ISO's movie copies gain the values the Stills menu writes into them, ISO Range Limit's limits say how they
  push each other, RAW Output sits on its row and the movie Custom Keys spell Focal Length and Fixed Speed REC.
- **The a1 II's Zebra Level Custom 1 and Custom 2 boxes are settings of their own:** Type, Standard 0 to 109, Range
  ±1 to ±10 and Lower Limit 50+ to 109+, each number proved at its ends and a few values between, the rest on their
  line. The boxes a Type does not draw show greyed, their numbers kept, as the camera leaves them out.
- **The a1 II's S&Q and Time-lapse frame rates per movie format:** S&Q's and Time-lapse's Rec Frame Rate under XAVC HS
  4K, XAVC S HD, XAVC S-I 4K and XAVC S-I HD are in the definition, each with only what its own box offers, named by
  their format as Record Setting's are, and S&Q's Frame Rate gains 240fps, offered under the two HD formats. Under XAVC
  HS 8K the camera offers no S&Q frame rate.
- **The a1 II's Time-lapse Record Setting per format and rate:** XAVC S 4K, XAVC HS 4K and XAVC S HD at every rate each
  offers, each record listing only its own list; the XAVC S-I formats and XAVC HS 8K are not tried yet.
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

- **Where the camera has several menus, the viewer's Menu is the first (the a1 II's Still menu), named over the
  column,** as the editor lays it out for the settings saved in that mode; Expert still lists every setting, the other
  menus' rows among them. The proof viewer hangs every record on the row the definition places it on, rows given by
  hand included.
- A file the viewer refuses shows its size and first bytes as a hex dump, to paste into a problem report: the file was
  read in your browser and never left it, but check that the dump holds nothing of yours before pasting it anywhere
  public.

### The mapping kit

- **`mode_switch.py --set` sets the S&Q Frame Rate boxes with the camera in S&Q mode:** the S&Q family's two-box rows
  are taken on the S&Q menu where that menu's own page scan draws them. Other menus and rows are refused as before.
- **The two-box path judges each row grey before opening it:** `boxes_run` presses no Right on a row drawn grey, as
  `set_row` already refuses a list row so drawn.
- **`mode_switch.py --set` chooses no option drawn grey and opens no row drawn grey:** it asks the camera's Help on a
  grey option where it may, closes the list with MENU and stops, as it does where whether an option is grey cannot be told.
- **The grey-row test of the old label list holds on any definition:** with "Focus Mode" now also a value name, that
  list names no blocker for Focus Mode Dial instead of the shorter one, and the test expects whichever its data gives.
- **A picker slot listed for review keeps its name's source on a pass over the writer's own output:** its readers'
  where its reading spells the name, "derived" where the name is its family's sure reading, else "schema kept".
- **A stopped Recall Custom run (`customshoot_values.py`, `customshoot_run.py`) presses nothing more but MENU:** its
  start file goes back and is checked, it exits 8 (4 for a STOP file left before it, which it names, or a working copy
  only a hand can put back), it gives `customshoot_values.py --put-back --against <its start file>` only where opening
  hold 3 restores the copy, and a hold that failed part way now exits 8 where it exited 0. A notice after Register
  counts only as the camera's "Registered." alone, and the coverage ledger no longer reads a registration mirror line
  not applied as a refusal.
- **A restore's check keeps trying a camera slow to restart for up to 300 s,** the one limit every run and tool goes
  by, where it gave up at 130 s; twice the camera had only been late.
- **A restore's check says what it waits for,** the camera's restart and up to 5 minutes, before its first try, and a
  first Ctrl-C meanwhile says the check goes on and that a second one would leave it undone.
- **`greyrow_run.py` takes a misread "This function is currently disabled." for no reason,** as OCR's "This tunction is
  currently disabled." was taken for one on five rows, which then got no Right. A real reason is still a reason.
- **`carousel_fields_run.py` walks the boxes of an option with a short name,** such as movie Self-timer's On: with a
  box lit, OCR's reading of the title stands where it is exactly that option's name, since the second reader then
  answers the lit box. A title naming another option still stops the walk, and so does a proof that moves the option's
  own record, which each line now keeps beside the title read.
- **`carousel_fields_run.py` judges a box lit on the frame its title was read from,** as it judges the option: a box
  seen lit just after a Right and gone once the title settled no longer passes, so no walk ends on an empty look.
- **The grey-row tests no longer pin what a live run folder holds:** every notice in the a1 II's
  `kit2_greyrow/greyrows.jsonl` is judged by the blocker rule, however many rows later runs add, and the first run's
  expectations are a copy kept in the test, names and labels only.
- **`customshoot_values.py --follow ROW=OPTION,OPTION --record KEY` registers a Recall Custom hold as it stands with a
  live list row on each option in turn, in one session,** for a record the hold writes from a setting its screen does
  not show (the a1 II's lead: 0x0c39 and the Exposure step). Each Register writes a "registration mirror" proof line, applied
  only where the hold's element of the record changed to the option's code.
- **A function picker's name that lost a word of the camera's is no longer taken for agreement:** pass 2's report
  marks it "wording" where the reading is still alike and names no other value, and the writer gives the camera's
  words where two readers read them ("AF Transition Speed", "Av Auto/Manual Switch"). `label_audit.py` lists such a
  picker name as "a cut form of what is read", never confirmed, and a name a family correction replaces is "derived".
- **`reader_census.py --questions` measures three wordings for the lit item (variant "cursor") and takes `--frames`:**
  the option with the radio dot and the left column's category are never the lit item, and the sample can be a list of
  frames kept outside the repository and the runs, options drawn alike taken too. Its variant "icon" asks the local
  readers what icon the lit item draws, written [icon] where it stands.
- **`reader_census.py --questions` and `label_audit.py` say why each reader failed, by count:** an HTTP status and
  its reason phrase (never the server's body), a timeout, a refused connection or "an answer that is no usable JSON",
  beside the asked line and in the line that stops a reader after a run of failures, never what an answer held.
- **A definition can say which of the camera's menus hold each setting:** a camera's `MENUS` hand table (a menu per
  position of its shooting-mode switch) becomes `camera.menus`, and each placed setting gets `row_menus` and
  `row_places` (a menu's tree holds its row, or that menu's own proofs reach it). `HAND_PLACES` places a record no
  proof path can, and `kit/tools/menu_tree.py --add` takes one group's pages from a page scan into a tree.
- **The camera's menus tell more records apart:** one setting kept in two records that Stills and Movie each move
  alone keeps each in its own mode's menu, and a row given by hand reaches the second of two rows of one label (`#1`)
  or a row named as its group. The camera file may word the menu buttons' label and hover (`camera.text.menus_label`,
  `menus_hover`).
- **The camera's menus rest on nothing of the owner's:** placement never reads My Menu's item pages, the kit reads a
  proof's context one way everywhere, and a write with no menu tree here leaves a definition's menus as they are. A
  menu's place always names its row and row_at, and a row given by hand never changes whether a record is shown.
- **The writer refuses camera menus the editor could not show truly:** a MENUS table the menu tree does not match or
  that leaves a mode without a menu, records of one row with overlapping menus, and a Main tile showing an Expert-only
  setting. No place rests on where an option list's reading began, a silent proof's mode comes from the camera's own
  files for placement alone, and a hand place's reason is the private hand evidence's.
- **A menu holds the rows its walk read as a list's options:** where a mode's walk read a row as a list or checklist,
  its options name the settings below it there (Movie's and S&Q's Playback Filter Condition).
- **A definition's menus are rebuilt alike without the runs:** the modes the camera's files give silent proofs are kept
  in their evidence, where placement reads them. At every pass the writer prints the settings listed in fewer menus than
  their row stands in, the mapping's open work.
- **`check_public.py` holds a definition's camera menus to names and places:** no row's state, option list, page
  counter or My Menu item page in `camera.menus`, `row_menus` or `row_places`.
- **A write from a definition read without its evidence keeps every place, menu tree or not:** a pass that proved a
  few rows no longer takes the row off every other setting. The writer's refusal of a Main tile on an Expert-only
  setting now says why that setting is Expert-only, and what to do about it.
- **Pass 2's report credits a record only `--number` lines move, each to the number named, by that number:** its
  label carries the other fields as they stood, so Drive Mode's Focus Bracket, its Step Width never walked there, left
  Number of Shots "missing" where it is now a number field the writer widens to what the camera stored.
- **`carousel_fields_run.py` refuses a Right onto Drive Mode's › box after the bracket fields,** which Touch Operation On
  outlines as a box and which opened Bracket Settings once a Right reached it, committing the option. The run stops as
  on any press the guards will not send; with Touch Operation Off the › is no box and nothing changes.
- **`carousel_fields_run.py --number` no longer passes every number over on Focus Bracket's digit boxes:** the camera
  held each number as asked, but the check before Enter compared a box's picture taken with one box lit against one
  taken with another, and the pixel reader finds a box's sides where the lit box beside it leaves them. Each box's
  stepping is now judged by the other boxes' pictures before and after it with that box lit, so a camera that carries
  or clamps between boxes still has its number passed over.
- **Pass 2's report no longer calls a whole grid not one to one where the fields' own walks chose some of its pairs
  too:** one label writing one value is one option, whatever its index, so Bracket Type's grids count 60 pairs each,
  not 78, and the writer lists them where it would have marked them disputed.
- **`carousel_fields_run.py` asks the third readers where OCR's plain reading of the lit box and the second reader's
  are two numbers,** in turn, the second reader's own question, and takes the reading that stands by the kit's one
  counting rule, its proof line keeping every vote with its reader's model ("read_by": "votes"); where none stands the
  row stops as before (OCR read a bullet for the minus sign of "2 Images (-)" on about one HDMI frame in twenty). The
  check before Enter on a box now reads it the same way, and a bullet in OCR's reading of a lit box is a doubt that the
  second reader settles.
- **A carousel option's lit box holding a long value is seen as lit,** where the pixel reader took only a box 60 %
  orange or more and "2 Images (+)" or "2 Images (-)" over HDMI leaves 58-60 % (Bracket Type's grid stopped at its first
  Down so): a box under that whose outline is whole now counts too.
- **A row's label is read to the right of the icon the camera draws before it** (a light box with letters in it, or
  a solid mark, found by its pixels and painted over for OCR), in the page model and on a crawl's submenu rows, and
  the row's `icon` says what was left out, or why the label stayed as read where that cannot be told. Where a reader
  read the page, the a1 II's scans now name S&Q Settings, ISO and IP Address Setting without a label read by eye, and
  its crawls name Record Setting where the reader read the S&Q box into it.
- **`ROW_NAMES` in a camera's hand tables names a row the records hold by an older name, its last label with an icon's
  letters in front or the kit's own name for one of two rows of a label** ("Proxy Settings > Px Proxy Recording"), and
  every comparison of a row's name takes the two as one row (the first-open procedure, `prove_run.py --rows`, the
  maps, the menu tree, each setting's place, the walk patterns, the definition's proof rows, the report, the viewer
  and the ledger), never a safety check, which judges the label the camera draws. Any other entry is refused, the runs'
  lines keep their names, and no camera's file holds the table yet.
- **`kit/provers/greyrow_run.py --in MODE --row ROW` asks the camera why a menu row is grey:** its Help first, and only
  where the guide says no more than that the function is disabled, one Right on the row for the camera's notice, then
  MENU, or the notice's lone OK where it refuses MENU, never on a row the kit may not open and never twice on one row in
  a run, however it is spelled. The blocker a notice names is a lead, never the values that grey the row, which come
  from setting each value of it with `mode_switch.py --set` and `greyrow_run.py --look`, the row's grey read with
  nothing pressed on it.
- **`drive.py` and `crawl_run.py` start and end through the kit's one session, as the provers do,** and a test fails
  any runner that downloads its start file or uploads a file outside it but the few it names with why. With HDMI eyes
  and a working feed, their check after putting the start file back reconnects once the camera is back from its restart,
  about 12 to 14 s into the check where it waited 20 s, and that watch, the provers' too, no longer takes a notice
  already on show for the restart's.
- **The third role in `private/config.json` may name several readers, `"third": ["gemma", "glm"]`, asked in turn
  where OCR and the second reader differ until two independent votes name one option;** of several, one that does not
  answer the start check is skipped for the run and said so, and one name, or none, works as before.
- **A reading neither OCR nor the second reader gave no longer stands on later votes alone** (the second OCR engine,
  the site's check or the third readers): it is refused, and `kit/pass1_map.py` sends such an option to review with
  every reading, as 7 of the 10 the a1 II's re-vote let stand were wrong.
- **One model is one vote, whatever its builds: two builds that read two things cast none, and a third reader of the
  second reader's model is not asked,** so a reading no longer stands on OCR and the third against the second when
  both readers are one model (as the quick start's old example had them), and the start check says so.
- **`kit/tiebreak.py` asks each third reader in turn and writes no line none of them answered, so a rerun asks it;**
  `kit/pass1_map.py` counts its new lines by model family, while older lines keep their winner until `kit/tiebreak.py
  RUN --revote --was MODEL` asks today's third readers about them (the old file kept beside it).
- **`kit/prove_run.py`'s carousel axis proofs take the screen after OK as its list proofs do,** an information screen
  left with MENU once the cursor is off its "Don't show this again." box (Framing Stabilizer = On: Manual), where the
  row failed. With `--eyes osd` an axis of a row in the reviewed scope's OSD group is read through the camera's own
  picture as that row's list is, not off a blanked HDMI frame, and without it is left out as the list is; `--first` on
  such an axis needs `--eyes osd-all`.
- **`kit/provers/carousel_fields_run.py --grid` proves every pair of an option's two fields, one a download, and
  `--number N` puts a named number into a digit field with no Enter on the way** (Bracket Type's Cont. and Single
  Bracket pairs, Focus Bracket's Number of Shots, each end taken only after presses the camera answered). The report
  lists the values of a record every pair of a whole grid moved, the pair held among them, where it counted them as a
  sample, and credits no named number's put-back.
- **`kit/tools/menu_tree.py --fold CRAWL` takes a later crawl's walk into the existing menu tree by label, moving no
  row of it** (rows that share a label only slot for slot), and a proof path names the second of two rows of one label
  with `#1`, which the ledger reads too, so the a1 II's Bracket Type options, Aspect Marker Disp. and movie Recording
  Media row can take the camera's order.
- **A record name in `docs/formats/sony_camset_ids_<model>_fw<fw>.ksy` is never given to another record:** a renamed
  record's old name is kept under the file's `-retired-ids`, which Kaitai's tools ignore, and the a1 II's file gives
  back the three names records lost (`jpeg_heif_quality`, `jpeg_heif_image_size`, `unknown_camera_state`).
- **A sampled record every value of which a walk chose, the one the camera held among them, is proved whole,** where
  the line that chose that one started from a file holding it (the a1 II's Playback Aspect Marker Level, published
  "sampled" beside its sixteen values).
- **A `NEW_RECORDS` entry can say `"live_only": true`:** the record is laid out of the memory sets while it says so and
  back in once it no longer does (the a1 II's 0x023c, which follows the video system), never against a copy a
  registration proved.
- **`kit/tools/label_audit.py` has every reader read again, with each kind's new question, the proof frames behind the
  names one reader or the vision model alone backs, and the checklists', star ratings' and table pickers',** and takes
  a name as confirmed only where two model families or more spell it as published. It prints counts only and keeps the
  names not every family confirmed in a private list under the camera's runs, changing nothing else.
- **A reader's Unsloth dynamic build ("UD") counts as the same model,** one vote with its other builds (decision 22).
- **A side list's options are told grey by the second reader's whole-list flag beside the pixels, a carousel's by its
  lit icon:** asked the whole list (`entries.v2`, once a screenful in the background) Qwen3.8-27B called 90.8% of grey
  side-list entries grey and no white one, so its flag adds grey there and never an Enter, while on lists it called 8
  in 100 white entries grey and a list keeps its pixels alone. A carousel's lit icon, dim red where the camera greys
  the option, told all 13 refused and 221 applied options apart and decides there, `carousel.v2.grey` asked only where
  it cannot tell (`reader_census.py --variants grey,entries`).
- **The coverage ledger keeps every record a look saw change,** where a later look of the same row, action and option
  took that look's place: such a record was left "never seen to change". The row's status is still its latest look's.
- **`kit/tools/lut_import.py --allow "Manage User LUTs" --seen-empty FRAME` imports one user LUT, a `.cube` file from
  `private/lut/`, into user place 16 through Sony's ImportLUTFile, and only where the camera's own Import/Edit table was
  seen to show it empty since the last import** (camlink's new `importlut`, decision 26), prints the settings records it
  changed, and fails its restore on any that did not go back. Only on the camera owner's word: the LUT stays until they
  delete it on the camera by hand.
- **Before a Right the kit looks at the screen once more, as before an Enter,** so the never-open check reads the lit
  row on show, never the frame the last press's settle ended on; a screen that does not read as the one the Right was
  chosen on, even once settled, gets no Right.
- **With the camera's own picture (no capture dongle) over the LAN a step settles sooner where it was measured:** 0.25
  s after the picture moved for Up and Down on a menu or submenu page's rows, 0.45 s for Left and Right on a menu page,
  where 0.75 s stood. Over USB, with HDMI eyes, on other screens and for a step that shows nothing (still 6 s), the
  waits are as they were.
- **With the camera's own picture over the LAN in Stills the menu's lock after a download ends once the shooting screen
  is back after the saving notice,** about 2.1 s where 4.5 s stood; with no notice seen, in Movie or S&Q, and over USB,
  it is still 4.5 s.
- **`kit/provers/carousel_fields_run.py` proves a carousel option's own fields one value a download** (Bracket Type's
  Cont., Single and Focus Bracket, with the drive mode dial on BRK), a value the camera does not keep written as asked
  and kept, crediting nothing. The report credits a record with both fields together ("0.5 EV 3 Img.") unless every
  field's walk finished and only one moved it, and the definition counts such a record's proofs and names it from its
  sibling's list, never from the values proved, which would tell the pair held.
- **`kit/axis_walk.py --map` walks a run's own map, and `kit/prove_run.py --map` proves the axes it walked there**
  (Bracket Type's Lo/Hi); a run on pass 1's map never takes them, and a row inside a submenu is keyed by its whole path.
- **The pixel reader tells a carousel option's lit field from the option lit:** a dialog gives the lit box's index
  among its boxes, Focus Bracket's three digit boxes told apart.
- **A run's start before its link is timed, and much shorter:** each link writes what the start took into the run's
  `events.jsonl` (`start_budget`), and `drive.py` and `crawl_run.py` went from about 9 s of work before the link to
  under 1 s, the page scan's screens kept in a cache signed with your own key, the coverage ledger built while the link
  opens and the readers checked while the eyes are made.
- **`kit/tools/upload_check.py` uploads nothing where the camera's own download shows it already holds the file,** so a
  chain's upload steps and its end file no longer restart the camera onto what it holds; `--always` uploads all the
  same.
- **Every runner waits the menu's lock after a download by the one watched rule,** about 2 s with HDMI eyes in Stills
  or Movie where 4.5 to 5 s stood, and none sleeps a second before a download any more. A key that is not MENU next
  (afreg's Fn hold, the focus frame's moves) still waits 4.5 s, as the lock was measured for MENU alone.
- **My Menu's picker lap asks the reader on several workers while it steps on,** and the lap it keeps is taken again
  only in the shooting mode and with the page scan it was made with.
- **The axis walk, the Picture Profile carousel and Creative Look's icons wait for the title strip over HDMI** instead
  of a fixed 0.4 s.
- **The settle's windows are one table per eyes, by key, at today's values,** and `kit/tools/settle_probe.py` measures
  them, and the lock after a download, on the camera, read-only, with HDMI or OSD eyes.
- **`scale_run.py` asks the vision reader where OCR misreads the number drawn over a picture slider** (Aspect Marker
  Level's 8 read as "00"). The marker's number stands only when the reader reads it too, and the proof line then keeps
  OCR's reading as `ocr_outvoted`.
- **The coverage to-do sends a row no look lap chooses in, once it has been looked at, to the owner's hand** instead
  of back to another look.
- **No reader credits a line the camera did not apply, and an option a list draws grey is never chosen:** the list and
  side-list provers write such an option greyed, with the camera's Help as its reason and no key pressed. The ledger,
  the report, the writer, the proof viewer and `replay_proofs` never credit a line with `"applied": false`, an old
  refused line carrying the diff of the option before it among them.
- **A side list's put-back the camera will not let back ends its attempt** (a Picture Profile's Color Mode proved with
  its Gamma on HLG, which greys the value it held): pass 2's report no longer leaves the attempt's lines out, and its
  failure re-arms no older failure of the same row.
- **"Nothing changed" credits a record only from a session whose lines move it:** a session made with Different Set
  for Still/Mv's box ticked, where a Stills choice leaves the movie copy alone, no longer names the copy's start value
  after one of its options (the a1 II's ISO AUTO Minimum and Exposure Comp. movie copies).
- **A put-back never takes the place of the line that proved its option:** a later line that only puts its session's
  start back no longer hides an earlier line of the same option that wrote (the a1 II's Exposure Comp. +2.7 EV on its
  movie copy).
- **A value the setting's `video_system_values` lists under the other video system is no list one value short,** as
  a not-offered mark is none (the a1 II's USB Streaming output rate under PAL).
- **A refusal takes the place of an applied line that only repeated the line before it,** so a code is no longer named
  twice from such a line ("BT.2020 / S-Gamut3" on Color Mode, "Flash Off / Rear Sync." on Flash Mode).
- **The ledger's private form infers a view-only readout's value** ("inferred from a shared list") where a proof chose
  it on the setting of the readout's row whose codes it holds (the a1 II's ISO in use), never proved and never in the
  definition.
- **Every write checks for a public list one value short** (`kit/writer/listgaps.py`): the gate line counts each, and
  `--write` refuses one whose missing value a start file of the camera held until a proof, a held not-offered mark or
  an unproved reason closes it; one no start file held is accepted by a ruling of kind "one value short".
- **A public proof marks a setting once where part of its list was named from another setting's proof**
  (`proved.shared`, decision 25): the writer names values afresh at every write, counts a name only a hand table gives
  and lets a copy take its setting's established values. The coverage ledger reads the writer's inference instead of a
  rule of its own (decision 23).
- **Every runner's session goes through one session manager,** whose start is the one place a start file is
  downloaded, the lock after it a watched wait where a fixed 5 s stood; `drive.py`, `crawl_run.py` and
  `take_picture.py` keep their own.
- **`kit/tools/chain.py` stops at the first step that fails;** a step marked `go_on_after_error = true` lets it go on
  only after an error the kit gives no meaning.
- **Cont. Play for Interval and Zoom act as they open,** so a look lap leaves them to the owner's own run, and the
  ledger counts both actions. A plain crawl keeps what a row's notice names (a blocking row's
  label, equipment or a remote session, never a value).
- **An owner decision's `"values": "logged"` no longer keeps the serial number screen's frames:** that screen is always
  saved black, as decision 8's body now says too.
- **Smaller fixes:** a notice or shooting screen over a dark scene is no longer taken for a black frame, so a capped
  lens's notice no longer ends a first open with `RESTORE_BY_HAND`, while a blanked HDMI frame stays black. `drive.py`
  takes the `--path`'s own row inside a submenu (its first open too) where the page read live ties the lit bar to it,
  and one read with a space before its bracket, and `--stepped` records that a look stepped its row's value; "Select
  media card." reads as boxed options, and a slider drawn over a picture as a slider, its number read off its marker
  on the scale's ticks.
- **The private hand evidence records what proved each direction of a limit pair** (`LIMIT_PAIRS`, its `"evidence"`
  by direction): where that file is present, a direction the hand table marks is written with `moves_it` only where
  its evidence is given, and the writer says so otherwise.
- **Smaller fixes:** the proof viewer shows the page an option opens in the definition's order (Zebra Level's Custom
  boxes: Type, Standard, Range, Lower Limit), and `framepos_run.py` records a press as refused only where it never
  went, any other link error stopping the run as a lost link does, the restore running as before. CONTRIBUTING says
  the kit's whole suite runs once in the clone that holds `private/` and `runs/` before a kit change lands, a test that
  needs the owner's config asking for it with the `owner_config` fixture.
- **Every prover judges what an OK did in one shared step:** `prove_run.py`, the axis, bracket, scale, portrait,
  two-box, option-boxes, grid and Shoot Mode provers and pass 3's switch write a choice the camera refused as
  `"applied": false` with its notice, closed with MENU, where several credited the label with the value kept before,
  and an information notice no longer counts as a refusal. A panel's slider (Monitor Brightness, Viewfinder Bright.)
  takes its OK again, by a consent judged on the panel's own shape, and pass 3's walk and proofs take the page scan
  the run was given.
- **Labels that differ by a point, a sign, a number or a short word are no longer one option:** 1.3" and 13", F1.1
  and F11, +0.3 and -0.3 EV, 1 Sec and 2 Sec stay apart, and a reading that cannot tell two options apart is a doubt,
  so the reader is asked again or nothing is chosen. A pass-1 label read with a mark before it (a radio ring read as
  "0 1 (Fast)") no longer matches the screen: correct it by eye in the crawl's `checked_labels.json` and make its map
  again with `kit/pass1_map.py <crawl> --own`.
- **The definition says which two settings the camera keeps in order (`at_most`, `at_least`):** the hand tables name
  the pairs (`LIMIT_PAIRS`), and both writer passes put each on its two settings where they list the same values and
  sit in the same sets, a camera download holding a pair out of order stopping the write. On the a1 II these are ISO
  Range Limit, its lower records now named "ISO Range Limit (lower)", and ISO AUTO Minimum and Maximum with each
  mode's copies.
- **A number field, box, grid or sampled scale every value of which a line of its own rows chose and saw written is
  proved with its values,** no longer filed as a sample (the a1 II's ISO Range Limit). `kit/rebuild.py` makes the
  report again before each further write, so a record first named in a write is credited by the next, and lists each
  file it changed once, with one line for those it rewrote unchanged.
- **Smaller kit fixes:** `drive.py` reads a lit bar's label behind its icon where OCR spells the icon as another row's
  letter, a run whose eyes cannot open says the run did not start, and `prove_run.py --eyes osd-all` takes an OSD
  page scan whatever eyes the config names.
- **One path for a new body, in the docs:** AGENTS.md, the quick start and the playbook take a mapper from quick
  start steps 0 to 6 through the playbook's section 16 and back to steps 7 to 9, then Phase 1, and the playbook now
  says what to do after a camera reset, how to reach the state a proof needs, the whole rebuild order and what the kit
  cannot yet do on a body other than the a1 II. Statements that disagreed with the tools now agree, among them why
  HDMI capture is held at 1080p (the pixel reader misreads option screens at 2160p).
- **`kit/rebuild.py --camera <model>_fw<fw> [--write]` runs the whole rebuild in order:** a look by default (pass 2's
  report and the writer's gate line, nothing written), and with `--write` the write until it changes nothing (three
  at most), the docs, the leads, the ledger and the editor's golden menu, stopping at the first step that fails. The
  definition is written one setting a line, the same JSON (the a1 II's 2.2 MB instead of 3.4 MB), so its diffs read
  setting by setting, and a ledger build takes about 5 s instead of 34 s.
- **The writer and the report:** an option's own row of boxes (Zebra Level's Custom 1 and 2) is placed in the order
  the camera draws it, Type first, and a live setting whose record a memory set's own setting describes is kept out
  of the sets, so a set shows that record once. The pass-2 report keeps a point, colon or slash between digits when
  it compares labels, so 1.3" and 13", F1.1 and F11 or 1/250 and 1250 no longer pass as one label.
- **Limits that move each other, and pass 3's switches:** where a choice in one of two limits that hold each other in
  order (ISO Range Limit, ISO AUTO Minimum and Maximum) also moves the other, the proof line says so (`moved_other`),
  the report leaves those records out of the choice's own, and the other is chosen back through the menu and checked
  before the next proof (`prove_run.py --field K` proves one number field alone). Pass 3 checks that a blocker's
  switch took: a refusal or a question after OK, or a download with no record of the switched row changed, stops the
  blocker, so nothing is walked or proved in a state the camera was not in.
- **The readers:** a vote counts once per model family, the start check says when two reader roles are one family,
  an answer another model gave is kept and voted under that model, and every question refuses a black frame and
  pauses a reader that failed twice running, so a hung reader costs one timeout. `go_to` takes the row named exactly
  before a loose match and reads the bar on arrival, the axis seek asks no reader where OCR plainly names another
  option, the two-box prover asks for the lit box's value, and the OCR cache keeps the 4096 frames used last.
- **Keys and the link:** a screen read that fails after a key went is no longer taken for the camera refusing it, so
  the key is never sent twice and `drive.py`'s armed or first-open press keeps `RESTORE_BY_HAND.json`. Every command,
  reads and the last download among them, now waits out the camera's network error (75 s at most, then plain words),
  and `drive.py` ends through the shared session end, so a STOP, a Ctrl-C or a link error there still restores.
- **Presses and scans:** every MENU from the shooting screen goes through one helper that looks again before a second
  MENU and, with HDMI eyes, waits for the menu page, and a press is judged on a frame no older than half a second,
  again on a fresh one when a reader call took long. A page scan records its eyes, a runner takes a scan of its own
  eyes (a named scan of other eyes stops before the link opens), and `page_scan.py`'s Right into the rows meets the
  never-open check.
- **Exit codes and smaller fixes:** `upload_check.py` exits 4 when its restore does not check out, and `chain.py`
  exits 1 for a failed step, 4 when the end file did not go back and 5 after a restore by hand, stopping at an upload
  that did not check out. `mode_switch.py --keep` refuses while a switch waits in any run folder, eyes that cannot
  open before anything was sent exit 1 instead of 4, no test reaches the camera or reads the owner's config unless it
  asks for it, and the migration tools (`migrate_runs.py`, `move_evidence.py`) are retired.
- **The coverage ledger infers what a shared list already shows** (decision 23): a slot's value another slot of its list
  is proved on counts "inferred from a shared list" in the private form once the slot's own record agrees on two values
  and no proof reads one otherwise (`kit/tools/coverage.py --shared` shows the grounds, `--todo` counts them apart). A
  row a proof went through now holds the setting it proved, so a setting the camera shows under two pages is proved
  under both.
- **The ledger's to-do list counts what is really left:** each value once on its setting's row, a look's changed
  records only where no setting maps them, no "(withheld)" row another crawl names, no field's closing proof as a test,
  and a row below one Sony's Save/Load list excludes as not in the file either.
- **`kit/schema_update.py` takes `optboxes_run.py`'s boxes:** a box's numbers as the camera draws them (Zebra's
  "±5", "100+") are numbers proved by samples on their line, never listed, and once a `RECORD_FIXES` range is
  there every number of it is named as drawn. A `RECORD_FIXES` entry can also give a setting's `inactive_when`, the
  other setting's values under which the camera leaves it out.
- **`kit/provers/optboxes_run.py` proves a list option that draws its own row of boxes,** such as Zebra Level's Custom
  1 and Custom 2: `--probe` walks each box to its ends and chooses nothing, then the proof run keeps a few values of each
  box with OK and puts the start file back.
- **`optboxes_run.py` checks after every press that its cursor is still in the box it means,** and stops at once
  otherwise: an earlier probe pressed Right past the last box and walked the list as if it were a box, so run the probe
  again before a proof run (a probe now writes its line only when it read every box).
- **HDMI eyes take a dongle that offers another size than the crop was measured on:** put its mode under `"capture"`
  in `private/config.json`'s `"hdmi"` and the kit scales the crop to it. A mode the dongle refuses is now said in plain
  words, with the modes it offers.
- **A run now survives a network error the camera reports on its remote link:** it sends nothing until the link
  recovers by itself, about a minute later, then cancels with MENU and restores, where it closed the link and left the
  camera unrestored. The error says so in plain words and names the screen that was on show.
- **The kit no longer presses Enter on a screen that asks something, whatever its words or language, unless the run
  names that screen.** `drive.py --confirm` now takes the screen's text and covers one press, and formatting or
  deleting a card needs the owner route (`drive.py --owner`).
- **A menu row the kit has never opened on your camera now opens only once you have said your cards hold nothing you
  want kept (`kit/tools/owner_statement.py cards`), and so that a lost link can be put right; `kit/tools/take_picture.py`
  takes one picture for the Playback rows, only when you answer its question at your own terminal.**
- **A coverage ledger** (`kit/tools/coverage.py`, decision 23) says for every menu row, value and record what is
  settled and what is left (`--todo`); `--write` writes a seen file into the data folder (the facts your looks
  established, nothing of your camera's state), `--print` prints the public form built from it and the public sources,
  and `--check` says whether both are lean. `drive.py`, `crawl_run.py` and `prove_run.py` print what it says of a row
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

- AGENTS.md's rules that are never broken are written by `kit/tools/build_docs.py` from the decision records marked
  Never broken, each rule's whole text pinned by a test; the playbook's section 1 keeps how an owner allows more.
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
