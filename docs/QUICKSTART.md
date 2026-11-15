# Quick start: from nothing to a first proved setting

This page takes an agent, or a person, from a fresh machine to one setting proved on the camera, in about an hour.
**Read the [playbook](REMAPPING_PLAYBOOK.md)'s section 1 (the rules) before step 5.** Mapping with an older clone?
[CONTRIBUTING](https://github.com/camset-dev/camset/blob/main/CONTRIBUTING.md) says how to take in a newer kit.

## What you need

The body check at the end of step 1 says, from Sony's SDK tables, what the kit can do with your camera
([Sony's SDK page](https://support.d-imaging.sony.co.jp/app/sdk/l/index.php) lists the bodies).

- **A computer** Sony's SDK supports: a Mac with macOS 14.1 or later, a Linux PC, or a Windows 11 PC on Intel or AMD
  (on the PCs the kit's camera runs are not yet tried: [PORTING](PORTING.md)).
- **Software:** Python 3.11 to 3.14 (macOS's own `python3` is older: `brew install python@3.14`), CMake, a C++
  compiler and git. Step 1 checks each and prints the command for what is missing.
- **The camera,** with the 2021-and-later menu (a1 II, a7S III, a7 IV, a7R V, a7C II, a7CR, a9 III, FX3, FX30) set to
  English by the owner's hand (decision 8: the readers know no older menu and no other language), the lens cap on, two
  test cards in and mains power where there is a socket.
- **A USB-C data cable,** with the camera's USB Connection Mode set to PC Remote. Wired LAN (Remote Shoot Function and
  Access Authen. on, set up by the owner) can replace USB; the kit has no Wi-Fi mode yet.
- **Eyes,** how the kit sees the screen: the camera's own OSD image through the SDK (`"eyes": "osd"`), on bodies that
  have it (the body check says). **An HDMI capture dongle is optional** (Elgato Cam Link 4K, the camera's HDMI at
  1080p, a micro-to-full HDMI cable for micro-HDMI): faster, and needed only without the OSD image. Scan the menu with
  the same eyes as the runs.
- **A reader:** at least one vision-language model (VLM) besides the built-in OCR. You choose it, and pay for it if it
  costs money ([Choosing a reader](#choosing-a-reader)).

## 0. Ask the owner first

Before installing anything, ask:

1. **Which camera?** The name on the body ("a7 IV") or the model number ("ILCE-7M4").
2. **How will it connect?** A USB-C data cable, Ethernet or Wi-Fi.
3. **Is there an HDMI capture dongle?** Without one the kit watches the camera's own screen image (OSD), on a body
   that has it.

The body check at the end of step 1 checks the answers against Sony's tables.

## 1. Install, then check the body (about 15 minutes)

Sony's Camera Remote SDK may not be shared: download it from Sony (v2.02 or later, the zip for your system;
`kit/sdk/README.md` says where), put the zip as it is into `kit/sdk/`, and from the clone's root run:

```sh
python3 kit/setup.py              # on Windows: py kit\setup.py; --check only reports
```

It unpacks the SDK, checks the tools, makes `.venv` and the hooks, builds the camera link, the camera helper and (on
macOS) the OCR helper, and runs the tests, which must pass before any camera work. A DO line is yours to do, with its
command, and the last lines list what is left. Ctrl+C stops it safely. Run it again until it says "the kit is set
up". By hand: [PORTING](PORTING.md), "Setup per OS".

- **With an HDMI capture dongle,** also install ffmpeg (`brew install ffmpeg`; Windows and Linux: PORTING).
- **On Windows,** the setup stops until Python's UTF-8 mode is on. Once per PC: `setx PYTHONUTF8 1`, then, in a new
  terminal in the clone's folder (the setting reaches only windows opened afterwards), `py kit\setup.py` again. Sony's USB driver is
  installed once per PC, as administrator: the setup prints the steps until it finds it.
- **On macOS:** run from Terminal.app, not tmux (Local Network privacy blocks the camera otherwise), and remove the
  quarantine attribute from the SDK libraries if Gatekeeper complains.

### Check the body

With the owner's three answers (`--link usb`, `lan` or `wifi`; `--eyes osd` or `hdmi`):

```sh
mkdir -p private/data                                     # your own folder, git-ignored (decision 18)
.venv/bin/python kit/tools/sdk_support.py --json          # Sony's support table, from your copy of the SDK
.venv/bin/python kit/tools/body_check.py --model "a7 IV" --link usb --eyes osd
```

`sdk_support.py` writes the table into `private/data/`, never the public repository (Sony's reference may not be
shared); run it again with each new SDK. `body_check.py` answers everything, settings files only, or nothing, names
what will not work and prints the settings for steps 3 and 4. Stop if it says "Nothing"; otherwise go on to step 2.

## 2. Credentials (the owner's job)

- **Camera, over the network:** the owner writes the camera's access-authentication user and password into
  `~/.config/camset/network.json` (`{"user": ..., "password": ...}`) on each computer they use, readable by them
  alone (mode 600): the camera link and the editor's helper refuse it otherwise. More cameras can each have a pair
  under their MAC address: `"cameras": {"AA:BB:CC:DD:EE:FF": {"name": ..., "user": ..., "password": ...}}`. Which
  pair a camera gets, the fingerprint check and Forget after a network reset:
  [The camera link](EDITOR.md#the-camera-link). The agent never reads them off the camera or types them.
- **Claude as a reader:** `brew install anthropics/tap/ant`, then `ant auth login`; or export `ANTHROPIC_API_KEY` in
  the shell profile.
- **Another hosted reader:** export its key in the shell profile, under the name its `api_key_env` gives (step 3).

## 3. Configure `private/config.json`

```sh
mkdir -p private && cp kit/config.example.json private/config.json
```

The copy names nothing to contact until you fill it in, and its `_safe`, `_camera` and `_comment` notes explain its
keys.

- **`camera_ip`:** the camera's address on the LAN. **Over USB** it is not read: run `export CAMSET_USB=1` in the
  shell the kit runs from (step 4).
- **`eyes`:** `"osd"` (the default) or `"hdmi"`; `CAMSET_EYES` overrides it for one command.
- **`hdmi`** (with `"eyes": "hdmi"`): the dongle's name (`device`), `size`, `fps` and the `crop` that maps the camera's
  UI to 640x480.
- **`camera_model`** (LAN only, optional): the SDK's model number, such as `"ILCE-1"`; the default is `ILCE-1M2`.
- **`camera`** and **`cameras`** (optional): which camera the kit works on, as `<model>_fw<firmware>` (step 4 prints
  it), and an entry for each of several cameras. With one camera, leave them out.
- **`ocr`** (optional): `"apple"` (the Mac's default) or `"rapidocr"` (the default elsewhere).
- **`readers`:** one entry per VLM ([Choosing a reader](#choosing-a-reader)).
- **`roles`** (optional): `{"second": ..., "third": ...}`, the reader that gives the second reading and the one that
  breaks ties; without it, the first reader in `readers` gives the second reading and the next breaks ties, and a paid
  reader is asked in no role but its own. The
  third counts as a vote of its own only when its `model` differs from the second's
  ([decision 22](decisions/0022-ocr-alone-only-for-a-plain-reading-the-reader-on-every-doubt.md)), so give one model
  one id.

### Choosing a reader

The kit reads the camera's screen with OCR and at least one vision-language model (VLM), an AI model that reads
images: OCR alone reads icons as letters and clips short words
([playbook, section 5](REMAPPING_PLAYBOOK.md#5-readers-accuracy-before-speed)). A full map makes thousands of reads,
each cached by frame, prompt and model. A hosted reader receives captures of the camera's menus, which can show names
and network settings: prefer a local one. Cheapest first:

1. **A model on your own computer or server:** an OpenAI-compatible server (Ollama, LM Studio, vLLM, omlx) running a
   VLM, with `url` ending in `/v1`. This project used Qwen3.8 27B: `RedHatAI/Qwen3.8-27B-INT4` through vLLM on a GPU
   server and `Qwen3.8-27B-4bit` through omlx on a Mac. Smaller models of the same family, Ollama and LM Studio are
   untested here.
2. **Claude through the Anthropic API:** the `claude` entry, with `ANTHROPIC_API_KEY` or `ant auth login` (step 2).
   Every read not cached costs money.
3. **Another hosted OpenAI-compatible service** (OpenAI, Gemini, others), untested here: the service's base URL (the
   kit adds `/chat/completions`) and `api_key_env`, the variable that holds your key, which the kit sends only in the
   `Authorization: Bearer` header and never writes anywhere. Every read not cached costs money. The request carries
   vLLM's `chat_template_kwargs`, `temperature` 0 and `max_tokens`, which a service may refuse.

Copy the entries you choose from `readers_examples` in `kit/config.example.json` into `readers`, with your own
server's address in a local one's `url`.

**Check that they answer.** Every camera run first asks its readers to read a test picture, skips one that does not
answer, and stops before it presses anything when none can stand in. To ask them the same with no camera:

```sh
.venv/bin/python kit/tools/reader_check.py           # each reader: kind, model, answered in how long, or the error
.venv/bin/python kit/tools/reader_check.py --all     # the paid readers too (each question costs money)
```

It exits 0 when a camera run would start.

## 4. Identify the camera and its file

```sh
export CAMSET_USB=1                               # over USB only, in every shell the kit runs from (step 3)
.venv/bin/python kit/tools/identify.py --camera
```

It prints the model, firmware and lens (never the serial number), downloads the camera's settings into
`runs/<model>_fw<firmware>/kit2_identify/`, and prints the file's layout fingerprint and the camera's key ("this
camera is ILCE-7M4_fw2.00"). Then one of three:

- **KNOWN ... definition ..., model page ...:** this body and firmware are mapped. Read its model page in
  `docs/models/` before going on.
- **Same model, different layout:** a firmware update moved records; treat the old definition as hints only.
- **UNKNOWN layout:** a new model or firmware. Follow the playbook's "New model: first day".

When no known container block reads the file, identify.py prints a draft block: correct it into the camera's
`data/<model>_fw<fw>/camera_<model>_fw<fw>.json` ("file"; [the container block](DATA_CONTRACTS.md#the-container-block-file))
and run it again until the file reads and both checksums hold. `kit/tools/identify.py FILE.DAT` reads a saved file
with no camera.

### Where the runs go

Everything the kit records for a camera goes into that camera's own folder:

```
runs/
  ILCE-1M2_fw4.00/   kit2_pass1/  kit2_pass2/  ...  _viewer/  _cache/  downloads.jsonl
  ILCE-7M4_fw2.00/   kit2_identify/  kit2_page_scan/  ...
```

A download of one camera is never uploaded to another. The kit works on the camera `"camera"` names in
`private/config.json`, else the one camera in `runs/`; `--camera <model>_fw<firmware>` on any command, or
`CAMSET_CAMERA` in the shell, picks another. A run or file named on a command line (`kit2_crawl`,
`kit2_crawl/map.json`) is read from the camera's runs. Below, `$CAM` is your camera's key:

```sh
CAM=ILCE-7M4_fw2.00                               # yours: the key identify.py printed
```

## 5. Keep the owner's file safe

Step 4's download, `runs/$CAM/kit2_identify/dat/NNNNN_identify.DAT`, is the owner's file: every session ends by
uploading it back. Leave it where it is: the link uploads only files the camera wrote, known by the SHA-256 in
`runs/$CAM/downloads.jsonl` (decision 6). Note its name:

```sh
OWNER=$(ls -t runs/$CAM/kit2_identify/dat/*_identify.DAT | head -1) && echo "$OWNER"
```

Next, the **start file**, the state the runs start from. With `"eyes": "hdmi"` the camera's HDMI output must be at
1080p: if it is not, set HDMI Resolution on the camera, then download the new state and compare it with the owner's
file:

```sh
.venv/bin/python kit/tools/upload_check.py --diff "$OWNER" start --run kit2_pass2
```

That saves the start file, `runs/$CAM/kit2_pass2/dat/NNNNN_start.DAT`, and lists the records that differ (only the
HDMI ones should). If nothing needed changing, the owner's file is the start file. Before each run,
`kit/prove_run.py --start` uploads the start file if the camera differs from it.

## 6. Check the eyes

```sh
.venv/bin/python kit/tools/selftest.py           # MENU open and close only, with the configured eyes (--eyes hdmi|osd, --no-press)
(cd kit && ../.venv/bin/python -m camkit.safety)  # review what the walker will never open
```

The self-test must read the shooting screen and a menu page. If it cannot, recalibrate the HDMI crop, or recut the
battery templates from the new camera's own frames (playbook, "New model: first day").

## 7. Map the menu: scan, read and crawl one row

```sh
.venv/bin/python -u kit/page_scan.py --mode Stills --run kit2_page_scan   # Down only, one full lap
.venv/bin/python -u kit/page_model.py --vlm kit2_page_scan
.venv/bin/python -u kit/crawl_run.py --start-label "Grid Line Display" --limit 1   # one row, read-only
```

- The scan must end with `LAP complete` and `cycle written`.
- `--mode` names the shooting mode the camera is in (Stills, Movie and S&Q each have a menu of their own). Give each
  mode's scan a run of its own.
- `page_model.py` lists the labels the readers disagree on: read them off the frames into
  `runs/$CAM/kit2_page_scan/checked_labels.json` and run it again.
- The crawl must end with `0 records differ from the start file`: walking a row read-only changed nothing. On a new
  body it opens the row only once the owner has answered `kit/tools/owner_statement.py cards` in their own terminal
  (the playbook's section 16); until then it skips the row and says so.

## 8. Prove one setting

The prover takes its exclusions from the reviewed scope, `runs/$CAM/kit2_pass1/pass2_scope_draft.json`. On a new
machine, copy `data/pass2_scope_template.json` there and review it (playbook, "Order of work", Phase 1); until then it
falls back to the template.

```sh
.venv/bin/python kit/pass1_labels.py kit2_crawl && .venv/bin/python kit/pass1_map.py kit2_crawl
.venv/bin/python -u kit/prove_run.py --map kit2_crawl/map.json --rows "Grid Line Display" --start kit2_pass2/dat/NNNNN_start.DAT
```

The output names, for each option, the record that changed and its old and new values. The held option proves last
with "no change", and the run ends with `0 records differ from the start file`. That is a proved setting.

## 9. End the session

```sh
.venv/bin/python -u kit/tools/upload_check.py "$OWNER"  # the owner's file, the download step 5 named
```

Only the records a file cannot set may differ, and the tool names them. Then follow the playbook's "Order of work"
for the full mapping.

## Command cheat sheet

Every kit command runs with the kit's own Python (`.venv/bin/python`, on Windows `.venv\Scripts\python`); started with
another, it stops and prints the command to run instead.

```sh
python3 kit/setup.py --check                                  # what is set up, changing nothing (--force: build from clean; --editor: the editor too)
.venv/bin/python -u kit/table_walk.py --rows "My Dial Settings"   # read-only walk of a table / Fn Menu / Custom Key
.venv/bin/python -u kit/prove_run.py --tables --picker-sample --start kit2_pass2/dat/NNNNN_start.DAT   # prove what they walked
.venv/bin/python -u kit/prove_run.py --map kit2_play2/map.json --rows "Rating Set(Custom Key)" --retry-failed --start kit2_pass2/dat/NNNNN_start.DAT
.venv/bin/python -u kit/page_scan.py --camera ILCE-7M4_fw2.00 --mode Stills --run kit2_page_scan   # any command: another camera's runs
.venv/bin/python kit/schema_update.py [--write]               # the active camera's definition from its runs (playbook, Phase 6)
.venv/bin/python kit/tools/build_docs.py [--check]           # the generated files, the reader and the viewer (--check: list the stale ones)
.venv/bin/python kit/tools/build_docs.py --write-schema       # the definition first, then the generated files
.venv/bin/python kit/tools/build_docs.py --definitions        # every definition's parts from data/ (after editing a camera file), no runs
.venv/bin/python kit/tools/proof_viewer.py --open            # the proof viewer: each value with the frames that proved it
.venv/bin/python kit/tools/proof_viewer.py --pack [--png]     # the same, with a copy of its frames, to open on another computer
```

The proof viewer is built from your camera's runs, at `runs/<model>_fw<fw>/_viewer/index.html`, and is never part of
a submission: it shows the camera's own screens, so keep it, packed or not, out of every repository. The notes at the
top of `kit/tools/proof_viewer.py` say the rest.
