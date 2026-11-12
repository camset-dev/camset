# Running the kit on Windows and Linux

The kit was built and proved on a Mac. This page covers four things:
- what has been changed so it can run on Windows and Linux;
- what has only been checked on the Mac;
- how to set up each OS;
- the first-day checks on a new PC, in order.

The editor's own packages for the three systems are in `RELEASING.md`, "Installers".

## Where each piece stands

| Piece | Mac | Windows | Linux |
|---|---|---|---|
| **camlink** (`kit/link/`, C++, Sony SDK) | built and used every day | code ready: SDK strings converted (`toCr`/`fromCr` in `kit/common/sdk_session.h`, shared with the camera helper, since Windows builds with `UNICODE`), home from `%USERPROFILE%`; the wide-string build compiles; not yet built with MSVC | built on Ubuntu 26.04 (libxml2: see Setup per OS); not yet run against a camera |
| **The editor and its camera helper** (`editor/`; `camset_probe`, `kit/probe/`) | built and used every day | not yet built | built and run on Ubuntu 26.04: the helper found an a1 II over the network and over USB (2026-11-05, "Seen on Windows / Linux" below) |
| **Build of camlink and the camera helper** (`kit/common/sdk_program.cmake`, which `kit/link/CMakeLists.txt` and `kit/probe/CMakeLists.txt` include) | as before | follows Sony's samples: `UNICODE`, static MSVC runtime, SDK DLLs copied next to the `.exe` | follows Sony's samples: threads, `-fsigned-char`, `$ORIGIN` rpath, `-rpath-link` to the SDK folder |
| **Setup** (`kit/setup.py`) | run on a Mac and on a fresh clone of the repository (2026-11-04) | not yet run | run on Ubuntu 26.04 after the by-hand steps (2026-11-05): --check and --editor both clean, tests 164 passed and 139 skipped; a fresh clone not yet |
| **Finding camlink** (`camkit.built`) | `build/camlink` | `build/camlink.exe` or `build/Release/camlink.exe` | `build/camlink` |
| **HDMI capture** (`frames.capture_input`) | ffmpeg avfoundation, live-checked after the change | ffmpeg DirectShow (`video=NAME`); not yet run | ffmpeg V4L2 (`/dev/videoN`, found by name in `/sys/class/video4linux`); not yet run |
| **No capture at all** (`"eyes": "osd"`) | tested in Movie mode ([the a1 II's page](models/ILCE-1M2_fw4.00.md)) | same code: the SDK sends the screen | same code |
| **OCR** (`camkit.ocr`) | Apple Vision, plus RapidOCR as a second vote | RapidOCR (default) | RapidOCR (default) |
| **Vision-language models, VLMs** (vLLM, omlx, Claude) | in use | HTTP only: no OS-specific code | HTTP only |
| **Text to and from camlink** | UTF-8 | UTF-8 forced (`encoding="utf-8"`), not the Windows code page | UTF-8 |

**Try the OSD first on a new PC.** It needs no capture device, so the first runs on Windows and
Linux depend only on the SDK.

## RapidOCR against Apple Vision

`kit/tools/ocr_compare.py` read four of the a1 II's menu scans (stills, Movie, Movie over the OSD, and
S&Q: 241 pages, 1036 rows). Each label and value had already been settled by two sources. The
comparison used the same boxes and the same matching rule as `page_model.py`.

| Engine | Labels | Values | Per frame |
|---|---|---|---|
| Apple Vision | 997/1036 (96.2%) | 571/575 (99.3%) | 0.07 s |
| RapidOCR 1.2.3 | 1015/1036 (98.0%) | 553/575 (96.2%) | 0.19 s |

The two engines miss different rows:
- **Apple Vision** reads a row's icon as letters glued to the label ("Sad ü Shoot Mode").
- **RapidOCR** drops a letter now and then ("Create Still mage"), or a closing bracket.

**So Windows and Linux lose nothing on OCR.** On the Mac, `page_model.py` now takes RapidOCR as a
second vote (`ocr2`) whenever it is installed. On the OSD Movie scan, that left 2 rows of 253
unconfirmed, against 12 before. No settled label changed on any of the four scans.

## Setup per OS

**One command does this section:** put Sony's SDK zip for the OS into `kit/sdk/` and run `python3 kit/setup.py` from
the clone's root (`py kit\setup.py` on Windows; `--check` only reports). It never runs sudo or an installer: for what
is missing it prints the command, and it checks again on the next run. The steps below are what it runs, for doing
them by hand or for when it stops.

**Every OS:**

- Python 3.11 or later: the version the CI workflow names, and every kit file compiles with 3.11 (2026-11-04). On
  Windows the venv's programs are in `.venv\Scripts\` (`.venv\Scripts\pre-commit install`). Not 3.15 yet:
  `onnxruntime`, which RapidOCR needs, had no build for it on 2026-11-04, so `kit/setup.py` makes `.venv` with the
  newest installed Python up to 3.14.
- To rebuild the Python reader a test generates from `docs/formats/sony_camset.ksy`: `kaitai-struct-compiler` 0.11
  (it runs on Java; `brew install kaitai-struct-compiler` on macOS, packages for Linux and Windows at kaitai.io).
  Without it the committed reader is used as it is until a `.ksy` changes in what the reader is made from (a record's
  name, a field): then `kit/tools/build_docs.py --check` (CI) and the kit's drift test fail, and the build without the
  compiler says so, until someone with the compiler runs `kit/tools/build_docs.py --no-viewer`.
- ffmpeg 5.1 or later on the PATH, only for HDMI capture.
- **Sony's Camera Remote SDK for that OS.** Each OS has its own download, and it cannot be
  redistributed. The download is a zip of zips: unpack the outer one, then `SimpleCli.zip` inside it
  as `kit/sdk/SimpleCli/`, so that `kit/sdk/SimpleCli/app/` (the headers in `CRSDK/` and
  `CrDebugString.cpp`) and `kit/sdk/SimpleCli/external/crsdk/` (the Cr_Core library for that OS and
  the `CrAdapter/` folder) exist. `RemoteCli.zip` and the PDFs are not used; the API reference is
  read only by `kit/tools/sdk_support.py`, so unpack it as its own folder. On Windows `Driver.zip`
  holds the USB driver (below). `kit/setup.py` unpacks it so; by hand, on macOS and Linux:

    ```
    mkdir -p kit/sdk && cd kit/sdk
    unzip -q ~/Downloads/CrSDK_v2.02.00_20260610a_Linux64PC.zip     # or the _Mac / _Linux64ARMv8 zip
    unzip -q SimpleCli.zip -d SimpleCli
    unzip -q CrSDK_API_Reference_v2.02.00.zip -d CrSDK_API_Reference_v2.02.00
    ls SimpleCli/external/crsdk SimpleCli/external/crsdk/CrAdapter   # the library and the four adapter files
    ```

    On Windows, in PowerShell: `Expand-Archive` the download into `kit\sdk`, then
    `Expand-Archive kit\sdk\SimpleCli.zip kit\sdk\SimpleCli`,
    `Expand-Archive kit\sdk\CrSDK_API_Reference_v2.02.00.zip kit\sdk\CrSDK_API_Reference_v2.02.00` and
    `Expand-Archive kit\sdk\Driver.zip kit\sdk\Driver`.

Then the rest of what `kit/setup.py` does. The camera helpers build as Release unless asked
otherwise (`kit/common/sdk_program.cmake`): `--config Release` picks it for Visual Studio's builds on
Windows, and `-DCMAKE_BUILD_TYPE=Debug` on a `cmake -S` line gives a build for a debugger:

```
python3 -m venv .venv && .venv/bin/pip install -r kit/requirements.txt
.venv/bin/pre-commit install
cmake -S kit/link -B kit/link/build && cmake --build kit/link/build --config Release
cmake -S kit/probe -B kit/probe/build && cmake --build kit/probe/build --config Release
mkdir -p kit/ocr/build && swiftc -O kit/ocr/ocr.swift -o kit/ocr/build/ocr      # macOS only: the OCR helper
.venv/bin/python -m pytest kit/tests -q                                         # must pass
```

**What a new PC builds,** in this order, after the packages below and Rust from rustup.rs (`kit/setup.py` builds
the first two, and the third with `--editor`):

1. The camera link, `camlink` (the block above): the kit's every use of the camera. Its build puts
   the SDK libraries beside it, loaded from its own folder, so nothing is installed system-wide.
2. The editor's camera helper, `camset_probe`, against the same SDK:
   `cmake -S kit/probe -B kit/probe/build && cmake --build kit/probe/build --config Release`. The
   kit's first day does not need it; the editor does, to read and write a camera.
3. The editor: `cd editor && cargo build --release`, after the windowing libraries the README names
   on Linux. The program is `editor/target/release/camset_editor` (`.exe` on Windows). `sh
   packaging/build_linux.sh`, run from `editor/`, makes the tarball.

Nothing else is built. OCR on Windows and Linux is RapidOCR from the pip install (the Swift helper
in `kit/ocr/` is macOS only), and the reader generated from the Kaitai spec is committed.

**Windows (11, on Intel or AMD: Sony's SDK page lists no other Windows, and not ARM):**

- **Tools:** Visual Studio 2022 or 2026 with the C++ workload, Windows SDK 10.0, and CMake 3.21
  or later (4.2 for VS 2026). With VS 2022, add `-A x64 -T v143,host=x64` to the
  `cmake -S` line of each build.
  ffmpeg: `winget install Gyan.FFmpeg`.
- **USB needs Sony's driver,** once per PC. In the SDK's `Driver` folder, right-click
  `srcameradriver.inf` and choose Install, or in a prompt run as administrator (the line `kit/setup.py`
  prints): `pnputil /add-driver kit\sdk\Driver\srcameradriver.inf /install`. Device Manager should then list
  "Sony Remote Control Camera" under "libusbK Usb Devices". (Sony's sample manual, "Installation of device driver".)
- **LAN without administrator rights:** turn on network discovery and file sharing.
- **Paths:** the credentials file is `%USERPROFILE%\.config\camset\network.json`, written by the
  owner as on the Mac.
- **Capture:** `"device"` in `private/config.json` is the DirectShow name. To list the names, run
  `ffmpeg -list_devices true -f dshow -i dummy`.

**Linux (Ubuntu 22.04 to 26.04, x86-64 or ARM64):**

- **Packages:** `sudo apt install autoconf libtool libudev-dev gcc g++ make cmake unzip libxml2-dev ffmpeg python3-venv`
  (`python3-venv` for the venv).
- **libxml2:** Sony's `libCr_Core.so` needs `libxml2.so.2`. Ubuntu up to 24.04 has it in the
  `libxml2` package, so the packages above are enough. Ubuntu 25.10 and later, and Debian 14, ship
  libxml2 2.14 or later, whose library is `libxml2.so.16`, and the link fails with "libxml2.so.2,
  needed by libCr_Core.so, not found". Ubuntu 26.04 has no `libxml2` package at all. On a
  distribution that still offers one, `sudo apt install libxml2` is enough. Otherwise build libxml2
  2.13.9 (2.13 is the last series with the old name) and put it beside the SDK's libraries, where
  the link's build finds it and copies it next to `camlink`:

    ```
    CLONE=$PWD   # run from the clone's root
    sudo apt install build-essential wget
    cd /tmp && wget https://download.gnome.org/sources/libxml2/2.13/libxml2-2.13.9.tar.xz
    tar xf libxml2-2.13.9.tar.xz && cd libxml2-2.13.9
    ./configure --prefix=/tmp/libxml2-2.13 --without-python --without-zlib --without-lzma --without-icu
    make -j"$(nproc)" && make install
    cp -P /tmp/libxml2-2.13/lib/libxml2.so.2* "$CLONE"/kit/sdk/SimpleCli/external/crsdk/ && cd "$CLONE"
    ```

    `kit/setup.py` does this itself when `ldconfig -p` lists no `libxml2.so.2` and there is none beside the SDK's
    libraries: it downloads the same tarball into `kit/sdk/.build/`, checks its SHA-256 against the one pinned in the
    script, builds it there with the same options and copies `libxml2.so.2*`, links kept, across.

- **USB buffer:** Sony asks for `usbcore.usbfs_memory_mb=150` on the kernel command line. Add it to
  `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, run `sudo update-grub` and reboot.
  Settings files are small, so the kit should work without it, but follow Sony (`kit/setup.py` reminds you while
  it is lower).
- **Not in Sony's notes; try these if a normal user can't see the camera:**
    - **USB permissions:** a udev rule for Sony's USB vendor id `054c`, for example
      `SUBSYSTEM=="usb", ATTR{idVendor}=="054c", TAG+="uaccess"` (the camera to the user at the seat, not to every
      local user) in
      `/etc/udev/rules.d/60-sony-camera.rules`. `kit/setup.py` prints the line that writes it:
      `echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="054c", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/60-sony-camera.rules && sudo udevadm control --reload-rules && sudo udevadm trigger`.
    - **A desktop's gvfs/gphoto2 monitor** can claim the camera, as `ptpcamerad` does on macOS.
- **LAN:** a direct cable needs the PC's network set to "Link-Local Only". Through a router, use
  DHCP.
- **Capture:** `"device"` is the V4L2 card name (`cat /sys/class/video4linux/video*/name`) or a
  `/dev/videoN` path.

## First day on a new PC, in order

Each step needs the one before it to have worked. Record anything that differs from the Mac in
the "Seen on Windows / Linux" log below.

1. **Tests:** `.venv/bin/python -m pytest kit/tests -q` (`.venv\Scripts\python` on Windows). They
   need no camera. A failure here is an OS difference in the Python code.
2. **Body check:** `.venv/bin/python kit/tools/sdk_support.py --json`, then
   `.venv/bin/python kit/tools/body_check.py --model ... --link usb --eyes osd` (`QUICKSTART.md`, step 1). On
   Windows every `.venv/bin/python` here is `.venv\Scripts\python`.
3. **Link:** `.venv/bin/python kit/tools/identify.py --camera`, with `CAMSET_USB=1` over USB.
   - It should print the model and firmware, and save a download.
   - On Windows this is the first real use of the converted SDK strings.
   - Compare the file's layout fingerprint with the one the Mac's download of the same body gives.
4. **Upload:** `.venv/bin/python kit/tools/upload_check.py` on that same file. It must end with `differences: 0`.
5. **Self-test over the OSD:** `CAMSET_EYES=osd .venv/bin/python kit/tools/selftest.py` presses MENU twice and reads
   both screens.
6. **OCR:** `.venv/bin/python kit/tools/ocr_compare.py runs/<model>_fw<fw>/<a scan copied from the Mac>`. The RapidOCR numbers should
   match the table above to within a row or two.
7. **HDMI** (if a dongle is attached): `.venv/bin/python kit/tools/selftest.py --eyes hdmi`.
   - It compares the HDMI frame with the OSD one.
   - Then calibrate the crop if the dongle or its driver scales differently.
8. **A scan and one proof,** as in `QUICKSTART.md` steps 7 and 8. Use the OSD first, then HDMI.

## Seen on Windows / Linux

Add a dated line for each difference found: the step, the message, the fix.

- 2026-11-04, Linux (Ubuntu 26.04), SDK unpack: the download is a zip of zips; unpacking only the
  outer one leaves no `.so`. Fix: the steps in "Setup per OS" (docs only).
- 2026-11-04, Linux (Ubuntu 26.04), step 3 (Link), `cmake --build kit/link/build`:
  `libxml2.so.2, needed by libCr_Core.so, not found`, then ten undefined `xml*@LIBXML2_2.4.30`
  references; the system has `libxml2.so.16` (libxml2 2.15), `libxml2-dev` does not help and there
  is no `libxml2` package. Fix: the libxml2 bullet above, and `-rpath-link` to the SDK folder in
  `kit/link/CMakeLists.txt` and `kit/probe/CMakeLists.txt`, since 2026-11-07 in the
  `kit/common/sdk_program.cmake` both include (confirmed: the link built, with `libxml2.so.2` copied beside
  `camlink`).
- 2026-11-04, Linux (Ubuntu 26.04), step 2 (Body check): `sdk_support.py` needs the API reference
  unpacked as `kit/sdk/CrSDK_API_Reference_v<version>/`; the setup steps said it was unused. Fix:
  docs only.
- 2026-11-04: `kit/setup.py` added; the by-hand steps above are what it runs.
- 2026-11-04, Ubuntu 26.04 (GNOME, Wayland), the editor: Open… under Compare opened the file dialog and
  GNOME showed "'Unknown' is not responding" (Force Quit / Wait; Wait worked). The dialogs blocked the
  window's thread on the desktop portal and the window had no application id. Fixed in the editor:
  every dialog waits on a helper thread, the window's id is `app.camset.editor` and the menu entry's
  `StartupWMClass` matches it (not yet re-checked on the PC).
- 2026-11-05, Linux (Ubuntu 26.04), the editor's Connect to the camera, Network: Search found the camera
  "(authenticated)", but the user name and password were "not saved yet" and the read failed with only a generic
  sentence. The credentials file `~/.config/camset/network.json` is per computer: the user name and password are
  entered once on each. The "Serial / id" column showed a 64-character hex string for the network camera: the
  SDK's network id is a binary record, not a serial, so the table now shows one identity, the serial over USB and
  the MAC address over the network (Sony's samples never display the network id either). Fixed: the probe prints
  a `cause:` line (credentials missing or refused, a USB cable still in, no answer, no USB camera, no USB
  permission on Linux, held by another program) and the editor explains it in plain words, with the probe's own
  messages in Expert mode.
- 2026-11-05, Linux (Ubuntu 26.04), the same test: a login is per computer and also per camera, so the credentials
  file now keeps one pair per camera under its MAC address beside a default pair, and the editor names each camera
  (known cameras, with the serial learned on connecting).
- 2026-11-05, Linux (Ubuntu 26.04), the editor's Connect to the camera, Network: in the morning the network row
  showed the camera's MAC address; later the same day the same row showed "not yet known" for both serial and MAC.
  A row from the probe's direct address check (used when the SDK's search does not list a camera at the saved
  address) carried neither, and the editor did not say which way the camera was found. Fixed: the probe searches
  twice before the direct check, the row says "answered at its address", its MAC address comes from the computer's
  network neighbour table (ARP), and the SDK's MAC string is read bounded by its size. The probe and the camera
  link now look for a camera's own login under each MAC address they know (the SDK's, the neighbour table's, then
  `CAMSET_MAC`), with the same code (`kit/common/camera_net.h`), since the SDK may name the camera's other network
  card (not yet re-checked on the PC).
- 2026-11-05, Linux (Ubuntu 26.04), the editor's Connect to the camera, USB: the USB row's serial number, which had
  shown in the found-cameras table before, stopped showing after commit 2c57f67, and a known camera had none after
  a connect either. Before that commit the probe's search printed the camera object's id whenever its bytes were
  text, with no check of the SDK's id type, and the serial number showed there as text; 2c57f67 kept the id
  only when the id type was the USB constant. Fixed: the probe keeps any id that is text, whatever its type, and
  every search row carries the raw bytes in `id_hex`, shown with the whole search output in the editor's Expert mode;
  after a connect the probe says in a `note:` line when the camera did not list its serial number property and when
  the serial number came from the id instead (not yet re-checked on the PC).
