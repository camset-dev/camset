# Running the kit on Windows and Linux

The kit was built and proved on a Mac. On every OS `kit/setup.py` sets it up and prints the command for what it
cannot do ([QUICKSTART](QUICKSTART.md), step 1). The editor's packages: [RELEASING](RELEASING.md#installers).

## Where each piece stands

| Piece | Windows | Linux |
|---|---|---|
| **Setup** (`kit/setup.py`) | clean on Windows 11 with Sony's Win64 zip (2026-11-12) | clean on Ubuntu 26.04 after the by-hand steps (2026-11-05); a fresh clone not yet |
| **camlink** (`kit/link/`) | built by the 2026-11-12 setup run; not yet run against a camera | built on Ubuntu 26.04; not yet run against a camera |
| **The editor and its camera helper** (`editor/`, `kit/probe/`) | built and used ("Seen on Windows / Linux") | built and used ("Seen on Windows / Linux") |
| **HDMI capture** (`frames.capture_input`) | ffmpeg DirectShow (`video=NAME`); not yet run | ffmpeg V4L2 (`/dev/videoN`, found by name in `/sys/class/video4linux`); not yet run |
| **OCR** | RapidOCR | RapidOCR |

**Try the OSD first on a new PC** (`"eyes": "osd"`): it needs no capture device, so the first runs depend only on the
SDK.

## RapidOCR against Apple Vision

Apple Vision is macOS only. `kit/tools/ocr_compare.py` on four of the a1 II's menu scans (241 pages, 1036 rows, each
label and value already settled by two sources):

| Engine | Labels | Values | Per frame |
|---|---|---|---|
| Apple Vision | 997/1036 (96.2%) | 571/575 (99.3%) | 0.07 s |
| RapidOCR 1.2.3 | 1015/1036 (98.0%) | 553/575 (96.2%) | 0.19 s |

They miss different rows, so Windows and Linux lose nothing on OCR; on the Mac RapidOCR is a second vote (`ocr2`).

## Setup per OS

`kit/setup.py` runs these steps itself; they are here for doing them by hand, or for when it stops.

**Every OS:**

- Python 3.11 to 3.14; not 3.15 yet, since `onnxruntime` (RapidOCR's) had no build for it.
- The SDK zip is a zip of zips. By hand on macOS and Linux:

    ```
    cd kit/sdk && unzip -q CrSDK_v<version>_<date>_<OS>.zip
    unzip -q SimpleCli.zip -d SimpleCli
    unzip -q CrSDK_API_Reference_v<version>.zip -d CrSDK_API_Reference_v<version>
    ```

    On Windows, `Expand-Archive` the download into `kit\sdk`, then `SimpleCli.zip` into `kit\sdk\SimpleCli`,
    `CrSDK_API_Reference_v<version>.zip` into a folder of its own name and `Driver.zip` into `kit\sdk\Driver`.

- `.venv` and the hooks as the README's "Develop" shows, then the builds:

    ```
    cmake -S kit/link -B kit/link/build && cmake --build kit/link/build --config Release
    cmake -S kit/probe -B kit/probe/build && cmake --build kit/probe/build --config Release
    mkdir -p kit/ocr/build && swiftc -O kit/ocr/ocr.swift -o kit/ocr/build/ocr      # macOS only: the OCR helper
    (cd editor && cargo build --release)                                            # the editor (setup.py --editor)
    ```

    The editor needs Rust from rustup.rs, and on Linux the windowing libraries the README names.
- ffmpeg 5.1 or later, only for an HDMI capture dongle.
- `kaitai-struct-compiler` 0.11, only to rebuild the generated reader after a `.ksy` change: packages at kaitai.io.

**Windows (11, on Intel or AMD; not ARM):**

- **Tools:** Visual Studio 2022 or 2026 with the C++ workload, Windows SDK 10.0, CMake 3.21 or later (4.2 for
  VS 2026). With VS 2022, add `-A x64 -T v143,host=x64` to each `cmake -S` line. ffmpeg: `winget install Gyan.FFmpeg`.
  After a winget install, open a new terminal: what winget installs reaches only windows opened after it.
- **Python's UTF-8 mode:** [QUICKSTART](QUICKSTART.md), step 1.
- **USB:** Sony's driver, once per PC, in a terminal run as administrator (Start, type Terminal, right-click, Run as
  administrator): `pnputil /add-driver "<clone>\kit\sdk\Driver\srcameradriver.inf" /install`. Device Manager then
  lists "Sony Remote Control Camera" under "libusbK Usb Devices".
- **LAN without administrator rights:** turn on network discovery and file sharing.
- **Credentials:** `%USERPROFILE%\.config\camset\network.json`.
- **Capture:** `"device"` in `private/config.json` is the DirectShow name: `ffmpeg -list_devices true -f dshow -i dummy`.

**Linux (Ubuntu 22.04 to 26.04, x86-64 or ARM64):**

- **Packages:** `sudo apt install autoconf libtool libudev-dev gcc g++ make cmake unzip libxml2-dev ffmpeg python3-venv`.
- **libxml2:** Sony's `libCr_Core.so` needs `libxml2.so.2`; Ubuntu 25.10 and later and Debian 14 ship only
  `libxml2.so.16` ("libxml2.so.2, needed by libCr_Core.so, not found"). Install a `libxml2` package where one is
  offered; else the setup builds 2.13.9, the last series with the old name, beside the SDK's libraries. By hand:

    ```
    CLONE=$PWD   # run from the clone's root
    sudo apt install build-essential wget
    cd /tmp && wget https://download.gnome.org/sources/libxml2/2.13/libxml2-2.13.9.tar.xz
    tar xf libxml2-2.13.9.tar.xz && cd libxml2-2.13.9
    ./configure --prefix=/tmp/libxml2-2.13 --without-python --without-zlib --without-lzma --without-icu
    make -j"$(nproc)" && make install
    cp -P /tmp/libxml2-2.13/lib/libxml2.so.2* "$CLONE"/kit/sdk/SimpleCli/external/crsdk/ && cd "$CLONE"
    ```

- **USB buffer:** Sony asks for `usbcore.usbfs_memory_mb=150`: add it to `GRUB_CMDLINE_LINUX_DEFAULT` in
  `/etc/default/grub`, run `sudo update-grub` and reboot.
- **If a normal user cannot see the camera:** a udev rule giving Sony's USB devices to the user at the seat:
  `echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="054c", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/60-sony-camera.rules && sudo udevadm control --reload-rules && sudo udevadm trigger`.
  A desktop's gvfs or gphoto2 monitor can also hold the camera, as `ptpcamerad` does on macOS; the kit leaves that to
  you.
- **LAN:** a direct cable needs the PC's network set to "Link-Local Only"; through a router, DHCP.
- **Capture:** `"device"` is the V4L2 card name (`cat /sys/class/video4linux/video*/name`) or a `/dev/videoN` path.

## First day on a new PC, in order

Each step needs the one before it. Run each kit program with `.venv/bin/python` (`.venv\Scripts\python` on Windows).

1. **Tests:** `.venv/bin/python -m pytest kit/tests -q`. They need no camera; a failure is an OS difference.
2. **Body check:** `kit/tools/sdk_support.py --json`, then `kit/tools/body_check.py --model ... --link usb --eyes osd`
   (QUICKSTART, step 1).
3. **Link:** `kit/tools/identify.py --camera` (`CAMSET_USB=1` over USB) prints the model and firmware and saves a
   download; compare its layout fingerprint with a Mac's download of the same body.
4. **Upload:** `kit/tools/upload_check.py` on that file must end with `differences: 0`.
5. **Self-test over the OSD:** `kit/tools/selftest.py` with `CAMSET_EYES=osd` presses MENU twice and reads both
   screens.
6. **OCR:** `kit/tools/ocr_compare.py runs/<model>_fw<fw>/<a scan copied from the Mac>` should match the table above
   to within a row or two.
7. **HDMI** (with a dongle): `kit/tools/selftest.py --eyes hdmi` compares the HDMI frame with the OSD one; calibrate
   the crop if the dongle scales differently.
8. **A scan and one proof** (QUICKSTART, steps 7 and 8), over the OSD first, then HDMI.

## Seen on Windows / Linux

Add a dated line for each difference: the step, the message, the fix.

- 2026-11-05, Ubuntu 26.04: the editor built and ran; its helper found an a1 II over the network and over USB.
- 2026-11-12, Windows 11 (Visual Studio 2022 Build Tools): the editor built, its tests passed, and its helper found
  and read a camera over the network.

Fixed since, not yet re-checked:

- 2026-11-04, Ubuntu 26.04 (GNOME, Wayland): a file dialog left the window "not responding"; fixed (dialogs on a
  helper thread, the window's id `app.camset.editor` matching the menu entry's `StartupWMClass`).
- 2026-11-05, Ubuntu 26.04, network: a camera found at its saved address showed no serial or MAC address; fixed (two
  searches first, the MAC from the neighbour table, a login looked up under each MAC known: `kit/common/camera_net.h`).
- 2026-11-05, Ubuntu 26.04, USB: the camera's serial number stopped showing; fixed (any text id kept, its bytes as
  `id_hex` in Expert mode, a `note:` line when the serial came from the id).
