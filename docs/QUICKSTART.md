# Quick start: from nothing to a first proved setting

This page gets an agent, or a person, from a fresh machine to one setting proved on the camera, in
about an hour. It is the short path only. Every step links into `REMAPPING_PLAYBOOK.md`, which
explains why. **Read the playbook's section 1 (the rules) before step 5.**

Already mapping with a clone? Update it first, as [UPDATING.md](UPDATING.md) says: every clone moves to the lean files
once, and one made before the repository's history was replaced by a single commit is moved onto the new commit
before that.

## What you need

**The body check** at the end of step 1 says whether the kit can drive your camera (what its answers mean:
`CAMERA_SUPPORT.md`).

- **A computer** that Sony's SDK page lists: a Mac with macOS 14.1 or later; a Linux PC (on Ubuntu 26.04 the setup,
  the tests and the editor's camera helper ran, the kit's camera runs not yet); or a Windows 11 PC on Intel or AMD
  (not yet tried). On Linux and Windows, `PORTING.md` has the setup and its first-day checks.
- **Software:** Python 3.11 to 3.14 (the `python3` macOS ships is older: install one, for example with
  `brew install python@3.14`), CMake, a C++ compiler (the Xcode Command Line Tools on a Mac, Visual Studio 2022 or
  2026 with the C++ workload on Windows, g++ on Linux) and git. Step 1's `kit/setup.py` checks each and prints the
  command for what is missing.
- **The camera,** with:
  - the lens cap on;
  - two test cards inserted;
  - mains power, where there is a socket.
- **A USB-C data cable** to the camera, with the camera's USB Connection Mode set to PC Remote (the editor's
  Connect to the camera lists the camera's steps for each link). Wired LAN (with Remote Shoot Function and
  Access Authen. on; the owner sets them up) is an alternative to USB, not a requirement; the kit's camera link
  has no Wi-Fi mode yet.
- **Eyes,** the way the kit sees the screen. The baseline is the camera's own OSD image through the SDK, on
  bodies that have it (the body check says): set `"eyes": "osd"` in `private/config.json`
  ([`CAMERA_SUPPORT.md`](CAMERA_SUPPORT.md#without-an-hdmi-capture-dongle) says how it works and what it costs).
  **An HDMI capture dongle is optional** (Elgato Cam Link 4K, with the camera's HDMI set to 1080p, and a
  micro-to-full HDMI cable for bodies with micro-HDMI): it is faster, and needed only on bodies without the OSD image.
- **Readers:** OCR is built in, but it misreads icons as letters, clips short words and confuses look-alike
  letters, so at least one vision-language model (VLM) is needed as well: one on your own computer or server
  first, a smaller local model if that cannot run, a paid service last. You choose it, and pay for it if it
  costs money ([Choosing a reader](#choosing-a-reader), in step 3). More readers give better labels
  (playbook, "Readers: accuracy before speed").

## 0. Ask the owner first

Ask three questions before installing anything:
1. **Which camera?** The name on the body ("a7 IV") or the model number ("ILCE-7M4").
2. **How will it connect?** A USB-C data cable, Ethernet, or Wi-Fi.
3. **Is there an HDMI capture dongle?** If not, the kit can watch the camera's own screen image
   (OSD) on a body whose SDK support has it.

The body check at the end of step 1 answers them from Sony's own tables: it needs the SDK, which step 1 unpacks.

## 1. Install, then check the body (about 15 minutes)

The Sony Camera Remote SDK cannot be redistributed. Download it from Sony (Camera Remote SDK v2.02
or later, the zip for your system; the README's "The camera helper" says where), put the zip as it is into
`kit/sdk/`, then run from the clone's root:

```sh
python3 kit/setup.py              # on Windows: py kit\setup.py; --check only reports
```

It unpacks the SDK, checks the tools, makes `.venv` and the hooks, builds the camera link, the camera helper and
(macOS) the OCR helper, and runs the tests, which must pass before any camera work. A DO line is yours to do, with its
command; one that needs another window or administrator rights comes as numbered steps. The setup does not wait for
a DO: it carries on with the other steps, and its last lines, after the table, list what is left for you, in order,
ending "Then run ... again". A step that takes a while says roughly how long before it starts and shows a progress
line while it runs (the tests take some minutes); Ctrl+C stops it safely, and the next run goes on from there. Run it
again until it says "the kit is set up". By hand: PORTING.md, "Setup per OS".

With an HDMI capture dongle, also install ffmpeg (`brew install ffmpeg`; Windows, Linux: PORTING.md).

On Windows the kit runs only in Python's UTF-8 mode, and the setup stops until it is on: with `PYTHONUTF8` set to 1,
or not set at all when the kit's Python is 3.15 or newer, which has it on by default (`PYTHONUTF8=0` turns it off).
Once per PC:

1. Run `setx PYTHONUTF8 1` (it answers that the value was saved).
2. Open a new terminal and keep the first one open for now: the setting reaches only windows opened afterwards. To
   check the new window, `echo %PYTHONUTF8%` in Command Prompt or `echo $env:PYTHONUTF8` in PowerShell prints 1.
3. In the new window, go to the clone's folder (Command Prompt: `cd /d "<clone>"`; PowerShell: `cd "<clone>"`) and
   run `py kit\setup.py` again. Once it runs there, the first window can be closed.

Sony's USB driver is installed once per PC, as administrator; the setup finds it once it is installed (it asks
`pnputil /enum-drivers`, which needs no administrator rights) and prints the steps until then.

On macOS:
- Run from Terminal.app, not tmux: Local Network privacy blocks the camera otherwise.
- Remove the quarantine attribute from the SDK libraries if Gatekeeper complains.
- `ptpcamerad` grabs USB cameras; the link kills it before each attempt.

### Check the body

With the owner's three answers (`--link usb`, `lan` or `wifi`; `--eyes osd` or `hdmi`):

```sh
mkdir -p private/data                                     # your own folder, git-ignored (decision 18)
.venv/bin/python kit/tools/sdk_support.py --json          # Sony's support table, from your copy of the SDK
.venv/bin/python kit/tools/body_check.py --model "a7 IV" --link usb --eyes osd
```

`sdk_support.py --json` writes the table into `private/data/` (`.cache/` when there is no `private/data/` folder),
kept out of the public repository: Sony's reference may not be redistributed. Run it again when a new SDK version
arrives. `body_check.py` answers everything, settings files only, or nothing (what each means: `CAMERA_SUPPORT.md`,
"The short answers"). It also names anything that won't work, such as Ethernet on a body that has no port, or the
OSD on a body without one, and prints the settings for steps 3 and 4. Stop here if it says "Nothing"; otherwise go
on with step 2.

## 2. Credentials (the owner's job)

- **Camera, over the network:** the owner writes the camera's access-authentication user and
  password into `~/.config/camset/network.json` (`{"user": ..., "password": ...}`, mode 600), on
  each computer they use: the file stays on the computer it was written on. With more than one
  camera, each can have its own pair under its MAC address beside that default pair
  (`"cameras": {"AA:BB:CC:DD:EE:FF": {"name": ..., "user": ..., "password": ...}}`). Which pair a
  camera gets is in `EDITOR.md`, "The camera link"; the camera link and the editor's helper use the
  same rule, and the editor's Save writes the same file. The agent never reads them off the camera
  or types them.
- **2026-11-05:** `network.json` must be readable by its owner only: the camera link and the editor's helper refuse
  one that other users of the computer can read, and say how to make it private (the editor's Save does). Beside it,
  `~/.config/camset/known_cameras.json` (mode 600, written by the camera link and the helper) holds the fingerprint
  each camera showed at its first successful connection; a login goes only to a camera whose fingerprint matches.
  After a reset of the camera's network settings, forget it in the editor (Connect to the camera, Known cameras,
  Forget) and connect again.
- **Claude as a reader:** `brew install anthropics/tap/ant`, then `ant auth login`. Or export
  `ANTHROPIC_API_KEY` in the shell profile.
- **Another hosted reader:** export its key in the shell profile, under the name the reader's
  `api_key_env` gives (step 3).

## 3. Configure `private/config.json`

Copy `kit/config.example.json` to `private/config.json` (the folder for your own setup, which git
ignores; decision 18) and fill it in. Without it a camera run stops and says so: the kit never uses the example's
addresses, and with no config at all the eyes are the OSD. A copy left as it is names nothing to contact: its
`camera_ip` is empty, so a run over the network stops and asks for it (with `CAMSET_USB=1` the kit connects over USB
instead), and its `readers` lists none, so a run that asks a reader (the crawl, the proofs, the walks) stops before it
presses anything and says to choose one.

```sh
mkdir -p private && cp kit/config.example.json private/config.json
```

- **`camera_ip`:** the camera's address on the LAN. **Over USB** the config has no setting: run
  `export CAMSET_USB=1` in the shell the kit runs from, and every command below then uses USB (step 4).
- **`eyes`:** `"osd"` (the camera's own screen through the SDK, the example's default) or `"hdmi"` (a capture
  dongle). `CAMSET_EYES` overrides it for one command.
- **`hdmi`** (with `"eyes": "hdmi"`): the dongle's name (`device`), `size`, `fps` and the `crop`
  that maps the camera's UI to 640x480.
- **`camera_model`** (LAN only, optional): the SDK's model number, for example `"ILCE-1"`. The
  default is `ILCE-1M2`.
- **`camera`** (optional): which camera the kit works on, as `<model>_fw<firmware>`, the key step 4 prints (for
  example `"ILCE-7M4_fw2.00"`). Each camera's runs go into a folder of their own, `runs/<model>_fw<firmware>/`
  ([Where the runs go](#where-the-runs-go)). With one camera you can leave it out: step 4 starts that camera's
  folder, and while `runs/` holds one camera's runs the kit takes that one.
- **`cameras`** (optional, for more than one camera): one entry per camera, `{"model": ..., "firmware": ...}` and
  any of the keys above that differ for it (`camera_ip`, `camera_model`, `hdmi`, `eyes`); `camera` names the one in
  use, and its keys are laid over the others. `kit/config.example.json` has an example under `cameras_example`,
  which the kit does not read.
- **`ocr`** (optional): `"apple"` (the Mac's default) or `"rapidocr"` (the default elsewhere).
- **`readers`:** one entry per VLM ([Choosing a reader](#choosing-a-reader), below).
  - An OpenAI-compatible server: `{"name", "url", "model", "parallel"}`, plus `"api_key_env"` for a
    hosted one.
  - Claude: `{"name": "claude", "kind": "anthropic", "model": "claude-opus-5-5", "parallel": 4}`.
- **`roles`** (optional): `{"second": ..., "third": ...}`, naming which reader gives the second
  reading and which breaks ties. The reading rule ([decision 22](decisions/0022-ocr-alone-only-for-a-plain-reading-the-reader-on-every-doubt.md))
  counts the third as a vote of its own only when its `model` differs from the second's, compared without case or
  surrounding spaces: the kit cannot tell the same weights under two ids apart, so give one model one id.

### Choosing a reader

The kit reads the camera's screen with OCR and with at least one vision-language model (VLM), an AI model that reads
images. The VLM is required, not optional: OCR alone reads icons as letters, clips short words and confuses
look-alike letters ([playbook, section 5](REMAPPING_PLAYBOOK.md#5-readers-accuracy-before-speed)). You choose the
VLM, and you pay for it if it costs money. A full map makes thousands of reads: every proof of a stills pass, which
runs to thousands, gets a second reading, besides the page and option labels (the figures: playbook, sections 5 and
11). Answers are cached by frame, prompt and model, so a frame is read once per model. The order, which is also
cheapest first: a model on your own computer or server if the hardware allows, a smaller local model if it does not,
a paid service last. A hosted reader receives screen captures of the camera's menus, which can show names, network
settings and the like, so prefer a local model when the menus hold such things.

1. **A model on your own computer or server,** free once you have the hardware: an OpenAI-compatible server such as
   Ollama, LM Studio, vLLM or omlx, running a VLM, with `url` ending in `/v1`. This project's proofs on the ILCE-1M2
   used Qwen3.8 27B: `RedHatAI/Qwen3.8-27B-INT4` through vLLM on a GPU server and `Qwen3.8-27B-4bit` through omlx on
   a Mac (playbook, section 5). If your hardware cannot run a 27B model, try a smaller vision-language model from
   the same family; smaller models are untested here, and so are Ollama and LM Studio.
2. **Claude through the Anthropic API** (`kit/camkit/claude_reader.py`): the Claude entry above, with
   `ANTHROPIC_API_KEY` or `ant auth login` (step 2). Every read that is not cached costs money.
3. **Another hosted service with an OpenAI-compatible API** (OpenAI, Google's Gemini through its OpenAI-compatible
   endpoint, others): an entry as for a local server, with the service's base URL (the kit adds
   `/chat/completions`) and `"api_key_env"`, the name of the environment variable that holds your key. The kit reads
   that variable when it sends a request and puts the key in the request's `Authorization: Bearer` header only;
   it never writes the key anywhere. Every read that is not cached costs money. **Untested here:** no hosted
   OpenAI-compatible service has been tried with the kit (2026-11-04). Its request also carries vLLM's
   `chat_template_kwargs` (thinking off), `temperature` 0 and `max_tokens`, which a service may refuse; a refused
   request comes back as an error from that reader.

`kit/config.example.json` has one entry of each kind under `readers_examples`, which the kit does not read: copy the
ones you choose into `readers`, which is empty until you do, and put your own server's address in a local one's `url`.

## 4. Identify the camera and its file

Over USB, run the first line too (step 3): every command from here on needs it, in the same shell.

```sh
export CAMSET_USB=1                               # over USB only (step 3)
.venv/bin/python kit/tools/identify.py --camera
```

This prints the model, firmware and lens (the serial number is never shown), downloads the
camera's settings into that camera's own folder, `runs/<model>_fw<firmware>/kit2_identify/`, and prints the file's
layout fingerprint and the camera's key ("this camera is ILCE-7M4_fw2.00"). When `private/config.json` names no
camera, or another one, it says what to put in it. Then it says one of three things:

- **KNOWN ... definition ..., model page ...:** this body and firmware are mapped: its definition
  (`editor/definitions/<model>_fw<fw>.json`) knows the file's layout. Read the model page in `docs/models/` before
  going on.
- **Same model, different layout:** a firmware update moved records. Treat the old definition as
  hints only.
- **UNKNOWN layout:** a new model or firmware. Follow the playbook's "New model: first day": its
  results go into a `data/<model>_fw<fw>/` folder and a model page of their own, and at the end
  `kit/schema_update.py --write` writes its own definition, `editor/definitions/<model>_fw<fw>.json`, which the
  editor takes with Add definition… (AGENTS.md).

When no known container block reads the file, identify.py says so and prints a draft block, with what holds under it
and what does not: correct it by hand into the camera's `data/<model>_fw<fw>/camera_<model>_fw<fw>.json` ("file";
[the container block](DATA_CONTRACTS.md#the-container-block-file)) and run identify.py again until the file reads
and both checksums hold.

`kit/tools/identify.py FILE.DAT` does the same for any saved file, with no camera needed.

### Where the runs go

Everything the kit records for a camera goes into that camera's folder, named as `data/` names its folders:

```
runs/
  ILCE-1M2_fw4.00/   kit2_pass1/  kit2_pass2/  ...  _viewer/  _cache/  downloads.jsonl
  ILCE-7M4_fw2.00/   kit2_identify/  kit2_page_scan/  ...
```

A second camera's runs never mix with the first's, and a download of one is never uploaded to the other. The kit
works on one camera at a time: `"camera"` in `private/config.json` (step 3), else the one camera in `runs/`.
`--camera <model>_fw<firmware>` on any kit command, or `CAMSET_CAMERA=<model>_fw<firmware>` in the shell, works on
another one for that command (identify.py's `--camera` alone asks the connected camera).

A run named on a command line is a folder in the camera's own runs: `kit2_crawl`, `kit2_crawl/map.json`,
`kit2_pass2/dat/00001_start.DAT`. A path that is there as written, such as `runs/ILCE-7M4_fw2.00/kit2_crawl`, works
too. The commands below are written that way; `$CAM` stands for your camera's key:

```sh
CAM=ILCE-7M4_fw2.00                               # yours: the key identify.py printed
```

**Runs from before 2026-11-05** sat at the top of `runs/` (`runs/kit2_pass2`, `runs/_viewer`). The kit no longer
uses them there: every kit command that reads or writes runs stops and names the command that moves them under
their camera's folder. It renames, copies nothing, deletes nothing, and moves nothing if any of them is already
there. Look at the plan first:

```sh
python3 kit/tools/migrate_runs.py --dry-run                        # the plan: what moves, what stays
python3 kit/tools/migrate_runs.py --camera ILCE-1M2_fw4.00         # the a1 II's runs into runs/ILCE-1M2_fw4.00/
```

Entries it does not know as the kit's (older tools' runs, logs of your own) are listed and left at the top of
`runs/`; `--all` moves them too, once the list shows they are all that camera's.

## 5. Keep the owner's file safe

Step 4 downloaded the camera's settings into `runs/$CAM/kit2_identify/dat/`, as `NNNNN_identify.DAT`. That download
is the owner's file: every session ends by uploading it back. Leave it where it is: only files the camera wrote are
uploaded. Each download's SHA-256 goes into the camera's `runs/$CAM/downloads.jsonl`, and `kit/tools/upload_check.py`
and the link refuse a file whose bytes are not a download of that camera's, wherever it is (decision 6).
Note its name:

```sh
OWNER=$(ls -t runs/$CAM/kit2_identify/dat/*_identify.DAT | head -1) && echo "$OWNER"
```

Next, a **start file**: the camera's settings in the state the runs start from. With `"eyes": "hdmi"` that state has
the camera's HDMI output at 1080p, so the capture works. If it is not, set HDMI Resolution on the camera, then
download the new state and compare it with the owner's file:

```sh
.venv/bin/python kit/tools/upload_check.py --diff "$OWNER" start --run kit2_pass2
```

That saves the download as `runs/$CAM/kit2_pass2/dat/NNNNN_start.DAT` and lists the records that differ (only the
HDMI ones should). It is the start file. If nothing needed changing, the owner's file is the start file too. Nothing has to
be uploaded now: before each run, `kit/prove_run.py --start` checks the camera against the start file and uploads it
only if they differ (playbook, "The proof, and how runs are shaped").

## 6. Check the eyes

```sh
.venv/bin/python kit/tools/selftest.py           # MENU open and close only, with the configured eyes (--eyes hdmi|osd, --no-press)
(cd kit && ../.venv/bin/python -m camkit.safety)  # review what the walker will never open
```

The self-test must read the shooting screen and a menu page. If it can't, recalibrate the HDMI
crop, or recut the battery templates from the new camera's own frames (playbook, "New model: first
day").

## 7. Map the menu: scan, read and crawl one row

```sh
.venv/bin/python -u kit/page_scan.py --mode Stills --run kit2_page_scan   # Down only, one full lap
.venv/bin/python -u kit/page_model.py --vlm kit2_page_scan
.venv/bin/python -u kit/crawl_run.py --start-label "Grid Line Display" --limit 1   # one row, read-only
```

- The scan must end with `LAP complete` and `cycle written`.
- `--mode` says which shooting mode the camera is in (Stills, Movie, S&Q: each has a menu of its own), and the
  scan records it. A prover takes by default only the latest scan of the mode it works in, once its lap is whole and
  `page_model.py` has built its page model after it; a scan that records no mode (one made before 2026-11-11) only
  when `--scan <run>` names it, or once `kit/page_model.py --mode Stills <run>` has recorded the mode it was made in.
  Give each mode's scan a run of its own: the scan refuses a folder that holds a scan recording no mode or another
  one.
- Labels the readers disagree on are listed by `page_model.py`. Read them off the frames into
  `runs/$CAM/kit2_page_scan/checked_labels.json` and run `page_model.py` again.
- The crawl must end with `0 records differ from the start file`: walking a row read-only changed nothing.

## 8. Prove one setting

The prover takes its exclusions from the reviewed scope, `runs/$CAM/kit2_pass1/pass2_scope_draft.json`.
On a new machine, copy `data/pass2_scope_template.json` there and review it (playbook, "Order of
work", Phase 1). Until then it falls back to the template.

```sh
.venv/bin/python kit/pass1_labels.py kit2_crawl && .venv/bin/python kit/pass1_map.py kit2_crawl
.venv/bin/python -u kit/prove_run.py --map kit2_crawl/map.json --rows "Grid Line Display" --start kit2_pass2/dat/NNNNN_start.DAT
```

The output names, for each option, the record that changed and its old and new values. The held
option proves last with "no change", and the run ends with `0 records differ from the start file`.
That is a proved setting.

## 9. End the session

```sh
.venv/bin/python -u kit/tools/upload_check.py "$OWNER"  # the owner's file, the download step 5 named
```

Only the records a file cannot set may differ, and the tool names them. Then follow the playbook's
"Order of work" for the full mapping.

## Command cheat sheet

The steps above show the install and build (step 1), the camera checks (step 6) and a first scan, crawl and proof
(steps 7 and 8); the rest is here. Every kit command runs with the kit's own Python (`.venv/bin/python`, on Windows
`.venv\Scripts\python`); one started with another Python that lacks the kit's packages, or older than 3.11, stops and
prints the command to run instead.

```sh
mkdir -p private                                                         # your own folder, git-ignored: config, camera files, help text, SDK table (decision 18)
python3 kit/setup.py --check                                            # what is set up, changing nothing (--force: build from clean; --editor: the editor too)
(cd editor && CAMSET_INTERNAL=1 sh packaging/build_macos_app.sh)          # the internal macOS app, into editor/target/dist-internal: never to be published
.venv/bin/python kit/tests/score_screen.py --every 10                    # pixel reader vs OCR on the corpus
.venv/bin/python -u kit/table_walk.py --rows "My Dial Settings"          # read-only walk of a table / Fn Menu / Custom Key
.venv/bin/python -u kit/prove_run.py --tables --picker-sample --start kit2_pass2/dat/NNNNN_start.DAT   # prove what they walked
.venv/bin/python -u kit/prove_run.py --map kit2_play2/map.json --rows "Rating Set(Custom Key)" --retry-failed --start kit2_pass2/dat/NNNNN_start.DAT
.venv/bin/python -u kit/page_scan.py --camera ILCE-7M4_fw2.00 --mode Stills --run kit2_page_scan   # any command: another camera's runs, for this command
python3 kit/tools/migrate_runs.py --dry-run                              # runs from before 2026-11-05: the plan to move them under their camera
.venv/bin/python kit/tools/build_docs.py [--check]                     # the committed generated files, the reader and the viewer (--check: lists the stale ones)
.venv/bin/python kit/schema_update.py [--write]                         # the active camera's definition from its runs (playbook, Phase 6)
.venv/bin/python kit/schema_update.py --drop-stale [--dry-run]          # show (by key and field) and remove the evidence file's "stale" section
.venv/bin/python kit/tools/move_evidence.py                            # once: your menu tree, accepted rulings and record shapes from data/ to private/evidence/
.venv/bin/python kit/provers/mode_switch.py --forget --shows "Stills M" --run kit2_pass2   # a left-over switch record, saying the mode the screen shows (family first); nothing sent
.venv/bin/python kit/tools/build_docs.py --write-schema                 # the same, then the generated files
.venv/bin/python kit/tools/build_docs.py --definitions                  # every definition's parts from data/ (after editing a camera file), no runs
.venv/bin/python kit/tools/proof_viewer.py --open                      # definition -> the frames that proved each value, in the browser (your camera's runs only)
.venv/bin/python kit/tools/proof_viewer.py --pack [--png] [--open]      # the same, with a copy of its frames beside the page
.venv/bin/python kit/tools/proof_viewer.py --public --out site/viewer   # the definition viewer, for anyone: every definition and its sample, public files only
.venv/bin/python kit/tools/proof_viewer.py --public --single --out site/camset-viewer.html   # the same as one file that opens from disk
.venv/bin/zensical serve                                                # the docs site, Status and Memory map rendered from the definitions
.venv/bin/pre-commit run --all-files                                    # what the pre-commit hook checks before each commit
```

The proof viewer is for whoever ran the kit on their camera: it shows that camera's own screens, from its runs, so
it exists only on the computer that holds them, and it is never part of a submission (a pull request carries the
camera's definition and its `data/` folder, never the runs). A clone where the kit has not run on a camera gets no
page: `proof_viewer.py` says so, with what would make it available, and writes nothing, and `kit/setup.py` reports
the proof viewer as not built. Where the kit has run, the page is built in the camera's folder of runs
(`runs/<model>_fw<fw>/_viewer/index.html`) from the definition of the camera the kit works on, or the one
`--definition <model>_fw<fw>` names; another camera's runs never hang on a definition, so with another camera named
there is no page. Each value's two proof pictures come in the order to read them: the screen after OK first (the row
shows the value, or the round dot is on it), then the option list before OK, where the orange bar is on the option
being chosen and the round dot still marks the value before. The rows only the Movie or S&Q menu has follow a group's
Stills rows under "In Movie mode" or "In S&Q mode", as in the editor. Its file layout view reads a download through
the definition's container block. Each setting's and option's help text shows on hover and in the chosen row, with
the camera's guide screens it was read from; a Main entry and the My Menu tab show the definition's tiles and pages
beside frames of the camera's own screens. Its title names the camera. `--open` opens it in the default browser; the
last line the build prints is the page's path.

Packed (`--pack`), its `_viewer/` folder is self-contained: the page and its frames as JPEG, about a third of the PNG
size (`--png` keeps them as they are), so the folder can be zipped or copied to another computer, where it opens
in a browser with no kit installed. A second pack redoes only the frames that changed; a build without `--pack`
(`build_docs.py` too) links the frames in the camera's runs again, so pack last before copying. The folder holds the
owner's screens, so like the rest of `runs/` it stays out of every repository.
